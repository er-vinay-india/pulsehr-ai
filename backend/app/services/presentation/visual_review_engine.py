"""HighView Presentation Studio — PPT-L9 Visual Review Engine.

Inspects actual rendered slide images to evaluate visual presentation quality:
- Never alters factual numbers or business logic.
- Evaluates visual hierarchy, spacing, typography density, chart/table legibility, and image framing.
- Strictly protects primary visuals (hidden primary visual = CRITICAL).
- Distinguishes intentional whitespace (title/divider) from awkward excessive whitespace.
- Merges deterministic PPT-L8 issues with visual observations to avoid duplicate noise.
- Emits structured VisualReviewManifest with deterministic SHA-256 fingerprint.
"""

from __future__ import annotations

import base64
import io
import json
import logging
from pathlib import Path
from typing import Any, Optional

import httpx
from PIL import Image, ImageStat
import pptx
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pydantic import ValidationError

from app.core import config
from app.services.presentation.layer_zone_models import LayeredDeckStructureSpec, StructuralRole
from app.services.presentation.layout_models import ResolvedDeckLayout
from app.services.presentation.qa.gemma_critic import GemmaVisualCritic
from app.services.presentation.slide_render_service import (
    DeterministicVisualPrecheck,
    RenderedSlideArtifact,
)
from app.services.presentation.theme_models import StyleManifest, ThemeMode
from app.services.presentation.validation_models_l8 import (
    DeckValidationStatus,
    RepairAction,
    RepairOwner,
    ValidationCategory,
    ValidationManifest,
    ValidationSeverity,
)
from app.services.presentation.visual_models_l9 import (
    RenderedSlideArtifact,
    SlideVisualReviewResult,
    VisualCategory,
    VisualCertificationStatus,
    VisualConfidence,
    VisualIssue,
    VisualReviewManifest,
    VisualSeverity,
    compute_visual_manifest_fingerprint,
)

logger = logging.getLogger(__name__)


class MultimodalVisualReviewer:
    """Specialist multimodal visual reviewer for PPT-L9.

    Inspects actual rendered PNG slide images using the configured visual model and pixel analysis.
    - Single specialist (council = 0).
    - Requires actual rendered image (PNG).
    - Receives structured high-level semantic slide context (no raw datasets or sensitive DB queries).
    - Produces schema-validated typed VisualIssue outputs.
    - Zero code generation, zero free-form code execution.
    - Fails safely if model times out, is unavailable, or returns invalid schema (no false certification).
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: float = 30.0,
        enabled: Optional[bool] = None,
    ):
        self.model_name = model_name or config.PRESENTATION_VISUAL_QA_MODEL
        self.base_url = base_url or config.OLLAMA_BASE_URL
        self.timeout_seconds = timeout_seconds
        self.enabled = enabled if enabled is not None else (config.PRESENTATION_VISUAL_QA_MODE == "AI_FULL")
        self.calls_count = 0

    def review_slide_image(
        self,
        artifact: RenderedSlideArtifact,
        semantic_context: dict[str, Any],
        expected_zones: Optional[list[dict[str, Any]]] = None,
    ) -> list[VisualIssue]:
        """Performs multimodal and pixel-level review on a rendered slide artifact."""
        issues: list[VisualIssue] = []
        p = Path(artifact.image_path)
        if not p.exists() or p.stat().st_size == 0:
            return [
                VisualIssue(
                    issue_id=f"VIS-PRE-{artifact.physical_slide_id}",
                    slide_id=artifact.physical_slide_id,
                    severity=VisualSeverity.CRITICAL,
                    category=VisualCategory.RENDER_CORRUPTION,
                    description=f"Rendered artifact missing or empty at '{artifact.image_path}'.",
                    visual_evidence="File does not exist or has 0 bytes.",
                    recommended_owner=RepairOwner.PPT_L6_RENDERER,
                    recommended_action=RepairAction.RENDER_RETRY_REQUIRED,
                    repairable=False,
                )
            ]

        with open(p, "rb") as f:
            img_bytes = f.read()

        # 1. Pixel-Level Visual Inspection
        pixel_issues = self._inspect_image_pixels(img_bytes, artifact, expected_zones)
        issues.extend(pixel_issues)

        # 2. Multimodal Model Inference
        if self.enabled:
            self.calls_count += 1
            img_b64 = base64.b64encode(img_bytes).decode("utf-8")
            model_issues = self._invoke_visual_model(
                artifact=artifact,
                img_b64=img_b64,
                semantic_context=semantic_context,
            )
            issues.extend(model_issues)

        return issues

    def _inspect_image_pixels(
        self,
        img_bytes: bytes,
        artifact: RenderedSlideArtifact,
        expected_zones: Optional[list[dict[str, Any]]] = None,
    ) -> list[VisualIssue]:
        """Inspects actual rendered image pixels for visual defects."""
        issues: list[VisualIssue] = []
        try:
            im = Image.open(io.BytesIO(img_bytes))
            w, h = im.size
            if w <= 0 or h <= 0:
                return issues

            # Check for opaque visual obstruction over expected primary visual zones
            if expected_zones:
                for zone in expected_zones:
                    if zone.get("is_primary_visual", False):
                        bounds = zone.get("bounds")  # (left, top, width, height) in 0.0-1.0 coords
                        if bounds:
                            l, t, bw, bh = bounds
                            crop_box = (
                                int(max(0, l * w)),
                                int(max(0, t * h)),
                                int(min(w, (l + bw) * w)),
                                int(min(h, (t + bh) * h)),
                            )
                            if crop_box[2] > crop_box[0] and crop_box[3] > crop_box[1]:
                                region = im.crop(crop_box).convert("RGB")
                                # Detect if primary visual viewport is blocked by solid opaque black obstruction
                                total_px = region.width * region.height
                                if total_px > 0:
                                    black_px = sum(1 for p in region.getdata() if p[0] < 5 and p[1] < 5 and p[2] < 5)
                                    black_ratio = black_px / float(total_px)
                                    if black_ratio > 0.60:
                                        issues.append(
                                            VisualIssue(
                                                issue_id=f"VIS-PIX-OBS-{artifact.physical_slide_id}",
                                                slide_id=artifact.physical_slide_id,
                                                severity=VisualSeverity.CRITICAL,
                                                category=VisualCategory.PRIMARY_VISUAL_OBSCURED,
                                                description=f"Primary visual region is visually obscured by opaque black block ({black_ratio:.1%} coverage) in rendered pixels.",
                                                visual_evidence=f"Rendered PNG pixels in chart viewport have {black_ratio:.1%} solid black obstruction.",
                                                confidence=VisualConfidence.HIGH,
                                                recommended_owner=RepairOwner.PPT_L5_LAYOUT,
                                                recommended_action=RepairAction.LAYOUT_REPLAN_REQUIRED,
                                                repairable=True,
                                            )
                                        )
        except Exception as e:
            logger.warning(f"Error inspecting pixels for {artifact.physical_slide_id}: {e}")
        return issues

    def _invoke_visual_model(
        self,
        artifact: RenderedSlideArtifact,
        img_b64: str,
        semantic_context: dict[str, Any],
    ) -> list[VisualIssue]:
        """Calls the configured multimodal visual model with image and structured context."""
        slide_id = artifact.physical_slide_id
        system_instruction = (
            "You are the HighView Presentation Visual Critic.\n"
            "Inspect the attached rendered slide screenshot for composition, spacing, hierarchy, and legibility defects.\n"
            "Do NOT check or alter business data or factual numbers.\n"
            "Focus strictly on visual defects observable in the image.\n"
            "Respond ONLY with a valid JSON object matching the schema."
        )

        user_prompt = (
            f"Slide Context:\n"
            f"- Slide ID: {slide_id}\n"
            f"- Topic: {semantic_context.get('semantic_topic', 'Executive Summary')}\n"
            f"- Structural Role: {semantic_context.get('structural_role', 'OVERVIEW')}\n"
            f"- Zones: {semantic_context.get('zone_count', 1)}\n\n"
            f"Schema:\n"
            f'{{"status": "PASS"|"WARNING"|"FAIL", "issues": [{{"category": "VISUAL_OVERLAP"|"PRIMARY_VISUAL_OBSCURED"|"AXIS_LABEL_COLLISION"|"TABLE_UNREADABLE"|"TEXT_CLIPPING"|"EXCESSIVE_WHITESPACE", "severity": "INFO"|"WARNING"|"CRITICAL", "description": "...", "visual_evidence": "...", "affected_objects": ["..."], "recommended_owner": "PPT_L5_LAYOUT"|"PPT_L4_STRUCTURE"|"PPT_L3_EXPANSION"|"PPT_L7_STYLE"|"PPT_L6_RENDERER"|"ASSET_PIPELINE", "recommended_action": "LAYOUT_REPLAN_REQUIRED"|"TABLE_SPLIT_REQUIRED"|"RENDER_RETRY_REQUIRED", "confidence": "HIGH"|"MEDIUM"|"LOW"}}]}}'
        )

        payload = {
            "model": self.model_name,
            "prompt": f"{system_instruction}\n\n{user_prompt}",
            "images": [img_b64],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1, "num_predict": 1024},
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                res = client.post(f"{self.base_url}/api/generate", json=payload)
                if res.status_code != 200:
                    return [
                        VisualIssue(
                            issue_id=f"VIS-AI-ERR-{slide_id}",
                            slide_id=slide_id,
                            severity=VisualSeverity.CRITICAL,
                            category=VisualCategory.RENDER_CORRUPTION,
                            description=f"Visual model endpoint returned HTTP {res.status_code}.",
                            visual_evidence="Inference endpoint failure.",
                            recommended_owner=RepairOwner.PPT_L6_RENDERER,
                            recommended_action=RepairAction.RENDER_RETRY_REQUIRED,
                            repairable=False,
                            confidence=VisualConfidence.HIGH,
                        )
                    ]
                raw_text = res.json().get("response", "")
        except httpx.TimeoutException:
            logger.warning(f"Visual review timed out for slide {slide_id}.")
            return [
                VisualIssue(
                    issue_id=f"VIS-AI-TIMEOUT-{slide_id}",
                    slide_id=slide_id,
                    severity=VisualSeverity.CRITICAL,
                    category=VisualCategory.RENDER_CORRUPTION,
                    description=f"Visual model call timed out after {self.timeout_seconds}s.",
                    visual_evidence="Inference timeout.",
                    recommended_owner=RepairOwner.PPT_L6_RENDERER,
                    recommended_action=RepairAction.RENDER_RETRY_REQUIRED,
                    repairable=False,
                    confidence=VisualConfidence.HIGH,
                )
            ]
        except Exception as e:
            logger.warning(f"Visual review endpoint unreachable for slide {slide_id}: {e}.")
            return [
                VisualIssue(
                    issue_id=f"VIS-AI-UNAVAIL-{slide_id}",
                    slide_id=slide_id,
                    severity=VisualSeverity.CRITICAL,
                    category=VisualCategory.RENDER_CORRUPTION,
                    description=f"Visual model unavailable: {e}.",
                    visual_evidence="Connection failure to model gateway.",
                    recommended_owner=RepairOwner.PPT_L6_RENDERER,
                    recommended_action=RepairAction.RENDER_RETRY_REQUIRED,
                    repairable=False,
                    confidence=VisualConfidence.HIGH,
                )
            ]

        # Parse & Validate Output JSON
        try:
            data = json.loads(raw_text)
            parsed_issues: list[VisualIssue] = []
            for idx, item in enumerate(data.get("issues", [])):
                cat_str = item.get("category", "STYLE_INCONSISTENCY").upper()
                cat = VisualCategory[cat_str] if cat_str in VisualCategory.__members__ else VisualCategory.STYLE_INCONSISTENCY
                sev_str = item.get("severity", "WARNING").upper()
                sev = VisualSeverity[sev_str] if sev_str in VisualSeverity.__members__ else VisualSeverity.WARNING
                owner_str = item.get("recommended_owner", "PPT_L5_LAYOUT").upper()
                owner = RepairOwner[owner_str] if owner_str in RepairOwner.__members__ else RepairOwner.PPT_L5_LAYOUT
                act_str = item.get("recommended_action", "LAYOUT_REPLAN_REQUIRED").upper()
                act = RepairAction[act_str] if act_str in RepairAction.__members__ else RepairAction.LAYOUT_REPLAN_REQUIRED
                conf_str = item.get("confidence", "HIGH").upper()
                conf = VisualConfidence[conf_str] if conf_str in VisualConfidence.__members__ else VisualConfidence.HIGH

                issue = VisualIssue(
                    issue_id=f"VIS-AI-{slide_id}-{idx+1}",
                    slide_id=slide_id,
                    severity=sev,
                    category=cat,
                    affected_object_ids=item.get("affected_objects", []),
                    description=item.get("description", "Multimodal visual observation"),
                    visual_evidence=item.get("visual_evidence", "Observed in rendered image pixels"),
                    confidence=conf,
                    recommended_owner=owner,
                    recommended_action=act,
                    repairable=item.get("repairable", True),
                )
                parsed_issues.append(issue)
            return parsed_issues
        except Exception as e:
            logger.warning(f"Invalid schema in visual model output for slide {slide_id}: {e}")
            return [
                VisualIssue(
                    issue_id=f"VIS-AI-SCHEMA-{slide_id}",
                    slide_id=slide_id,
                    severity=VisualSeverity.CRITICAL,
                    category=VisualCategory.RENDER_CORRUPTION,
                    description=f"Visual model emitted invalid schema: {e}.",
                    visual_evidence="Schema validation failure on model output.",
                    recommended_owner=RepairOwner.PPT_L6_RENDERER,
                    recommended_action=RepairAction.RENDER_RETRY_REQUIRED,
                    repairable=False,
                    confidence=VisualConfidence.HIGH,
                )
            ]


class VisualReviewEngine:
    """The central PPT-L9 Visual Review Engine evaluating actual rendered slide evidence."""

    def __init__(
        self,
        critic: Optional[GemmaVisualCritic] = None,
        reviewer: Optional[MultimodalVisualReviewer] = None,
        review_model: Optional[str] = None,
    ):
        self.review_model = review_model or config.PRESENTATION_VISUAL_QA_MODEL
        self.critic = critic or GemmaVisualCritic(model_name=self.review_model)
        self.reviewer = reviewer or MultimodalVisualReviewer(model_name=self.review_model)

    def review_deck(
        self,
        artifacts: list[RenderedSlideArtifact],
        validation_manifest: ValidationManifest,
        resolved_deck: ResolvedDeckLayout,
        deck_structure: LayeredDeckStructureSpec,
        style_manifest: StyleManifest,
        prs: pptx.presentation.Presentation,
        is_technical_deck: bool = False,
    ) -> VisualReviewManifest:
        """Executes full rendered visual review across all slides in canonical order."""
        deck_id = getattr(deck_structure, "deck_id", getattr(resolved_deck, "deck_id", "default_deck"))
        slide_results: list[SlideVisualReviewResult] = []
        all_visual_issues: list[VisualIssue] = []
        issue_counter = 0

        def _make_issue(
            slide_id: str,
            severity: VisualSeverity,
            category: VisualCategory,
            description: str,
            visual_evidence: str,
            affected_objs: Optional[list[str]] = None,
            owner: RepairOwner = RepairOwner.PPT_L5_LAYOUT,
            action: RepairAction = RepairAction.LAYOUT_REPLAN_REQUIRED,
            confidence: VisualConfidence = VisualConfidence.HIGH,
            deterministic_support: bool = False,
            repairable: bool = True,
        ) -> VisualIssue:
            nonlocal issue_counter
            issue_counter += 1
            issue = VisualIssue(
                issue_id=f"VIS-{issue_counter:04d}",
                slide_id=slide_id,
                severity=severity,
                category=category,
                affected_object_ids=affected_objs or [],
                description=description,
                visual_evidence=visual_evidence,
                confidence=confidence,
                deterministic_support=deterministic_support,
                recommended_owner=owner,
                recommended_action=action,
                repairable=repairable,
            )
            all_visual_issues.append(issue)
            return issue

        # Compute expected aspect ratio from prs dimensions
        slide_w = getattr(prs, "slide_width", 12192000) or 12192000
        slide_h = getattr(prs, "slide_height", 6858000) or 6858000
        deck_aspect_ratio = slide_w / slide_h if slide_h > 0 else (16.0 / 9.0)

        # -----------------------------------------------------------------
        # PER-SLIDE VISUAL REVIEW
        # -----------------------------------------------------------------
        for s_idx, artifact in enumerate(artifacts):
            slide_id = artifact.physical_slide_id
            prs_slide = prs.slides[s_idx] if s_idx < len(prs.slides) else None
            struct_slide = deck_structure.slides[s_idx] if s_idx < len(deck_structure.slides) else None
            layout_slide = resolved_deck.slides[s_idx] if s_idx < len(resolved_deck.slides) else None

            slide_issues: list[VisualIssue] = []

            # 1. Deterministic Visual Precheck
            precheck_issues = DeterministicVisualPrecheck.check_artifact(
                artifact=artifact,
                expected_aspect_ratio=deck_aspect_ratio,
            )
            for pi in precheck_issues:
                issue = _make_issue(
                    slide_id=slide_id,
                    severity=pi.severity,
                    category=pi.category,
                    description=pi.description,
                    visual_evidence=pi.visual_evidence,
                    repairable=pi.repairable,
                )
                slide_issues.append(issue)

            # If precheck failed with corruption, halt review of this slide
            has_corrupt = any(i.severity == VisualSeverity.CRITICAL and i.category == VisualCategory.RENDER_CORRUPTION for i in slide_issues)
            if has_corrupt:
                slide_results.append(
                    SlideVisualReviewResult(
                        physical_slide_id=slide_id,
                        slide_index=s_idx + 1,
                        status=VisualCertificationStatus.FAIL,
                        critical_issues_count=sum(1 for i in slide_issues if i.severity == VisualSeverity.CRITICAL),
                        warnings_count=sum(1 for i in slide_issues if i.severity == VisualSeverity.WARNING),
                        info_count=sum(1 for i in slide_issues if i.severity == VisualSeverity.INFO),
                        issues=slide_issues,
                        render_artifact=artifact,
                    )
                )
                continue

            # 2. Multimodal & Pixel-Level Visual Review (examining actual rendered PNG pixels)
            semantic_ctx = {
                "semantic_topic": getattr(struct_slide, "semantic_topic", ""),
                "structural_role": getattr(struct_slide, "structural_role", ""),
                "zone_count": len(getattr(struct_slide, "zones", [])),
                "object_kinds": [getattr(o, "kind", "") for z in getattr(struct_slide, "zones", []) for o in getattr(z, "objects", [])],
            }
            expected_zones = []
            if layout_slide:
                for obj_l in layout_slide.object_layouts:
                    is_chart = "CHART" in obj_l.object_name.upper() or (struct_slide and any(getattr(o, "kind", "") == "CHART" for z in struct_slide.zones for o in z.objects if o.object_name == obj_l.object_name))
                    expected_zones.append({
                        "object_name": obj_l.object_name,
                        "is_primary_visual": is_chart,
                        "bounds": (obj_l.bounds.left, obj_l.bounds.top, obj_l.bounds.width, obj_l.bounds.height),
                    })
            mm_issues = self.reviewer.review_slide_image(
                artifact=artifact,
                semantic_context=semantic_ctx,
                expected_zones=expected_zones,
            )
            for mmi in mm_issues:
                _make_issue(
                    slide_id=slide_id,
                    severity=mmi.severity,
                    category=mmi.category,
                    description=mmi.description,
                    visual_evidence=mmi.visual_evidence,
                    affected_objs=mmi.affected_object_ids,
                    owner=mmi.recommended_owner,
                    action=mmi.recommended_action,
                    confidence=mmi.confidence,
                    repairable=mmi.repairable,
                )
                slide_issues.append(mmi)

            # 3. Inspect rendered shapes on slide for visual defects
            if prs_slide and struct_slide:
                self._inspect_rendered_shapes(
                    prs_slide=prs_slide,
                    struct_slide=struct_slide,
                    layout_slide=layout_slide,
                    slide_id=slide_id,
                    _make_issue=_make_issue,
                    slide_issues=slide_issues,
                    is_technical_deck=is_technical_deck,
                )

            # 4. Primary Visual Protection Audit
            self._audit_primary_visual_protection(
                prs_slide=prs_slide,
                struct_slide=struct_slide,
                slide_id=slide_id,
                _make_issue=_make_issue,
                slide_issues=slide_issues,
            )

            # Determine slide status
            criticals = sum(1 for i in slide_issues if i.severity == VisualSeverity.CRITICAL)
            warnings = sum(1 for i in slide_issues if i.severity == VisualSeverity.WARNING)
            infos = sum(1 for i in slide_issues if i.severity == VisualSeverity.INFO)

            slide_status = VisualCertificationStatus.VISUALLY_CERTIFIED
            if criticals > 0:
                slide_status = VisualCertificationStatus.REPAIR_REQUIRED

            slide_results.append(
                SlideVisualReviewResult(
                    physical_slide_id=slide_id,
                    slide_index=s_idx + 1,
                    status=slide_status,
                    critical_issues_count=criticals,
                    warnings_count=warnings,
                    info_count=infos,
                    issues=slide_issues,
                    render_artifact=artifact,
                )
            )

        # -----------------------------------------------------------------
        # ISSUE MERGING WITH PPT-L8
        # -----------------------------------------------------------------
        # Unify PPT-L8 deterministic issues with PPT-L9 visual issues
        l8_issues_by_slide: dict[str, list[Any]] = {}
        for l8_i in validation_manifest.issues:
            if l8_i.slide_id:
                l8_issues_by_slide.setdefault(l8_i.slide_id, []).append(l8_i)

        for s_res in slide_results:
            matching_l8 = l8_issues_by_slide.get(s_res.physical_slide_id, [])
            for l8_i in matching_l8:
                # If an equivalent visual issue already exists, link deterministic support
                already_covered = any(
                    vi.category.value == l8_i.category.value or (l8_i.object_name and vi.description and l8_i.object_name in vi.description)
                    for vi in s_res.issues
                )
                if not already_covered:
                    mapped_cat = self._map_l8_category(l8_i.category)
                    mapped_sev = VisualSeverity(l8_i.severity.value)
                    imported_issue = _make_issue(
                        slide_id=s_res.physical_slide_id,
                        severity=mapped_sev,
                        category=mapped_cat,
                        description=f"[Deterministic Support] {l8_i.message}",
                        visual_evidence=f"Deterministically identified by PPT-L8 in category '{l8_i.category.value}'.",
                        affected_objs=[l8_i.object_id] if l8_i.object_id else [],
                        owner=l8_i.recommended_owner or RepairOwner.PPT_L5_LAYOUT,
                        action=l8_i.repair_action or RepairAction.LAYOUT_REPLAN_REQUIRED,
                        deterministic_support=True,
                    )
                    s_res.issues.append(imported_issue)

            s_res.critical_issues_count = sum(1 for i in s_res.issues if i.severity == VisualSeverity.CRITICAL)
            s_res.warnings_count = sum(1 for i in s_res.issues if i.severity == VisualSeverity.WARNING)
            s_res.info_count = sum(1 for i in s_res.issues if i.severity == VisualSeverity.INFO)
            if s_res.status == VisualCertificationStatus.FAIL or any(
                i.severity == VisualSeverity.CRITICAL and not i.repairable for i in s_res.issues
            ):
                s_res.status = VisualCertificationStatus.FAIL
            elif s_res.critical_issues_count > 0:
                s_res.status = VisualCertificationStatus.REPAIR_REQUIRED

        # Severity counts across deck
        total_counts = {
            "CRITICAL": sum(1 for i in all_visual_issues if i.severity == VisualSeverity.CRITICAL),
            "WARNING": sum(1 for i in all_visual_issues if i.severity == VisualSeverity.WARNING),
            "INFO": sum(1 for i in all_visual_issues if i.severity == VisualSeverity.INFO),
        }

        # Overall deck certification decision
        if (
            validation_manifest.status == DeckValidationStatus.FAIL
            or any(s.status == VisualCertificationStatus.FAIL for s in slide_results)
            or any(i.severity == VisualSeverity.CRITICAL and not i.repairable for i in all_visual_issues)
        ):
            deck_status = VisualCertificationStatus.FAIL
        elif total_counts["CRITICAL"] > 0:
            deck_status = VisualCertificationStatus.REPAIR_REQUIRED
        else:
            deck_status = VisualCertificationStatus.VISUALLY_CERTIFIED

        manifest = VisualReviewManifest(
            manifest_id=f"VMAN-{deck_id}",
            deck_id=deck_id,
            status=deck_status,
            slides=slide_results,
            issues=all_visual_issues,
            counts_by_severity=total_counts,
            review_backend="MULTIMODAL_SPECIALIST" if (self.reviewer.enabled or self.reviewer.calls_count > 0) else "DETERMINISTIC_VISUAL",
            review_model=self.review_model,
            render_backend=artifacts[0].renderer_backend if artifacts else "PIL_DRAWINGML_RENDERER",
            stats={
                "total_slides_reviewed": len(slide_results),
                "total_visual_issues": len(all_visual_issues),
                "critical_count": total_counts["CRITICAL"],
                "warning_count": total_counts["WARNING"],
                "info_count": total_counts["INFO"],
                "visual_model_calls": self.reviewer.calls_count,
                "council_calls": 0,
            },
        )
        manifest.visual_fingerprint = compute_visual_manifest_fingerprint(manifest)
        return manifest

    def _inspect_rendered_shapes(
        self,
        prs_slide: Any,
        struct_slide: Any,
        layout_slide: Any,
        slide_id: str,
        _make_issue: Any,
        slide_issues: list[VisualIssue],
        is_technical_deck: bool,
    ) -> None:
        """Inspects rendered slide shapes for visual presentation defects."""
        # Check text boxes for text clipping and excessive density
        for sh in prs_slide.shapes:
            sh_name = (sh.name or "").upper()
            if sh.has_text_frame:
                txt = sh.text_frame.text.strip()

                # 1. Governance leak check (internal developer tags)
                if not is_technical_deck:
                    forbidden_tokens = ["HV_", "EVID-", "SCEN-", "JoinPlan", "{{", "}}"]
                    for token in forbidden_tokens:
                        if token in txt:
                            issue = _make_issue(
                                slide_id=slide_id,
                                severity=VisualSeverity.CRITICAL,
                                category=VisualCategory.STYLE_INCONSISTENCY,
                                description=f"Governance token leak '{token}' visible in rendered text of '{sh.name}'.",
                                visual_evidence=f"Found unrendered token '{token}' in shape text.",
                                affected_objs=[sh.name],
                                owner=RepairOwner.PPT_L4_STRUCTURE,
                                action=RepairAction.LAYOUT_REPLAN_REQUIRED,
                            )
                            slide_issues.append(issue)

                # 2. Text density check (overloaded text box)
                if len(txt) > 400 and ("BODY" in sh_name or "PARAGRAPH" in sh_name or "BULLET" in sh_name):
                    issue = _make_issue(
                        slide_id=slide_id,
                        severity=VisualSeverity.WARNING,
                        category=VisualCategory.TEXT_TOO_DENSE,
                        description=f"Text density exceeds visual readability budget ({len(txt)} chars) in '{sh.name}'.",
                        visual_evidence=f"Rendered text block contains {len(txt)} characters without paragraph splitting.",
                        affected_objs=[sh.name],
                        owner=RepairOwner.PPT_L5_LAYOUT,
                        action=RepairAction.TEXT_REFLOW_REQUIRED,
                    )
                    slide_issues.append(issue)

            # 3. Chart visual checks
            if sh.has_chart:
                chart = sh.chart
                # Check for axis label collisions / tick crowding
                if hasattr(chart, "plots") and len(chart.plots) > 0:
                    plot = chart.plots[0]
                    if hasattr(plot, "categories") and len(plot.categories) > 8:
                        # Crowded categories risk label collision
                        issue = _make_issue(
                            slide_id=slide_id,
                            severity=VisualSeverity.WARNING,
                            category=VisualCategory.AXIS_LABEL_COLLISION,
                            description=f"Chart category count ({len(plot.categories)}) risks x-axis label collision in '{sh.name}'.",
                            visual_evidence=f"Plot contains {len(plot.categories)} adjacent category tick labels.",
                            affected_objs=[sh.name],
                            owner=RepairOwner.PPT_L5_LAYOUT,
                            action=RepairAction.CHART_LABEL_REPLAN_REQUIRED,
                        )
                        slide_issues.append(issue)

                # Check for chart too small relative to slide
                slide_w = prs_slide.part.slide.slide_width if hasattr(prs_slide.part.slide, "slide_width") else 12192000
                if sh.width < int(slide_w * 0.20):
                    issue = _make_issue(
                        slide_id=slide_id,
                        severity=VisualSeverity.CRITICAL,
                        category=VisualCategory.CHART_TOO_SMALL,
                        description=f"Primary chart width is too small ({sh.width} EMUs, <20% canvas width) to be legible in '{sh.name}'.",
                        visual_evidence=f"Chart occupied width is only {sh.width} EMUs.",
                        affected_objs=[sh.name],
                        owner=RepairOwner.PPT_L5_LAYOUT,
                        action=RepairAction.LAYOUT_REPLAN_REQUIRED,
                    )
                    slide_issues.append(issue)

            # 4. Table visual checks
            if sh.has_table:
                tbl = sh.table
                # Check for table dense/unreadable rows
                if len(tbl.rows) > 12:
                    issue = _make_issue(
                        slide_id=slide_id,
                        severity=VisualSeverity.CRITICAL,
                        category=VisualCategory.TABLE_UNREADABLE,
                        description=f"Table row count ({len(tbl.rows)}) exceeds single-slide readability limit in '{sh.name}'.",
                        visual_evidence=f"Rendered table contains {len(tbl.rows)} rows crushed into single viewport.",
                        affected_objs=[sh.name],
                        owner=RepairOwner.PPT_L3_EXPANSION,
                        action=RepairAction.TABLE_SPLIT_REQUIRED,
                    )
                    slide_issues.append(issue)

            # 5. Image & Map visual checks
            if "MAP" in sh_name or "GEO" in sh_name:
                # If map is smaller than 25% of body area
                if sh.width < 2500000 or sh.height < 1500000:
                    issue = _make_issue(
                        slide_id=slide_id,
                        severity=VisualSeverity.WARNING,
                        category=VisualCategory.MAP_UNREADABLE,
                        description=f"Rendered map '{sh.name}' is too small to distinguish geographic regions clearly.",
                        visual_evidence=f"Dimensions ({sh.width}x{sh.height} EMUs) below minimum legible resolution.",
                        affected_objs=[sh.name],
                        owner=RepairOwner.PPT_L5_LAYOUT,
                        action=RepairAction.LAYOUT_REPLAN_REQUIRED,
                    )
                    slide_issues.append(issue)

            if "IMAGE" in sh_name or getattr(sh, "shape_type", None) == MSO_SHAPE_TYPE.PICTURE:
                # Check for bad aspect ratio distortion (extreme stretch)
                if sh.width > 0 and sh.height > 0:
                    ratio = sh.width / sh.height
                    if ratio > 5.0 or ratio < 0.2:
                        issue = _make_issue(
                            slide_id=slide_id,
                            severity=VisualSeverity.WARNING,
                            category=VisualCategory.IMAGE_DISTORTION,
                            description=f"Image shape '{sh.name}' exhibits extreme aspect ratio distortion ({ratio:.2f}).",
                            visual_evidence=f"Rendered aspect ratio is {ratio:.2f}.",
                            affected_objs=[sh.name],
                            owner=RepairOwner.ASSET_PIPELINE,
                            action=RepairAction.ASSET_REPLACEMENT_REQUIRED,
                        )
                        slide_issues.append(issue)

        # 6. Intentional vs Excessive Whitespace Check
        content_shapes = [sh for sh in prs_slide.shapes if not (sh.name and sh.name.startswith("Theme background"))]
        if struct_slide.structural_role not in (StructuralRole.TITLE, StructuralRole.CLOSING):
            # Non-title slide: if total content area is less than 15% of canvas, flag excessive whitespace
            total_area = sum(sh.width * sh.height for sh in content_shapes)
            canvas_area = 12192000 * 6858000
            if total_area < canvas_area * 0.15 and len(content_shapes) > 0:
                issue = _make_issue(
                    slide_id=slide_id,
                    severity=VisualSeverity.WARNING,
                    category=VisualCategory.EXCESSIVE_WHITESPACE,
                    description=f"Slide exhibits excessive unexplained dead space (content covers <15% canvas).",
                    visual_evidence=f"Total content bounding box area: {total_area} EMUs.",
                    owner=RepairOwner.PPT_L5_LAYOUT,
                    action=RepairAction.LAYOUT_REPLAN_REQUIRED,
                )
                slide_issues.append(issue)

    def _audit_primary_visual_protection(
        self,
        prs_slide: Any,
        struct_slide: Any,
        slide_id: str,
        _make_issue: Any,
        slide_issues: list[VisualIssue],
    ) -> None:
        """Ensures the primary visual on analytical slides is never obscured or hidden."""
        if not prs_slide or not struct_slide:
            return

        # Check if slide expects a primary visual (chart, map, table)
        expects_primary = any(
            z.zone_type.value in ("PRIMARY_VISUAL", "DATA_TABLE", "DATA_CHART")
            for z in struct_slide.zones
        )
        if not expects_primary:
            return

        # Locate primary visual shape
        primary_shape = next((sh for sh in prs_slide.shapes if sh.has_chart or sh.has_table or "MAP" in (sh.name or "").upper()), None)
        if not primary_shape:
            issue = _make_issue(
                slide_id=slide_id,
                severity=VisualSeverity.CRITICAL,
                category=VisualCategory.PRIMARY_VISUAL_OBSCURED,
                description="Primary visual expected on analytical slide is missing or completely hidden.",
                visual_evidence="No chart, table, or map shape found on slide viewport.",
                owner=RepairOwner.PPT_L6_RENDERER,
                action=RepairAction.LAYOUT_REPLAN_REQUIRED,
            )
            slide_issues.append(issue)
            return

        # Check if another shape obscures the primary visual (e.g. control or card placed directly over it)
        for sh in prs_slide.shapes:
            if sh == primary_shape or (sh.name and sh.name.startswith("Theme background")):
                continue
            # Check overlap with primary shape
            left_max = max(primary_shape.left, sh.left)
            right_min = min(primary_shape.left + primary_shape.width, sh.left + sh.width)
            top_max = max(primary_shape.top, sh.top)
            bottom_min = min(primary_shape.top + primary_shape.height, sh.top + sh.height)

            if right_min > left_max and bottom_min > top_max:
                overlap_w = right_min - left_max
                overlap_h = bottom_min - top_max
                overlap_area = overlap_w * overlap_h
                primary_area = primary_shape.width * primary_shape.height
                overlap_ratio = overlap_area / primary_area if primary_area > 0 else 0.0

                # If an unrelated shape covers > 35% of the primary visual, flag as PRIMARY_VISUAL_OBSCURED
                if overlap_ratio > 0.35 and not (sh.name and "CONTAINER" in sh.name.upper() and sh.width >= primary_shape.width):
                    issue = _make_issue(
                        slide_id=slide_id,
                        severity=VisualSeverity.CRITICAL,
                        category=VisualCategory.PRIMARY_VISUAL_OBSCURED,
                        description=f"Primary visual '{primary_shape.name}' is materially obscured by '{sh.name}' ({overlap_ratio:.1%} overlap).",
                        visual_evidence=f"Interference area {overlap_area} EMUs obscuring primary data visualization.",
                        affected_objs=[primary_shape.name, sh.name],
                        owner=RepairOwner.PPT_L5_LAYOUT,
                        action=RepairAction.LAYOUT_REPLAN_REQUIRED,
                    )
                    slide_issues.append(issue)

    def _map_l8_category(self, cat: ValidationCategory) -> VisualCategory:
        """Maps PPT-L8 deterministic validation categories to PPT-L9 visual categories."""
        mapping = {
            ValidationCategory.TEXT_CLIPPING: VisualCategory.TEXT_CLIPPING,
            ValidationCategory.COLLISION: VisualCategory.VISUAL_OVERLAP,
            ValidationCategory.SAFE_AREA: VisualCategory.FRAME_COLLISION,
            ValidationCategory.GEOMETRY: VisualCategory.ALIGNMENT_DEFECT,
            ValidationCategory.CONTRAST: VisualCategory.CONTRAST_DEFECT,
            ValidationCategory.STYLE_REFLOW_RISK: VisualCategory.TEXT_CLIPPING,
            ValidationCategory.GOVERNANCE_LEAK: VisualCategory.STYLE_INCONSISTENCY,
            ValidationCategory.PACKAGE_INTEGRITY: VisualCategory.RENDER_CORRUPTION,
            ValidationCategory.CONTINUATION_SEQUENCE: VisualCategory.CONTINUATION_VISUAL_DEFECT,
            ValidationCategory.OBJECT_EXISTENCE: VisualCategory.PRIMARY_VISUAL_OBSCURED,
        }
        return mapping.get(cat, VisualCategory.ALIGNMENT_DEFECT)
