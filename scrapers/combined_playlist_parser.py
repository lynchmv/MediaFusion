import logging
import httpx
import collections
import re
from ipytv import playlist
from ipytv.channel import IPTVAttr
from urllib.parse import urlparse
import os
from datetime import datetime, timedelta
from dateparser.search import search_dates
import dateparser
from thefuzz import fuzz
from beanie.odm.operators.find.comparison import In

FUZZY_MATCH_THRESHOLD = 90
TIME_WINDOW_SECONDS = 3600  # 1 hour

# Add imports for creating and saving data
from db import schemas, models
from db.models import MediaFusionTVMetaData, MediaFusionEventsMetaData, TVStreams
from db.redis_database import REDIS_ASYNC_CLIENT
from utils import validation_helper, crypto
from scrapers.tv import add_tv_metadata


class CombinedPlaylistParser:
    """
    Parses a combined M3U, groups the channels, and processes/saves
    only the regular TV channels.
    """

    def __init__(self, source_urls: list[str]):
        self.source_urls = source_urls
        self.playlist_source = "Combined Playlist"
        self.logger = logging.getLogger(__name__)
        self.skipped_duplicate_tv_channels_count = 0
        self.added_new_tv_channels_count = 0
        self.merged_tv_streams_count = 0
        self.logger.info(f"Parser initialized for {len(source_urls)} source URLs.")

    async def _generate_combined_content(self) -> str | None:
        """Fetches and combines source playlists into a single M3U string."""
        final_m3u_string = "#EXTM3U\n"
        async with httpx.AsyncClient() as client:
            for url in self.source_urls:
                try:
                    response = await client.get(url, follow_redirects=True, timeout=30)
                    response.raise_for_status()
                    path = urlparse(url).path
                    default_group_name = os.path.basename(path)
                    for line in response.text.splitlines():
                        if line.startswith("#EXTINF"):
                            if "group-title" not in line:
                                line = line.replace(
                                    "EXTINF:-1",
                                    f'EXTINF:-1 group-title="{default_group_name}"'
                                )
                            final_m3u_string += line + "\n"
                        elif line.startswith("http"):
                            final_m3u_string += line + "\n"
                except httpx.RequestError as e:
                    logging.error(f"Failed to fetch source playlist {url}: {e}")
                    continue
        return final_m3u_string

    async def _process_event(self, channel, event_list):
        """Processes a channel as a live event."""
        raw_name = channel.name.strip()
        self.logger.debug(f"Channel '{raw_name}' classified as a live event.")
        try:
            found_dates = search_dates(raw_name)
            if not found_dates:
                raise ValueError("Date could not be found in the event title")

            event_datetime = found_dates[0][1]
            event_start_timestamp = int(event_datetime.timestamp())

            event_id = f"event{crypto.get_text_hash(raw_name)}"
            poster_url = channel.attributes.get(IPTVAttr.TVG_LOGO.value)
            event_genre = channel.attributes.get("group-title", "Other Sports").strip()

            min_score = event_start_timestamp - TIME_WINDOW_SECONDS
            max_score = event_start_timestamp + TIME_WINDOW_SECONDS

            found_duplicate_event = False
            existing_event_keys = await REDIS_ASYNC_CLIENT.zrangebyscore(
                "events:all", min=min_score, max=max_score
            )

            for event_key in existing_event_keys:
                existing_event_json = await REDIS_ASYNC_CLIENT.get(event_key)
                if existing_event_json:
                    existing_event = MediaFusionEventsMetaData.model_validate_json(
                        existing_event_json
                    )
                    if (
                        fuzz.ratio(raw_name, existing_event.title)
                        >= FUZZY_MATCH_THRESHOLD
                    ):
                        found_duplicate_event = True
                        new_stream_url = channel.url
                        stream_exists = any(
                            s.url == new_stream_url for s in existing_event.streams
                        )

                        if not stream_exists:
                            new_stream = models.TVStreams(
                                meta_id=existing_event.id,
                                name=raw_name,
                                url=new_stream_url,
                                source=self.playlist_source,
                                is_working=True,
                            )
                            existing_event.streams.append(new_stream)
                            await REDIS_ASYNC_CLIENT.set(
                                event_key,
                                existing_event.model_dump_json(exclude_none=True),
                                ex=int(
                                    (
                                        existing_event.event_start_timestamp
                                        - datetime.now().timestamp()
                                    )
                                    + 86400
                                ),
                            )
                            self.logger.info(
                                f"Merged new stream for event '{raw_name}' into existing event '{existing_event.title}'."
                            )
                        else:
                            self.logger.info(
                                f"Skipped duplicate stream for event '{raw_name}' as it already exists in '{existing_event.title}'."
                            )
                        break

            if not found_duplicate_event:
                stream_as_dict = {
                    "meta_id": event_id,
                    "name": raw_name,
                    "url": channel.url,
                    "source": self.playlist_source,
                    "is_working": True,
                }
                event_metadata = MediaFusionEventsMetaData(
                    id=event_id,
                    title=raw_name,
                    event_start_timestamp=event_start_timestamp,
                    poster=poster_url
                    if validation_helper.is_valid_url(poster_url)
                    else None,
                    genres=[event_genre],
                    is_add_title_to_poster=False,
                    streams=[stream_as_dict],
                )
                event_list.append(event_metadata)
        except Exception as e:
            logging.warning(
                f"Skipping event due to processing error: '{raw_name}' | Error: {e}"
            )

    async def _process_regular_channel(
        self,
        channel,
        existing_tv_channels_in_db,
        unique_channels_in_group,
        channel_batch,
        existing_stream_urls,
        new_streams_batch,
    ):
        """Processes a channel as a regular TV channel."""
        raw_name = channel.name.strip()
        self.logger.debug(f"Channel '{raw_name}' classified as a regular TV channel.")

        clean_name = channel.attributes.get(IPTVAttr.TVG_NAME.value, raw_name)
        genres = [
            re.sub(r"\s+", " ", genre).strip()
            for genre in re.split(
                "[,;|]",
                channel.attributes.get(IPTVAttr.GROUP_TITLE.value, ""),
            )
        ]
        channel_name = re.sub(r"\s+", " ", clean_name).strip()

        if len(channel_name) < 2:
            self.logger.debug(f"Skipping TV channel '{channel_name}' due to short name.")
            return

        channel_id = f"tv.{crypto.get_text_hash(channel_name)}"
        poster_url = channel.attributes.get(IPTVAttr.TVG_LOGO.value)

        in_memory_key = (channel_name, channel.url)
        if in_memory_key in unique_channels_in_group:
            self.skipped_duplicate_tv_channels_count += 1
            self.logger.debug(
                f"Skipped in-memory duplicate TV channel: '{channel_name}' with URL '{channel.url}'."
            )
            return
        unique_channels_in_group.add(in_memory_key)

        found_duplicate_tv = False
        for existing_channel in existing_tv_channels_in_db:
            self.logger.debug(
                f"Comparing '{channel_name}' with existing '{existing_channel.title}'. Fuzzy ratio: {fuzz.ratio(channel_name, existing_channel.title)}."
            )
            if (
                fuzz.ratio(channel_name, existing_channel.title)
                >= FUZZY_MATCH_THRESHOLD
            ):
                found_duplicate_tv = True
                self.logger.debug(
                    f"Found fuzzy duplicate TV channel '{channel_name}' with existing '{existing_channel.title}'."
                )
                new_stream_url = channel.url
                stream_exists = new_stream_url in existing_stream_urls

                if not stream_exists:
                    self.merged_tv_streams_count += 1
                    new_stream = models.TVStreams(
                        meta_id=existing_channel.id,
                        name=channel_name,
                        url=new_stream_url,
                        source=self.playlist_source,
                    )
                    new_streams_batch.append(new_stream)
                    self.logger.info(
                        f"Added new stream for '{channel_name}' to batch, to be merged into existing TV channel '{existing_channel.title}'."
                    )
                else:
                    self.skipped_duplicate_tv_channels_count += 1
                    self.logger.info(
                        f"Skipped duplicate TV channel '{channel_name}' as stream already exists in '{existing_channel.title}'."
                    )
                break

        if not found_duplicate_tv:
            self.added_new_tv_channels_count += 1
            self.logger.debug(f"Adding new TV channel '{channel_name}' to batch.")
            metadata = schemas.TVMetaData(
                id=channel_id,
                title=channel_name,
                poster=poster_url
                if validation_helper.is_valid_url(poster_url)
                else None,
                logo=poster_url
                if validation_helper.is_valid_url(poster_url)
                else None,
                genres=genres,
                streams=[
                    schemas.TVStreams(
                        meta_id=channel_id,
                        name=channel_name,
                        url=channel.url,
                        source=self.playlist_source,
                    ).model_dump()
                ],
            )
            channel_batch.append(metadata.model_dump())

    async def run(self):
        """
        The main method to fetch, parse, group, and store both regular
        channels and live events, using robust date searching.
        """
        content = await self._generate_combined_content()
        if not content:
            logging.error("No content generated, aborting run.")
            return

        iptv_playlist = playlist.loads(content)
        channels = list(iptv_playlist)

        grouped_channels = collections.defaultdict(list)
        for channel in channels:
            group_title = channel.attributes.get("group-title", "Uncategorized").strip()
            grouped_channels[group_title].append(channel)

        logging.info(
            f"Successfully parsed and grouped {len(channels)} entries into {len(grouped_channels)} groups."
        )

        existing_tv_channels_in_db = await MediaFusionTVMetaData.find_all(
            projection_model=schemas.TVMetaProjection
        ).to_list()
        self.logger.debug(
            f"Found {len(existing_tv_channels_in_db)} existing TV channels in DB for comparison."
        )

        # Batch-fetch existing stream URLs for faster lookups
        playlist_stream_urls = {c.url for c in channels if c.url}
        existing_streams = await models.TVStreams.find(
            In(models.TVStreams.url, list(playlist_stream_urls))
        ).to_list()
        existing_stream_urls = {stream.url for stream in existing_streams}
        self.logger.debug(
            f"Found {len(existing_stream_urls)} existing streams in the database from the current playlist."
        )

        channel_batch = []
        event_list = []
        unique_channels_in_group = set()
        new_streams_batch = []

        date_pattern = re.compile(
            r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b[ -]\d{1,2}[, -]\d{4}",
            re.IGNORECASE,
        )
        time_pattern = re.compile(
            r"\d{1,2}:\d{2}(?:\d{2})?\s*(?:AM|PM|ET|EST|EDT|UTC)?", re.IGNORECASE
        )

        for channels_in_group in grouped_channels.values():
            for channel in channels_in_group:
                if not channel.url:
                    logging.warning(f"Skipping channel with no URL: {channel.name}")
                    continue

                raw_name = channel.name.strip()
                is_event = date_pattern.search(raw_name) and time_pattern.search(
                    raw_name
                )

                if is_event:
                    await self._process_event(channel, event_list)
                else:
                    await self._process_regular_channel(
                        channel,
                        existing_tv_channels_in_db,
                        unique_channels_in_group,
                        channel_batch,
                        existing_stream_urls,
                        new_streams_batch,
                    )

        if new_streams_batch:
            self.logger.debug(
                f"Processing a batch of {len(new_streams_batch)} new TV streams."
            )
            await TVStreams.insert_many(new_streams_batch)

        if channel_batch:
            self.logger.debug(
                f"Processing a batch of {len(channel_batch)} TV channels."
            )
            await add_tv_metadata(batch=channel_batch, namespace="mediafusion")

        if event_list:
            logging.info(
                f"Saving and indexing {len(event_list)} live events in Redis."
            )
            pipeline = REDIS_ASYNC_CLIENT.pipeline()
            for event in event_list:
                event_key = f"event:{event.id}"
                event_json = event.model_dump_json(exclude_none=True)
                ttl = int(
                    (event.event_start_timestamp - datetime.now().timestamp()) + 86400
                )
                if ttl > 0:
                    pipeline.set(event_key, event_json, ex=ttl)
                    pipeline.zadd(
                        "events:all", {event_key: event.event_start_timestamp}
                    )
                    for genre in event.genres:
                        pipeline.zadd(
                            f"events:genre:{genre}",
                            {event_key: event.event_start_timestamp},
                        )
            await pipeline.execute()

        logging.info(
            "Finished processing and storing all regular channels and live events."
        )
        self.logger.info(
            f"Combined Playlist Parser Summary: Added new TV channels: {self.added_new_tv_channels_count}, Skipped duplicate TV channels: {self.skipped_duplicate_tv_channels_count}, Merged TV streams: {self.merged_tv_streams_count}"
        )