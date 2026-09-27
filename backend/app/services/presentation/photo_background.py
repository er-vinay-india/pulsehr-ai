"""Render approved browse-photo backgrounds behind native PowerPoint content."""
from functools import lru_cache
from io import BytesIO
from urllib.parse import urlparse
from urllib.request import urlopen

from PIL import Image, ImageOps


@lru_cache(maxsize=24)
def photo_bytes(url: str) -> bytes:
    # Browse photos come from this public image CDN. Never fetch arbitrary internal URLs.
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "images.unsplash.com":
        raise ValueError("Unsupported presentation photo source")
    with urlopen(url, timeout=12) as response:
        if urlparse(response.url).hostname != "images.unsplash.com":
            raise ValueError("Unexpected image redirect")
        data = response.read(12 * 1024 * 1024 + 1)
    if len(data) > 12 * 1024 * 1024:
        raise ValueError("Presentation photo is too large")
    return data


def add_photo_background(slide, slide_data, width, height):
    url = slide_data.get("background_image")
    if not url:
        return
    with Image.open(BytesIO(photo_bytes(url))) as source:
        canvas = ImageOps.fit(source.convert("RGB"), (1920, 1080))
    opacity = max(0, min(90, float(slide_data.get("scrim_opacity", 70)))) / 100
    canvas = Image.blend(canvas, Image.new("RGB", canvas.size, "black"), opacity)
    output = BytesIO()
    canvas.save(output, format="JPEG", quality=90)
    output.seek(0)
    slide.shapes.add_picture(output, 0, 0, width=width, height=height)
