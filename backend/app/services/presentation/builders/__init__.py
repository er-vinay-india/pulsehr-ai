from .common import (
    THEMES,
    BRIEFING_CFG,
    DECK_DEFAULTS,
    calculate_timing,
    find_evidence,
    format_briefing,
    build_default_evidence_ledger,
    load_json_template,
)
from .summary_builder import (
    build_executive_summary_slide,
    build_baseline_scope_slide,
)
from .strengths_builder import (
    build_strengths_slides,
)
from .headwinds_builder import (
    build_headwinds_slides,
)
from .industrial_builder import (
    build_industrial_slides,
)
from .governance_builder import (
    build_boundary_and_evidence_slides,
    build_evidence_ledger_slides,
)
from .roadmap_builder import (
    build_roadmap_slides,
)

__all__ = [
    "THEMES",
    "BRIEFING_CFG",
    "DECK_DEFAULTS",
    "calculate_timing",
    "find_evidence",
    "format_briefing",
    "build_default_evidence_ledger",
    "load_json_template",
    "build_executive_summary_slide",
    "build_baseline_scope_slide",
    "build_strengths_slides",
    "build_headwinds_slides",
    "build_industrial_slides",
    "build_boundary_and_evidence_slides",
    "build_evidence_ledger_slides",
    "build_roadmap_slides",
]
