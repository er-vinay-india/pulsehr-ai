"""HighView Slide Composition Intelligence — Granite LoRA Fine-Tuning Runner.

Runs LoRA fine-tuning for IBM Granite on Apple Silicon Metal using MLX LM,
evaluates train and validation loss curves, and exports the adapter.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_lora_training():
    config_file = Path("backend/data/composition_tuning/lora_config.yaml")
    adapter_dir = Path("backend/models/granite_presentation_composition_lora_v1")
    adapter_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "backend/.venv/bin/python",
        "-m",
        "mlx_lm",
        "lora",
        "--config",
        str(config_file),
    ]

    logger.info("Executing Granite LoRA fine-tuning command: %s", " ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    metrics_log = []
    for line in proc.stdout:
        print(line, end="")
        if "Iter " in line or "Val loss" in line:
            metrics_log.append(line.strip())

    proc.wait()
    if proc.returncode != 0:
        logger.error("LoRA training exited with code %s", proc.returncode)
        sys.exit(proc.returncode)

    logger.info("Granite LoRA fine-tuning completed successfully!")
    # Write metrics summary
    metrics_path = adapter_dir / "training_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump({"metrics_log": metrics_log, "status": "COMPLETED"}, f, indent=2)
    logger.info("Saved training metrics to %s", metrics_path)


if __name__ == "__main__":
    run_lora_training()
