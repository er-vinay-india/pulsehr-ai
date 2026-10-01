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


def _contrast(a, b):
    def lum(c):
        values = [int(c[i:i+2], 16) / 255 for i in (1, 3, 5)]
        return sum(w * (v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4) for w, v in zip((.2126, .7152, .0722), values))
    low, high = sorted((lum(a), lum(b)))
    return (high + .05) / (low + .05)


def photo_scrim_opacity(slide_data, theme):
    import math
    foregrounds = [theme[k] for k in ("primary_text", "secondary_text", "muted_text", "brand_color", "accent_color", "success_color", "danger_color", "warning_color")]
    requested = max(0, min(100, float(slide_data.get("scrim_opacity", 70)))) / 100
    for step in range(math.ceil(requested * 1000), 1001):
        alpha = step / 1000
        extremes = ["#" + "".join(f"{int(int(theme['bg_color'][i:i+2],16)*alpha+pixel*(1-alpha)+.5):02x}" for i in (1,3,5)) for pixel in (0,255)]
        if all(_contrast(c, bg) >= 7.1 for c in foregrounds for bg in extremes):
            return alpha
    return 1.0


def add_photo_background(slide, slide_data, width, height, theme=None):
    url = slide_data.get("background_image")
    if not url:
        return
    try:
        raw_data = photo_bytes(url)
        with Image.open(BytesIO(raw_data)) as source:
            canvas = ImageOps.fit(source.convert("RGB"), (1920, 1080))
        from .visual.design_tokens import slide_theme_preset
        theme = slide_theme_preset(theme)
        opacity = photo_scrim_opacity(slide_data, theme)
        canvas = Image.blend(canvas, Image.new("RGB", canvas.size, theme["bg_color"]), opacity)
        output = BytesIO()
        canvas.save(output, format="PNG")
        output.seek(0)
        slide.shapes.add_picture(output, 0, 0, width=width, height=height)
    except Exception as exc:
        logger.warning("Could not apply presentation photo background from %s: %s", url, exc)
