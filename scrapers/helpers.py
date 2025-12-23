"""
Common utilities and helpers for scrapers.
Provides shared functionality to reduce code duplication across scrapers.
"""
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path

import dramatiq
from bs4 import BeautifulSoup

from db.config import settings
from db.schemas import TorrentStreamData, EpisodeFileData
from utils.torrent import info_hashes_to_torrent_metadata
from utils.http_client import get_shared_proxy_client

# set httpx logging level
logging.getLogger("httpx").setLevel(logging.WARNING)

# Cache for country data
_country_cache: Optional[Dict[str, str]] = None


def get_country_name(country_code: str) -> str:
    """
    Get country name from country code.
    Uses caching to avoid repeated file reads.
    
    Args:
        country_code: Two-letter country code
        
    Returns:
        Country name or "India" as default
    """
    global _country_cache
    if _country_cache is None:
        countries_file = Path("resources/json/countries.json")
        if countries_file.exists():
            with open(countries_file) as file:
                _country_cache = json.load(file)
        else:
            _country_cache = {}
    return _country_cache.get(country_code.upper(), "India")


async def get_page_bs4(url: str, timeout: int = 10) -> Optional[BeautifulSoup]:
    """
    Fetch a webpage and parse it with BeautifulSoup.
    Uses shared HTTP client for better performance.
    
    Args:
        url: URL to fetch
        timeout: Request timeout in seconds
        
    Returns:
        BeautifulSoup object or None if fetch fails
    """
    try:
        client = get_shared_proxy_client()
        response = await client.get(url, timeout=timeout)
        if response.status_code != 200:
            return None
        return BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        logging.error(f"Error fetching page: {url}, error: {e}")
        return None


def extract_torrent_info(item: Dict[str, Any], field_mapping: Dict[str, str]) -> Dict[str, Any]:
    """
    Extract torrent information from a dictionary using field mapping.
    Common utility for indexer scrapers (Prowlarr, Jackett).
    
    Args:
        item: Dictionary containing torrent data
        field_mapping: Mapping of standard fields to item-specific field names
        
    Returns:
        Dictionary with standardized field names
    """
    result = {}
    for standard_field, item_field in field_mapping.items():
        if item_field in item:
            result[standard_field] = item[item_field]
    return result


def normalize_torrent_title(title: str) -> str:
    """
    Normalize torrent title for better matching.
    Removes extra whitespace and common prefixes/suffixes.
    
    Args:
        title: Original torrent title
        
    Returns:
        Normalized title
    """
    if not title:
        return ""
    # Remove extra whitespace
    title = " ".join(title.split())
    # Remove common prefixes/suffixes that don't affect matching
    title = title.strip()
    return title


def validate_torrent_item(item: Dict[str, Any], required_fields: List[str]) -> bool:
    """
    Validate that a torrent item has all required fields.
    
    Args:
        item: Dictionary containing torrent data
        required_fields: List of required field names
        
    Returns:
        True if all required fields are present, False otherwise
    """
    return all(field in item and item[field] for field in required_fields)
