from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

# Curated catalog of high-resolution, commercial-friendly free workplace photography
# Ready out-of-the-box with zero API key requirement.
CURATED_WORKPLACE_IMAGES: list[dict[str, Any]] = [
    {
        "id": "curated-01",
        "title": "Modern Executive Boardroom Meeting",
        "url": "https://images.unsplash.com/photo-1542744173-8e7e53415bb0?auto=format&fit=crop&w=1600&q=80",
        "thumbnail": "https://images.unsplash.com/photo-1542744173-8e7e53415bb0?auto=format&fit=crop&w=400&q=80",
        "creator": "Campaign Creators",
        "source": "Unsplash (Free Commercial)",
        "tags": ["executive", "boardroom", "strategy", "leadership", "meeting"],
        "category": "executive",
    },
    {
        "id": "curated-02",
        "title": "Frontline Retail Operations & Logistics",
        "url": "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?auto=format&fit=crop&w=1600&q=80",
        "thumbnail": "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?auto=format&fit=crop&w=400&q=80",
        "creator": "Adrian Sulyok",
        "source": "Unsplash (Free Commercial)",
        "tags": ["retail", "store", "warehouse", "logistics", "operations"],
        "category": "operations",
    },
    {
        "id": "curated-03",
        "title": "Cross-Functional Team Collaboration",
        "url": "https://images.unsplash.com/photo-1522071820081-009f0129c71c?auto=format&fit=crop&w=1600&q=80",
        "thumbnail": "https://images.unsplash.com/photo-1522071820081-009f0129c71c?auto=format&fit=crop&w=400&q=80",
        "creator": "Annie Spratt",
        "source": "Unsplash (Free Commercial)",
        "tags": ["team", "collaboration", "workforce", "people", "office"],
        "category": "team",
    },
    {
        "id": "curated-04",
        "title": "People Analytics & Dashboard Review",
        "url": "https://images.unsplash.com/photo-1551836022-d5d88e9218df?auto=format&fit=crop&w=1600&q=80",
        "thumbnail": "https://images.unsplash.com/photo-1551836022-d5d88e9218df?auto=format&fit=crop&w=400&q=80",
        "creator": "Amy Hirschi",
        "source": "Unsplash (Free Commercial)",
        "tags": ["analytics", "data", "metrics", "performance", "review"],
        "category": "analytics",
    },
    {
        "id": "curated-05",
        "title": "Store Floor Shift Attendance & Customer Flow",
        "url": "https://images.unsplash.com/photo-1556742049-0a67c5574f73?auto=format&fit=crop&w=1600&q=80",
        "thumbnail": "https://images.unsplash.com/photo-1556742049-0a67c5574f73?auto=format&fit=crop&w=400&q=80",
        "creator": "Blake Wisz",
        "source": "Unsplash (Free Commercial)",
        "tags": ["store", "retail", "frontline", "attendance", "service"],
        "category": "operations",
    },
    {
        "id": "curated-06",
        "title": "Workforce Diversity & Human Capital",
        "url": "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=1600&q=80",
        "thumbnail": "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=400&q=80",
        "creator": "Christina @ wocintechchat.com",
        "source": "Unsplash (Free Commercial)",
        "tags": ["hr", "diversity", "equity", "retention", "talent"],
        "category": "team",
    },
    {
        "id": "curated-07",
        "title": "Financial Economics & Payroll Planning",
        "url": "https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?auto=format&fit=crop&w=1600&q=80",
        "thumbnail": "https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?auto=format&fit=crop&w=400&q=80",
        "creator": "Towfiqu barbhuiya",
        "source": "Unsplash (Free Commercial)",
        "tags": ["finance", "economics", "budget", "payroll", "cost"],
        "category": "analytics",
    },
    {
        "id": "curated-08",
        "title": "Supply Chain & Fulfillment Hub",
        "url": "https://images.unsplash.com/photo-1553413077-190dd305871c?auto=format&fit=crop&w=1600&q=80",
        "thumbnail": "https://images.unsplash.com/photo-1553413077-190dd305871c?auto=format&fit=crop&w=400&q=80",
        "creator": "CHUTTERSNAP",
        "source": "Unsplash (Free Commercial)",
        "tags": ["warehouse", "fulfillment", "supply chain", "logistics", "store"],
        "category": "operations",
    },
    {
        "id": "curated-09",
        "title": "Strategic Leadership & Board Presentation",
        "url": "https://images.unsplash.com/photo-1517245386807-bb43f82c33c4?auto=format&fit=crop&w=1600&q=80",
        "thumbnail": "https://images.unsplash.com/photo-1517245386807-bb43f82c33c4?auto=format&fit=crop&w=400&q=80",
        "creator": "Headway",
        "source": "Unsplash (Free Commercial)",
        "tags": ["presentation", "leadership", "boardroom", "c-suite", "governance"],
        "category": "executive",
    },
    {
        "id": "curated-10",
        "title": "Healthcare & Essential Workforce Operations",
        "url": "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=1600&q=80",
        "thumbnail": "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=400&q=80",
        "creator": "National Cancer Institute",
        "source": "Unsplash (Free Commercial)",
        "tags": ["operations", "essential", "shifts", "care", "clinical"],
        "category": "operations",
    },
    {
        "id": "curated-11",
        "title": "Architecture & Engineering Planning Studio",
        "url": "https://images.unsplash.com/photo-1503387762-592deb58ef4e?auto=format&fit=crop&w=1600&q=80",
        "thumbnail": "https://images.unsplash.com/photo-1503387762-592deb58ef4e?auto=format&fit=crop&w=400&q=80",
        "creator": "Daniel McCullough",
        "source": "Unsplash (Free Commercial)",
        "tags": ["architecture", "engineering", "design", "planning", "projects"],
        "category": "executive",
    },
    {
        "id": "curated-12",
        "title": "Forward Forecasting & Predictive Modeling",
        "url": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1600&q=80",
        "thumbnail": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=400&q=80",
        "creator": "Carlos Muza",
        "source": "Unsplash (Free Commercial)",
        "tags": ["forecast", "trends", "growth", "outlook", "analytics"],
        "category": "analytics",
    },
]


def search_free_images(query: str = "workplace", category: str | None = None, page_size: int = 12) -> list[dict[str, Any]]:
    """
    Search royalty-free images using Openverse API with seamless fallback to curated library.
    Zero API keys required; 100% compliant with commercial use.
    """
    results: list[dict[str, Any]] = []
    clean_query = query.strip() or "workplace"

    # 1. Try Openverse Public Domain / CC-0 API
    try:
        encoded_query = urllib.parse.quote(clean_query)
        url = f"https://api.openverse.org/v1/images/?q={encoded_query}&license_type=commercial&page_size={page_size}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "HighView/1.0 (Executive Presentation Studio; powered by HRIDAY)",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                raw_results = data.get("results", [])
                for item in raw_results:
                    image_url = item.get("url")
                    thumb_url = item.get("thumbnail") or image_url
                    if image_url and (image_url.startswith("http://") or image_url.startswith("https://")):
                        results.append(
                            {
                                "id": f"openverse-{item.get('id', '')}",
                                "title": item.get("title") or f"{clean_query.capitalize()} Image",
                                "url": image_url,
                                "thumbnail": thumb_url,
                                "creator": item.get("creator") or "Openverse Contributor",
                                "source": "Openverse (CC-0 / Commercial)",
                                "tags": [clean_query.lower()],
                                "category": category or "general",
                            }
                        )
    except Exception as exc:
        logger.debug("Openverse API lookup bypassed/failed: %s", exc)

    # 2. Augment / Fallback with Curated High-Res Workplace Photography
    # Filter curated images matching query or category
    curated_matches = []
    q_lower = clean_query.lower()

    for img in CURATED_WORKPLACE_IMAGES:
        if category and img.get("category") == category:
            curated_matches.append(img)
        elif any(q_lower in tag for tag in img.get("tags", [])) or q_lower in img.get("title", "").lower():
            curated_matches.append(img)

    if not curated_matches:
        # If no specific keyword match, supply diverse top picks
        curated_matches = CURATED_WORKPLACE_IMAGES

    # Combine: Curated high-res images first for supreme boardroom aesthetic, followed by API results
    combined = curated_matches + [r for r in results if r["url"] not in [c["url"] for c in curated_matches]]
    return combined[:page_size]
