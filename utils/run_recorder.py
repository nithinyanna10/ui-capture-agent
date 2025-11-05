"""Lightweight run recorder for compact step logs and summaries."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime


class RunRecorder:
    """Writes lightweight per-step logs and a final summary for a task run.

    Outputs under data/{task_name}/:
      - steps.jsonl: one compact JSON line per step
      - summary.json: concise run summary (start/end, counts, last state)
    """

    def __init__(self, task_name: str, base_dir: str = "data") -> None:
        self.task_name = task_name
        self.run_dir = Path(base_dir) / task_name
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.steps_path = self.run_dir / "steps.jsonl"
        self.summary_path = self.run_dir / "summary.json"
        self.started_at = datetime.now().isoformat()
        self.num_steps = 0
        self.last_entry: Optional[Dict[str, Any]] = None

    def record_step(
        self,
        *,
        step: int,
        url: str,
        image_path: str,
        action: str,
        target: Optional[str],
        buttons: List[str],
        status: str,
        reasoning: Optional[str] = None,
    ) -> None:
        """Append a compact step entry to steps.jsonl.

        status: "success" | "failure" | "skipped"
        """
        entry: Dict[str, Any] = {
            "step": step,
            "timestamp": datetime.now().isoformat(),
            "url": url,
            "image": image_path,
            "action": action,
            "target": target,
            "buttons": buttons,
            "status": status,
        }
        if reasoning:
            entry["reasoning"] = reasoning

        with open(self.steps_path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        self.num_steps = max(self.num_steps, step + 1)
        self.last_entry = entry

    def write_summary(
        self,
        *,
        completed: bool,
        error: Optional[str],
    ) -> None:
        """Write concise run summary."""
        summary: Dict[str, Any] = {
            "task_name": self.task_name,
            "started_at": self.started_at,
            "finished_at": datetime.now().isoformat(),
            "completed": completed,
            "total_steps": self.num_steps,
            "error": error,
            "last_entry": self.last_entry,
        }
        with open(self.summary_path, "w") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)


