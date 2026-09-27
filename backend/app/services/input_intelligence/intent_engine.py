"""User Intent Parser, Question-to-Data Alignment, and Readiness Engine.

Enforces:
- User Intent Precedence (Explicit Instruction > Source Content > Inferred)
- No-Intent Fallback (mark UNSPECIFIED, suggest capabilities without fabricating goals)
- Question-to-Data Mapping (SUPPORTED, PARTIALLY_SUPPORTED, UNSUPPORTED)
- Output Intent Detection (ANALYSIS, DASHBOARD, PRESENTATION, REPORT, etc.)
- Analysis Readiness Scoring (READY, READY_WITH_WARNINGS, UNSUPPORTED)
"""

from __future__ import annotations

import re
from typing import Any

from .models import (
    AlignmentStatus,
    AnalysisReadiness,
    DatasetProfile,
    IntentStatus,
    OutputIntent,
    ProvenanceOrigin,
    QuestionDataMapping,
    ReadinessStatus,
    UserIntentContext,
)


class UserIntentEngine:
    """Parses user instructions, reconciles intent against data capabilities, and checks question alignment."""

    QUESTION_STARTERS = ("which", "what", "who", "where", "when", "why", "how", "compare", "find", "identify", "is there", "are there")

    @classmethod
    def parse_user_intent(
        cls,
        raw_instruction: str = "",
        dataset_profiles: list[DatasetProfile] | None = None,
        user_overrides: dict[str, Any] | None = None
    ) -> UserIntentContext:
        """Parses natural language instruction with strict precedence and no-intent fallback."""
        profiles = dataset_profiles or []
        overrides = user_overrides or {}

        clean_text = raw_instruction.strip() if raw_instruction else ""

        # ---------------------------------------------------------------------
        # CASE 1: NO INSTRUCTION PROVIDED (No-Intent Fallback)
        # ---------------------------------------------------------------------
        if not clean_text:
            safe_capabilities = cls._infer_safe_capabilities(profiles)
            col_summary = ", ".join([c.name for p in profiles for c in p.columns[:5]])
            norm_obj = f"Exploratory dataset review based on available columns ({col_summary})." if col_summary else "Dataset overview."

            # Apply any explicit user override
            if "objective" in overrides:
                norm_obj = overrides["objective"]

            return UserIntentContext(
                raw_instruction="",
                normalized_objective=norm_obj,
                explicit_questions=[],
                expected_output=OutputIntent.ANALYSIS,
                intent_status=IntentStatus.UNSPECIFIED,
                possible_analysis_capabilities=safe_capabilities,
                confidence=0.50,
                provenance=ProvenanceOrigin.SYSTEM_DEFAULT
            )

        # ---------------------------------------------------------------------
        # CASE 2: EXPLICIT USER INSTRUCTION PROVIDED
        # ---------------------------------------------------------------------
        lower_text = clean_text.lower()

        # 1. Output Intent
        output_intent = OutputIntent.ANALYSIS
        if any(k in lower_text for k in ("presentation", "ppt", "slide", "deck", "pitch", "briefing")):
            output_intent = OutputIntent.PRESENTATION
        elif any(k in lower_text for k in ("dashboard", "board", "kpi view")):
            output_intent = OutputIntent.DASHBOARD
        elif any(k in lower_text for k in ("report", "memo", "executive summary", "document")):
            output_intent = OutputIntent.REPORT
        elif any(k in lower_text for k in ("chart", "graph", "plot", "visualize")):
            output_intent = OutputIntent.CHART
        elif any(k in lower_text for k in ("table", "roster", "spreadsheet")):
            output_intent = OutputIntent.TABLE

        # 2. Extract Explicit Questions
        questions = cls._extract_explicit_questions(clean_text)

        # 3. Audience Detection
        audience = None
        if "c-suite" in lower_text or "executive" in lower_text or "leadership" in lower_text or "board" in lower_text:
            audience = "Executive Leadership & Board"
        elif "manager" in lower_text or "team lead" in lower_text:
            audience = "Operations Management"
        elif "student" in lower_text or "beginner" in lower_text:
            audience = "Students & Practitioners"
        elif "client" in lower_text or "customer" in lower_text:
            audience = "External Client"

        # 4. Extract Constraints
        output_constraints = []
        pres_constraints = []

        exact_slide = re.search(r'(?:exactly|strictly)\s+(\d+)\s*slides?', lower_text)
        if exact_slide:
            pres_constraints.append(f"Exactly {exact_slide.group(1)} slides")

        max_slide = re.search(r'(?:maximum|max|limit to|up to)\s+(\d+)\s*slides?', lower_text)
        if max_slide:
            pres_constraints.append(f"Maximum {max_slide.group(1)} slides")

        if "executive tone" in lower_text:
            output_constraints.append("Executive tone")
        if "beginner-friendly" in lower_text or "low cognitive load" in lower_text:
            output_constraints.append("Low cognitive load")
        if "do not include methodology" in lower_text or "appendix" in lower_text:
            pres_constraints.append("Route methodology to appendix")
        if "cautious language" in lower_text or "do not fabricate" in lower_text:
            output_constraints.append("Cautious non-projected language")

        # 5. Focus Areas
        focus_areas = []
        if "margin" in lower_text:
            focus_areas.append("margin")
        if "attendance" in lower_text:
            focus_areas.append("attendance")
        if "variance" in lower_text:
            focus_areas.append("variance")
        if "leave" in lower_text:
            focus_areas.append("leave")
        if "latency" in lower_text:
            focus_areas.append("latency")

        # Normalized objective
        norm_obj = clean_text.split(".")[0].strip()
        if len(norm_obj) > 120:
            norm_obj = norm_obj[:117] + "..."

        # Apply any explicit user overrides
        if "objective" in overrides:
            norm_obj = overrides["objective"]
        if "audience" in overrides:
            audience = overrides["audience"]
        if "output_intent" in overrides:
            output_intent = OutputIntent(overrides["output_intent"])

        return UserIntentContext(
            raw_instruction=clean_text,
            normalized_objective=norm_obj,
            explicit_questions=questions,
            expected_output=output_intent,
            audience=audience,
            decision_context="Operational assessment and decision briefing",
            analysis_focus=focus_areas,
            excluded_topics=["unsupported external assumptions"],
            output_constraints=output_constraints,
            presentation_constraints=pres_constraints,
            intent_status=IntentStatus.EXPLICIT,
            confidence=1.0,
            provenance=ProvenanceOrigin.USER_EXPLICIT
        )

    @classmethod
    def reconcile_questions_against_data(
        cls,
        questions: list[str],
        profiles: list[DatasetProfile]
    ) -> list[QuestionDataMapping]:
        """Maps each explicit user question to available dataset columns and flags unsupported questions."""
        mappings: list[QuestionDataMapping] = []

        # Collect all available column names and tokens
        available_cols = {}
        for p in profiles:
            for c in p.columns:
                available_cols[c.name.lower()] = c.name

        for q in questions:
            q_clean = q.lower().replace("?", "")
            words = [w for w in re.findall(r'\b\w+\b', q_clean) if len(w) > 3]

            mapped = {}
            unmapped = []

            for word in words:
                # Check direct or partial match
                matched_col = None
                for col_lower, original in available_cols.items():
                    if word in col_lower or col_lower in word:
                        matched_col = original
                        break

                if matched_col:
                    mapped[word] = matched_col
                else:
                    # Filter out common stop words
                    if word not in ("which", "what", "where", "when", "most", "best", "highest", "lowest", "show", "tell", "find", "have"):
                        unmapped.append(word)

            # Determine alignment
            if not mapped and unmapped:
                alignment = AlignmentStatus.UNSUPPORTED
                expl = f"None of the required concepts ({', '.join(unmapped)}) were found in the uploaded columns."
            elif mapped and not unmapped:
                alignment = AlignmentStatus.SUPPORTED
                expl = f"All required concepts mapped to columns: {', '.join(mapped.values())}."
            elif mapped and unmapped:
                # If critical concepts like 'salary', 'cost' are missing, mark unsupported or partially supported
                critical_missing = [u for u in unmapped if u in ("salary", "compensation", "revenue", "cost", "profit", "diagnosis")]
                if critical_missing:
                    alignment = AlignmentStatus.UNSUPPORTED
                    expl = f"Critical analytical concept '{critical_missing[0]}' is completely missing from the dataset."
                else:
                    alignment = AlignmentStatus.PARTIALLY_SUPPORTED
                    expl = f"Partially supported: mapped {', '.join(mapped.values())}, but could not confirm {', '.join(unmapped)}."
            else:
                alignment = AlignmentStatus.SUPPORTED
                expl = "Grounded on general dataset metrics."

            mappings.append(
                QuestionDataMapping(
                    question=q,
                    required_concepts=list(mapped.keys()) + unmapped,
                    mapped_fields=mapped,
                    unmapped_concepts=unmapped,
                    alignment_status=alignment,
                    explanation=expl
                )
            )

        return mappings

    @classmethod
    def evaluate_readiness(
        cls,
        profiles: list[DatasetProfile],
        intent: UserIntentContext,
        question_mappings: list[QuestionDataMapping]
    ) -> AnalysisReadiness:
        """Evaluates whether dataset and intent alignment is ready for downstream analytical pipelines."""
        issues = []

        if not profiles:
            return AnalysisReadiness(
                status=ReadinessStatus.INSUFFICIENT_DATA,
                is_ready=False,
                issues=["No datasets or sheets found in workspace."]
            )

        total_rows = sum(p.row_count for p in profiles)
        if total_rows < 5:
            issues.append(f"Very small sample size ({total_rows} records). Generalizations must be bounded.")

        # Check for completely unsupported user questions
        unsupported_qs = [m for m in question_mappings if m.alignment_status == AlignmentStatus.UNSUPPORTED]
        if unsupported_qs:
            issues.append(f"{len(unsupported_qs)} explicit question(s) cannot be answered by this dataset: '{unsupported_qs[0].question}'")
            return AnalysisReadiness(
                status=ReadinessStatus.NEEDS_MAPPING,
                is_ready=False,
                issues=issues,
                missing_prerequisites=[u for m in unsupported_qs for u in m.unmapped_concepts]
            )

        if issues:
            return AnalysisReadiness(
                status=ReadinessStatus.READY_WITH_WARNINGS,
                is_ready=True,
                issues=issues
            )

        return AnalysisReadiness(
            status=ReadinessStatus.READY,
            is_ready=True,
            issues=[]
        )

    @classmethod
    def _extract_explicit_questions(cls, text: str) -> list[str]:
        """Extracts interrogative sentences or explicit analysis questions from user instruction."""
        sentences = re.split(r'[.?!\n]+', text)
        questions = []
        for s in sentences:
            s_clean = s.strip()
            if not s_clean:
                continue
            lower = s_clean.lower()
            if any(lower.startswith(starter) for starter in cls.QUESTION_STARTERS) or "compare" in lower or "who" in lower or "?" in s:
                q_text = s_clean + ("?" if not s_clean.endswith("?") else "")
                questions.append(q_text)
        return questions

    @classmethod
    def _infer_safe_capabilities(cls, profiles: list[DatasetProfile]) -> list[str]:
        """Infers safe high-level analytical capabilities from column profiles without inventing business goals."""
        capabilities = []
        all_cols = [c.name.lower() for p in profiles for c in p.columns]

        if any("attend" in c for c in all_cols):
            capabilities.append("Attendance and in-office presence patterns")
        if any("department" in c or "team" in c for c in all_cols):
            capabilities.append("Departmental or organizational cohort comparison")
        if any("leave" in c or "vacation" in c for c in all_cols):
            capabilities.append("Leave and unplanned absence distribution")
        if any("sales" in c or "revenue" in c for c in all_cols):
            capabilities.append("Commercial revenue and volume distribution")
        if any("date" in c or "time" in c for c in all_cols):
            capabilities.append("Chronological trend and timeline evaluation")
        if any("cost" in c or "budget" in c for c in all_cols):
            capabilities.append("Financial variance and expenditure breakdown")

        if not capabilities:
            capabilities.append("Categorical breakdown and metric distribution")

        return capabilities
