"""Evaluate fine-tuned Granite 4 Composition LoRA checkpoints (20, 40, 60) on validation and holdout sets.

Base Model: mlx-community/granite-4.0-h-micro-4bit
Adapter Path: backend/models/granite4_presentation_composition_lora_v1
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any
from mlx_lm import load, generate
from app.services.presentation.composition.composition_models import CompositionDecision
from app.services.presentation.composition.composition_validator import CompositionDecisionValidator

def evaluate_checkpoint(adapter_weights_file: str, checkpoint_name: str) -> dict[str, Any]:
    model_path = "mlx-community/granite-4.0-h-micro-4bit"
    adapter_dir = Path("backend/models/granite4_presentation_composition_lora_v1")
    
    target_weights = adapter_dir / adapter_weights_file
    active_weights = adapter_dir / "adapters.safetensors"
    shutil.copyfile(target_weights, active_weights)

    print(f"\n========================================================")
    print(f"EVALUATING GRANITE 4 CHECKPOINT: {checkpoint_name} ({adapter_weights_file})")
    print(f"========================================================")
    
    model, tokenizer = load(model_path, adapter_path=str(adapter_dir))
    data_dir = Path("backend/data/composition_tuning")
    
    results = {}
    for split in ["valid", "holdout"]:
        records_path = data_dir / f"{split}.jsonl"
        with open(records_path) as f:
            lines = [json.loads(l) for l in f]

        total = len(lines)
        schema_valid = 0
        hallucinated_id = 0
        invalid_enum = 0
        forbidden_rendering = 0
        details = []

        for rec in lines:
            messages = rec["messages"]
            prompt = tokenizer.apply_chat_template(messages[:2], tokenize=False, add_generation_prompt=True)
            response = generate(
                model,
                tokenizer,
                prompt=prompt,
                max_tokens=1024,
                verbose=False,
            )

            lower_resp = response.lower()
            if any(term in lower_resp for term in ["pt", "rgb(", "#", "drawingml", "<svg", "width:", "height:"]):
                forbidden_rendering += 1

            m = re.search(r"\{[\s\S]*\}", response)
            if not m:
                invalid_enum += 1
                details.append((rec["example_id"], "NO_JSON_FOUND"))
                continue

            try:
                data = json.loads(m.group(0))
                decision = CompositionDecision.model_validate(data)
                schema_valid += 1
            except Exception as e:
                invalid_enum += 1
                details.append((rec["example_id"], f"SCHEMA/ENUM_ERR: {e}"))
                continue

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
                hallucinated_id += 1
                details.append((rec["example_id"], f"UNGROUNDED_IDS: {ungrounded}"))

        res_split = {
            "total": total,
            "schema_valid": schema_valid,
            "schema_valid_rate": schema_valid / total,
            "hallucinated_id": hallucinated_id,
            "hallucinated_id_rate": hallucinated_id / total,
            "invalid_enum": invalid_enum,
            "invalid_enum_rate": invalid_enum / total,
            "forbidden_rendering": forbidden_rendering,
            "forbidden_rendering_rate": forbidden_rendering / total,
            "details": details,
        }
        results[split] = res_split
        print(f"Split [{split}]: Schema Valid={schema_valid}/{total} ({schema_valid/total*100:.1f}%), "
              f"Invalid Enum={invalid_enum}/{total}, Hallucinated={hallucinated_id}/{total}, "
              f"Forbidden Rendering={forbidden_rendering}/{total}")
        if details:
            for ex_id, err in details:
                print(f"   -> {ex_id}: {err}")

    return results

def main():
    checkpoints = [
        ("0000020_adapters.safetensors", "Granite 4 Iteration 20 (Val Loss: 0.161)"),
        ("0000040_adapters.safetensors", "Granite 4 Iteration 40 (Val Loss: 0.189)"),
        ("0000060_adapters.safetensors", "Granite 4 Iteration 60 (Val Loss: 0.205)"),
    ]
    
    summary = {}
    for filename, name in checkpoints:
        res = evaluate_checkpoint(filename, name)
        summary[name] = res
        
    print("\n\n========================================================")
    print("GRANITE 4 CHECKPOINT COMPARISON SUMMARY")
    print("========================================================")
    for name, res in summary.items():
        v = res["valid"]
        h = res["holdout"]
        print(f"{name}:")
        print(f"  Validation Schema-Valid: {v['schema_valid_rate']*100:.1f}% ({v['schema_valid']}/{v['total']}) | Enums Invalid: {v['invalid_enum']}")
        print(f"  Holdout    Schema-Valid: {h['schema_valid_rate']*100:.1f}% ({h['schema_valid']}/{h['total']}) | Enums Invalid: {h['invalid_enum']}")

if __name__ == "__main__":
    main()
