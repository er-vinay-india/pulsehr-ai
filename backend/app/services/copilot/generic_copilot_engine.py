"""Generic Grounded Copilot Engine (Phase 5).

Answers user questions across arbitrary datasets strictly grounded in:
1. Deterministic calculations & CandidateFacts
2. Interestingness ranking
3. Non-causal Analyst interpretations with automated claim auditing
4. Intelligent visualization recommendations
"""

import re
import logging
from typing import Any
import pandas as pd

from ..data_engine.semantic_classifier import SemanticDatasetProfile, ColumnSemanticProfile
from ..data_engine.opportunity_map import OpportunityMapGenerator
from ..data_engine.candidate_fact_discovery import CandidateFactDiscoveryEngine
from ..data_engine.candidate_fact import CandidateFact
from ..data_engine.interestingness_ranker import FactInterestingnessRanker, RankedFact
from ..data_engine.fact_visualizer import FactVisualizer
from ..analyst.analyst_agent import AnalystAgent
from ..analyst.interpretation_validator import InterpretationClaimValidator
from .copilot_models import GroundedAnswer

logger = logging.getLogger(__name__)


class GenericCopilotEngine:
    """Interprets and answers analytical user queries against arbitrary datasets."""

    @classmethod
    def _classify_intent(cls, query: str, profile: SemanticDatasetProfile) -> str:
        """Classifies user query into actionable analytical intent."""
        q_lower = query.lower()

        # 1. Ambiguity / Meaning query
        if any(w in q_lower for w in ["what does", "meaning of", "what is"]) and any(c.lower() in q_lower for c in profile.columns.keys()):
            return "AMBIGUITY"

        # 2. Calculation query
        if any(w in q_lower for w in ["calculate", "total", "average", "mean of", "sum of"]):
            return "CALCULATION"

        # 3. Trend query
        if any(w in q_lower for w in ["trend", "trajectory", "over time", "progression"]):
            return "TREND"

        # 4. Highest / Lowest Ranking query
        if any(w in q_lower for w in ["which", "highest", "lowest", "top", "rank", "maximum", "minimum"]):
            return "RANKING"

        # 5. Surprise me / Summary / Top findings
        if any(w in q_lower for w in ["surprise me", "top findings", "most interesting", "key facts", "strongest findings", "overview", "summary"]):
            return "SURPRISE_ME"

        # 6. Interpretation / "Why"
        if any(w in q_lower for w in ["why", "causes", "reason for", "explain why", "driver of"]):
            return "INTERPRETATION"

        # 7. Default to drilldown / entity inspection
        return "ENTITY_DRILLDOWN"

    @classmethod
    def _find_matching_facts(cls, query: str, facts: list[CandidateFact]) -> list[CandidateFact]:
        """Finds candidate facts whose metric, dimension, or values appear in the query."""
        q_lower = query.lower()
        matched = []

        for f in facts:
            score = 0
            if f.metric.lower() in q_lower:
                score += 2
            if f.dimensions:
                for k, v in f.dimensions.items():
                    if str(v).lower() in q_lower:
                        score += 3
                    if str(k).lower() in q_lower:
                        score += 1
            if score > 0:
                matched.append((score, f))

        matched.sort(key=lambda x: x[0], reverse=True)
        return [f for _, f in matched]

    @classmethod
    def _resolve_metric_column(cls, query: str, profile: SemanticDatasetProfile) -> str | None:
        """Resolves target metric column from query keywords or common synonyms."""
        q_lower = query.lower()
        # Direct match
        for c in profile.columns.keys():
            if c.lower() in q_lower:
                return c
        # Synonym mappings
        synonyms = {
            "revenue": ["sales_amount", "sales", "amount", "revenue", "value1"],
            "sales": ["sales_amount", "sales", "amount", "revenue"],
            "profit": ["profit", "margin", "net_profit"],
            "scrap": ["scrap_rate_pct", "scrap_rate", "scrap"],
            "defect": ["defect_count", "defects"],
            "overtime": ["overtime_hours", "overtime", "ot_hours"],
            "discount": ["discount_rate", "discount"]
        }
        for syn, candidates in synonyms.items():
            if syn in q_lower:
                for cand in candidates:
                    if cand in profile.columns:
                        return cand
        # Fallback to first numeric measure
        for c, cp in profile.columns.items():
            if getattr(cp, "semantic_type", "") in ("numeric measure", "currency / monetary measure", "percentage / rate"):
                return c
        return None

    @classmethod
    def answer_query(
        cls,
        df: pd.DataFrame,
        profile: SemanticDatasetProfile,
        user_query: str,
        facts: list[CandidateFact] | None = None,
        existing_ranked_facts: list[RankedFact] | None = None,
        existing_interpretation: Any | None = None
    ) -> GroundedAnswer:
        """Processes and answers a user query strictly grounded in evidence with zero duplicate analytical work."""
        intent = cls._classify_intent(user_query, profile)

        # Ensure facts are available
        if facts is None:
            opp_map = OpportunityMapGenerator.generate(profile)
            facts, _ = CandidateFactDiscoveryEngine.discover_facts(df, profile, opp_map)

        facts_lookup = {f.fact_id: f for f in facts}

        # ---------------------------------------------------------------------
        # INTENT 1: AMBIGUITY / COLUMN MEANING (0 LLM Calls)
        # ---------------------------------------------------------------------
        if intent == "AMBIGUITY":
            mentioned_col = None
            for c in profile.columns.keys():
                if c.lower() in user_query.lower():
                    mentioned_col = c
                    break

            col_prof = profile.columns.get(mentioned_col) if mentioned_col else None
            is_low_conf = getattr(col_prof, "semantic_confidence", 1.0) < 0.6 if col_prof else False
            is_masked = any(mentioned_col.startswith(p) for p in ["col_", "val", "flag"]) if mentioned_col else False

            if is_low_conf or is_masked or getattr(profile, "domain", "") in ("UNKNOWN", "generic", "unknown"):
                text = (
                    f"Column `{mentioned_col}` contains recorded data values, but has masked or ambiguous naming. "
                    "The mathematical difference is supported, but its business meaning cannot be determined "
                    "from the available column semantics."
                )
                return GroundedAnswer(
                    query=user_query,
                    intent=intent,
                    answer_markdown=text,
                    followup_questions=[f"Are there data dictionary mappings or business definitions available for `{mentioned_col}`?"],
                    metadata={"llm_calls": 0}
                )

        # ---------------------------------------------------------------------
        # INTENT 2: DETERMINISTIC CALCULATION (0 LLM Calls)
        # ---------------------------------------------------------------------
        if intent == "CALCULATION":
            metric_col = cls._resolve_metric_column(user_query, profile)
            if metric_col and metric_col in df.columns:
                cleaned_vals = df[metric_col].apply(FactVisualizer._clean_series_value).dropna()
                q_lower = user_query.lower()
                unit = FactVisualizer._infer_unit(metric_col, profile)
                if any(w in q_lower for w in ["average", "mean"]):
                    op = "Mean"
                    calc_val = float(cleaned_vals.mean())
                else:
                    op = "Total"
                    calc_val = float(cleaned_vals.sum())

                unit_prefix = unit if unit == "$" else ""
                unit_suffix = unit if unit != "$" else ""
                text = (
                    f"**Calculated {op} {metric_col.replace('_', ' ').title()}**: "
                    f"**{unit_prefix}{calc_val:,.2f}{unit_suffix}** "
                    f"(computed deterministically across n={len(cleaned_vals):,} rows)."
                )
                return GroundedAnswer(
                    query=user_query,
                    intent=intent,
                    answer_markdown=text,
                    followup_questions=[
                        f"Would you like to see how {metric_col} varies across segments?",
                        f"Would you like to examine the chronological trend for {metric_col}?"
                    ],
                    metadata={"llm_calls": 0, "operation": op, "result": calc_val}
                )

        # ---------------------------------------------------------------------
        # INTENT 3: RANKING / "WHICH ENTITY HAS HIGHEST/LOWEST" (0 LLM Calls)
        # ---------------------------------------------------------------------
        if intent == "RANKING":
            matching = cls._find_matching_facts(user_query, facts)
            # Find segment facts
            seg_facts = [f for f in matching if f.fact_type in ("segment_comparison", "segment_gap")]
            if not seg_facts:
                seg_facts = [f for f in facts if f.fact_type in ("segment_comparison", "segment_gap")]

            if seg_facts:
                q_lower = user_query.lower()
                is_lowest = "lowest" in q_lower or "minimum" in q_lower
                sorted_facts = sorted(seg_facts, key=lambda f: f.value or 0.0, reverse=not is_lowest)
                top_fact = sorted_facts[0]
                unit = FactVisualizer._infer_unit(top_fact.metric, profile)
                chart = FactVisualizer.recommend_chart(top_fact, df=df, profile=profile)

                dim_name = list(top_fact.dimensions.values())[0] if top_fact.dimensions else "Segment"
                text = (
                    f"**Highest/Lowest Observation for {top_fact.metric.replace('_', ' ').title()}**:\n"
                    f"- Leading segment: **{dim_name}** with observed value **{top_fact.value:,.2f}** "
                    f"vs overall baseline of {top_fact.baseline_value:,.2f} "
                    f"({top_fact.relative_difference:+.1f}%) [{top_fact.fact_id}].\n"
                    f"- Sample size: n={top_fact.sample_size}"
                )
                return GroundedAnswer(
                    query=user_query,
                    intent=intent,
                    answer_markdown=text,
                    cited_facts=[top_fact],
                    recommended_chart=chart,
                    followup_questions=[f"What operational conditions characterize {dim_name}?"],
                    metadata={"llm_calls": 0}
                )

        # ---------------------------------------------------------------------
        # INTENT 4: TREND QUERY (0 LLM Calls)
        # ---------------------------------------------------------------------
        if intent == "TREND":
            metric_col = cls._resolve_metric_column(user_query, profile)
            trend_facts = [f for f in facts if f.fact_type == "period_trend" and (not metric_col or f.metric == metric_col)]
            if not trend_facts:
                trend_facts = [f for f in facts if f.fact_type == "period_trend"]

            if trend_facts:
                tf = trend_facts[0]
                chart = FactVisualizer.recommend_chart(tf, df=df, profile=profile)
                text = (
                    f"**Chronological Trend for {tf.metric.replace('_', ' ').title()}**:\n"
                    f"- {tf.statement} [{tf.fact_id}]\n"
                    f"- Trajectory window: {tf.time_window or 'Observed Range'}\n"
                    f"- Overall baseline: {tf.baseline_value}"
                )
                return GroundedAnswer(
                    query=user_query,
                    intent=intent,
                    answer_markdown=text,
                    cited_facts=[tf],
                    recommended_chart=chart,
                    followup_questions=[f"Would you like to analyze which segments drive this {tf.metric} trend?"],
                    metadata={"llm_calls": 0}
                )

        # ---------------------------------------------------------------------
        # INTENT 5: SURPRISE ME / TOP FINDINGS (0 LLM Calls if Ranked/Interpreted)
        # ---------------------------------------------------------------------
        if intent == "SURPRISE_ME":
            if existing_ranked_facts:
                top_facts = [rf.fact for rf in existing_ranked_facts[:3]]
            else:
                ranked = FactInterestingnessRanker.rank_interesting_facts(facts, limit=5)
                top_facts = [rf.fact for rf in ranked[:3]]

            lines = ["### Top Verified Findings\n"]
            for i, f in enumerate(top_facts, 1):
                diff_str = f" ({f.relative_difference:+.1f}% vs baseline)" if f.relative_difference is not None else ""
                lines.append(f"{i}. **{f.metric.replace('_', ' ').title()}**: {f.statement} [{f.fact_id}]")

            recommended_chart = FactVisualizer.recommend_chart(top_facts[0], df=df, profile=profile) if top_facts else None
            followups = [
                f"Would you like to drill down into {top_facts[0].metric}?",
                "Would you like to explore segment variations?"
            ] if top_facts else []

            return GroundedAnswer(
                query=user_query,
                intent=intent,
                answer_markdown="\n".join(lines),
                cited_facts=top_facts,
                recommended_chart=recommended_chart,
                followup_questions=followups,
                metadata={"llm_calls": 0}
            )

        # ---------------------------------------------------------------------
        # INTENT 6: INTERPRETATION / "WHY" (Reuse existing or Qwen 3.5)
        # ---------------------------------------------------------------------
        if intent == "INTERPRETATION":
            # Check if pre-computed interpretation already covers this topic
            matching_existing_insight = None
            if existing_interpretation and hasattr(existing_interpretation, "insights"):
                q_words = set(re.findall(r'\b\w+\b', user_query.lower()))
                for ins in existing_interpretation.insights:
                    ins_words = set(re.findall(r'\b\w+\b', (ins.title + " " + ins.observation).lower()))
                    if q_words.intersection(ins_words) - {"why", "is", "the", "what", "of", "and", "in"}:
                        matching_existing_insight = ins
                        break

            if matching_existing_insight:
                # 0 LLM Calls - Direct Evidence Reuse
                ins = matching_existing_insight
                text = (
                    f"**Observation**: {ins.observation}\n\n"
                    f"**Interpretation**: {ins.interpretation}\n\n"
                    f"*Note*: Statistical associations indicate correlation rather than direct causation."
                )
                primary_fid = ins.supporting_fact_ids[0] if ins.supporting_fact_ids else None
                chart = FactVisualizer.recommend_chart(facts_lookup[primary_fid], df=df, profile=profile) if primary_fid and primary_fid in facts_lookup else None
                cited = [facts_lookup[fid] for fid in ins.supporting_fact_ids if fid in facts_lookup]
                return GroundedAnswer(
                    query=user_query,
                    intent=intent,
                    answer_markdown=text,
                    cited_facts=cited,
                    recommended_chart=chart,
                    followup_questions=ins.questions_to_investigate,
                    audit_passed=True,
                    metadata={"llm_calls": 0, "reused_existing": True}
                )

            # Otherwise, invoke AnalystAgent Qwen 3.5 (1 LLM Call)
            matching = cls._find_matching_facts(user_query, facts)
            eval_facts = matching[:4] if matching else facts[:4]

            ranked_eval = FactInterestingnessRanker.rank_interesting_facts(eval_facts, limit=4)
            interpretation, _ = AnalystAgent.interpret(profile, ranked_eval, max_facts=4)
            audit = InterpretationClaimValidator.audit_response(interpretation, facts_lookup, profile=profile)

            ins = interpretation.insights[0] if interpretation.insights else None
            if ins:
                text = (
                    f"**Observation**: {ins.observation}\n\n"
                    f"**Interpretation**: {ins.interpretation}\n\n"
                    f"*Note*: Statistical associations indicate correlation rather than direct causation."
                )
                chart = FactVisualizer.recommend_chart(facts_lookup[ins.supporting_fact_ids[0]], df=df, profile=profile) if ins.supporting_fact_ids else None
                followups = ins.questions_to_investigate
                cited = [facts_lookup[fid] for fid in ins.supporting_fact_ids if fid in facts_lookup]
            else:
                text = "The available candidate facts confirm observed numerical variance without establishing direct causation."
                chart = None
                followups = ["What external factors might account for this variation?"]
                cited = []

            return GroundedAnswer(
                query=user_query,
                intent=intent,
                answer_markdown=text,
                cited_facts=cited,
                recommended_chart=chart,
                followup_questions=followups,
                audit_passed=audit.all_passed,
                metadata={"llm_calls": 1}
            )

        # ---------------------------------------------------------------------
        # INTENT 7: ENTITY DRILLDOWN / TARGET (0 LLM Calls)
        # ---------------------------------------------------------------------
        matching = cls._find_matching_facts(user_query, facts)
        if matching:
            target_fact = matching[0]
            chart = FactVisualizer.recommend_chart(target_fact, df=df, profile=profile)
            text = (
                f"**Evidence for {target_fact.metric.replace('_', ' ').title()}**:\n"
                f"- {target_fact.statement} [{target_fact.fact_id}]\n"
                f"- Baseline value: {target_fact.baseline_value}\n"
                f"- Sample size: n={target_fact.sample_size}"
            )
            return GroundedAnswer(
                query=user_query,
                intent="ENTITY_DRILLDOWN",
                answer_markdown=text,
                cited_facts=[target_fact],
                recommended_chart=chart,
                followup_questions=[f"What operational conditions characterize {target_fact.dimensions}?"],
                metadata={"llm_calls": 0}
            )

        # Fallback to general data summary (0 LLM Calls)
        text = f"Dataset '{profile.dataset_name}' contains {profile.row_count} rows across {profile.column_count} columns."
        return GroundedAnswer(
            query=user_query,
            intent="GENERAL",
            answer_markdown=text,
            cited_facts=[],
            metadata={"llm_calls": 0}
        )
