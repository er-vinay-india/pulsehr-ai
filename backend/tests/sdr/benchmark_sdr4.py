"""
Benchmark script for SDR-4 Controlled Enrichment Framework.
Measures Candidate Generation, Hard Gate Filtering, Utility Evaluation,
Runtime, and Memory across Small, Medium, and Large datasets.
"""
import time
import tracemalloc
from app.services.sdr.contracts.profiles import (
    SemanticColumnProfile,
    DeterministicColumnFeatures,
    SemanticColumnRole,
    SemanticDtype,
    ProfilingAmbiguityState,
    SourceCoordinateRef,
)
from app.services.sdr.contracts.policies import EnrichmentPolicy
from app.services.sdr.enrichment.provider import EnrichmentProviderRegistry
from app.services.sdr.enrichment.mock_providers import (
    DatePartProvider,
    CodeLabelProvider,
    MockLowUtilityProvider,
    MockAmbiguousProvider,
    MockSensitiveInferenceProvider,
)
from app.services.sdr.enrichment.enrichment_engine import SDREnrichmentEngine
from app.services.sdr.contracts.enrichment import EnrichmentDecisionType


from tests.sdr.test_sdr4_certification_corpus import _create_profile


def make_profiles(num_cols: int, dataset_id: str, sheet_id: str) -> list[SemanticColumnProfile]:
    profiles = []
    for i in range(num_cols):
        col_id = f"col_{i:03d}"
        if i % 5 == 0:
            role = SemanticColumnRole.TIME
            dtype = SemanticDtype.DATE
            name = f"date_{i}"
            ambig = ProfilingAmbiguityState.CLEAR
        elif i % 5 == 1:
            role = SemanticColumnRole.DIMENSION
            dtype = SemanticDtype.CATEGORICAL_CODE
            name = f"dept_code_{i}"
            ambig = ProfilingAmbiguityState.CLEAR
        elif i % 5 == 2:
            role = SemanticColumnRole.FREE_TEXT
            dtype = SemanticDtype.NATURAL_LANGUAGE_TEXT
            name = f"notes_{i}"
            ambig = ProfilingAmbiguityState.CLEAR
        elif i % 5 == 3:
            role = SemanticColumnRole.DIMENSION
            dtype = SemanticDtype.CATEGORICAL_CODE
            name = f"ambig_{i}"
            ambig = ProfilingAmbiguityState.AMBIGUOUS_TYPE
        else:
            role = SemanticColumnRole.IDENTIFIER
            dtype = SemanticDtype.IDENTIFIER_CODE
            name = f"id_{i}"
            ambig = ProfilingAmbiguityState.CLEAR

        p = _create_profile(
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            column_id=col_id,
            source_name=name,
            role=role,
            dtype=dtype,
            ambiguity=ambig,
        )
        profiles.append(p)
    return profiles


def run_benchmark():
    reg = EnrichmentProviderRegistry()
    reg.register_provider(DatePartProvider())
    reg.register_provider(CodeLabelProvider())
    reg.register_provider(MockLowUtilityProvider())
    reg.register_provider(MockAmbiguousProvider())
    reg.register_provider(MockSensitiveInferenceProvider())

    policy = EnrichmentPolicy(
        max_candidates_per_column=5,
        max_enrichments_per_column=3,
        max_enrichment_depth=2,
        max_total_enrichments_per_dataset=100,
        max_materialized_enrichments=20,
        min_utility_score=0.60,
        min_confidence=0.80,
    )
    engine = SDREnrichmentEngine(registry=reg, policy=policy)

    scenarios = [
        ("Small", 50, 10),
        ("Medium", 1000, 25),
        ("Large", 10000, 50),
    ]

    print("=" * 90)
    print("SDR-4 CONTROLLED ENRICHMENT BENCHMARK REPORT")
    print("=" * 90)

    for name, rows, cols in scenarios:
        tracemalloc.start()
        start_time = time.perf_counter()

        profiles = make_profiles(cols, f"ds_{name.lower()}", "sheet_main")
        result = engine.analyze_enrichments(
            dataset_id=f"ds_{name.lower()}",
            sheet_id="sheet_main",
            profiles=profiles,
            materialize_all=False,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        candidates_count = len(result.candidates)
        decisions = result.decisions
        hard_gate_rejections = len([d for d in decisions if not d.hard_gate_passed or d.decision == EnrichmentDecisionType.REJECT and "Hard gate" in d.rationale])
        utility_rejections = len([d for d in decisions if d.hard_gate_passed and d.decision in (EnrichmentDecisionType.REJECT, EnrichmentDecisionType.DEFER)])
        ambiguous_count = len([d for d in decisions if d.decision == EnrichmentDecisionType.AMBIGUOUS])
        accepted_count = len(result.validated_enrichments)

        print(f"Scenario: {name.upper()} ({rows} rows, {cols} columns)")
        print(f"  - Columns Profiled:        {cols}")
        print(f"  - Candidates Generated:    {candidates_count}")
        print(f"  - Hard Gate Rejections:    {hard_gate_rejections}")
        print(f"  - Utility Rejections/Defer:{utility_rejections}")
        print(f"  - Ambiguous Withheld:      {ambiguous_count}")
        print(f"  - Accepted Enrichments:    {accepted_count}")
        print(f"  - Execution Time:          {elapsed_ms:.2f} ms")
        print(f"  - Peak Memory:             {peak_mem / 1024:.2f} KB")
        print("-" * 90)


if __name__ == "__main__":
    run_benchmark()
