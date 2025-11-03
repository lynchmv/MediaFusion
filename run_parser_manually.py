import asyncio
import logging
from db.config import settings
from api.scheduler import run_combined_parser_job

# Configure logging (similar to how it's done in main.py)
logging.basicConfig(
    format="%(levelname)s::%(asctime)s::%(pathname)s::%(lineno)d - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    level=settings.logging_level,
)

async def main():
    logging.info("Manually triggering Combined Playlist Parser job...")
    await run_combined_parser_job()
    logging.info("Combined Playlist Parser job finished.")

if __name__ == "__main__":
    asyncio.run(main())
