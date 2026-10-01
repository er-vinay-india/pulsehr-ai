import re
from typing import Any


def _extract_unit(text: str) -> str:
    """Extracts standard unit from metric label or value string."""
    t = text.lower()
    if "%" in t or "percent" in t or "rate" in t or "share" in t or "pct" in t:
        return "%"
    if "$" in t or "usd" in t or "dollar" in t:
        return "$"
    if "€" in t or "eur" in t:
        return "€"
    if "£" in t or "gbp" in t:
        return "£"
    if re.search(r'\b\d+(?:\.\d+)?x\b', t) or "ratio" in t or "spread" in t or "multiple" in t:
        return "x"
    if "pts" in t or "points" in t:
        return "pts"
    if any(w in t for w in ("record", "records", "row", "rows", "headcount", "staff", "personnel", "count")):
        return "count"
    return "unit"


def _extract_primary_and_denominator(val_str: str) -> tuple[float | None, float | None]:
    """Extracts the primary claimed number and optional denominator (e.g., '187 of 232')."""
    # Check for "X of Y" pattern
    of_match = re.search(r'([\d,.]+)\s*(?:of|out of|/)\s*([\d,.]+)', val_str)
    if of_match:
        try:
            num = float(of_match.group(1).replace(",", ""))
            denom = float(of_match.group(2).replace(",", ""))
            return num, denom
        except (ValueError, TypeError):
            pass

    # Extract all numbers
    numbers = []
    for raw in re.findall(r'[\d,.]+', val_str):
        clean = raw.replace(",", "").rstrip(".")
        if clean and clean != '.':
            try:
                numbers.append(float(clean))
            except (ValueError, TypeError):
                pass

    if numbers:
        return numbers[0], None
    return None, None


def verify_presentation_claims(
    deck_spec: dict[str, Any],
    evidence_ledger: list[dict[str, Any]]
) -> dict[str, Any]:
    """Audits all numerical claims across slides against the ground-truth evidence ledger.

    Strict Data-Driven Presentation Standard:
    1. Verifies complete claims against actual evidence values, units, and denominators.
    2. No skipping of selected metrics (flight risk, top performer, strain rate are fully verified).
    3. No blanket 100% assumptions without explicit evidence support.
    4. Enforces metric agreement within +/- 0.1% rounding tolerance.
    """
    if isinstance(deck_spec, list):
        deck_spec = {"slides": deck_spec}

    if deck_spec.get("metadata", {}).get("deck_style") == "decision_brief":
        from .decision_deck import verify_decision_deck
        return verify_decision_deck(deck_spec, evidence_ledger)

    checked_items = []
    discrepancies = []

    # Map evidence items by ID and normalized metric name
    ev_by_id = {
        (e.get("evidence_id") or e.get("id")): e
        for e in evidence_ledger
        if isinstance(e, dict) and (e.get("evidence_id") or e.get("id"))
    }
    ev_by_name = {
        e.get("metric_name", "").lower().replace("_", " ").replace("-", " ").strip(): e
        for e in evidence_ledger
        if isinstance(e, dict) and e.get("metric_name")
    }

    total_dataset_records = float(deck_spec.get("metadata", {}).get("total_records") or 0)

    for slide_idx, slide in enumerate(deck_spec.get("slides", [])):
        slide_title = slide.get("title", f"Slide {slide_idx+1}")
        slide_ev_id = slide.get("evidence_id")

        metrics_to_check = list(slide.get("metrics") or [])
        if not metrics_to_check:
            # Check bullets and title for explicit numerical claims
            texts = [slide.get("title", ""), slide.get("takeaway", "")]
            if isinstance(slide.get("content"), dict):
                texts.extend(slide.get("content", {}).get("bullets", []))
            for txt in texts:
                for match in re.finditer(r'([A-Za-z\s]{3,30}?)\s+(?:is|at|reached|to|soared to)?\s*([$€£¥]?\d+(?:\.\d+)?%?)', txt):
                    lbl_cand = match.group(1).strip()
                    val_cand = match.group(2).strip()
                    if any(c.isdigit() for c in val_cand) and len(lbl_cand) > 3:
                        metrics_to_check.append({"label": lbl_cand, "value": val_cand})

        for metric in metrics_to_check:
            lbl = metric.get("label", "")
            val_str = str(metric.get("value", ""))
            lbl_clean = lbl.lower().replace("_", " ").replace("-", " ").strip()

            # 1. Skip strictly non-numeric qualitative metadata cards (e.g. date strings, entity names)
            if not re.match(r'^\s*[$€£¥+\-]?\s*\d', val_str):
                continue
            if any(k in lbl_clean for k in ("observation window", "reporting period", "date range", "horizon", "audit scope window", "evaluation horizon")):
                if any(c in val_str.lower() for c in ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec", "sheet", "recorded", "–", "-", "stop", "rqi", "llp")):
                    continue

            # Extract claimed primary number and optional denominator
            claimed_num, claimed_denom = _extract_primary_and_denominator(val_str)
            if claimed_num is None:
                continue

            claimed_unit = _extract_unit(f"{lbl} {val_str}")

            # 2. Match specifically against evidence ledger item
            matched_ev = None
            metric_ev_id = metric.get("evidence_id")
            if metric_ev_id and metric_ev_id in ev_by_id:
                matched_ev = ev_by_id[metric_ev_id]
            elif lbl_clean in ev_by_name:
                matched_ev = ev_by_name[lbl_clean]
            elif any(k in lbl_clean for k in ("record", "population", "evaluated", "audited", "staff", "employee", "headcount")):
                matched_ev = ev_by_id.get("EVID-EXEC-01")
            elif any(k in lbl_clean for k in ("baseline", "network mean", "benchmark mean", "average", "weekly sales", "sales mean", "performance benchmark")):
                matched_ev = ev_by_id.get("EVID-KPI-01")
            elif any(k in lbl_clean for k in ("surge", "strength", "peak", "leader", "benchmark leader", "high")):
                matched_ev = ev_by_id.get("EVID-STRENGTH-01")
            elif any(k in lbl_clean for k in ("dispersion", "spread", "headwind", "variance", "ratio", "trailing", "gap", "disparity")):
                matched_ev = ev_by_id.get("EVID-HEADWIND-01")
            elif any(k in lbl_clean for k in ("link", "relational", "segment", "coverage", "boundary", "isolation", "key integrity")):
                matched_ev = ev_by_id.get("EVID-REL-01") or ev_by_id.get("EVID-GOV-01")
            elif any(k in lbl_clean for k in ("confidence", "lesson", "empirical")):
                matched_ev = ev_by_id.get("EVID-LESSON-01")
            elif any(k in lbl_clean for k in ("initiative", "proposal", "roadmap", "phase", "action", "recommendation")):
                matched_ev = ev_by_id.get("EVID-REC-01")
            elif any(k in lbl_clean for k in ("completeness", "integrity", "audit", "governance", "resilience", "hash", "trail")):
                matched_ev = ev_by_id.get("EVID-GOV-01") or ev_by_id.get("EVID-REL-01")
            elif "top performer" in lbl_clean:
                meta_ind = deck_spec.get("metadata", {}).get("industrial_models") or deck_spec.get("industrial_models") or {}
                t9 = meta_ind.get("talent_9box")
                if t9:
                    matched_ev = {
                        "evidence_id": "MODEL-9BOX-TOP",
                        "metric_name": "Top Performers",
                        "numeric_value": float(t9.get("high_performers_count", 0)),
                        "metric_value": str(t9.get("high_performers_count", 0)),
                        "unit": "count"
                    }
            elif "flight risk" in lbl_clean:
                meta_ind = deck_spec.get("metadata", {}).get("industrial_models") or deck_spec.get("industrial_models") or {}
                t9 = meta_ind.get("talent_9box")
                if t9:
                    matched_ev = {
                        "evidence_id": "MODEL-9BOX-RISK",
                        "metric_name": "Flight Risk Stars",
                        "numeric_value": float(t9.get("retention_vulnerable_stars", 0)),
                        "metric_value": str(t9.get("retention_vulnerable_stars", 0)),
                        "unit": "count"
                    }
            elif "severe strain" in lbl_clean:
                meta_ind = deck_spec.get("metadata", {}).get("industrial_models") or deck_spec.get("industrial_models") or {}
                bs = meta_ind.get("burnout_strain")
                if bs:
                    matched_ev = {
                        "evidence_id": "MODEL-STRAIN-01",
                        "metric_name": "Severe Strain",
                        "numeric_value": float(bs.get("severe_strain_count", 0)),
                        "metric_value": str(bs.get("severe_strain_count", 0)),
                        "unit": "count"
                    }
            elif "at-risk share" in lbl_clean or "strain share" in lbl_clean:
                meta_ind = deck_spec.get("metadata", {}).get("industrial_models") or deck_spec.get("industrial_models") or {}
                bs = meta_ind.get("burnout_strain")
                if bs:
                    matched_ev = {
                        "evidence_id": "MODEL-STRAIN-02",
                        "metric_name": "At-Risk Share",
                        "numeric_value": float(bs.get("at_risk_share_pct", 0)),
                        "metric_value": f"{bs.get('at_risk_share_pct', 0)}%",
                        "unit": "%"
                    }
            elif slide_ev_id and slide_ev_id in ev_by_id:
                cand = ev_by_id[slide_ev_id]
                cand_name = cand.get("metric_name", "").lower()
                if cand_name in lbl_clean or lbl_clean in cand_name or any(w in lbl_clean for w in cand_name.split() if len(w) > 3):
                    matched_ev = cand

            # 3. Check number agreement, unit agreement, and denominator agreement
            if matched_ev:
                nums_expected = []
                if matched_ev.get("numeric_value") is not None:
                    nums_expected.append(float(matched_ev["numeric_value"]))
                if matched_ev.get("value") is not None:
                    try:
                        nums_expected.append(float(matched_ev["value"]))
                    except (ValueError, TypeError):
                        pass
                if matched_ev.get("row_count") is not None:
                    nums_expected.append(float(matched_ev["row_count"]))
                if matched_ev.get("metric_value"):
                    for n in re.findall(r'[\d,.]+', str(matched_ev["metric_value"])):
                        clean_n = n.replace(",", "").rstrip(".")
                        if clean_n and clean_n != '.':
                            try:
                                nums_expected.append(float(clean_n))
                            except ValueError:
                                pass

                # If slide has chart with categories, allow category count for segment/category count
                if slide.get("chart") and slide["chart"].get("categories"):
                    cat_count = float(len(slide["chart"]["categories"]))
                    if any(k in lbl_clean for k in ("segment", "category", "count", "unit")):
                        nums_expected.append(cat_count)

                # Check unit consistency
                expected_unit = _extract_unit(f"{matched_ev.get('metric_name', '')} {matched_ev.get('metric_value', '')}")
                unit_match = (
                    claimed_unit == expected_unit
                    or claimed_unit == "unit"
                    or expected_unit == "unit"
                    or (claimed_unit == "%" and any(k in lbl_clean for k in ("completeness", "integrity", "rate", "share", "pct")))
                )

                # Check denominator consistency if denominator was claimed
                denom_match = True
                if claimed_denom is not None:
                    ev_rows = float(matched_ev.get("row_count") or total_dataset_records)
                    if ev_rows > 0:
                        denom_diff = abs(claimed_denom - ev_rows) / ev_rows
                        denom_match = (denom_diff <= 0.001)

                # Find closest number match
                passed_num = False
                best_diff_pct = 100.0
                for e_val in nums_expected:
                    diff = abs(claimed_num - e_val) / abs(e_val) if e_val != 0 else abs(claimed_num - e_val)
                    diff_pct = round(diff * 100, 3)
                    if diff <= 0.001 or (abs(claimed_num - e_val) <= 0.01):
                        passed_num = True
                        best_diff_pct = 0.0
                        break
                    if diff_pct < best_diff_pct:
                        best_diff_pct = diff_pct

                overall_passed = passed_num and unit_match and denom_match
                expected_display = matched_ev.get("metric_value", str(matched_ev.get("numeric_value", "")))

                item_record = {
                    "slide": slide_title,
                    "metric": lbl,
                    "claimed_value": val_str,
                    "claimed_unit": claimed_unit,
                    "expected_value": expected_display,
                    "expected_unit": expected_unit,
                    "difference_pct": best_diff_pct if not overall_passed else 0.0,
                    "unit_match": unit_match,
                    "denominator_match": denom_match,
                    "passed": overall_passed,
                    "status": "PASSED" if overall_passed else "DISCREPANCY"
                }
                checked_items.append(item_record)

                if not overall_passed:
                    discrepancy_reason = []
                    if not passed_num:
                        discrepancy_reason.append(f"Number discrepancy: claimed {claimed_num} vs expected {nums_expected}")
                    if not unit_match:
                        discrepancy_reason.append(f"Unit mismatch: claimed '{claimed_unit}' vs expected '{expected_unit}'")
                    if not denom_match:
                        discrepancy_reason.append(f"Denominator mismatch: claimed {claimed_denom} vs expected {total_dataset_records}")

                    discrepancies.append({
                        "slide": slide_title,
                        "metric": lbl,
                        "claimed": val_str,
                        "expected": expected_display,
                        "reason": "; ".join(discrepancy_reason)
                    })
            else:
                # Metric could not be matched against any ledger item -> UNVERIFIED / FAILED
                checked_items.append({
                    "slide": slide_title,
                    "metric": lbl,
                    "claimed_value": val_str,
                    "claimed_unit": claimed_unit,
                    "expected_value": "Evidence in verified ledger",
                    "expected_unit": "unknown",
                    "difference_pct": 100.0,
                    "unit_match": False,
                    "denominator_match": False,
                    "passed": False,
                    "status": "UNVERIFIED"
                })
                discrepancies.append({
                    "slide": slide_title,
                    "metric": lbl,
                    "claimed": val_str,
                    "expected": "Evidence in verified ledger",
                    "reason": "Metric claim has no corresponding verified evidence in ledger."
                })

    total = max(len(checked_items), 1)
    passed_count = sum(1 for c in checked_items if c["passed"])
    disc_count = len(discrepancies)

    return {
        "total_metrics_checked": total,
        "passed_verification": passed_count,
        "discrepancies_flagged": disc_count,
        "tolerance_threshold": "±0.1%",
        "status": "PASSED" if disc_count == 0 else "DISCREPANCIES_FLAGGED",
        "checked_items": checked_items,
        "discrepancies": discrepancies
    }
