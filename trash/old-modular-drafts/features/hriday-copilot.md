# HRIDAY Copilot & Identity Architecture

> **Parent:** [README.md](../../README.md) &rsaquo; Features

## 1. Unified Persona Architecture (`assistant_identity.py`)

Across all three backend inference transports—`ModelGateway`, Multi-Model Council (`union_war_room.py`), and conversational copilot (`copilot.py`)—the user-facing assistant identity is strictly **HRIDAY** within the **HighView** application:

```text
User: "Who are you?"
HRIDAY: "I'm HRIDAY, the AI assistant in HighView."

User: "Which model is powering this response?"
HRIDAY: "I'm HRIDAY, and this response is powered by phi4-mini:latest."
```

### Configuration (`backend/app/core/config.py`)
- `ASSISTANT_NAME`: `HRIDAY`
- `ASSISTANT_PRODUCT_NAME`: `HighView`
- `ASSISTANT_IDENTITY_ENABLED`: `true`
- `ASSISTANT_HIDE_MODEL_IDENTITY`: `true` (intercepts unprompted model self-introductions)
- `ASSISTANT_ALLOW_MODEL_DISCLOSURE`: `true` (allows truthful disclosure only when explicitly asked)

---

## 2. Model Roles & Configuration (`models_config.py`)

Local inference is organized into 5 logical model roles with automatic fallbacks:

| Role | Primary Model | Fallback Model | Max Tokens | Target Task Types |
| :--- | :--- | :--- | :---: | :--- |
| **`FAST`** | `phi4-mini:latest` | `llama3.1:8b` | 2,048 | Schema naming, column classification, quick metadata (<250ms). |
| **`ANALYST`** | `qwen3.5:9b` | `gemma4:12b` | 2,048 | Pattern discovery, finding interpretation, metric prioritization (~1.5s). |
| **`REASONER`** | `deepseek-r1:7b` | `qwen3.5:9b` | 4,096 | Deep root-cause analysis, strategic trade-offs, causal reasoning (~3.5s). |
| **`WRITER`** | `gemma4:12b` | `qwen3.5:9b` | 4,096 | Executive narrative prose, slide bullet points, leadership memos (~1.8s). |
| **`CRITIC`** | `deepseek-r1:7b` | `llama3.1:8b` | 3,072 | Factual claim verification, contradiction checks, hallucination audit. |

### Confidence-Based Escalation
`ModelRouter.should_escalate()` automatically escalates requests if confidence falls below threshold:
- `FAST` &rarr; `ANALYST` if confidence < 0.65 or schema invalid.
- `ANALYST` &rarr; `REASONER` if confidence < 0.50 or schema invalid.

---

## 3. Leakage Guard & Bounded Retries

- **Guard Function (`identity_leak`)**: Scans candidate responses for unasked self-identifications (e.g., `I am DeepSeek`, `As Qwen`, `My name is Phi`) outside of code blocks.
- **Bounded Retry**: On leakage detection, triggers at most **1 corrective retry** with an identity reminder, preserving the original query and schema.

---

## 4. Analytical Query Grain Invariant

> **Acceptance Principle**: Retrieving a nearby department insight is never proof of an employee calculation.

- When a user asks an employee-level question (e.g. "What was John's absenteeism in Q3?"), HRIDAY must execute calculation directly at the employee row grain.
- The assistant is forbidden from returning a department-level aggregate as a substitute for an individual calculation.
- Conversational follow-ups maintain the active entity and grain scope until explicitly changed by the user.

---

## 5. Copilot Endpoints (`backend/app/routers/copilot.py`)

- `POST /api/copilot/generic`: Factual Q&A with 0-LLM math via `GenericCopilotEngine`.
- `POST /api/copilot/query`: Conversational endpoint with deterministic intent auto-routing.
- `POST /api/copilot/query/stream`: Server-Sent Events (SSE) streaming chat responses.
- `POST /api/copilot/war-room`: Multi-model council consensus generation.
- `GET /api/copilot/identity`: Public configuration for frontend identity hydration.
