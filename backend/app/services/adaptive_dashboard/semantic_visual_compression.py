"""Semantic Visual Compression Layer & Semantic Icon Registry.

Converts Level-1 executive analytical topics and stories into minimal,
decision-first visual language without repetitive report prose.

Governed Contracts:
1. short_title: <= 7 words
2. short_context: <= 8 words
3. short_finding: <= 12 words
4. cta: <= 3 words (default "Inspect →")
5. Deterministic semantic icon resolution via SemanticIconRegistry
6. Recommended action is NEVER rendered permanently inside Level-1 cards
   (retained on demand in Quick Inspect / Data Explorer drawer).
"""
from __future__ import annotations

import re
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class VisualMicrocopy(BaseModel):
    """Compressed microcopy contract for Level-1 executive dashboard cards."""
    model_config = ConfigDict(extra="ignore")

    icon: str = "bar_chart"                # Canonical semantic icon key
    short_title: str = ""                  # <= 7 words
    primary_number: str = ""               # Contextual focal metric or target
    short_context: str = ""                # <= 8 words
    short_finding: str = ""                # <= 12 words
    cta: str = "Inspect"                   # <= 3 words


class SemanticIconRegistry:
    """Deterministically resolves semantic icons based on intent, measure concept, and domain."""

    INTENT_ICON_MAP: dict[str, str] = {
        "TARGET_VS_ACTUAL": "target",
        "RANKING": "trophy",
        "DISTRIBUTION": "distribution",
        "RELATIONSHIP": "relationship",
        "COMPOSITION": "composition",
        "COMPARISON": "compare",
        "ANOMALY": "alert",
        "TREND": "trend",
        "TEMPORAL": "trend",
        "MATRIX": "matrix",
    }

    CONCEPT_ICON_MAP: list[tuple[re.Pattern, str]] = [
        (re.compile(r"\b(policy|compliance|standard|adherence)\b", re.IGNORECASE), "shield"),
        (re.compile(r"\b(target|goal|benchmark|threshold)\b", re.IGNORECASE), "target"),
        (re.compile(r"\b(attendance|wfo|presence|office|employee)\b", re.IGNORECASE), "users"),
        (re.compile(r"\b(leave|vacation|absence|holiday|calendar)\b", re.IGNORECASE), "calendar"),
        (re.compile(r"\b(top|leader|winner|champion|rank|podium)\b", re.IGNORECASE), "trophy"),
        (re.compile(r"\b(alert|outlier|anomaly|hazard|spike|risk)\b", re.IGNORECASE), "alert"),
        (re.compile(r"\b(pm10|pm2\.5|so2|no2|air|pollution|particulate|emission)\b", re.IGNORECASE), "wind"),
        (re.compile(r"\b(spread|dispersion|variance|quartile|iqr)\b", re.IGNORECASE), "distribution"),
        (re.compile(r"\b(disparity|ratio|gap|difference|vs)\b", re.IGNORECASE), "compare"),
        (re.compile(r"\b(correlation|association|scatter)\b", re.IGNORECASE), "relationship"),
        (re.compile(r"\b(heatmap|matrix|grid)\b", re.IGNORECASE), "matrix"),
    ]

    @classmethod
    def resolve_icon(
        cls,
        intent: str,
        title: str = "",
        measure: str = "",
        domain: str = "general",
    ) -> str:
        """Deterministically selects a semantic icon token."""
        combined_text = f"{title} {measure}".lower()

        # 1. Match high-priority conceptual triggers
        for pattern, icon_key in cls.CONCEPT_ICON_MAP:
            if pattern.search(combined_text):
                return icon_key

        # 2. Fallback to analytical intent mapping
        norm_intent = intent.upper()
        if norm_intent in cls.INTENT_ICON_MAP:
            return cls.INTENT_ICON_MAP[norm_intent]

        # 3. Domain fallback
        if "env" in domain.lower() or "air" in domain.lower():
            return "wind"
        if "workforce" in domain.lower() or "hr" in domain.lower():
            return "users"

        return "bar_chart"


class SemanticVisualCompressionLayer:
    """Applies executive microcopy compression to topics and analytical stories."""

    @classmethod
    def truncate_words(cls, text: str, max_words: int, suffix: str = "…") -> str:
        """Truncates text to a maximum word count, stripping template braces."""
        if not text:
            return ""
        clean = re.sub(r"\{[a-zA-Z0-9_]+\}", "", text).strip()
        clean = re.sub(r"\s+", " ", clean)
        words = clean.split()
        if len(words) <= max_words:
            return clean
        return " ".join(words[:max_words]).rstrip(",;.:-") + suffix

    @classmethod
    def compress_topic(
        cls,
        title: str,
        takeaway: str,
        intent: str,
        key_metric: str = "",
        tokens: dict[str, Any] | None = None,
        domain: str = "general",
    ) -> VisualMicrocopy:
        """Compresses full analytical topic narrative into Level-1 VisualMicrocopy."""
        tokens = tokens or {}
        primary_meas = tokens.get("primary_measure") or ""

        # 1. Resolve deterministic semantic icon
        icon = SemanticIconRegistry.resolve_icon(
            intent=intent,
            title=title,
            measure=primary_meas,
            domain=domain,
        )

        # 2. Compressed Title (<= 7 words)
        short_title = cls._compress_title(title, intent, tokens, domain=domain)

        # 3. Primary number & context (focal metrics)
        primary_number, short_context = cls._derive_metric_and_context(key_metric, intent, tokens)

        # 4. Short finding insight (<= 12 words)
        short_finding = cls._compress_finding(takeaway, intent, tokens)

        # 5. Compressed CTA (<= 3 words)
        cta = cls._derive_cta(intent)

        return VisualMicrocopy(
            icon=icon,
            short_title=short_title,
            primary_number=primary_number,
            short_context=short_context,
            short_finding=short_finding,
            cta=cta,
        )

    @classmethod
    def _humanize_label(cls, label: str) -> str:
        """Removes underscores and normalizes to clean executive title casing."""
        if not label:
            return ""
        clean = re.sub(r"[_\s]+", " ", str(label)).strip()
        acronyms = {"cpi", "gdp", "roi", "pm10", "pm25", "pm2.5", "so2", "no2", "co2", "aqi", "wfo", "hr", "kpi"}
        words = []
        for w in clean.split():
            w_lower = w.lower()
            if w_lower in acronyms:
                words.append("PM2.5" if w_lower == "pm25" else w.upper())
            elif w_lower in {"vs", "and", "of", "in", "on", "for", "to", "with", "by"}:
                words.append(w_lower if words else w.title())
            else:
                words.append(w.title())
        return " ".join(words)

    @classmethod
    def _compress_title(
        cls,
        title: str,
        intent: str,
        tokens: dict[str, Any],
        domain: str = "general",
    ) -> str:
        """Generates an executive short title <= 7 words strictly preserving domain and topic semantics."""
        title_lower = title.lower()
        domain_lower = (domain or "").lower()
        is_workforce = "workforce" in domain_lower or domain_lower in ("hr", "workforce_hr")
        is_env = "env" in domain_lower or "air" in domain_lower
        is_retail = "retail" in domain_lower or "sales" in domain_lower or "commercial" in domain_lower

        # 1. RELATIONSHIP / Scatter: derive strictly from measures or clean "X vs Y"
        if intent == "RELATIONSHIP" or " vs " in title_lower:
            x_m = tokens.get("x_measure")
            y_m = tokens.get("y_measure")
            if x_m and y_m:
                clean_x = re.sub(r"\b(Annual Average|Rate|Total|Observed)\b", "", str(x_m), flags=re.IGNORECASE).strip()
                clean_y = re.sub(r"\b(Annual Average|Rate|Total|Observed)\b", "", str(y_m), flags=re.IGNORECASE).strip()
                clean_x = cls._humanize_label(clean_x or str(x_m))
                clean_y = cls._humanize_label(clean_y or str(y_m))
                short_rel = f"{clean_x} vs {clean_y}"
                if len(short_rel.split()) <= 7:
                    return short_rel
                return cls.truncate_words(short_rel, max_words=7, suffix="")
            if " vs " in title:
                parts = title.split(" vs ", 1)
                left = re.sub(r"\b(Statistical Association|Multi-Pollutant Association|Association|Relationship|Correlation|Analysis|Study)\b", "", parts[0], flags=re.IGNORECASE).strip()
                right = re.sub(r"\b(Statistical Association|Multi-Pollutant Association|Association|Relationship|Correlation|Analysis|Study)\b", "", parts[1], flags=re.IGNORECASE).strip()
                left = cls._humanize_label(left)
                right = cls._humanize_label(right)
                if left and right:
                    short_rel = f"{left} vs {right}"
                    if len(short_rel.split()) <= 7:
                        return short_rel
                    return cls.truncate_words(short_rel, max_words=7, suffix="")

        # 2. TOP 3 PODIUM / LEADERS / HOTSPOTS / PERFORMERS
        if "top 3" in title_lower:
            meas = tokens.get("primary_measure") or tokens.get("measure_column") or ""
            if not meas:
                if is_workforce or "attendance" in title_lower:
                    meas = "Attendance"
                elif is_env or "pm10" in title_lower:
                    meas = "PM10"
                elif is_retail or "sales" in title_lower:
                    meas = "Sales"
            meas_str = cls._humanize_label(str(meas))
            if meas_str:
                if is_workforce:
                    return f"Top 3 {meas_str} Leaders"
                elif is_env:
                    hot_name = meas_str.upper() if len(meas_str) <= 4 else meas_str
                    return f"Top 3 {hot_name} Hotspots"
                elif is_retail:
                    return f"Top 3 {meas_str} Stores"
                return f"Top 3 {meas_str} Performers"

        # 3. Domain-specific verified patterns (ONLY when domain matches)
        if is_workforce:
            if "attendance ranking & policy benchmark" in title_lower or "attendance ranking" in title_lower:
                return "Department Attendance Ranking"
            if "governed policy benchmark" in title_lower or "attendance vs governed policy" in title_lower:
                return "WFO Policy Compliance"
            if "cross-source" in title_lower and "leave" in title_lower:
                return "Attendance vs Leave Capacity"
            if "variance & dispersion" in title_lower or "spread & quartile" in title_lower:
                return "Attendance Spread & Dispersion"
            if "leave allocation benchmark" in title_lower:
                return "Department Leave Utilization"
            if "weekly attendance heatmap" in title_lower or ("attendance" in title_lower and ("matrix" in title_lower or "heatmap" in title_lower)):
                return "Weekly Attendance Heatmap"

        elif is_env:
            if "particulate" in title_lower and ("dispersion" in title_lower or "spread" in title_lower):
                return "Particulate Quartile Dispersion"
            if "pollutant" in title_lower and ("matrix" in title_lower or "zone" in title_lower or "intensity" in title_lower):
                return "Pollutant Zone Matrix"
            if "outlier concentration" in title_lower or "outlier variance" in title_lower or "outlier spikes" in title_lower:
                return "Pollution Outlier Spikes"

        elif is_retail:
            if "store performance" in title_lower or "sales revenue ranking" in title_lower:
                return "Store Sales Ranking"
            if "store sales" in title_lower and ("dispersion" in title_lower or "spread" in title_lower or "quartile" in title_lower):
                return "Store Sales Dispersion"
            if "category revenue composition" in title_lower:
                return "Merchandise Category Mix"

        # 4. Standard intent-based compression if tokens provide clean measure
        if intent == "DISTRIBUTION":
            m = tokens.get("primary_measure")
            if m:
                clean_m = cls._humanize_label(str(m))
                return f"{clean_m} Quartile Dispersion"

        if intent == "ANOMALY":
            m = tokens.get("primary_measure")
            if m:
                clean_m = cls._humanize_label(str(m))
                return f"{clean_m} Outlier Exceptions"

        # 5. General truncation to <= 7 words without corrupting domain words
        clean = re.sub(r"\b(how do|what is the|statistical|analysis of|breakdown of|ranking & policy benchmark)\b", "", title, flags=re.IGNORECASE).strip()
        clean = cls._humanize_label(clean or title)
        return cls.truncate_words(clean, max_words=7, suffix="")

    @classmethod
    def _derive_metric_and_context(
        cls,
        key_metric: str,
        intent: str,
        tokens: dict[str, Any],
    ) -> tuple[str, str]:
        """Derives clean primary number and short context <= 8 words."""
        bench = tokens.get("benchmark")
        unit = tokens.get("unit", "")
        cats = tokens.get("categories", [])
        vals = tokens.get("values", [])

        # Priority 1: Target / Benchmark
        if intent == "TARGET_VS_ACTUAL" and bench is not None:
            above = sum(1 for v in vals if v >= bench) if vals else 0
            below = sum(1 for v in vals if v < bench) if vals else 0
            primary_num = f"{bench} {unit}".strip() + " target"
            context = f"{above} above · {below} below" if (above or below) else f"Benchmark: {bench} {unit}".strip()
            return primary_num, cls.truncate_words(context, max_words=8, suffix="")

        # Priority 2: Key metric provided
        if key_metric and ":" in key_metric:
            parts = [p.strip() for p in key_metric.split(":", 1)]
            primary_num = parts[1]
            context = parts[0]
            return cls.truncate_words(primary_num, max_words=5, suffix=""), cls.truncate_words(context, max_words=8, suffix="")

        if key_metric:
            return cls.truncate_words(key_metric, max_words=5, suffix=""), f"{len(cats)} cohorts" if cats else ""

        # Priority 3: Fallback from categories
        if cats and vals:
            top_val = vals[0]
            primary_num = f"{top_val} {unit}".strip()
            context = f"Top: {cats[0]}"
            return primary_num, cls.truncate_words(context, max_words=8, suffix="")

        return "", ""

    @classmethod
    def _compress_finding(cls, takeaway: str, intent: str, tokens: dict[str, Any]) -> str:
        """Compresses takeaway into a single punchy sentence <= 12 words."""
        if not takeaway:
            return "Evaluated performance across reporting population."

        # Simplify common verbose patterns
        clean = takeaway
        clean = re.sub(r"^(Observed|Substantial|Core departments)\s+", "", clean)
        clean = re.sub(r"between presence and approved leaves\.", "between presence and leaves.", clean)
        clean = re.sub(r"reflecting department-level scheduling differences\.", "highlighting department variations.", clean)
        clean = re.sub(r"substantially exceeding the 60 µg/m³ NAAQS annual benchmark\.", "exceeding NAAQS 60 µg/m³ standard.", clean)

        return cls.truncate_words(clean, max_words=12, suffix=".")

    @classmethod
    def _derive_cta(cls, intent: str) -> str:
        """Generates a compact CTA <= 3 words."""
        if intent == "RANKING":
            return "View ranking"
        if intent == "TARGET_VS_ACTUAL":
            return "Inspect target"
        if intent == "RELATIONSHIP":
            return "Explore"
        if intent == "DISTRIBUTION":
            return "Inspect spread"
        if intent == "ANOMALY":
            return "View outliers"
        if intent == "MATRIX":
            return "View matrix"
        return "Inspect"
