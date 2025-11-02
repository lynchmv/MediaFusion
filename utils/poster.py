import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import textwrap

import aiohttp
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError
from aiohttp_socks import ProxyConnector

from db.config import settings
from db.models import MediaFusionMetaData
from scrapers.imdb_data import get_imdb_rating
from utils import const
from db.redis_database import REDIS_ASYNC_CLIENT

# Use a more efficient ThreadPoolExecutor with a fixed number of workers
executor = ThreadPoolExecutor(max_workers=4)

# --- Optimization 1: Pre-load and cache fonts at startup ---
FONT_CACHE = {
    "medium_24": ImageFont.truetype("resources/fonts/IBMPlexSans-Medium.ttf", 24),
    "bold_50": ImageFont.truetype("resources/fonts/IBMPlexSans-Bold.ttf", 50),
    "bold_40": ImageFont.truetype("resources/fonts/IBMPlexSans-Bold.ttf", 40),
    "bold_30": ImageFont.truetype("resources/fonts/IBMPlexSans-Bold.ttf", 30),
}
IMDB_LOGO = Image.open("resources/images/imdb_logo.png")
WATERMARK_LOGO = Image.open("resources/images/logo_text.png")


async def fetch_poster_image(url: str) -> bytes:
    cached_image = await REDIS_ASYNC_CLIENT.get(url)
    if cached_image:
        return cached_image

    connector = aiohttp.TCPConnector()
    if settings.requests_proxy_url:
        connector = ProxyConnector.from_url(settings.requests_proxy_url)

    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.get(url, timeout=30, headers=const.UA_HEADER) as response:
            response.raise_for_status()
            if not response.headers["Content-Type"].lower().startswith("image/"):
                raise ValueError(f"Unexpected content type: {response.headers['Content-Type']}")
            content = await response.read()
            await REDIS_ASYNC_CLIENT.set(url, content, ex=3600)
            return content

# --- Optimization 2: Simplified and more efficient text drawing ---
def add_elements_to_poster(image: Image.Image, imdb_rating: float = None) -> Image.Image:
    draw = ImageDraw.Draw(image, "RGBA")
    margin = 10
    padding = 5

    if imdb_rating:
        imdb_text = f" {imdb_rating}/10"
        font = FONT_CACHE["medium_24"]

        bbox = draw.textbbox((0, 0), imdb_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        aspect_ratio = IMDB_LOGO.width / IMDB_LOGO.height
        imdb_logo_resized = IMDB_LOGO.resize((int(text_height * aspect_ratio), text_height))

        rect_x0 = margin
        rect_y0 = image.height - margin - text_height - (2 * padding)
        rect_x1 = rect_x0 + imdb_logo_resized.width + text_width + (2 * padding)
        rect_y1 = image.height - margin

        draw.rounded_rectangle((rect_x0, rect_y0, rect_x1, rect_y1), fill=(0, 0, 0, 176), radius=8)
        image.paste(imdb_logo_resized, (rect_x0 + padding, rect_y0 + padding), imdb_logo_resized)
        draw.text((rect_x0 + padding + imdb_logo_resized.width, rect_y0 + padding), imdb_text, font=font, fill="#F5C518")

    aspect_ratio = WATERMARK_LOGO.width / WATERMARK_LOGO.height
    new_width = int(image.width * 0.4)
    watermark_resized = WATERMARK_LOGO.resize((new_width, int(new_width / aspect_ratio)))
    watermark_position = (image.width - watermark_resized.width - margin, margin)
    image.paste(watermark_resized, watermark_position, watermark_resized)

    return image

# --- Optimization 3: Simplified text color logic ---
def get_text_color_for_background(image: Image.Image, area: tuple) -> tuple:
    cropped = image.crop(area).resize((1, 1), Image.Resampling.LANCZOS)
    avg_color = cropped.getpixel((0, 0))
    brightness = (avg_color[0] * 299 + avg_color[1] * 587 + avg_color[2] * 114) / 1000
    return ("black", "white") if brightness > 128 else ("white", "black")

# --- Optimization 4: Simplified text wrapping and drawing ---
def add_title_to_poster(image: Image.Image, title_text: str) -> Image.Image:
    draw = ImageDraw.Draw(image)
    max_width_px = image.width - 40

    font = FONT_CACHE["bold_50"]
    avg_char_width = font.getlength("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") / 62
    max_chars_per_line = int(max_width_px / avg_char_width) if avg_char_width > 0 else 20

    wrapped_lines = textwrap.wrap(title_text, width=max_chars_per_line, max_lines=3, placeholder="...")

    text_block_height = len(wrapped_lines) * (font.size + 5)
    y_position = (image.height - text_block_height) / 2

    text_color, outline_color = get_text_color_for_background(image, (20, y_position, image.width - 20, y_position + text_block_height))

    for line in wrapped_lines:
        line_width = draw.textlength(line, font=font)
        x_position = (image.width - line_width) / 2

        for dx, dy in [(-1,-1), (-1,1), (1,-1), (1,1)]:
            draw.text((x_position+dx, y_position+dy), line, font=font, fill=outline_color)
        draw.text((x_position, y_position), line, font=font, fill=text_color)

        y_position += font.size + 5

    return image


def process_poster_image(content: bytes, mediafusion_data: MediaFusionMetaData) -> BytesIO:
    try:
        original_image = Image.open(BytesIO(content)).convert("RGB")

        # --- Start of Aspect Ratio Preservation Logic ---
        target_width, target_height = 300, 450
        original_width, original_height = original_image.size

        # Calculate the ratio to fit within the target dimensions
        ratio = min(target_width / original_width, target_height / original_height)
        new_width = int(original_width * ratio)
        new_height = int(original_height * ratio)

        # Resize the image while maintaining aspect ratio
        resized_image = original_image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Create a new black background canvas
        background = Image.new('RGB', (target_width, target_height), (0, 0, 0))

        # Calculate position to paste the resized image so it's centered
        paste_x = (target_width - new_width) // 2
        paste_y = (target_height - new_height) // 2

        # Paste the resized image onto the background
        background.paste(resized_image, (paste_x, paste_y))

        # Use the new composite image for further processing
        image = background
        # --- End of Aspect Ratio Preservation Logic ---

        # Safely get the imdb_rating, defaulting to None if it doesn't exist
        imdb_rating = getattr(mediafusion_data, 'imdb_rating', None)
        image = add_elements_to_poster(image, imdb_rating)

        if mediafusion_data.is_add_title_to_poster:
            image = add_title_to_poster(image, mediafusion_data.title)

        byte_io = BytesIO()
        image.save(byte_io, "JPEG", quality=85)
        byte_io.seek(0)
        return byte_io
    except UnidentifiedImageError:
        raise ValueError("Cannot identify image from provided content")

async def create_poster(mediafusion_data: MediaFusionMetaData) -> BytesIO:
    content = await fetch_poster_image(mediafusion_data.poster)

    if mediafusion_data.id.startswith("tt") and getattr(mediafusion_data, 'imdb_rating', None) is None:
        imdb_rating = await get_imdb_rating(mediafusion_data.id)
        if imdb_rating:
            # This part of the code is tricky, as MediaFusionTVMetaData doesn't have this field.
            # We'll set it dynamically if the object allows, but the main fix is in process_poster_image
            if hasattr(mediafusion_data, 'imdb_rating'):
                mediafusion_data.imdb_rating = imdb_rating

    loop = asyncio.get_running_loop()
    byte_io = await loop.run_in_executor(
        executor, process_poster_image, content, mediafusion_data
    )
    return byte_io

