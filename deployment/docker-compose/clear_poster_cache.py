import asyncio
import logging

from db import database
from db.redis_database import REDIS_ASYNC_CLIENT

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def clear_all_poster_caches():
    """
    Connects to Redis and deletes all cached poster images.
    """
    print("Connecting to the database and Redis...")
    await database.init()
    print("Connections established.")

    print("\n--- Scanning for poster cache keys ---")

    # The pattern for generated posters is typically: {type}_{id}.jpg
    # We will scan for any key that ends with .jpg
    cache_keys_to_delete = []
    async for key in REDIS_ASYNC_CLIENT.scan_iter("*_*.jpg"):
        cache_keys_to_delete.append(key)

    if not cache_keys_to_delete:
        print("No poster cache keys found to delete.")
        return

    print(f"Found {len(cache_keys_to_delete)} poster cache keys to delete.")

    # Delete all the found keys in a single operation
    print("Deleting keys...")
    await REDIS_ASYNC_CLIENT.delete(*cache_keys_to_delete)

    print("\nSuccess! All identified poster cache keys have been deleted.")
    print("New posters will be generated on the next request.")


if __name__ == "__main__":
    # This allows the script to be run directly from the command line
    try:
        asyncio.run(clear_all_poster_caches())
    except KeyboardInterrupt:
        print("\nScript interrupted by user.")


