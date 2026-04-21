#!/usr/bin/env python3
"""Part 2 — multi-model evaluation runner.

Runs the 30-case ground-truth dataset against a configurable list of models
via OpenRouter, grades each response with `dataset.grade`, and emits:
  - artifacts/eval_results.json   per-case raw result
  - artifacts/eval_summary.json   per-model accuracy + confusion by category
  - artifacts/eval_grid.svg       visual grid (model x case) for README
  - stdout summary table

The dataset is defined in eval/dataset.py and is also exported to YAML/JSON
so the same cases can be run via `npx promptfoo eval`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tool  # noqa: E402
from eval.dataset import CASES, grade  # noqa: E402


DEFAULT_MODELS = [
    {"id": "openai/gpt-oss-120b", "label": "gpt-oss-120b", "tier": "open"},
    {"id": "deepseek/deepseek-chat", "label": "deepseek-v3", "tier": "open"},
    {"id": "anthropic/claude-sonnet-4.5", "label": "claude-sonnet-4.5", "tier": "closed"},
]


def call_model(model_id: str, user: str, retries: int = 2) -> str:
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            raw = tool.call_llm(model_id, tool.NL_TO_SEARCH_SYSTEM, user)
            return tool.normalize_query_output(raw)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"call_model failed after retries: {last_exc}")


def run_case(model: dict, case: dict) -> dict:
    t0 = time.time()
    try:
        output = call_model(model["id"], case["query"])
        passed, reason = grade(output, case["expect"])
        error = None
    except Exception as exc:  # noqa: BLE001
        output = ""
        passed = False
        reason = f"error: {exc}"
        error = str(exc)
    return {
        "model": model["label"],
        "model_id": model["id"],
        "tier": model["tier"],
        "case_id": case["id"],
        "category": case["category"],
        "query": case["query"],
        "output": output,
        "passed": passed,
        "reason": reason,
        "error": error,
        "latency_s": round(time.time() - t0, 2),
    }


def summarize(results: list[dict]) -> dict:
    by_model: dict[str, dict] = {}
    for r in results:
        m = r["model"]
        entry = by_model.setdefault(m, {
            "tier": r["tier"],
            "passed": 0,
            "total": 0,
            "per_category": {},
            "failures": [],
            "avg_latency_s": 0.0,
            "_latency_total": 0.0,
        })
        entry["total"] += 1
        entry["_latency_total"] += r["latency_s"]
        cat = entry["per_category"].setdefault(r["category"], {"passed": 0, "total": 0})
        cat["total"] += 1
        if r["passed"]:
            entry["passed"] += 1
            cat["passed"] += 1
        else:
            entry["failures"].append({
                "case_id": r["case_id"],
                "category": r["category"],
                "query": r["query"],
                "output": r["output"],
                "reason": r["reason"],
            })

    for m, entry in by_model.items():
        entry["accuracy"] = round(entry["passed"] / entry["total"], 4) if entry["total"] else 0.0
        entry["avg_latency_s"] = round(entry["_latency_total"] / entry["total"], 2) if entry["total"] else 0.0
        del entry["_latency_total"]
    return by_model


def render_svg(results: list[dict], summary: dict, out_path: Path) -> None:
    models = list(summary.keys())
    case_ids = sorted({r["case_id"] for r in results})
    cell = 28
    label_x = 20
    acc_x = 230
    tier_x = 300
    grid_x = 360
    top = 100
    width = grid_x + cell * len(case_ids) + 40
    height = top + cell * len(models) + 70

    lookup = {(r["model"], r["case_id"]): r for r in results}

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="Menlo, Monaco, monospace">',
        f'<rect width="100%" height="100%" fill="#0b1220"/>',
        f'<text x="20" y="34" font-size="20" font-weight="700" fill="#f9fafb">Part 2 — Multi-Model Eval ({len(case_ids)} cases × {len(models)} models)</text>',
        f'<text x="20" y="60" font-size="13" fill="#9ca3af">Green = pass, red = fail. Column numbers are case IDs.</text>',
        f'<text x="{label_x}" y="{top - 12}" font-size="11" fill="#6b7280">model</text>',
        f'<text x="{acc_x}" y="{top - 12}" font-size="11" fill="#6b7280" text-anchor="end">accuracy</text>',
        f'<text x="{tier_x}" y="{top - 12}" font-size="11" fill="#6b7280">tier</text>',
    ]

    # Column headers (case ids)
    for i, cid in enumerate(case_ids):
        x = grid_x + i * cell + cell / 2
        svg.append(f'<text x="{x}" y="{top - 12}" font-size="10" fill="#9ca3af" text-anchor="middle">{cid}</text>')

    # Rows
    for row, model in enumerate(models):
        y = top + row * cell
        entry = summary[model]
        acc = entry["accuracy"] * 100
        tier = entry["tier"]
        color = "#10b981" if acc >= 85 else "#f59e0b" if acc >= 70 else "#ef4444"
        text_y = y + cell - 9
        svg.append(
            f'<text x="{label_x}" y="{text_y}" font-size="13" fill="#e5e7eb">{model}</text>'
        )
        svg.append(
            f'<text x="{acc_x}" y="{text_y}" font-size="13" font-weight="600" fill="{color}" text-anchor="end">{acc:5.1f}%</text>'
        )
        svg.append(
            f'<text x="{tier_x}" y="{text_y}" font-size="11" fill="#9ca3af">{tier}</text>'
        )
        for i, cid in enumerate(case_ids):
            r = lookup.get((model, cid))
            fill = "#1f2937"
            if r is not None:
                fill = "#10b981" if r["passed"] else "#ef4444"
            x = grid_x + i * cell
            svg.append(
                f'<rect x="{x + 2}" y="{y + 2}" width="{cell - 4}" height="{cell - 4}" fill="{fill}" rx="4"/>'
            )

    legend_y = top + cell * len(models) + 34
    svg.append(
        f'<text x="20" y="{legend_y}" font-size="12" fill="#9ca3af">Threshold: &gt;85% accuracy. Models ≥85% shown in green.</text>'
    )
    svg.append("</svg>")
    out_path.write_text("\n".join(svg), encoding="utf-8")


def render_png(results: list[dict], summary: dict, out_path: Path) -> None:
    """Render a crisp PNG version of the eval grid (no SVG→PNG conversion)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return
    models = list(summary.keys())
    case_ids = sorted({r["case_id"] for r in results})
    scale = 2
    cell = 28 * scale
    label_x = 20 * scale
    acc_x = 260 * scale
    tier_x = 320 * scale
    grid_x = 380 * scale
    top = 110 * scale
    width = grid_x + cell * len(case_ids) + 40 * scale
    height = top + cell * len(models) + 70 * scale

    img = Image.new("RGB", (width, height), "#0b1220")
    draw = ImageDraw.Draw(img)

    def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        candidates = [
            "/System/Library/Fonts/Supplemental/Menlo.ttc",
            "/System/Library/Fonts/Menlo.ttc",
            "/System/Library/Fonts/Supplemental/Courier New.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
        for path in candidates:
            if Path(path).exists():
                try:
                    return ImageFont.truetype(path, size * scale)
                except Exception:
                    pass
        return ImageFont.load_default()

    lookup = {(r["model"], r["case_id"]): r for r in results}

    draw.text((20 * scale, 28 * scale), f"Part 2 — Multi-Model Eval ({len(case_ids)} cases × {len(models)} models)",
              fill="#f9fafb", font=font(20, bold=True))
    draw.text((20 * scale, 58 * scale), "Green = pass, red = fail. Column numbers are case IDs.",
              fill="#9ca3af", font=font(13))

    # Column headers
    for i, cid in enumerate(case_ids):
        x = grid_x + i * cell + cell // 2
        draw.text((x, top - 16 * scale), str(cid), fill="#9ca3af", font=font(10), anchor="mm")

    draw.text((label_x, top - 16 * scale), "model", fill="#6b7280", font=font(11))
    draw.text((acc_x, top - 16 * scale), "accuracy", fill="#6b7280", font=font(11), anchor="rm")
    draw.text((tier_x, top - 16 * scale), "tier", fill="#6b7280", font=font(11))

    for row, model in enumerate(models):
        y = top + row * cell
        entry = summary[model]
        acc = entry["accuracy"] * 100
        color = "#10b981" if acc >= 85 else "#f59e0b" if acc >= 70 else "#ef4444"
        text_y = y + cell // 2
        draw.text((label_x, text_y), model, fill="#e5e7eb", font=font(13), anchor="lm")
        draw.text((acc_x, text_y), f"{acc:5.1f}%", fill=color, font=font(13), anchor="rm")
        draw.text((tier_x, text_y), entry["tier"], fill="#9ca3af", font=font(11), anchor="lm")
        for i, cid in enumerate(case_ids):
            r = lookup.get((model, cid))
            fill = "#1f2937" if r is None else ("#10b981" if r["passed"] else "#ef4444")
            x = grid_x + i * cell
            draw.rounded_rectangle((x + 2, y + 2, x + cell - 2, y + cell - 2), radius=4 * scale, fill=fill)

    legend_y = top + cell * len(models) + 34 * scale
    draw.text((20 * scale, legend_y), "Threshold: >85% accuracy. Models ≥85% shown in green.",
              fill="#9ca3af", font=font(12))

    img.save(out_path, "PNG")


def print_summary(summary: dict) -> None:
    print("\n" + "═" * 72)
    print(f"{'Model':<22}{'Tier':<10}{'Pass/Total':<14}{'Accuracy':<12}{'Avg latency':<12}")
    print("─" * 72)
    for model, entry in summary.items():
        acc = entry["accuracy"] * 100
        mark = "✅" if acc >= 85 else "⚠️ "
        print(
            f"{model:<22}{entry['tier']:<10}"
            f"{entry['passed']}/{entry['total']:<12}"
            f"{acc:5.1f}% {mark}  "
            f"{entry['avg_latency_s']:>5.2f}s"
        )
    print("═" * 72)


def run(models: list[dict], case_subset: list[int] | None, workers: int, verbose: bool) -> tuple[list[dict], dict]:
    cases = [c for c in CASES if case_subset is None or c["id"] in case_subset]
    tasks = [(m, c) for m in models for c in cases]
    results: list[dict] = []

    # Slight parallelism, but keep it low to stay friendly to free tiers.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run_case, m, c): (m, c) for m, c in tasks}
        for i, fut in enumerate(as_completed(futures), 1):
            r = fut.result()
            results.append(r)
            if verbose:
                mark = "PASS" if r["passed"] else "FAIL"
                print(f"  [{i:>3}/{len(tasks)}] {mark} {r['model']:<20} #{r['case_id']:>2} [{r['category']}] — {r['reason']}")

    results.sort(key=lambda r: (r["model"], r["case_id"]))
    return results, summarize(results)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", help="Comma-separated OpenRouter IDs (optional).")
    parser.add_argument("--case-ids", help="Comma-separated case ids to run (optional).")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--out-dir", default="artifacts")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if args.models:
        models: list[dict] = []
        for raw in args.models.split(","):
            mid = raw.strip()
            if not mid:
                continue
            label = mid.split("/", 1)[-1]
            models.append({"id": mid, "label": label, "tier": "?"})
    else:
        models = DEFAULT_MODELS

    case_ids = None
    if args.case_ids:
        case_ids = [int(x) for x in args.case_ids.split(",") if x.strip()]

    print(f"Running {len(models)} model(s) × {len(case_ids) if case_ids else len(CASES)} case(s)…")
    results, summary = run(models, case_ids, args.workers, verbose=not args.quiet)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "eval_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "eval_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    render_svg(results, summary, out_dir / "eval_grid.svg")
    render_png(results, summary, out_dir / "eval_grid.png")

    print_summary(summary)

    all_pass_threshold = all(entry["accuracy"] >= 0.85 for entry in summary.values())
    if not all_pass_threshold:
        print("\n⚠️  One or more models fell below the 85% threshold. Inspect eval_results.json and iterate.")
        sys.exit(2)


if __name__ == "__main__":
    main()
