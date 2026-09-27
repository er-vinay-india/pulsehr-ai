"""Render approved browse-photo backgrounds behind native PowerPoint content."""
from functools import lru_cache
from io import BytesIO
import ipaddress
import logging
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)


def _is_safe_public_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("https", "http"):
            return False
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return False
        # Block localhost / link-local / internal names
        if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1") or hostname.endswith(".local") or hostname.endswith(".internal"):
            return False
        # Check IP addresses against private / loopback / link-local subnets
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        except ValueError:
            pass  # It's a standard hostname / domain name
        return True
    except Exception:
        return False


@lru_cache(maxsize=24)
def photo_bytes(url: str) -> bytes:
    # Browse photos come from public image CDNs. Never fetch arbitrary internal URLs.
    if not _is_safe_public_url(url):
        raise ValueError(f"Unsupported presentation photo source: {url}")
    req = Request(
        url,
        headers={
            "User-Agent": "HighView-Presentation/1.0 (Commercial Workplace Photography Provider)",
            "Accept": "image/*",
        },
    )
    with urlopen(req, timeout=10) as response:
        if not _is_safe_public_url(response.url):
            raise ValueError("Unexpected image redirect to invalid target")
        data = response.read(12 * 1024 * 1024 + 1)
    if len(data) > 12 * 1024 * 1024:
        raise ValueError("Presentation photo is too large")
    return data


def add_photo_background(slide, slide_data, width, height):
    url = slide_data.get("background_image")
    if not url:
        return
    try:
        raw_data = photo_bytes(url)
        with Image.open(BytesIO(raw_data)) as source:
            canvas = ImageOps.fit(source.convert("RGB"), (1920, 1080))
        opacity = max(0, min(90, float(slide_data.get("scrim_opacity", 70)))) / 100
        canvas = Image.blend(canvas, Image.new("RGB", canvas.size, "black"), opacity)
        output = BytesIO()
        canvas.save(output, format="JPEG", quality=90)
        output.seek(0)
        slide.shapes.add_picture(output, 0, 0, width=width, height=height)
    except Exception as exc:
        logger.warning("Could not apply presentation photo background from %s: %s", url, exc)
