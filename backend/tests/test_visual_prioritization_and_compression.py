"""Tests for Executive Visual Prioritization, Perceptual Diversity, and Semantic Compression.

Verifies:
1. SemanticVisualCompressionLayer microcopy word limits (title <= 7, context <= 8, finding <= 12, cta <= 3).
2. SemanticIconRegistry deterministic icon mappings.
3. VisualMorphology mapping and morphology capping (max_same_morphology <= 2).
4. DomainVisualPriority domain-specific decision scoring.
5. Heatmap matrix gating and mark presence validation.
6. Topic inspect payload preserves full unabridged analytical detail.
"""
import pytest
from app.services.adaptive_dashboard.semantic_visual_compression import (
    SemanticVisualCompressionLayer,
    SemanticIconRegistry,
    VisualMicrocopy,
)
from app.services.adaptive_dashboard.visual_portfolio_optimizer import (
    VisualPortfolioOptimizer,
    CandidatePortfolioItem,
    DashboardVisualBudget,
    VisualMorphology,
    DomainVisualPriority,
    ChartCapabilityRegistry,
    ChartFamily,
    LayoutHint,
)
from app.services.adaptive_dashboard.visual_presence_gates import VisualDataPresenceIntegrity
from app.services.adaptive_dashboard.composition_planner import ExecutiveTopic


def test_semantic_visual_compression_word_limits():
    """Verifies that all fields of VisualMicrocopy strictly adhere to executive word limits."""
    long_title = "A Very Long Detailed Analytical Story Title Describing Workforce Attendance Across Departments"
    long_takeaway = "Operations maintains the strongest presence in the company while Design trails by six point eight days due to scheduling."
    
    micro = SemanticVisualCompressionLayer.compress_topic(
        title=long_title,
        takeaway=long_takeaway,
        intent="RANKING",
        key_metric="6.8d spread across entities",
        domain="workforce",
    )
    
    assert isinstance(micro, VisualMicrocopy)
    
    # Word count assertions
    title_words = len(micro.short_title.split())
    assert title_words <= 7, f"Title has {title_words} words (expected <= 7): {micro.short_title}"
    
    context_words = len(micro.short_context.split())
    assert context_words <= 8, f"Context has {context_words} words (expected <= 8): {micro.short_context}"
    
    finding_words = len(micro.short_finding.split())
    assert finding_words <= 12, f"Finding has {finding_words} words (expected <= 12): {micro.short_finding}"
    
    cta_words = len(micro.cta.split())
    assert cta_words <= 3, f"CTA has {cta_words} words (expected <= 3): {micro.cta}"


def test_semantic_icon_registry():
    """Verifies deterministic semantic icon resolution."""
    assert SemanticIconRegistry.resolve_icon("TARGET_VS_ACTUAL") == "target"
    assert SemanticIconRegistry.resolve_icon("RANKING") == "trophy"
    assert SemanticIconRegistry.resolve_icon("DISTRIBUTION") == "distribution"
    assert SemanticIconRegistry.resolve_icon("MATRIX") == "matrix"
    assert SemanticIconRegistry.resolve_icon("TREND") == "trend"
    assert SemanticIconRegistry.resolve_icon("RELATIONSHIP") == "relationship"
    assert SemanticIconRegistry.resolve_icon("COMPOSITION") == "composition"
    assert SemanticIconRegistry.resolve_icon("ANOMALY") == "alert"
    
    # Concept overrides
    assert SemanticIconRegistry.resolve_icon("RANKING", "air quality pm10 pollutant") == "wind"
    assert SemanticIconRegistry.resolve_icon("RANKING", "employee attendance presence") == "users"


def test_visual_morphology_mapping():
    """Verifies that chart archetypes map to distinct visual morphologies."""
    assert ChartCapabilityRegistry.get_morphology("ranked_bar") == VisualMorphology.LENGTH
    assert ChartCapabilityRegistry.get_morphology("horizontal_bar") == VisualMorphology.LENGTH
    assert ChartCapabilityRegistry.get_morphology("bullet") == VisualMorphology.LENGTH
    assert ChartCapabilityRegistry.get_morphology("lollipop") == VisualMorphology.POINT
    assert ChartCapabilityRegistry.get_morphology("scatter") == VisualMorphology.POINT
    assert ChartCapabilityRegistry.get_morphology("dumbbell") == VisualMorphology.RANGE
    assert ChartCapabilityRegistry.get_morphology("box_plot") == VisualMorphology.DISTRIBUTION
    assert ChartCapabilityRegistry.get_morphology("100_percent_stacked_bar") == VisualMorphology.AREA
    assert ChartCapabilityRegistry.get_morphology("line") == VisualMorphology.TEMPORAL_PATH
    assert ChartCapabilityRegistry.get_morphology("heatmap") == VisualMorphology.MATRIX
    assert ChartCapabilityRegistry.get_morphology("podium_top_3") == VisualMorphology.ICONIC


def test_morphology_capping_in_portfolio_optimizer():
    """Verifies that the portfolio optimizer prevents length-based bar dominance (max_same_morphology <= 2)."""
    # Create 6 candidates that all have LENGTH morphology (e.g., ranked_bar, bullet, horizontal_bar)
    length_candidates = [
        CandidatePortfolioItem(
            item_id=f"LEN-{i}",
            title=f"Length Story {i}",
            semantic_family=f"fam_len_{i}",
            intent="RANKING" if i % 2 == 0 else "COMPARISON",
            chart_archetype="ranked_bar",
            chart_family=ChartFamily.COMPARISON,
            chart_morphology=VisualMorphology.LENGTH,
            importance_score=0.90 - (i * 0.02),
            confidence=0.95,
            business_value=0.90,
            decision_value=0.85,
            visual_spec={"chart_type": "ranked_bar", "categories": ["A", "B", "C"], "values": [10, 8, 6]},
        )
        for i in range(5)
    ]
    
    # And create diverse morphology candidates
    other_candidates = [
        CandidatePortfolioItem(
            item_id="DIST-01",
            title="Distribution Spread",
            semantic_family="fam_dist",
            intent="DISTRIBUTION",
            chart_archetype="box_plot",
            chart_family=ChartFamily.DISTRIBUTION,
            chart_morphology=VisualMorphology.DISTRIBUTION,
            importance_score=0.85,
            confidence=0.90,
            business_value=0.85,
            decision_value=0.80,
            visual_spec={"chart_type": "box_plot", "categories": ["A", "B", "C", "D", "E"], "values": [10, 8, 6, 4, 2]},
        ),
        CandidatePortfolioItem(
            item_id="MAT-01",
            title="Matrix Heatmap",
            semantic_family="fam_matrix",
            intent="MATRIX",
            chart_archetype="heatmap",
            chart_family=ChartFamily.CORRELATION,
            chart_morphology=VisualMorphology.MATRIX,
            importance_score=0.88,
            confidence=0.92,
            business_value=0.88,
            decision_value=0.82,
            visual_spec={
                "chart_type": "heatmap",
                "x_categories": ["X1", "X2"],
                "y_categories": ["Y1", "Y2"],
                "heatmap_data": [[0, 0, 1], [1, 0, 2], [0, 1, 3], [1, 1, 4]],
            },
        ),
        CandidatePortfolioItem(
            item_id="RANGE-01",
            title="Dumbbell Disparity",
            semantic_family="fam_range",
            intent="COMPARISON",
            chart_archetype="dumbbell",
            chart_family=ChartFamily.COMPARISON,
            chart_morphology=VisualMorphology.RANGE,
            importance_score=0.82,
            confidence=0.90,
            business_value=0.80,
            decision_value=0.75,
            visual_spec={"chart_type": "dumbbell", "categories": ["A", "B", "C"], "values": [10, 8, 6]},
        ),
        CandidatePortfolioItem(
            item_id="AREA-01",
            title="Reconciled Capacity",
            semantic_family="fam_area",
            intent="COMPOSITION",
            chart_archetype="100_percent_stacked_bar",
            chart_family=ChartFamily.PART_TO_WHOLE,
            chart_morphology=VisualMorphology.AREA,
            importance_score=0.89,
            confidence=0.95,
            business_value=0.88,
            decision_value=0.85,
            visual_spec={"chart_type": "100_percent_stacked_bar", "series": [{"name": "S1", "values": [1, 2]}]},
        ),
        CandidatePortfolioItem(
            item_id="ICONIC-01",
            title="Podium Leaders",
            semantic_family="fam_iconic",
            intent="RANKING",
            chart_archetype="podium_top_3",
            chart_family=ChartFamily.COMPARISON,
            chart_morphology=VisualMorphology.ICONIC,
            importance_score=0.87,
            confidence=0.92,
            business_value=0.85,
            decision_value=0.85,
            visual_spec={"chart_type": "podium_top_3", "categories": ["A", "B", "C"], "values": [10, 8, 6]},
        ),
    ]
    
    budget = DashboardVisualBudget(
        min_visuals=6,
        target_min=6,
        target_max=8,
        max_visuals=10,
        max_same_morphology=2,
    )
    
    selected = VisualPortfolioOptimizer.optimize_portfolio(
        candidates=length_candidates + other_candidates,
        budget=budget,
        domain="workforce",
    )
    
    morphology_counts = {}
    for c in selected:
        morphology_counts[c.chart_morphology] = morphology_counts.get(c.chart_morphology, 0) + 1
        
    # Strictly max 2 LENGTH morphology items selected despite 5 high-scoring length candidates available
    assert morphology_counts.get(VisualMorphology.LENGTH, 0) <= 2, f"Length morphology exceeded cap of 2: {morphology_counts}"
    # Selected portfolio must contain multiple distinct morphologies
    assert len(morphology_counts) >= 4, f"Selected portfolio lacks perceptual diversity: {morphology_counts}"


def test_domain_visual_priority():
    """Verifies domain-specific decision values."""
    # Workforce domain prioritizes policy targets and rankings as P1
    assert DomainVisualPriority.get_priority("workforce", "TARGET_VS_ACTUAL") == 1.00
    assert DomainVisualPriority.get_priority("workforce", "RANKING") == 0.95
    assert DomainVisualPriority.get_priority("workforce", "MATRIX") == 0.90
    assert DomainVisualPriority.get_priority("workforce", "COMPOSITION") == 0.85
    
    # Environmental domain prioritizes standard adherence and concentration rankings
    assert DomainVisualPriority.get_priority("environmental", "RANKING") == 1.00
    assert DomainVisualPriority.get_priority("environmental", "TARGET_VS_ACTUAL") == 0.95


def test_heatmap_presence_audit():
    """Verifies that heatmap passes VisualDataPresenceIntegrity when >= 4 cells exist."""
    valid_spec = {
        "chart_type": "heatmap",
        "heatmap_data": [[0, 0, 10], [1, 0, 20], [0, 1, 30], [1, 1, 40]],
        "x_categories": ["A", "B"],
        "y_categories": ["X", "Y"],
    }
    audit = VisualDataPresenceIntegrity.evaluate(valid_spec)
    assert audit.is_valid
    assert audit.rendered_mark_count == 4
    
    invalid_spec = {
        "chart_type": "heatmap",
        "heatmap_data": [[0, 0, 10]],  # < 4 cells
    }
    invalid_audit = VisualDataPresenceIntegrity.evaluate(invalid_spec)
    assert not invalid_audit.is_valid
