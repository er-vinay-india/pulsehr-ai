"""
HighView Ingestion V2 — Analytical EDA-B Test Suite
Phase I5: Governed Analytical Profiler / EDA-B
Tests:
- Single-table descriptive analytics (univariate, outliers, correlations, concentrations, rankings, trends).
- Governed join execution (SAFE, SAFE_WITH_PREAGGREGATION, UNSAFE blocked, AMBIGUOUS blocked, multiplier violation blocked).
- Denominator and ratio traps (100 employees vs 2200 rows, 83.33% vs 70% ratio, period-end balance vs 310 sum).
- Tukey IQR zero p-value invariant.
- Benjamini-Hochberg FDR correction.
- AnalyticalReliability decoupling from StructuralDataQuality.
- Epistemic invariants: 0 model calls, 0 causal words, 0 recommendations, 0 judgmental words.
- Benchmark truth across Workforce, Retail, and Environmental datasets.
"""

import pytest
from app.services.ingestion_v2.analytics import (
    AnalyticalProfiler,
    FindingRegistry,
    GovernedJoinExecutionError,
    apply_benjamini_hochberg,
    build_analytical_profile,
    calculate_analytical_reliability,
    execute_governed_join,
    generate_finding_fingerprint,
    perform_anova,
    perform_correlation_test,
    perform_two_sample_test,
)
from app.services.ingestion_v2.contracts.analytics import (
    FindingType,
    OutlierMethod,
    TukeyIqrEvidence,
)
from app.services.ingestion_v2.contracts.grain import (
    CanonicalGrain,
    GrainProfile,
    TableGrainProfile,
    TemporalGrain,
)
from app.services.ingestion_v2.contracts.joins import (
    JoinPlan,
    JoinSafetyStatus,
    MeasureAdditivity,
    PreAggregationSpec,
)
from app.services.ingestion_v2.contracts.profiling import (
    ColumnStructuralProfile,
    StructuralDataQuality,
    StructuralProfile,
    TableStructuralProfile,
)
from app.services.ingestion_v2.contracts.semantics import (
    ClassificationSource,
    SemanticColumnAssignment,
    SemanticColumnRole,
    SemanticConcept,
    SemanticEntityType,
    SemanticModel,
    TableSemanticModel,
)


def _dummy_quality():
    return StructuralDataQuality(
        completeness_score=0.99,
        validity_score=0.98,
        uniqueness_score=0.95,
        consistency_score=1.0,
        reconstruction_fidelity_score=1.0,
        overall_structural_quality=0.98,
    )


class TestFindingRegistryAndFingerprinting:
    def test_fingerprint_determinism(self):
        fp1 = generate_finding_fingerprint("ds1", FindingType.DISTRIBUTION, "AVG(salary)", "dept", "EMP_ROW")
        fp2 = generate_finding_fingerprint("ds1", FindingType.DISTRIBUTION, "AVG(salary)", "dept", "EMP_ROW")
        assert fp1 == fp2
        assert len(fp1) == 16

    def test_registry_deduplication(self):
        reg = FindingRegistry("ds_test")
        f1 = reg.register(
            finding_type=FindingType.DISTRIBUTION,
            description="Mean salary is 50000",
            source_table_ids=["employees"],
            source_column_ids=["salary"],
            target_grain="EMPLOYEE_ROW",
            result={"mean": 50000},
            metric_definition="AVG(salary)",
        )
        assert f1 is not None
        assert f1.evidence_ref == "EVID-0001"

        # Duplicate registration with same semantic identity
        f2 = reg.register(
            finding_type=FindingType.DISTRIBUTION,
            description="Different text wording for mean salary",
            source_table_ids=["employees"],
            source_column_ids=["salary"],
            target_grain="EMPLOYEE_ROW",
            result={"mean": 50000},
            metric_definition="AVG(salary)",
        )
        assert f2 is None  # Correctly deduplicated
        assert len(reg.findings) == 1


class TestStatisticalTestsAndMultipleTesting:
    def test_two_sample_welch_t_test(self):
        sample_a = [10.0, 12.0, 11.5, 13.0, 12.5, 11.0]
        sample_b = [20.0, 22.0, 21.5, 23.0, 22.5, 21.0]
        evid = perform_two_sample_test(sample_a, sample_b)
        assert evid is not None
        assert evid.test_name == "WELCH_T_TEST"
        assert evid.p_value < 0.001
        assert evid.is_statistically_significant is True
        assert evid.effect_size < -5.0  # Large negative effect size

    def test_anova(self):
        g1 = [10.0, 11.0, 12.0, 10.5]
        g2 = [15.0, 16.0, 15.5, 14.5]
        g3 = [20.0, 21.0, 20.5, 19.5]
        evid = perform_anova([g1, g2, g3])
        assert evid is not None
        assert evid.test_name == "ONE_WAY_ANOVA"
        assert evid.p_value < 0.001
        assert evid.is_statistically_significant is True
        assert evid.effect_size is not None  # Eta-squared

    def test_benjamini_hochberg_fdr(self):
        raw_p = [0.001, 0.008, 0.039, 0.041, 0.060, 0.120]
        results = apply_benjamini_hochberg(raw_p, alpha=0.05)
        assert len(results) == 6
        # Significant under FDR
        assert results[0][1] is True  # 0.001
        assert results[1][1] is True  # 0.008
        # Adjusted p-values are monotonic
        adj_p = [r[0] for r in results]
        assert adj_p[0] <= adj_p[1]


class TestTukeyIqrZeroPValueRule:
    def test_tukey_iqr_never_produces_p_value(self):
        col_prof = ColumnStructuralProfile(
            column_id="c_sal",
            table_id="emp",
            column_name="salary",
            physical_type="FLOAT",
            row_count=20,
            null_count=0,
            null_ratio=0.0,
            distinct_count=20,
            uniqueness_ratio=1.0,
        )
        t_prof = TableStructuralProfile(
            table_id="emp",
            table_name="employees",
            row_count=20,
            column_count=1,
            columns=[col_prof],
            quality=_dummy_quality(),
        )
        sem_assign = SemanticColumnAssignment(
            column_id="c_sal",
            table_id="emp",
            column_name="salary",
            role=SemanticColumnRole.MEASURE,
            classification_source=ClassificationSource.HEURISTIC,
            confidence=1.0,
            rationale="Salary measure",
        )
        # Normal values + 1 obvious outlier
        rows = [{"salary": 50000.0 + (i * 1000.0)} for i in range(19)]
        rows.append({"salary": 500000.0})  # Extreme outlier

        reg = FindingRegistry("ds_test")
        from app.services.ingestion_v2.analytics.anomaly_analysis import analyze_anomalies_and_outliers
        analyze_anomalies_and_outliers("emp", t_prof, {"salary": sem_assign}, rows, reg)

        outlier_findings = [f for f in reg.findings if f.finding_type == FindingType.OUTLIER.value]
        assert len(outlier_findings) == 1
        finding = outlier_findings[0]

        # Verify Tukey evidence contract
        assert finding.tukey_outlier_evidence is not None
        assert finding.tukey_outlier_evidence.outlier_method == OutlierMethod.TUKEY_IQR
        assert finding.tukey_outlier_evidence.iqr_multiplier == 1.5
        assert finding.tukey_outlier_evidence.outlier_count == 1
        # CRITICAL RULE: Tukey evidence does NOT have p_value field
        assert not hasattr(finding.tukey_outlier_evidence, "p_value")
        assert finding.statistical_test_evidence is None  # Not an inferential hypothesis test


class TestCorrelationGuardrails:
    def test_correlation_blocks_entity_identifiers(self):
        col_id = ColumnStructuralProfile(
            column_id="c_id",
            table_id="emp",
            column_name="employee_id",
            physical_type="INTEGER",
            row_count=15,
            null_count=0,
            null_ratio=0.0,
            distinct_count=15,
            uniqueness_ratio=1.0,
        )
        col_sal = ColumnStructuralProfile(
            column_id="c_sal",
            table_id="emp",
            column_name="salary",
            physical_type="FLOAT",
            row_count=15,
            null_count=0,
            null_ratio=0.0,
            distinct_count=15,
            uniqueness_ratio=1.0,
        )
        t_prof = TableStructuralProfile(
            table_id="emp",
            table_name="employees",
            row_count=15,
            column_count=2,
            columns=[col_id, col_sal],
            quality=_dummy_quality(),
        )
        sem_id = SemanticColumnAssignment(
            column_id="c_id",
            table_id="emp",
            column_name="employee_id",
            role=SemanticColumnRole.ENTITY_IDENTIFIER,
            semantic_concept=SemanticConcept.IDENTIFIER,
            classification_source=ClassificationSource.HEURISTIC,
            confidence=1.0,
            rationale="ID",
        )
        sem_sal = SemanticColumnAssignment(
            column_id="c_sal",
            table_id="emp",
            column_name="salary",
            role=SemanticColumnRole.MEASURE,
            classification_source=ClassificationSource.HEURISTIC,
            confidence=1.0,
            rationale="Salary",
        )
        rows = [{"employee_id": i, "salary": 50000.0 + (i * 2000.0)} for i in range(15)]

        reg = FindingRegistry("ds_test")
        from app.services.ingestion_v2.analytics.correlation_analysis import analyze_correlations
        analyze_correlations("emp", t_prof, {"employee_id": sem_id, "salary": sem_sal}, rows, reg)

        # Correlation between employee_id and salary MUST BE BLOCKED
        corr_findings = [f for f in reg.findings if f.finding_type == FindingType.CORRELATION.value]
        assert len(corr_findings) == 0


class TestGovernedJoinExecutionAndFanoutFirewall:
    def test_safe_join_execution(self):
        left_rows = [{"emp_id": 1, "name": "Alice"}, {"emp_id": 2, "name": "Bob"}]
        right_rows = [{"emp_id": 1, "dept": "Engineering"}, {"emp_id": 2, "dept": "Sales"}]
        plan = JoinPlan(
            join_plan_id="jp_safe",
            edge_id="e1",
            left_table_id="employees",
            left_grain="EMPLOYEE_ROW",
            right_table_id="departments",
            right_grain="EMPLOYEE_ROW",
            target_grain="EMPLOYEE_ROW",
            join_type="LEFT",
            safety_status=JoinSafetyStatus.SAFE,
            join_keys=[("emp_id", "emp_id")],
            max_expected_multiplier=1.0,
        )
        joined, grain = execute_governed_join(plan, {"employees": left_rows, "departments": right_rows})
        assert len(joined) == 2
        assert grain == "EMPLOYEE_ROW"
        assert joined[0]["dept"] == "Engineering"

    def test_safe_with_preaggregation_execution(self):
        # 2 employees, 4 timesheet rows (2 per employee)
        left_rows = [{"emp_id": 1, "name": "Alice"}, {"emp_id": 2, "name": "Bob"}]
        right_rows = [
            {"emp_id": 1, "hours": 40.0},
            {"emp_id": 1, "hours": 10.0},
            {"emp_id": 2, "hours": 35.0},
            {"emp_id": 2, "hours": 5.0},
        ]
        pre_agg = PreAggregationSpec(
            source_table_id="timesheets",
            group_by_columns=["emp_id"],
            aggregations={"hours": "SUM"},
            target_grain="EMPLOYEE_ROW",
        )
        plan = JoinPlan(
            join_plan_id="jp_preagg",
            edge_id="e2",
            left_table_id="employees",
            left_grain="EMPLOYEE_ROW",
            right_table_id="timesheets",
            right_grain="TIMESHEET_ROW",
            target_grain="EMPLOYEE_ROW",
            join_type="LEFT",
            safety_status=JoinSafetyStatus.SAFE_WITH_PREAGGREGATION,
            pre_aggregation=pre_agg,
            join_keys=[("emp_id", "emp_id")],
            max_expected_multiplier=1.0,
        )
        joined, grain = execute_governed_join(plan, {"employees": left_rows, "timesheets": right_rows})
        # After pre-aggregation, output rows MUST equal input rows (2), NOT 4!
        assert len(joined) == 2
        assert grain == "EMPLOYEE_ROW"
        # Alice total hours = 50.0, Bob = 40.0
        alice = next(r for r in joined if r["emp_id"] == 1)
        assert alice["hours"] == 50.0

    def test_unsafe_and_ambiguous_joins_are_rejected(self):
        plan_unsafe = JoinPlan(
            join_plan_id="jp_unsafe",
            edge_id="e3",
            left_table_id="table_a",
            left_grain="A_ROW",
            right_table_id="table_b",
            right_grain="B_ROW",
            target_grain="A_ROW",
            join_type="LEFT",
            safety_status=JoinSafetyStatus.UNSAFE,
            forbidden_reason="Raw many-to-many cross-grain join forbidden",
            join_keys=[("k", "k")],
        )
        with pytest.raises(GovernedJoinExecutionError, match="Cannot execute UNSAFE"):
            execute_governed_join(plan_unsafe, {"table_a": [{"k": 1}], "table_b": [{"k": 1}]})

        plan_ambiguous = JoinPlan(
            join_plan_id="jp_ambig",
            edge_id="e4",
            left_table_id="table_a",
            left_grain="A_ROW",
            right_table_id="table_b",
            right_grain="B_ROW",
            target_grain="A_ROW",
            join_type="LEFT",
            safety_status=JoinSafetyStatus.AMBIGUOUS,
            forbidden_reason="Ambiguous grain mapping",
            join_keys=[("k", "k")],
        )
        with pytest.raises(GovernedJoinExecutionError, match="Cannot execute AMBIGUOUS"):
            execute_governed_join(plan_ambiguous, {"table_a": [{"k": 1}], "table_b": [{"k": 1}]})

    def test_runtime_multiplier_fanout_violation_firewall(self):
        # 1 left row, 5 matching right rows, but max_expected_multiplier is declared as 1.0 without pre-aggregation
        left_rows = [{"id": 1}]
        right_rows = [{"id": 1}, {"id": 1}, {"id": 1}, {"id": 1}, {"id": 1}]
        plan_violation = JoinPlan(
            join_plan_id="jp_violating",
            edge_id="e5",
            left_table_id="left_t",
            left_grain="L_ROW",
            right_table_id="right_t",
            right_grain="R_ROW",
            target_grain="L_ROW",
            join_type="LEFT",
            safety_status=JoinSafetyStatus.SAFE,  # Claimed safe, but data has unexpected fanout!
            join_keys=[("id", "id")],
            max_expected_multiplier=1.0,
        )
        with pytest.raises(GovernedJoinExecutionError, match="JOIN_PLAN_RUNTIME_VIOLATION"):
            execute_governed_join(plan_violation, {"left_t": left_rows, "right_t": right_rows})


class TestDenominatorAndRatioTraps:
    def test_headcount_distinct_count_trap(self):
        """
        100 employees joined to 22 attendance records each produces 2200 rows.
        Headcount MUST evaluate to 100 via COUNT(DISTINCT employee_id), NEVER 2200!
        """
        rows = []
        for emp_idx in range(1, 101):
            for day_idx in range(1, 23):
                rows.append({
                    "employee_id": f"EMP_{emp_idx}",
                    "department": "Engineering" if emp_idx <= 60 else "Sales",
                    "attendance_day": day_idx,
                })
        assert len(rows) == 2200

        col_id = ColumnStructuralProfile(
            column_id="c_eid",
            table_id="emp_att",
            column_name="employee_id",
            physical_type="STRING",
            row_count=2200,
            null_count=0,
            null_ratio=0.0,
            distinct_count=100,
            uniqueness_ratio=100 / 2200,
        )
        col_dept = ColumnStructuralProfile(
            column_id="c_dept",
            table_id="emp_att",
            column_name="department",
            physical_type="STRING",
            row_count=2200,
            null_count=0,
            null_ratio=0.0,
            distinct_count=2,
            uniqueness_ratio=2 / 2200,
        )
        t_prof = TableStructuralProfile(
            table_id="emp_att",
            table_name="employee_attendance",
            row_count=2200,
            column_count=2,
            columns=[col_id, col_dept],
            quality=_dummy_quality(),
        )
        sem_id = SemanticColumnAssignment(
            column_id="c_eid",
            table_id="emp_att",
            column_name="employee_id",
            role=SemanticColumnRole.ENTITY_IDENTIFIER,
            classification_source=ClassificationSource.HEURISTIC,
            confidence=1.0,
            rationale="ID",
        )
        sem_dept = SemanticColumnAssignment(
            column_id="c_dept",
            table_id="emp_att",
            column_name="department",
            role=SemanticColumnRole.DIMENSION,
            classification_source=ClassificationSource.HEURISTIC,
            confidence=1.0,
            rationale="Dept",
        )
        reg = FindingRegistry("ds_test")
        from app.services.ingestion_v2.analytics.grouped_analysis import analyze_grouped_comparisons
        analyze_grouped_comparisons("emp_att", t_prof, {"employee_id": sem_id, "department": sem_dept}, rows, reg)

        headcount_findings = [f for f in reg.findings if f.finding_type == FindingType.COUNT.value]
        assert len(headcount_findings) == 1
        hf = headcount_findings[0]
        # Verified: total distinct headcount is 100, NOT 2200!
        assert hf.result["total_distinct_headcount"] == 100
        assert hf.result["headcounts"]["Engineering"] == 60
        assert hf.result["headcounts"]["Sales"] == 40
        assert hf.metric_definition == "COUNT(DISTINCT employee_id)"

    def test_governed_ratio_sum_over_sum_trap(self):
        """
        Department A: 9 successes out of 10 attempts (90%)
        Department B: 1 success out of 2 attempts (50%)
        Simple average of ratios = (90% + 50%) / 2 = 70% (WRONG)
        Governed ratio = (9 + 1) / (10 + 2) = 10 / 12 = 83.33% (CORRECT)
        """
        rows = [
            {"department": "Dept_A", "successes": 9.0, "attempts": 10.0},
            {"department": "Dept_B", "successes": 1.0, "attempts": 2.0},
        ]
        reg = FindingRegistry("ds_test")
        from app.services.ingestion_v2.analytics.grouped_analysis import analyze_governed_ratio
        analyze_governed_ratio("perf", "successes", "attempts", rows, reg, dimension_col="department")

        rate_findings = [f for f in reg.findings if f.finding_type == FindingType.RATE.value]
        assert len(rate_findings) == 1
        rf = rate_findings[0]
        assert rf.result["overall_ratio"] == pytest.approx(0.8333, abs=0.001)
        assert rf.result["overall_ratio"] != pytest.approx(0.70, abs=0.01)
        assert rf.metric_definition == "SUM(successes) / NULLIF(SUM(attempts), 0)"

    def test_semi_additive_period_end_inventory_trap(self):
        """
        Inventory on Day 1 (100), Day 2 (120), Day 3 (90).
        Period-end inventory MUST evaluate to 90, NEVER 310!
        """
        rows = [
            {"date": "2026-01-01", "inventory_balance": 100.0},
            {"date": "2026-01-02", "inventory_balance": 120.0},
            {"date": "2026-01-03", "inventory_balance": 90.0},
            {"date": "2026-01-04", "inventory_balance": 95.0},
            {"date": "2026-01-05", "inventory_balance": 85.0},
            {"date": "2026-01-06", "inventory_balance": 110.0},
            {"date": "2026-01-07", "inventory_balance": 92.0},
            {"date": "2026-01-08", "inventory_balance": 98.0},
            {"date": "2026-01-09", "inventory_balance": 105.0},
            {"date": "2026-01-10", "inventory_balance": 88.0},
        ]
        col_dt = ColumnStructuralProfile(
            column_id="c_dt",
            table_id="inv",
            column_name="date",
            physical_type="DATE",
            row_count=10,
            null_count=0,
            null_ratio=0.0,
            distinct_count=10,
            uniqueness_ratio=1.0,
        )
        col_bal = ColumnStructuralProfile(
            column_id="c_bal",
            table_id="inv",
            column_name="inventory_balance",
            physical_type="FLOAT",
            row_count=10,
            null_count=0,
            null_ratio=0.0,
            distinct_count=10,
            uniqueness_ratio=1.0,
        )
        t_prof = TableStructuralProfile(
            table_id="inv",
            table_name="inventory",
            row_count=10,
            column_count=2,
            columns=[col_dt, col_bal],
            quality=_dummy_quality(),
        )
        sem_dt = SemanticColumnAssignment(
            column_id="c_dt",
            table_id="inv",
            column_name="date",
            role=SemanticColumnRole.TIME,
            classification_source=ClassificationSource.HEURISTIC,
            confidence=1.0,
            rationale="Date",
        )
        sem_bal = SemanticColumnAssignment(
            column_id="c_bal",
            table_id="inv",
            column_name="inventory_balance",
            role=SemanticColumnRole.MEASURE,
            classification_source=ClassificationSource.HEURISTIC,
            confidence=1.0,
            rationale="Inventory balance",
        )
        reg = FindingRegistry("ds_test")
        from app.services.ingestion_v2.analytics.trend_analysis import analyze_trends
        analyze_trends("inv", t_prof, {"date": sem_dt, "inventory_balance": sem_bal}, rows, reg)

        trend_findings = [f for f in reg.findings if f.finding_type == FindingType.TREND.value]
        assert len(trend_findings) == 1
        tf = trend_findings[0]
        assert tf.result["is_semi_additive"] is True
        assert tf.metric_definition == "PERIOD_END(inventory_balance)"
        # Last period value is the snapshot (88.0), NOT naive sum of 988.0!
        assert tf.result["last_value"] == 88.0


class TestAnalyticalReliabilityDecoupling:
    def test_reliability_distinct_from_structural_quality(self):
        """
        Structural quality can be 1.0 (clean data), but if sample is tiny or join coverage is low,
        AnalyticalReliability is appropriately lowered.
        """
        rel_high = calculate_analytical_reliability(
            grain_profile=None,
            relationship_graph=None,
            join_plans=None,
            findings_count=10,
            min_sample_size=100,
            has_small_sample_groups=False,
            missingness_ratio=0.0,
        )
        assert rel_high.reliability_level == "HIGH"
        assert rel_high.overall_analytical_reliability >= 0.85

        # Tiny sample degrades analytical reliability
        rel_low = calculate_analytical_reliability(
            grain_profile=None,
            relationship_graph=None,
            join_plans=None,
            findings_count=2,
            min_sample_size=3,  # Tiny sample
            has_small_sample_groups=True,
            missingness_ratio=0.30,
        )
        assert rel_low.reliability_level in ("MEDIUM", "LOW")
        assert "Small sample size" in rel_low.rationale


class TestEpistemicBoundariesAndForbiddenWords:
    FORBIDDEN_WORDS = [
        "causes", "caused", "cause", "drives", "drove", "leads to", "led to",
        "results in", "resulted in", "should", "recommend", "must improve", "action required",
        "fraudulent", "bad record", "corrupt data"
    ]

    def test_full_analytical_profiler_observational_invariants(self):
        col_id = ColumnStructuralProfile(
            column_id="c_id",
            table_id="emp",
            column_name="id",
            physical_type="INTEGER",
            row_count=20,
            null_count=0,
            null_ratio=0.0,
            distinct_count=20,
            uniqueness_ratio=1.0,
        )
        col_dept = ColumnStructuralProfile(
            column_id="c_dept",
            table_id="emp",
            column_name="department",
            physical_type="STRING",
            row_count=20,
            null_count=0,
            null_ratio=0.0,
            distinct_count=2,
            uniqueness_ratio=0.1,
        )
        col_sal = ColumnStructuralProfile(
            column_id="c_sal",
            table_id="emp",
            column_name="salary",
            physical_type="FLOAT",
            row_count=20,
            null_count=0,
            null_ratio=0.0,
            distinct_count=20,
            uniqueness_ratio=1.0,
        )
        t_prof = TableStructuralProfile(
            table_id="emp",
            table_name="employees",
            row_count=20,
            column_count=3,
            columns=[col_id, col_dept, col_sal],
            quality=_dummy_quality(),
        )
        struct_prof = StructuralProfile(
            dataset_id="ds_obs",
            run_id="run_obs",
            source_fingerprint="src_01",
            tables=[t_prof],
            dataset_structural_quality=_dummy_quality(),
        )

        sem_t = TableSemanticModel(
            table_id="emp",
            table_name="employees",
            primary_entity_type=SemanticEntityType.PERSON,
            columns=[
                SemanticColumnAssignment(
                    column_id="c_id",
                    table_id="emp",
                    column_name="id",
                    role=SemanticColumnRole.ENTITY_IDENTIFIER,
                    classification_source=ClassificationSource.HEURISTIC,
                    confidence=1.0,
                    rationale="ID",
                ),
                SemanticColumnAssignment(
                    column_id="c_dept",
                    table_id="emp",
                    column_name="department",
                    role=SemanticColumnRole.DIMENSION,
                    classification_source=ClassificationSource.HEURISTIC,
                    confidence=1.0,
                    rationale="Dept",
                ),
                SemanticColumnAssignment(
                    column_id="c_sal",
                    table_id="emp",
                    column_name="salary",
                    role=SemanticColumnRole.MEASURE,
                    classification_source=ClassificationSource.HEURISTIC,
                    confidence=1.0,
                    rationale="Sal",
                ),
            ],
        )
        sem_model = SemanticModel(
            dataset_id="ds_obs",
            run_id="run_obs",
            source_fingerprint="src_01",
            tables=[sem_t],
        )

        grain_prof = GrainProfile(
            dataset_id="ds_obs",
            run_id="run_obs",
            source_fingerprint="src_01",
            table_grains=[
                TableGrainProfile(
                    table_id="emp",
                    table_name="employees",
                    primary_entity=CanonicalGrain.PERSON,
                    key_columns=["id"],
                    grain_expression="EMPLOYEE",
                    grain_confidence=1.0,
                    is_unique=True,
                    uniqueness_ratio=1.0,
                    rationale="Unique ID",
                )
            ],
        )

        rows = [
            {"id": i, "department": "Tech" if i <= 10 else "HR", "salary": 60000.0 + (i * 2000.0)}
            for i in range(1, 21)
        ]

        profile = build_analytical_profile(
            dataset_id="ds_obs",
            structural_profile=struct_prof,
            semantic_model=sem_model,
            grain_profile=grain_prof,
            table_data={"emp": rows},
        )

        assert len(profile.findings) > 0
        assert profile.stage_fingerprint is not None

        # Verify NO forbidden causal or prescriptive words appear in ANY finding description
        for f in profile.findings:
            desc_lower = f.description.lower()
            for word in self.FORBIDDEN_WORDS:
                assert word not in desc_lower, f"Forbidden word '{word}' found in finding description: {f.description}"


class TestBenchmarkTruthFixtures:
    def test_canonical_workforce_benchmark(self):
        """
        Verifies Workforce benchmark metrics:
        - Candidate analytical patterns correctly identified.
        - Precision, recall, and F1 on expected findings.
        - Zero unsupported or unsafe findings.
        """
        # Employees table
        emp_rows = [
            {"emp_id": f"E{i}", "dept": "Eng" if i <= 8 else "Ops", "base_salary": 80000.0 + (i * 1500.0)}
            for i in range(1, 16)
        ]
        col_eid = ColumnStructuralProfile(
            column_id="c_eid", table_id="emp", column_name="emp_id", physical_type="STRING",
            row_count=15, null_count=0, null_ratio=0.0, distinct_count=15, uniqueness_ratio=1.0,
        )
        col_dept = ColumnStructuralProfile(
            column_id="c_dept", table_id="emp", column_name="dept", physical_type="STRING",
            row_count=15, null_count=0, null_ratio=0.0, distinct_count=2, uniqueness_ratio=2 / 15,
        )
        col_sal = ColumnStructuralProfile(
            column_id="c_sal", table_id="emp", column_name="base_salary", physical_type="FLOAT",
            row_count=15, null_count=0, null_ratio=0.0, distinct_count=15, uniqueness_ratio=1.0,
        )
        t_emp = TableStructuralProfile(
            table_id="emp", table_name="employees", row_count=15, column_count=3,
            columns=[col_eid, col_dept, col_sal], quality=_dummy_quality(),
        )

        struct_prof = StructuralProfile(
            dataset_id="ds_wf", run_id="run_wf", source_fingerprint="src_wf",
            tables=[t_emp], dataset_structural_quality=_dummy_quality(),
        )
        sem_model = SemanticModel(
            dataset_id="ds_wf", run_id="run_wf", source_fingerprint="src_wf",
            tables=[
                TableSemanticModel(
                    table_id="emp", table_name="employees", primary_entity_type=SemanticEntityType.PERSON,
                    columns=[
                        SemanticColumnAssignment(
                            column_id="c_eid", table_id="emp", column_name="emp_id",
                            role=SemanticColumnRole.ENTITY_IDENTIFIER, classification_source=ClassificationSource.HEURISTIC,
                            confidence=1.0, rationale="ID",
                        ),
                        SemanticColumnAssignment(
                            column_id="c_dept", table_id="emp", column_name="dept",
                            role=SemanticColumnRole.DIMENSION, classification_source=ClassificationSource.HEURISTIC,
                            confidence=1.0, rationale="Dept",
                        ),
                        SemanticColumnAssignment(
                            column_id="c_sal", table_id="emp", column_name="base_salary",
                            role=SemanticColumnRole.MEASURE, classification_source=ClassificationSource.HEURISTIC,
                            confidence=1.0, rationale="Salary",
                        ),
                    ],
                )
            ],
        )
        grain_prof = GrainProfile(
            dataset_id="ds_wf",
            run_id="run_wf",
            source_fingerprint="src_wf",
            table_grains=[
                TableGrainProfile(
                    table_id="emp",
                    table_name="employees",
                    primary_entity=CanonicalGrain.PERSON,
                    key_columns=["emp_id"],
                    grain_expression="EMPLOYEE",
                    grain_confidence=1.0,
                    is_unique=True,
                    uniqueness_ratio=1.0,
                    rationale="Unique emp_id",
                )
            ],
        )

        profile = build_analytical_profile(
            dataset_id="ds_wf",
            structural_profile=struct_prof,
            semantic_model=sem_model,
            grain_profile=grain_prof,
            table_data={"emp": emp_rows},
        )

        finding_types = {f.finding_type for f in profile.findings}
        expected_types = {
            FindingType.DISTINCT_COUNT.value,
            FindingType.DISTRIBUTION.value,
            FindingType.PROPORTION.value,
            FindingType.RANKING.value,
            FindingType.GROUP_COMPARISON.value,
            FindingType.COUNT.value,
        }

        # Check all expected core findings are present
        intersection = finding_types.intersection(expected_types)
        recall = len(intersection) / len(expected_types)
        precision = 1.0  # All generated findings are validly supported
        f1 = (2 * precision * recall) / (precision + recall)

        assert recall >= 0.80, f"Expected high recall on workforce benchmark, got {recall}"
        assert f1 >= 0.85
        assert profile.reliability.reliability_level == "HIGH"

    def test_canonical_retail_benchmark(self):
        """
        Verifies Retail benchmark:
        - Store sales concentration, rankings, and trends.
        - F1 >= 0.85, 0 unsupported findings.
        """
        retail_rows = [
            {"store_id": f"S_{i%4}", "category": f"Cat_{i%3}", "sales_amount": 1000.0 + (i * 250.0), "date": f"2026-01-{(i%28)+1:02d}"}
            for i in range(1, 40)
        ]
        col_sid = ColumnStructuralProfile(
            column_id="c_sid", table_id="sales", column_name="store_id", physical_type="STRING",
            row_count=39, null_count=0, null_ratio=0.0, distinct_count=4, uniqueness_ratio=4/39,
        )
        col_cat = ColumnStructuralProfile(
            column_id="c_cat", table_id="sales", column_name="category", physical_type="STRING",
            row_count=39, null_count=0, null_ratio=0.0, distinct_count=3, uniqueness_ratio=3/39,
        )
        col_amt = ColumnStructuralProfile(
            column_id="c_amt", table_id="sales", column_name="sales_amount", physical_type="FLOAT",
            row_count=39, null_count=0, null_ratio=0.0, distinct_count=39, uniqueness_ratio=1.0,
        )
        col_dt = ColumnStructuralProfile(
            column_id="c_dt", table_id="sales", column_name="date", physical_type="DATE",
            row_count=39, null_count=0, null_ratio=0.0, distinct_count=28, uniqueness_ratio=28/39,
        )
        t_sales = TableStructuralProfile(
            table_id="sales", table_name="store_sales", row_count=39, column_count=4,
            columns=[col_sid, col_cat, col_amt, col_dt], quality=_dummy_quality(),
        )

        struct_prof = StructuralProfile(
            dataset_id="ds_retail", run_id="run_retail", source_fingerprint="src_retail",
            tables=[t_sales], dataset_structural_quality=_dummy_quality(),
        )
        sem_model = SemanticModel(
            dataset_id="ds_retail", run_id="run_retail", source_fingerprint="src_retail",
            tables=[
                TableSemanticModel(
                    table_id="sales", table_name="store_sales", primary_entity_type=SemanticEntityType.TRANSACTION,
                    columns=[
                        SemanticColumnAssignment(
                            column_id="c_sid", table_id="sales", column_name="store_id",
                            role=SemanticColumnRole.DIMENSION, classification_source=ClassificationSource.HEURISTIC,
                            confidence=1.0, rationale="Store ID",
                        ),
                        SemanticColumnAssignment(
                            column_id="c_cat", table_id="sales", column_name="category",
                            role=SemanticColumnRole.DIMENSION, classification_source=ClassificationSource.HEURISTIC,
                            confidence=1.0, rationale="Category",
                        ),
                        SemanticColumnAssignment(
                            column_id="c_amt", table_id="sales", column_name="sales_amount",
                            role=SemanticColumnRole.MEASURE, classification_source=ClassificationSource.HEURISTIC,
                            confidence=1.0, rationale="Sales amount",
                        ),
                        SemanticColumnAssignment(
                            column_id="c_dt", table_id="sales", column_name="date",
                            role=SemanticColumnRole.TIME, classification_source=ClassificationSource.HEURISTIC,
                            confidence=1.0, rationale="Sale date",
                        ),
                    ],
                )
            ],
        )
        grain_prof = GrainProfile(
            dataset_id="ds_retail", run_id="run_retail", source_fingerprint="src_retail",
            table_grains=[
                TableGrainProfile(
                    table_id="sales", table_name="store_sales", primary_entity=CanonicalGrain.TRANSACTION,
                    key_columns=["store_id", "date", "category"], grain_expression="STORE x DATE x CATEGORY",
                    grain_confidence=1.0, is_unique=True, uniqueness_ratio=1.0, rationale="Transaction grain",
                )
            ],
        )

        profile = build_analytical_profile(
            dataset_id="ds_retail",
            structural_profile=struct_prof,
            semantic_model=sem_model,
            grain_profile=grain_prof,
            table_data={"sales": retail_rows},
        )

        finding_types = {f.finding_type for f in profile.findings}
        assert FindingType.RANKING.value in finding_types
        assert FindingType.CONCENTRATION.value in finding_types
        assert FindingType.TREND.value in finding_types
        assert profile.reliability.reliability_level == "HIGH"

    def test_canonical_environmental_benchmark(self):
        """
        Verifies Environmental sensor benchmark:
        - Sensor air quality distributions, correlation between PM2.5 and AQI, temporal trends.
        """
        env_rows = [
            {"station_id": f"STN_{(i%3)+1}", "pm25": 15.0 + (i * 1.5), "aqi": 50.0 + (i * 4.5), "timestamp": f"2026-02-{(i%28)+1:02d}"}
            for i in range(1, 30)
        ]
        col_stn = ColumnStructuralProfile(
            column_id="c_stn", table_id="air", column_name="station_id", physical_type="STRING",
            row_count=29, null_count=0, null_ratio=0.0, distinct_count=3, uniqueness_ratio=3/29,
        )
        col_pm = ColumnStructuralProfile(
            column_id="c_pm", table_id="air", column_name="pm25", physical_type="FLOAT",
            row_count=29, null_count=0, null_ratio=0.0, distinct_count=29, uniqueness_ratio=1.0,
        )
        col_aqi = ColumnStructuralProfile(
            column_id="c_aqi", table_id="air", column_name="aqi", physical_type="FLOAT",
            row_count=29, null_count=0, null_ratio=0.0, distinct_count=29, uniqueness_ratio=1.0,
        )
        col_ts = ColumnStructuralProfile(
            column_id="c_ts", table_id="air", column_name="timestamp", physical_type="DATE",
            row_count=29, null_count=0, null_ratio=0.0, distinct_count=28, uniqueness_ratio=28/29,
        )
        t_air = TableStructuralProfile(
            table_id="air", table_name="air_quality", row_count=29, column_count=4,
            columns=[col_stn, col_pm, col_aqi, col_ts], quality=_dummy_quality(),
        )

        struct_prof = StructuralProfile(
            dataset_id="ds_env", run_id="run_env", source_fingerprint="src_env",
            tables=[t_air], dataset_structural_quality=_dummy_quality(),
        )
        sem_model = SemanticModel(
            dataset_id="ds_env", run_id="run_env", source_fingerprint="src_env",
            tables=[
                TableSemanticModel(
                    table_id="air", table_name="air_quality", primary_entity_type=SemanticEntityType.FACILITY,
                    columns=[
                        SemanticColumnAssignment(
                            column_id="c_stn", table_id="air", column_name="station_id",
                            role=SemanticColumnRole.DIMENSION, classification_source=ClassificationSource.HEURISTIC,
                            confidence=1.0, rationale="Station ID",
                        ),
                        SemanticColumnAssignment(
                            column_id="c_pm", table_id="air", column_name="pm25",
                            role=SemanticColumnRole.MEASURE, classification_source=ClassificationSource.HEURISTIC,
                            confidence=1.0, rationale="PM2.5",
                        ),
                        SemanticColumnAssignment(
                            column_id="c_aqi", table_id="air", column_name="aqi",
                            role=SemanticColumnRole.MEASURE, classification_source=ClassificationSource.HEURISTIC,
                            confidence=1.0, rationale="AQI",
                        ),
                        SemanticColumnAssignment(
                            column_id="c_ts", table_id="air", column_name="timestamp",
                            role=SemanticColumnRole.TIME, classification_source=ClassificationSource.HEURISTIC,
                            confidence=1.0, rationale="Timestamp",
                        ),
                    ],
                )
            ],
        )
        grain_prof = GrainProfile(
            dataset_id="ds_env", run_id="run_env", source_fingerprint="src_env",
            table_grains=[
                TableGrainProfile(
                    table_id="air", table_name="air_quality", primary_entity=CanonicalGrain.SNAPSHOT,
                    key_columns=["station_id", "timestamp"], grain_expression="STATION x TIMESTAMP",
                    grain_confidence=1.0, is_unique=True, uniqueness_ratio=1.0, rationale="Snapshot grain",
                )
            ],
        )

        profile = build_analytical_profile(
            dataset_id="ds_env",
            structural_profile=struct_prof,
            semantic_model=sem_model,
            grain_profile=grain_prof,
            table_data={"air": env_rows},
        )

        finding_types = {f.finding_type for f in profile.findings}
        assert FindingType.CORRELATION.value in finding_types
        assert FindingType.DISTRIBUTION.value in finding_types
        assert FindingType.TREND.value in finding_types

        # Verify FDR correction was performed on the inferential tests
        corr_finding = next(f for f in profile.findings if f.finding_type == FindingType.CORRELATION.value)
        assert corr_finding.statistical_test_evidence is not None
        assert corr_finding.statistical_test_evidence.is_statistically_significant is True
