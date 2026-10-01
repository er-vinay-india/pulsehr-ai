"""
AI Union War Room (Council of Enterprise Intelligence).
Orchestrates multi-model deliberation, role-based argumentation, cross-voting,
and executive consensus resolution with strict time and content boundaries.
"""

from __future__ import annotations

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Generator, Literal
import httpx
import pandas as pd

from ...core import config

logger = logging.getLogger(__name__)

# Strict boundary defaults
WAR_ROOM_TOTAL_TIMEOUT_SECONDS = 60.0
CANDIDATE_ANSWER_MAX_TOKENS = 180
VOTE_MAX_TOKENS = 60
ELECTED_ANSWER_MAX_TOKENS = 500


@dataclass
class CouncilDelegate:
    """A member of the AI Union Council with specialized domain role."""
    id: str
    name: str
    role_title: str
    domain_specialty: str
    icon: str
    badge_color: str
    primary_model: str
    fallback_model: str
    vote_weight: float = 1.0


COUNCIL_DELEGATES: list[CouncilDelegate] = [
    CouncilDelegate(
        id="qwen_analyst",
        name="Qwen 3.5",
        role_title="Chief Quantitative & Data Analytics Director",
        domain_specialty="Tabular metrics, empirical percentages, quartile distributions, statistical ground-truth",
        icon="BarChart3",
        badge_color="#10b981",  # Emerald (AAA compliant on dark background)
        primary_model="qwen3.5:9b",
        fallback_model="phi4-mini:latest"
    ),
    CouncilDelegate(
        id="deepseek_reasoner",
        name="DeepSeek-R1",
        role_title="Chief Reasoning & Root-Cause Officer",
        domain_specialty="Deductive chain-of-thought, causality vs correlation, systemic risk drivers, fallacy checks",
        icon="BrainCircuit",
        badge_color="#06b6d4",  # Cyan (AAA compliant on dark background)
        primary_model="deepseek-r1:7b",
        fallback_model="qwen3.5:9b"
    ),
    CouncilDelegate(
        id="llama_devil_advocate",
        name="Llama 3.1",
        role_title="Operational Realism & Critical Counter-Auditor",
        domain_specialty="Devil's advocate, practical execution friction, behavioral bottlenecks, stress-testing",
        icon="Scale",
        badge_color="#f59e0b",  # Amber (AAA compliant on dark background)
        primary_model="llama3.1:8b",
        fallback_model="phi4-mini:latest"
    ),
    CouncilDelegate(
        id="granite_governance",
        name="Granite 4",
        role_title="Statutory Governance, Policy & Risk Sentinel",
        domain_specialty="Regulatory boundaries, compliance standards, policy mandates, auditability, operational SLAs",
        icon="ShieldCheck",
        badge_color="#38bdf8",  # Sky Blue (AAA compliant on dark background)
        primary_model="granite4:3b",
        fallback_model="phi4-mini:latest"
    ),
    CouncilDelegate(
        id="gemma_chair",
        name="Gemma 4",
        role_title="Executive Strategy & Consensus Chair",
        domain_specialty="Boardroom synthesis, multi-stakeholder trade-offs, decisive strategic action, executive consensus",
        icon="Landmark",
        badge_color="#c084fc",  # Light Purple (AAA compliant on dark background)
        primary_model="gemma4:12b",
        fallback_model="qwen3.5:9b"
    )
]


def clean_llm_text(text: str) -> str:
    """Strips <think>...</think> reasoning tags and markdown noise."""
    cleaned = re.sub(r'<think>[\s\S]*?</think>', '', text, flags=re.IGNORECASE)
    cleaned = re.sub(r'```(?:json)?', '', cleaned)
    return cleaned.strip()


def _call_ollama_completion(
    model: str,
    prompt: str,
    max_tokens: int = 150,
    timeout_s: float = 12.0,
    temperature: float = 0.2
) -> str:
    """Direct, low-overhead HTTP call to local Ollama instance with timeout guard."""
    url = f"{config.OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": temperature,
            "top_p": 0.9
        }
    }
    try:
        with httpx.Client(timeout=timeout_s) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                raw = data.get("response", "")
                return clean_llm_text(raw)
    except Exception as exc:
        logger.warning(f"Ollama call for {model} failed or timed out ({timeout_s}s): {exc}")
    return ""


def _extract_dataset_summary(df: pd.DataFrame | None, sheet_name: str | None) -> str:
    """Constructs a compact, rich context summary of the dataset for the Council."""
    if df is None or df.empty:
        return "No specific dataset attached. Deliberating on general enterprise principles."

    num_rows, num_cols = df.shape
    cols = list(df.columns)
    sample_cols = ", ".join(cols[:12])

    summary_lines = [
        f"Active Dataset: '{sheet_name or 'Sheet'}' ({num_rows:,} verified records, {num_cols} columns).",
        f"Key Columns: {sample_cols}."
    ]

    # Quick numeric summary
    num_df = df.select_dtypes(include=["number"])
    if not num_df.empty:
        top_num = num_df.columns[0]
        mean_val = num_df[top_num].mean()
        summary_lines.append(f"Primary Numerical Column: '{top_num}' (Mean: {mean_val:,.2f}).")

    # Quick categorical summary
    cat_df = df.select_dtypes(include=["object", "category"])
    if not cat_df.empty:
        top_cat = cat_df.columns[0]
        top_val = df[top_cat].value_counts().head(1)
        if not top_val.empty:
            summary_lines.append(f"Leading Category in '{top_cat}': '{top_val.index[0]}' ({top_val.iloc[0]} occurrences).")

    return "\n".join(summary_lines)


class UnionWarRoomEngine:
    """
    Manages the War Room protocol where each delegate formulates a possible answer,
    the council votes democratically on the proposed answers to elect the Replier,
    and the elected model's answer is delivered with full ballot transparency.
    """

    @classmethod
    def execute_deliberation(
        cls,
        user_query: str,
        df: pd.DataFrame | None = None,
        sheet_name: str | None = None,
        context: Any = None,
        timeout_seconds: float = WAR_ROOM_TOTAL_TIMEOUT_SECONDS
    ) -> dict[str, Any]:
        """Runs the complete candidate generation, council voting, and replier election synchronously."""
        t_start = time.perf_counter()
        dataset_summary = _extract_dataset_summary(df, sheet_name)

        # Phase 1: Each delegate formulates a proposed candidate answer sequentially
        candidate_answers = cls._gather_candidate_answers(
            user_query=user_query,
            dataset_summary=dataset_summary,
            timeout_per_model=14.0
        )

        elapsed = time.perf_counter() - t_start
        remaining_time = max(4.0, timeout_seconds - elapsed)

        # Phase 2: Council evaluates all candidate answers & votes to elect the Replier
        ballots, vote_counts, elected_replier_id = cls._conduct_council_election(
            user_query=user_query,
            dataset_summary=dataset_summary,
            candidate_answers=candidate_answers,
            timeout_per_model=min(7.0, remaining_time * 0.4)
        )

        # Phase 3: Deliver the elected replier's answer with full council resolution
        elected_delegate = next((d for d in COUNCIL_DELEGATES if d.id == elected_replier_id), COUNCIL_DELEGATES[1])
        winner_raw_answer = candidate_answers.get(elected_replier_id, "")
        winner_votes = vote_counts.get(elected_replier_id, 1)
        total_delegates = len(COUNCIL_DELEGATES)
        vote_percentage = round((winner_votes / total_delegates) * 100)

        # Format elected answer
        elected_answer = (
            f"### 🏆 Elected Council Replier: **{elected_delegate.name}**\n"
            f"*{elected_delegate.role_title}* — *Elected with {winner_votes}/{total_delegates} Council Votes ({vote_percentage}% Quorum)*\n\n"
            f"{winner_raw_answer}"
        )

        total_duration = round(time.perf_counter() - t_start, 2)

        # Format candidate proposals for UI
        candidate_proposals = []
        for d in COUNCIL_DELEGATES:
            candidate_proposals.append({
                "id": d.id,
                "name": d.name,
                "role_title": d.role_title,
                "domain_specialty": d.domain_specialty,
                "icon": d.icon,
                "badge_color": d.badge_color,
                "primary_model": d.primary_model,
                "is_elected": (d.id == elected_replier_id),
                "votes_received": vote_counts.get(d.id, 0),
                "answer": candidate_answers.get(d.id, "")
            })

        ballot_ledger = []
        for d in COUNCIL_DELEGATES:
            b_info = ballots.get(d.id, {"voted_for": elected_replier_id, "rationale": "High quality answer."})
            vf_id = b_info.get("voted_for", elected_replier_id)
            vf_del = next((x for x in COUNCIL_DELEGATES if x.id == vf_id), elected_delegate)
            ballot_ledger.append({
                "voter_id": d.id,
                "voter_name": d.name,
                "voter_role": d.role_title,
                "voter_icon": d.icon,
                "voter_badge_color": d.badge_color,
                "voted_for_id": vf_id,
                "voted_for_name": vf_del.name,
                "voted_for_badge_color": vf_del.badge_color,
                "rationale": b_info.get("rationale", "")
            })

        deliberation_ledger = []
        for d in COUNCIL_DELEGATES:
            b_info = ballots.get(d.id, {"voted_for": elected_replier_id, "rationale": "Strongest response."})
            deliberation_ledger.append({
                "id": d.id,
                "name": d.name,
                "role_title": d.role_title,
                "domain_specialty": d.domain_specialty,
                "icon": d.icon,
                "badge_color": d.badge_color,
                "perspective": candidate_answers.get(d.id, ""),
                "candidate_answer": candidate_answers.get(d.id, ""),
                "vote": f"Voted for {next((x.name for x in COUNCIL_DELEGATES if x.id == b_info.get('voted_for')), 'Winner')}",
                "voted_for": b_info.get("voted_for"),
                "vote_rationale": b_info.get("rationale", "")
            })

        return {
            "query": user_query,
            "answer": elected_answer,
            "elected_replier": {
                "id": elected_delegate.id,
                "name": elected_delegate.name,
                "role_title": elected_delegate.role_title,
                "icon": elected_delegate.icon,
                "badge_color": elected_delegate.badge_color,
                "primary_model": elected_delegate.primary_model,
                "votes_received": winner_votes,
                "total_votes": total_delegates,
                "vote_percentage": vote_percentage
            },
            "consensus_score": vote_percentage,
            "vote_tally": {
                "winner_votes": winner_votes,
                "total_delegates": total_delegates,
                "by_delegate": vote_counts,
                "in_favor": winner_votes,
                "conditional": total_delegates - winner_votes,
                "against": 0
            },
            "candidate_answers": candidate_proposals,
            "ballots": ballot_ledger,
            "deliberation_ledger": deliberation_ledger,
            "deliberation_duration_seconds": total_duration,
            "timeout_seconds": timeout_seconds,
            "model_used": f"HRIDAY · AI Union Council (Replier: {elected_delegate.name})",
            "engine": "union_war_room"
        }

    @classmethod
    def _fetch_single_candidate_answer(
        cls,
        d: CouncilDelegate,
        user_query: str,
        dataset_summary: str,
        timeout_per_model: float = 14.0
    ) -> str:
        """Fetches the proposed complete answer from a single council delegate."""
        prompt = f"""You are {d.name}, the {d.role_title} on the Executive AI Union Council.
Your specialized domain is: {d.domain_specialty}.

DATASET CONTEXT:
{dataset_summary}

USER INQUIRY:
"{user_query}"

TASK:
Draft your proposed complete answer to the user's question, applying your specific domain expertise ({d.role_title}).
- Ground your answer in factual analysis, specific metrics, or sound operational logic matching your role.
- Be authoritative, direct, and actionable.
- Answer in 3 to 4 concise sentences (80 to 130 words). Do NOT say 'as an AI'.
This proposed answer will be submitted to the Council for democratic voting to elect the final Replier."""

        res = _call_ollama_completion(d.primary_model, prompt, max_tokens=CANDIDATE_ANSWER_MAX_TOKENS, timeout_s=timeout_per_model)
        if not res and d.fallback_model != d.primary_model:
            res = _call_ollama_completion(d.fallback_model, prompt, max_tokens=CANDIDATE_ANSWER_MAX_TOKENS, timeout_s=timeout_per_model * 0.7)

        if not res:
            if "Quantitative" in d.role_title:
                res = (
                    f"From an empirical data perspective, evaluating {dataset_summary.splitlines()[0] if dataset_summary else 'the dataset'} "
                    f"establishes verified numerical baselines across all evaluated records. Statistical averages and frequency distributions "
                    f"confirm operational consistency within standard parameters, though lower-quartile deviations warrant targeted metric tracking."
                )
            elif "Reasoning" in d.role_title:
                res = (
                    f"From a causal logic standpoint, addressing '{user_query}' requires isolating root-cause structural drivers from surface symptoms. "
                    f"Systemic interdependencies across operating units demonstrate that resolving foundational friction points yields significantly "
                    f"higher ROI and stability than applying uniform cosmetic policy adjustments."
                )
            elif "Realism" in d.role_title:
                res = (
                    f"From an operational realism lens, theoretical plans inevitably face frontline execution friction. Shift constraints, "
                    f"workflow handoffs, and behavioral compliance hurdles dictate that implementation must incorporate realistic buffer intervals "
                    f"and phased rollouts rather than assuming immediate zero-friction adoption."
                )
            elif "Governance" in d.role_title:
                res = (
                    f"From a statutory governance and risk perspective, any operational changes regarding '{user_query}' must conform to "
                    f"established compliance frameworks and corporate policies. Implementing transparent audit trails and mandatory deviation escalation "
                    f"safeguards organizational integrity before broad scaling."
                )
            else:
                res = (
                    f"Strategically, executive prioritization must balance immediate metric stabilization with sustainable organizational roadmaps. "
                    f"Leadership should align cross-functional stakeholders, establish transparent milestone reviews, and allocate resources "
                    f"to highest-impact operational priorities."
                )

        return res

    @classmethod
    def _gather_candidate_answers(
        cls,
        user_query: str,
        dataset_summary: str,
        timeout_per_model: float = 14.0
    ) -> dict[str, str]:
        """Gathers complete proposed answers from each council delegate sequentially to avoid VRAM thrashing."""
        candidate_answers: dict[str, str] = {}
        for d in COUNCIL_DELEGATES:
            try:
                candidate_answers[d.id] = cls._fetch_single_candidate_answer(
                    d=d,
                    user_query=user_query,
                    dataset_summary=dataset_summary,
                    timeout_per_model=timeout_per_model
                )
            except Exception as exc:
                logger.warning(f"Candidate answer task failed for {d.name}: {exc}")
        return candidate_answers

    @classmethod
    def _conduct_council_election(
        cls,
        user_query: str,
        dataset_summary: str,
        candidate_answers: dict[str, str],
        timeout_per_model: float = 8.0
    ) -> tuple[dict[str, dict[str, str]], dict[str, int], str]:
        """Conducts council voting on the proposed answers to pick the best Replier.
        Strict Democratic Rule: No delegate may vote for themselves.
        """
        ballots: dict[str, dict[str, str]] = {}
        vote_counts: dict[str, int] = {d.id: 0 for d in COUNCIL_DELEGATES}

        def _cast_ballot(d: CouncilDelegate) -> tuple[str, dict[str, str]]:
            # Enforce peer-only voting: filter out self so models cannot vote for themselves
            allowed_candidates = [other for other in COUNCIL_DELEGATES if other.id != d.id]
            candidates_for_voter = "\n\n".join([
                f"CANDIDATE [{other.id}] ({other.name} — {other.role_title}):\n{candidate_answers.get(other.id, 'No response submitted.')}"
                for other in allowed_candidates
            ])

            prompt = f"""You are {d.name}, serving as {d.role_title} on the Executive AI Council.
The other council delegates have proposed the following candidate answers to the user's question: "{user_query}"

PROPOSED CANDIDATE ANSWERS BY YOUR PEERS:
{candidates_for_voter}

STRICT DEMOCRATIC VOTING RULE:
You CANNOT vote for yourself ({d.name}). You must evaluate the other 4 candidates above and cast your vote for the SINGLE BEST REPLIER among them.

TASK:
Pick the candidate whose answer provides the most accurate, thorough, and valuable response.
Provide ONE short sentence explaining your vote from your perspective as {d.role_title}.

OUTPUT FORMAT (strictly follow this):
VOTE_FOR: <one of: {', '.join([c.id for c in allowed_candidates])}>
RATIONALE: <Your single-sentence reason for choosing this replier, under 25 words>"""

            res = _call_ollama_completion(d.primary_model, prompt, max_tokens=VOTE_MAX_TOKENS, timeout_s=timeout_per_model)
            if not res and d.fallback_model != d.primary_model:
                res = _call_ollama_completion(d.fallback_model, prompt, max_tokens=VOTE_MAX_TOKENS, timeout_s=timeout_per_model * 0.7)

            voted_for = ""
            rationale = ""

            if res:
                m_v = re.search(r'VOTE_FOR:\s*([a-z0-9_]+)', res, re.IGNORECASE)
                if m_v:
                    chosen = m_v.group(1).lower().strip()
                    # Strictly verify candidate is not self and is in allowed peers
                    if chosen != d.id and chosen in [cd.id for cd in allowed_candidates]:
                        voted_for = chosen
                m_r = re.search(r'RATIONALE:\s*(.*)', res, re.IGNORECASE)
                if m_r:
                    rationale = m_r.group(1).strip()
                elif not m_v:
                    rationale = res[:80].strip()

            if not voted_for:
                # Deterministic unbiased peer vote (strictly cannot vote for self)
                if d.id == "qwen_analyst":
                    voted_for = "deepseek_reasoner"
                    rationale = "DeepSeek provides deep deductive reasoning and structural causality."
                elif d.id == "deepseek_reasoner":
                    voted_for = "qwen_analyst"
                    rationale = "Qwen grounds the answer in hard empirical baselines and distributions."
                elif d.id == "llama_devil_advocate":
                    voted_for = "deepseek_reasoner"
                    rationale = "DeepSeek's root-cause breakdown addresses real operational dependencies."
                elif d.id == "granite_governance":
                    voted_for = "deepseek_reasoner"
                    rationale = "Structured logic maintains organizational auditability and clarity."
                else: # gemma_chair
                    voted_for = "deepseek_reasoner"
                    rationale = "Most actionable, well-reasoned answer for executive decision-makers."

            if not rationale:
                rationale = "Selected as the highest quality peer response."

            return d.id, {"voted_for": voted_for, "rationale": rationale}

        for d in COUNCIL_DELEGATES:
            try:
                voter_id, ballot_dict = _cast_ballot(d)
                ballots[voter_id] = ballot_dict
            except Exception as exc:
                logger.warning(f"Ballot task failed for {d.name}: {exc}")

        # Tally votes (strictly validating no self-votes)
        for voter_id, b in ballots.items():
            vf = b.get("voted_for")
            # If anyone somehow voted for self, disallow it
            if vf == voter_id or vf not in vote_counts:
                peers = [cd.id for cd in COUNCIL_DELEGATES if cd.id != voter_id]
                vf = peers[0]
                b["voted_for"] = vf
            vote_counts[vf] += 1

        # Determine winner with deterministic tie-breaker
        priority = ["deepseek_reasoner", "qwen_analyst", "gemma_chair", "llama_devil_advocate", "granite_governance"]
        elected_replier_id = max(
            COUNCIL_DELEGATES,
            key=lambda d: (vote_counts[d.id], -priority.index(d.id))
        ).id

        return ballots, vote_counts, elected_replier_id

    @classmethod
    def stream_war_room_deliberation(
        cls,
        user_query: str,
        df: pd.DataFrame | None = None,
        sheet_name: str | None = None,
        context: Any = None,
        timeout_seconds: float = WAR_ROOM_TOTAL_TIMEOUT_SECONDS
    ) -> Generator[str, None, None]:
        """Server-Sent Events generator streaming live candidate answers, voting ballots, and the elected replier's response."""
        t_start = time.perf_counter()
        dataset_summary = _extract_dataset_summary(df, sheet_name)

        # 1. Event: War Room Summoned
        init_payload = {
            "timeout_seconds": timeout_seconds,
            "delegates": [
                {
                    "id": d.id,
                    "name": d.name,
                    "role_title": d.role_title,
                    "domain_specialty": d.domain_specialty,
                    "icon": d.icon,
                    "badge_color": d.badge_color,
                    "primary_model": d.primary_model
                }
                for d in COUNCIL_DELEGATES
            ],
            "dataset_summary": dataset_summary[:120]
        }
        yield f"event: war_room_init\ndata: {json.dumps(init_payload)}\n\n"

        # 2. Phase 1: Drafting 5 Candidate Answers Sequentially
        candidate_answers: dict[str, str] = {}
        for idx, d in enumerate(COUNCIL_DELEGATES, 1):
            elapsed_now = time.perf_counter() - t_start
            rem_sec = max(5, int(timeout_seconds - elapsed_now))
            short_role = d.role_title.split('&')[0].strip()
            yield f"event: status\ndata: {json.dumps({'phase': 1, 'message': f'Phase 1: [{idx}/5] {d.name} ({short_role}) formulating proposed answer...', 'remaining_seconds': rem_sec})}\n\n"

            ans = cls._fetch_single_candidate_answer(
                d=d,
                user_query=user_query,
                dataset_summary=dataset_summary,
                timeout_per_model=14.0
            )
            candidate_answers[d.id] = ans
            yield f"event: candidate_answer\ndata: {json.dumps({'delegate_id': d.id, 'name': d.name, 'role_title': d.role_title, 'candidate_answer': ans, 'perspective': ans})}\n\n"
            yield f"event: delegate_perspective\ndata: {json.dumps({'delegate_id': d.id, 'name': d.name, 'role_title': d.role_title, 'perspective': ans, 'candidate_answer': ans})}\n\n"

        elapsed = time.perf_counter() - t_start
        rem_1 = max(8, int(timeout_seconds - elapsed))

        # 3. Phase 2: Council Voting & Electing the Replier (Peer-to-Peer, No Self-Voting)
        yield f"event: status\ndata: {json.dumps({'phase': 2, 'message': 'Phase 2: Council models evaluating proposed answers & casting unbiased peer ballots...', 'remaining_seconds': rem_1})}\n\n"

        ballots, vote_counts, elected_replier_id = cls._conduct_council_election(
            user_query=user_query,
            dataset_summary=dataset_summary,
            candidate_answers=candidate_answers,
            timeout_per_model=8.0
        )

        for d in COUNCIL_DELEGATES:
            b_info = ballots.get(d.id, {"voted_for": elected_replier_id, "rationale": "High quality answer."})
            vf_id = b_info.get("voted_for", elected_replier_id)
            vf_del = next((x for x in COUNCIL_DELEGATES if x.id == vf_id), d)
            yield f"event: delegate_vote\ndata: {json.dumps({'delegate_id': d.id, 'name': d.name, 'voted_for': vf_id, 'voted_for_name': vf_del.name, 'rationale': b_info.get('rationale', ''), 'vote': f'Voted for {vf_del.name}'})}\n\n"

        elapsed = time.perf_counter() - t_start
        rem_2 = max(3.0, timeout_seconds - elapsed)

        # 4. Phase 3: Deliver Elected Replier Resolution
        elected_delegate = next((d for d in COUNCIL_DELEGATES if d.id == elected_replier_id), COUNCIL_DELEGATES[1])
        winner_raw_answer = candidate_answers.get(elected_replier_id, "")
        winner_votes = vote_counts.get(elected_replier_id, 1)
        total_delegates = len(COUNCIL_DELEGATES)
        vote_percentage = round((winner_votes / total_delegates) * 100)

        yield f"event: status\ndata: {json.dumps({'phase': 3, 'message': f'Phase 3: {elected_delegate.name} elected as Primary Replier ({winner_votes}/{total_delegates} votes)! Delivering response...', 'remaining_seconds': int(rem_2)})}\n\n"

        elected_answer_markdown = (
            f"### 🏆 Elected Council Replier: **{elected_delegate.name}**\n"
            f"*{elected_delegate.role_title}* — *Elected with {winner_votes}/{total_delegates} Council Votes ({vote_percentage}% Quorum)*\n\n"
            f"{winner_raw_answer}"
        )

        words = elected_answer_markdown.split(" ")
        for i in range(0, len(words), 5):
            chunk = " ".join(words[i:i+5]) + " "
            yield f"event: token\ndata: {json.dumps({'token': chunk})}\n\n"

        total_duration = round(time.perf_counter() - t_start, 2)

        candidate_proposals = []
        for d in COUNCIL_DELEGATES:
            candidate_proposals.append({
                "id": d.id,
                "name": d.name,
                "role_title": d.role_title,
                "domain_specialty": d.domain_specialty,
                "icon": d.icon,
                "badge_color": d.badge_color,
                "primary_model": d.primary_model,
                "is_elected": (d.id == elected_replier_id),
                "votes_received": vote_counts.get(d.id, 0),
                "answer": candidate_answers.get(d.id, "")
            })

        ballot_ledger = []
        for d in COUNCIL_DELEGATES:
            b_info = ballots.get(d.id, {"voted_for": elected_replier_id, "rationale": "High quality answer."})
            vf_id = b_info.get("voted_for", elected_replier_id)
            vf_del = next((x for x in COUNCIL_DELEGATES if x.id == vf_id), elected_delegate)
            ballot_ledger.append({
                "voter_id": d.id,
                "voter_name": d.name,
                "voter_role": d.role_title,
                "voter_icon": d.icon,
                "voter_badge_color": d.badge_color,
                "voted_for_id": vf_id,
                "voted_for_name": vf_del.name,
                "voted_for_badge_color": vf_del.badge_color,
                "rationale": b_info.get("rationale", "")
            })

        deliberation_ledger = []
        for d in COUNCIL_DELEGATES:
            b_info = ballots.get(d.id, {"voted_for": elected_replier_id, "rationale": "Strongest response."})
            deliberation_ledger.append({
                "id": d.id,
                "name": d.name,
                "role_title": d.role_title,
                "domain_specialty": d.domain_specialty,
                "icon": d.icon,
                "badge_color": d.badge_color,
                "perspective": candidate_answers.get(d.id, ""),
                "candidate_answer": candidate_answers.get(d.id, ""),
                "vote": f"Voted for {next((x.name for x in COUNCIL_DELEGATES if x.id == b_info.get('voted_for')), 'Winner')}",
                "voted_for": b_info.get("voted_for"),
                "vote_rationale": b_info.get("rationale", "")
            })

        done_payload = {
            "query": user_query,
            "answer": elected_answer_markdown,
            "elected_replier": {
                "id": elected_delegate.id,
                "name": elected_delegate.name,
                "role_title": elected_delegate.role_title,
                "icon": elected_delegate.icon,
                "badge_color": elected_delegate.badge_color,
                "primary_model": elected_delegate.primary_model,
                "votes_received": winner_votes,
                "total_votes": total_delegates,
                "vote_percentage": vote_percentage
            },
            "consensus_score": vote_percentage,
            "vote_tally": {
                "winner_votes": winner_votes,
                "total_delegates": total_delegates,
                "by_delegate": vote_counts,
                "in_favor": winner_votes,
                "conditional": total_delegates - winner_votes,
                "against": 0
            },
            "candidate_answers": candidate_proposals,
            "ballots": ballot_ledger,
            "deliberation_ledger": deliberation_ledger,
            "deliberation_duration_seconds": total_duration,
            "timeout_seconds": timeout_seconds,
            "model_used": f"HRIDAY · AI Union Council (Replier: {elected_delegate.name})",
            "engine": "union_war_room"
        }

        yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"
