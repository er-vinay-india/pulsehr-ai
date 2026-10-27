"""Evaluate fine-tuned Granite Composition LoRA adapter on validation and holdout sets.

Computes:
- Schema-valid output rate
- Hallucinated-ID rate
- Invalid-enum rate
- Forbidden-rendering-instruction rate (coordinates, colors, fonts, markup)
"""

from __future__ import annotations

import json
from pathlib import Path
from mlx_lm import load, generate
from app.services.presentation.composition.composition_models import CompositionDecision
from app.services.presentation.composition.composition_validator import CompositionDecisionValidator
from app.services.presentation.story_models import LogicalSlidePlan, StructuralRole, ContentBinding, ContentBindingRole

def evaluate():
    model_path = "mlx-community/granite-3b-code-instruct-4bit"
    adapter_path = "backend/models/granite_presentation_composition_lora_v1"

    print("Loading Granite base model with LoRA adapter...")
    model, tokenizer = load(model_path, adapter_path=adapter_path)
    print("Loaded fine-tuned model!")

    data_dir = Path("backend/data/composition_tuning")
    for split in ["valid", "holdout"]:
        records_path = data_dir / f"{split}.jsonl"
        with open(records_path) as f:
            lines = [json.loads(l) for l in f]

        total = len(lines)
        schema_valid = 0
        hallucinated_id = 0
        invalid_enum = 0
        forbidden_rendering = 0

        print(f"\nEvaluating on {split} set ({total} examples)...")
        for rec in lines:
            messages = rec["messages"]
            # Format prompt using tokenizer chat template
            prompt = tokenizer.apply_chat_template(messages[:2], tokenize=False, add_generation_prompt=True)
            response = generate(
                model,
                tokenizer,
                prompt=prompt,
                max_tokens=1024,
                verbose=False,
            )

            # Check for forbidden rendering patterns in raw text
            lower_resp = response.lower()
            if any(term in lower_resp for term in ["pt", "rgb(", "#", "drawingml", "<svg", "width:", "height:"]):
                forbidden_rendering += 1

            # Extract JSON
            try:
                # Find outermost JSON object
                import re
                m = re.search(r"\{[\s\S]*\}", response)
                if not m:
                    raise ValueError("No JSON object found")
                data = json.loads(m.group(0))
                decision = CompositionDecision.model_validate(data)
                schema_valid += 1
            except Exception as e:
                print(f"  [{rec['example_id']}] JSON/Schema error: {e}")
                invalid_enum += 1
                continue

            # Check grounding against expected bound IDs
            grounded_ids = set()
            for b in rec["messages"][1]["content"].split("AVAILABLE CONTENT BINDINGS:")[1].split("]")[0].split('"content_id":'):
                if '"' in b:
                    grounded_ids.add(b.split('"')[1])

            used_ids = set()
            if decision.primary_content_id:
                used_ids.add(decision.primary_content_id)
            used_ids.update(decision.supporting_content_ids)
            for g in decision.content_groups:
                used_ids.update(g.content_ids)

            ungrounded = used_ids - grounded_ids
            if ungrounded:
                print(f"  [{rec['example_id']}] Hallucinated IDs: {ungrounded}")
                hallucinated_id += 1

        print(f"Results for {split}:")
        print(f"  Schema-valid rate: {schema_valid / total * 100:.1f}% ({schema_valid}/{total})")
        print(f"  Hallucinated-ID rate: {hallucinated_id / total * 100:.1f}% ({hallucinated_id}/{total})")
        print(f"  Invalid-enum rate: {invalid_enum / total * 100:.1f}% ({invalid_enum}/{total})")
        print(f"  Forbidden-rendering rate: {forbidden_rendering / total * 100:.1f}% ({forbidden_rendering}/{total})")

if __name__ == "__main__":
    evaluate()
