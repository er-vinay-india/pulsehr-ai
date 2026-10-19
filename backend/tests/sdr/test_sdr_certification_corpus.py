"""
HighView Semantic Data Refinery — Phase SDR-1
Certification Corpus Benchmark & Evaluation Suite
"""

import hashlib
import json
from pathlib import Path
import pytest

from app.services.ingestion_v2.contracts.semantics import SemanticColumnRole
from app.services.ingestion_v2.retrieval.namespaces import RetrievalNamespace
from app.services.sdr.artifacts.artifact_writer import SDRArtifactWriter
from app.services.sdr.contracts.policies import SDRPolicySuite
from app.services.sdr.decomposition.decomposition_engine import SDRDecompositionEngine
from app.services.sdr.profiling.column_profiler import SDRColumnProfiler
from app.services.sdr.retrieval.retrieval_adapter import SDRRetrievalAdapter
from tests.sdr.certification_corpus import CERTIFICATION_CORPUS

P0_EXPECTED_SHA = "1561d64eeae26f4d30926371740d6ca9dc41eb6ea7c537281763b7d5aabd9496"
P0_EXPECTED_SIZE = 70385664


def test_sdr1_certification_corpus_benchmark(tmp_path: Path):
    """
    Executes the full SDR-1 certification benchmark across 15 canonical column archetypes.
    Verifies:
    1. Zero high-confidence false classifications
    2. Zero high-confidence false decompositions
    3. 100% false-split protection
    4. Determinism of artifact fingerprints
    5. Pure compliance with frozen retrieval namespaces (RAW_SCHEMA and SEMANTIC only)
    6. Bit-identical P0 database isolation
    """
    profiler = SDRColumnProfiler()
    decomp_engine = SDRDecompositionEngine()
    policy_suite = SDRPolicySuite()

    # Track metrics
    total_columns = len(CERTIFICATION_CORPUS)
    high_confidence_false_classifications = 0
    high_confidence_false_decompositions = 0
    correct_abstentions = 0
    promoted_correct = 0

    all_profiles = []
    all_candidates = []

    for col in CERTIFICATION_CORPUS:
        prof = profiler.profile_column(
            dataset_id="ds_cert",
            sheet_id="sheet1",
            column_id=col.column_id,
            source_name=col.column_name,
            physical_dtype=col.physical_dtype,
            raw_values=col.raw_values,
        )
        all_profiles.append(prof)

        # Evaluate Semantic Classification
        if prof.confidence >= profiler.policy.promotion_threshold:
            # Promoted classification
            if prof.semantic_role == col.expected_semantic_role and prof.semantic_dtype == col.expected_semantic_dtype:
                promoted_correct += 1
            else:
                # High confidence wrong classification!
                high_confidence_false_classifications += 1
        else:
            # Abstention band
            if col.expected_semantic_role in (SemanticColumnRole.UNKNOWN, SemanticColumnRole.AMBIGUOUS):
                correct_abstentions += 1

        # Evaluate Decomposition Candidates
        candidates = decomp_engine.generate_candidates(prof, col.raw_values)
        all_candidates.extend(candidates)

        if col.is_false_split_target:
            # False-split target: candidates MUST be 0!
            if len(candidates) > 0:
                high_confidence_false_decompositions += 1
        elif col.should_be_composite:
            assert len(candidates) >= 1
            cand = candidates[0]
            assert cand.pattern_type == col.expected_pattern_type
            assert cand.is_destructive is False
        else:
            # Not a composite column
            if len(candidates) > 0 and candidates[0].confidence >= 0.80:
                high_confidence_false_decompositions += 1

    # Invariants Verification
    assert high_confidence_false_classifications == 0, (
        f"Expected 0 high-confidence false classifications, got {high_confidence_false_classifications}"
    )
    assert high_confidence_false_decompositions == 0, (
        f"Expected 0 high-confidence false decompositions, got {high_confidence_false_decompositions}"
    )

    # Retrieval Document Verification
    retrieval_docs = []
    for prof in all_profiles:
        raw_doc = SDRRetrievalAdapter.build_raw_schema_document(prof)
        sem_doc = SDRRetrievalAdapter.build_semantic_profile_document(prof)
        retrieval_docs.extend([raw_doc, sem_doc])
        assert raw_doc.namespace == RetrievalNamespace.RAW_SCHEMA
        assert sem_doc.namespace == RetrievalNamespace.SEMANTIC

    for cand in all_candidates:
        cand_doc = SDRRetrievalAdapter.build_decomposition_candidate_document(cand)
        retrieval_docs.append(cand_doc)
        assert cand_doc.namespace == RetrievalNamespace.SEMANTIC

    # Verify no documents leaked into RELATIONSHIP or ANALYTICAL
    forbidden_namespaces = {RetrievalNamespace.RELATIONSHIP, RetrievalNamespace.ANALYTICAL}
    for doc in retrieval_docs:
        assert doc.namespace not in forbidden_namespaces

    # Artifact Serialization & Determinism Verification
    writer = SDRArtifactWriter(base_data_dir=tmp_path)
    res1 = writer.write_artifacts(
        dataset_id="ds_cert",
        profiles=all_profiles,
        candidates=all_candidates,
        policy_suite=policy_suite,
    )
    res2 = writer.write_artifacts(
        dataset_id="ds_cert",
        profiles=all_profiles,
        candidates=all_candidates,
        policy_suite=policy_suite,
    )

    # Deterministic fingerprint match
    assert res1["manifest_fingerprint"] == res2["manifest_fingerprint"]

    # Verify files exist on disk
    manifest_p = Path(res1["profiling_manifest"])
    assert manifest_p.exists()
    manifest_data = json.loads(manifest_p.read_text(encoding="utf-8"))
    assert manifest_data["profiles_count"] == total_columns
    assert manifest_data["candidates_count"] == len(all_candidates)

    # P0 Verification
    p0_path = Path("backend/data/db/pulsehr.sqlite3")
    assert p0_path.exists()
    p0_bytes = p0_path.read_bytes()
    p0_sha = hashlib.sha256(p0_bytes).hexdigest()
    assert len(p0_bytes) == P0_EXPECTED_SIZE
    assert p0_sha == P0_EXPECTED_SHA
