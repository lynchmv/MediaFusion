
import aiohttp
import xml.etree.ElementTree as ET
from db.schemas import EPGChannel, EPGProgram

async def fetch_and_parse_epg(url: str) -> tuple[list[EPGChannel], list[EPGProgram]]:
    """
    Fetches an XMLTV EPG file from a URL and extracts channel and program data.

    Args:
        url (str): The URL of the EPG file.

    Returns:
        tuple: A tuple containing a list of EPGChannel objects and a list of EPGProgram objects.
    """
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                content = await response.read()
        except aiohttp.ClientError as e:
            # Handle client-side errors (e.g., connection error, timeout)
            raise ConnectionError(f"Failed to fetch EPG file from {url}: {e}") from e

    root = ET.fromstring(content)

    channels = []
    for channel_elem in root.findall('channel'):
        channel_id = channel_elem.get('id')
        display_name = channel_elem.find('display-name').text
        icon = channel_elem.find('icon').get('src') if channel_elem.find('icon') is not None else None
        channels.append(EPGChannel(id=channel_id, display_name=display_name, icon=icon))

    programs = []
    for program_elem in root.findall('programme'):
        start_time = program_elem.get('start')
        stop_time = program_elem.get('stop')
        channel_id = program_elem.get('channel')
        title = program_elem.find('title').text
        desc = program_elem.find('desc').text if program_elem.find('desc') is not None else None
        programs.append(EPGProgram(start_time=start_time, stop_time=stop_time, channel_id=channel_id, title=title, desc=desc))

    return channels, programs

