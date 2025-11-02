import logging
import httpx
import collections
import re
from ipytv import playlist
from ipytv.channel import IPTVAttr
from urllib.parse import urlparse
import os
from datetime import datetime
from dateparser.search import search_dates
import dateparser

# Add imports for creating and saving data
from db import schemas
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
        logging.info(f"Parser initialized for {len(source_urls)} source URLs.")

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
                            if 'group-title' not in line:
                                line = line.replace('EXTINF:-1', f'EXTINF:-1 group-title="{default_group_name}"')
                            final_m3u_string += line + "\n"
                        elif line.startswith("http"):
                            final_m3u_string += line + "\n"
                except httpx.RequestError as e:
                    logging.error(f"Failed to fetch source playlist {url}: {e}")
                    continue
        return final_m3u_string

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
            group_title = channel.attributes.get('group-title', 'Uncategorized').strip()
            grouped_channels[group_title].append(channel)

        logging.info(f"Successfully parsed and grouped {len(channels)} entries into {len(grouped_channels)} groups.")

        channel_batch = []
        event_list = []
        batch_size = 25

        # Regex to find date and time patterns
        date_pattern = re.compile(r'\d{1,2}/\d{1,2}/\d{2,4}|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b \d{1,2}, \d{4}')
        time_pattern = re.compile(r'\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|ET|EST|EDT|UTC)', re.IGNORECASE)

        for group_name, channels_in_group in grouped_channels.items():
            for channel in channels_in_group:
                if not channel.url:
                    logging.warning(f"Skipping channel with no URL: {channel.name}")
                    continue

                raw_name = channel.name.strip()

                # Use regex to determine if the title is an event
                is_event = date_pattern.search(raw_name) and time_pattern.search(raw_name)

                if is_event:
                    # --- Process as a Live Event ---
                    try:
                        found_dates = search_dates(raw_name)
                        if not found_dates:
                            raise ValueError("Date could not be found in the event title")

                        event_datetime = found_dates[0][1]
                        event_start_timestamp = int(event_datetime.timestamp())

                        unique_str = f"{raw_name}{event_start_timestamp}"
                        event_id = f"event{crypto.get_text_hash(unique_str)}"
                        poster_url = channel.attributes.get(IPTVAttr.TVG_LOGO.value)
                        event_genre = channel.attributes.get('group-title', 'Other Sports').strip()

                        # --- Start of New Logic ---
                        # Manually create the stream as a dictionary to avoid validation conflicts
                        stream_as_dict = {
                            "meta_id": event_id,
                            "name": raw_name,
                            "url": channel.url,
                            "source": self.playlist_source,
                            # Add other default fields from the TVStreams model if necessary
                            "is_working": True
                        }

                        event_metadata = MediaFusionEventsMetaData(
                            id=event_id,
                            title=raw_name,
                            event_start_timestamp=event_start_timestamp,
                            poster=poster_url if validation_helper.is_valid_url(poster_url) else None,
                            genres=[event_genre],
                            is_add_title_to_poster=False,
                            streams=[stream_as_dict] # Pass the dictionary here
                        )
                        # --- End of New Logic ---

                        event_list.append(event_metadata)
                    except Exception as e:
                        logging.warning(f"Skipping event due to processing error: '{raw_name}' | Error: {e}")
                else:
                    # --- Process as a Regular Channel ---
                    clean_name = channel.attributes.get(IPTVAttr.TVG_NAME.value, raw_name)
                    genres = [
                        re.sub(r"\s+", " ", genre).strip()
                        for genre in re.split(
                            "[,;|]", channel.attributes.get(IPTVAttr.GROUP_TITLE.value, "")
                        )
                    ]
                    channel_name = re.sub(r"\s+", " ", clean_name).strip()

                    if len(channel_name) < 2:
                        continue

                    channel_id = f"tv.{crypto.get_text_hash(channel_name)}"
                    poster_url = channel.attributes.get(IPTVAttr.TVG_LOGO.value)

                    metadata = schemas.TVMetaData(
                        id=channel_id,
                        title=channel_name,
                        poster=poster_url if validation_helper.is_valid_url(poster_url) else None,
                        logo=poster_url if validation_helper.is_valid_url(poster_url) else None,
                        genres=genres,
                        streams=[
                            schemas.TVStreams(
                                meta_id=channel_id,
                                name=channel_name,
                                url=channel.url,
                                source=self.playlist_source
                            ).model_dump()
                        ]
                    )
                    channel_batch.append(metadata.model_dump())

        # Process any remaining regular channels
        if channel_batch:
            await add_tv_metadata(batch=channel_batch, namespace="mediafusion")

        # Save all found events to the Redis cache
        if event_list:
            logging.info(f"Saving and indexing {len(event_list)} live events in Redis.")
            for event in event_list:
                event_key = f"event:{event.id}"
                event_json = event.model_dump_json(exclude_none=True)
                # Cache event until 24 hours after it's over
                ttl = int((event.event_start_timestamp - datetime.now().timestamp()) + 86400)
                if ttl > 0:
                    await REDIS_ASYNC_CLIENT.set(event_key, event_json, ex=ttl)
                    await REDIS_ASYNC_CLIENT.zadd("events:all", {event_key: event.event_start_timestamp})
                    for genre in event.genres:
                        await REDIS_ASYNC_CLIENT.zadd(f"events:genre:{genre}", {event_key: event.event_start_timestamp})

        logging.info("Finished processing and storing all regular channels and live events.")
