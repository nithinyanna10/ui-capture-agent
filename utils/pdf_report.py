"""Generate a concise PDF report for a run with embedded screenshots."""
from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any
import json
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader


def _read_steps_jsonl(steps_path: Path) -> List[Dict[str, Any]]:
    steps: List[Dict[str, Any]] = []
    if not steps_path.exists():
        return steps
    with open(steps_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                steps.append(json.loads(line))
            except Exception:
                continue
    # Deduplicate by step keeping last status (pending -> success/failure)
    last_by_step: Dict[int, Dict[str, Any]] = {}
    for entry in steps:
        s = int(entry.get("step", 0))
        last_by_step[s] = entry
    ordered = [last_by_step[k] for k in sorted(last_by_step.keys())]
    return ordered


def _read_summary(summary_path: Path) -> Dict[str, Any]:
    if summary_path.exists():
        try:
            return json.loads(summary_path.read_text())
        except Exception:
            pass
    return {}


def generate_run_pdf(task_name: str, base_dir: str = "data") -> Path:
    """Create data/{task_name}/report.pdf with images and concise details.

    Returns the path to the created PDF.
    """
    run_dir = Path(base_dir) / task_name
    steps_path = run_dir / "steps.jsonl"
    summary_path = run_dir / "summary.json"
    pdf_path = run_dir / "report.pdf"

    steps = _read_steps_jsonl(steps_path)
    summary = _read_summary(summary_path)

    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    width, height = A4

    # Cover page
    c.setFont("Helvetica-Bold", 18)
    c.drawString(2 * cm, height - 2.5 * cm, f"Run Report: {task_name}")
    c.setFont("Helvetica", 12)
    c.drawString(2 * cm, height - 3.5 * cm, f"Started: {summary.get('started_at', '')}")
    c.drawString(2 * cm, height - 4.1 * cm, f"Finished: {summary.get('finished_at', '')}")
    c.drawString(2 * cm, height - 4.7 * cm, f"Completed: {summary.get('completed', False)}")
    c.drawString(2 * cm, height - 5.3 * cm, f"Total Steps: {summary.get('total_steps', len(steps))}")
    if summary.get("error"):
        c.setFillColorRGB(0.8, 0, 0)
        c.drawString(2 * cm, height - 5.9 * cm, f"Error: {summary.get('error')}")
        c.setFillColorRGB(0, 0, 0)
    c.showPage()

    # Per-step pages (image + details)
    for entry in steps:
        step = entry.get("step")
        url = entry.get("url", "")
        image_path = entry.get("image", "")
        action = entry.get("action", "")
        target = entry.get("target", "")
        buttons = entry.get("buttons", []) or []
        status = entry.get("status", "")
        reasoning = entry.get("reasoning", "")

        c.setFont("Helvetica-Bold", 14)
        c.drawString(2 * cm, height - 2 * cm, f"Step {step}")
        c.setFont("Helvetica", 10)
        c.drawString(2 * cm, height - 2.7 * cm, f"URL: {url}")
        c.drawString(2 * cm, height - 3.3 * cm, f"Action: {action}  Target: {target}")
        c.drawString(2 * cm, height - 3.9 * cm, f"Status: {status}")
        if buttons:
            c.drawString(2 * cm, height - 4.5 * cm, f"Buttons: {', '.join([b for b in buttons if b])[:120]}")
        if reasoning:
            # Wrap reasoning across lines
            text = c.beginText(2 * cm, height - 5.3 * cm)
            text.setFont("Helvetica", 10)
            wrap_width = int((width - 4 * cm) / 5.6)  # rough char wrap
            for i in range(0, len(reasoning), wrap_width):
                text.textLine(reasoning[i:i + wrap_width])
            c.drawText(text)

        # Place image scaled to fit below text
        img_y_top = height - 11.5 * cm
        img_box_w = width - 4 * cm
        img_box_h = 9 * cm
        img_x = 2 * cm
        img_y = img_y_top - img_box_h

        try:
            img_file = Path(image_path)
            if img_file.exists():
                img = ImageReader(str(img_file))
                iw, ih = img.getSize()
                scale = min(img_box_w / iw, img_box_h / ih)
                dw, dh = iw * scale, ih * scale
                c.drawImage(img, img_x, img_y, width=dw, height=dh, preserveAspectRatio=True, anchor='sw')
        except Exception:
            pass

        c.showPage()

    c.save()
    return pdf_path


