#!/usr/bin/env python3
"""
failure_mode_analysis.py — HalluMaze 실패 모드 분류학

각 trial을 4가지 유형으로 자동 분류:
  TYPE_S: Success           — sr == 1.0
  TYPE_A: Mirage_Undetected — hallucination_count > 0 AND backtrack_count == 0
  TYPE_B: Mirage_Detected_Failed — hallucination_count > 0 AND backtrack_count > 0 AND hrr < 0.5
  TYPE_C: Loop_Trapped      — loop_count >= 2 AND sr == 0

Usage:
    python scripts/failure_mode_analysis.py
    # Output: experiment_results/failure_modes.json
"""
from __future__ import annotations
import json
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).parent.parent / "experiment_results"

# ── Data Sources (same as build_final_analysis.py) ──────────────
SOURCES = {
    "checkpoint_rerun": {
        "file": BASE / "checkpoint_rerun.json",
        "model_key": "model",
    },
    "or_phaseB_scout_gemini": {
        "file": BASE / "or_phaseB.json",
        "model_key": "or_model_id",
        "filter_models": ["meta-llama/llama-4-scout", "google/gemini-2.0-flash-lite-001"],
    },
    "or_haiku":    {"file": BASE / "or_haiku.json",    "model_key": "or_model_id"},
    "or_gptmini":  {"file": BASE / "or_gptmini.json",  "model_key": "or_model_id"},
    "or_maverick": {"file": BASE / "or_maverick.json",  "model_key": "or_model_id"},
    "or_qwen":     {"file": BASE / "or_qwen.json",     "model_key": "or_model_id"},
}

MODEL_DISPLAY = {
    "glm-4.7": "GLM-4.7",
    "MiniMax-M2.5": "MiniMax-M2.5",
    "meta-llama/llama-4-scout": "Llama-4-Scout",
    "meta-llama/llama-4-maverick": "Llama-4-Maverick",
    "google/gemini-2.0-flash-lite-001": "Gemini-2.0-Flash-Lite",
    "openai/gpt-4o-mini": "GPT-4o-mini",
    "anthropic/claude-3-haiku": "Claude-3-Haiku",
    "qwen/qwen-2.5-72b-instruct": "Qwen-2.5-72B",
}


def load_all_records() -> dict[str, list[dict]]:
    """Load all trial records grouped by display model name."""
    by_model: dict[str, list[dict]] = defaultdict(list)
    for src_name, src in SOURCES.items():
        fpath = src["file"]
        if not fpath.exists():
            print(f"  [SKIP] {fpath.name} not found")
            continue
        with open(fpath) as f:
            records = json.load(f)
        model_key = src.get("model_key", "model")
        filter_models = src.get("filter_models")
        for rec in records:
            raw_model = rec.get(model_key) or rec.get("model", "unknown")
            if filter_models and raw_model not in filter_models:
                continue
            # Skip error trials
            if rec.get("error"):
                continue
            display = MODEL_DISPLAY.get(raw_model, raw_model)
            by_model[display].append(rec)
    return dict(by_model)


def classify_trial(rec: dict) -> str:
    """Classify a single trial into one of 4 failure modes."""
    sr = rec.get("sr", 0)
    hallucination_count = rec.get("hallucination_count", 0)
    backtrack_count = rec.get("backtrack_count", 0)
    loop_count = rec.get("loop_count", 0)
    hrr = rec.get("hrr", 0.0)

    # Priority order: Success first, then specific failure modes
    if sr == 1.0:
        return "TYPE_S"
    if hallucination_count > 0 and backtrack_count == 0:
        return "TYPE_A"
    if hallucination_count > 0 and backtrack_count > 0 and hrr < 0.5:
        return "TYPE_B"
    if loop_count >= 2:
        return "TYPE_C"
    # Fallback: failure that doesn't match specific patterns
    return "TYPE_OTHER"


def analyze_failure_modes(by_model: dict[str, list[dict]]) -> dict:
    """Run failure mode classification on all models."""
    results = {}
    for model, trials in sorted(by_model.items()):
        counts = {"TYPE_S": 0, "TYPE_A": 0, "TYPE_B": 0, "TYPE_C": 0, "TYPE_OTHER": 0}
        for rec in trials:
            ftype = classify_trial(rec)
            counts[ftype] += 1
        n = len(trials)
        pcts = {k: round(v / n * 100, 1) if n > 0 else 0.0 for k, v in counts.items()}
        results[model] = {
            "n": n,
            "counts": counts,
            "percentages": pcts,
            "labels": {
                "TYPE_S": "Success",
                "TYPE_A": "Mirage_Undetected",
                "TYPE_B": "Mirage_Detected_Failed",
                "TYPE_C": "Loop_Trapped",
                "TYPE_OTHER": "Other_Failure",
            },
        }
    return results


def print_summary(results: dict) -> None:
    """Print a readable summary table."""
    header = f"{'Model':<25} {'n':>3}  {'Success':>8}  {'Undetect':>8}  {'Det+Fail':>8}  {'Loop':>8}  {'Other':>8}"
    print("\n" + "=" * len(header))
    print("HalluMaze Failure Mode Taxonomy")
    print("=" * len(header))
    print(header)
    print("-" * len(header))
    for model, data in sorted(results.items(), key=lambda x: x[1]["percentages"]["TYPE_S"], reverse=True):
        p = data["percentages"]
        print(f"{model:<25} {data['n']:>3}  {p['TYPE_S']:>7.1f}%  {p['TYPE_A']:>7.1f}%  {p['TYPE_B']:>7.1f}%  {p['TYPE_C']:>7.1f}%  {p['TYPE_OTHER']:>7.1f}%")
    print("=" * len(header))
    print("\nLegend:")
    print("  TYPE_S: Success (sr=1.0)")
    print("  TYPE_A: Mirage_Undetected (hallucination but no backtrack)")
    print("  TYPE_B: Mirage_Detected_Failed (backtracked but hrr < 0.5)")
    print("  TYPE_C: Loop_Trapped (loop_count >= 2, failed)")
    print("  TYPE_OTHER: Other failure mode")


def main() -> None:
    print("Loading trial data...")
    by_model = load_all_records()
    total = sum(len(v) for v in by_model.values())
    print(f"Loaded {total} valid trials across {len(by_model)} models")

    results = analyze_failure_modes(by_model)
    print_summary(results)

    outpath = BASE / "failure_modes.json"
    with open(outpath, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nSaved to {outpath}")


if __name__ == "__main__":
    main()
