#!/usr/bin/env python3
"""
calibration_analysis.py — HalluMaze Confidence Calibration Analysis

Computes per-model calibration metrics from existing trial data:
  - ECE (Expected Calibration Error): binned CE across trials
  - Brier Score proxy: mean((ce_i)^2) per model
  - Mean CE, median CE, and coverage statistics

Data source: ce field (per-trial Calibration Error) already computed by hallumaze.py.
CE = mean |confidence/100 - correctness| per step within each trial.

When confidence_log data is available (future runs), computes step-level ECE with
10 bins. For current data, uses trial-level CE values.

Usage:
    python3 scripts/calibration_analysis.py
    # Output: experiment_results/calibration.json
"""
from __future__ import annotations
import json, math
from pathlib import Path
from collections import defaultdict
from statistics import mean, median, stdev

BASE = Path(__file__).parent.parent / "experiment_results"

# ── Data Sources (consistent with build_final_analysis.py) ──────
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
            if rec.get("error"):
                continue
            display = MODEL_DISPLAY.get(raw_model, raw_model)
            by_model[display].append(rec)
    return dict(by_model)


def compute_ece_from_confidence_logs(trials: list[dict], n_bins: int = 10) -> dict | None:
    """Compute step-level ECE if confidence_log data is available."""
    all_confs = []
    all_outcomes = []
    for rec in trials:
        conf_log = rec.get("confidence_log", [])
        if not conf_log:
            continue
        hrr = rec.get("hrr", 0.0)
        for entry in conf_log:
            if entry is None:
                continue
            conf = entry.get("conf")
            if conf is None:
                continue
            all_confs.append(conf / 100.0)
            all_outcomes.append(hrr)

    if len(all_confs) < 5:
        return None

    # 10-bin ECE
    bins = [[] for _ in range(n_bins)]
    outcome_bins = [[] for _ in range(n_bins)]
    for c, o in zip(all_confs, all_outcomes):
        idx = min(int(c * n_bins), n_bins - 1)
        bins[idx].append(c)
        outcome_bins[idx].append(o)

    ece = 0.0
    n_total = len(all_confs)
    for b_confs, b_outs in zip(bins, outcome_bins):
        if not b_confs:
            continue
        avg_conf = mean(b_confs)
        avg_acc = mean(b_outs)
        ece += (len(b_confs) / n_total) * abs(avg_acc - avg_conf)

    brier = mean((c - o) ** 2 for c, o in zip(all_confs, all_outcomes))
    return {
        "ece": round(ece, 4),
        "brier": round(brier, 4),
        "n_steps": len(all_confs),
        "mean_confidence": round(mean(all_confs), 4),
    }


def compute_calibration_from_ce(trials: list[dict]) -> dict:
    """Compute model-level calibration statistics from pre-computed CE values."""
    ce_values = [rec["ce"] for rec in trials if rec.get("ce") is not None]
    hrr_values = [rec.get("hrr", 0.0) for rec in trials]
    sr_values = [rec.get("sr", 0.0) for rec in trials]

    n_total = len(trials)
    n_with_ce = len(ce_values)

    result = {
        "n_total": n_total,
        "n_with_confidence": n_with_ce,
        "coverage": round(n_with_ce / n_total, 4) if n_total > 0 else 0.0,
    }

    if n_with_ce == 0:
        result.update({
            "mean_ce": None,
            "median_ce": None,
            "std_ce": None,
            "ece_trial_level": None,
            "brier_proxy": None,
            "mean_hrr": round(mean(hrr_values), 4) if hrr_values else None,
            "mean_sr": round(mean(sr_values), 4) if sr_values else None,
        })
        return result

    # Trial-level ECE: bin trials by their CE value, compute weighted average
    n_bins = 10
    bins = [[] for _ in range(n_bins)]
    for ce in ce_values:
        idx = min(int(ce * n_bins), n_bins - 1)
        bins[idx].append(ce)

    ece = 0.0
    for i, b in enumerate(bins):
        if not b:
            continue
        bin_center = (i + 0.5) / n_bins
        avg_ce = mean(b)
        ece += (len(b) / n_with_ce) * abs(avg_ce - bin_center)

    # Brier proxy: mean(ce^2)
    brier_proxy = mean(ce ** 2 for ce in ce_values)

    result.update({
        "mean_ce": round(mean(ce_values), 4),
        "median_ce": round(median(ce_values), 4),
        "std_ce": round(stdev(ce_values), 4) if n_with_ce > 1 else 0.0,
        "ece_trial_level": round(ece, 4),
        "brier_proxy": round(brier_proxy, 4),
        "mean_hrr": round(mean(hrr_values), 4),
        "mean_sr": round(mean(sr_values), 4),
    })
    return result


def analyze_calibration(by_model: dict[str, list[dict]]) -> dict:
    """Run calibration analysis on all models."""
    results = {}
    for model, trials in sorted(by_model.items()):
        # Try step-level ECE first (from confidence_log)
        step_level = compute_ece_from_confidence_logs(trials)
        # Always compute trial-level CE stats
        trial_level = compute_calibration_from_ce(trials)

        if step_level:
            trial_level["ece_step_level"] = step_level["ece"]
            trial_level["brier_step_level"] = step_level["brier"]
            trial_level["n_confidence_steps"] = step_level["n_steps"]
            trial_level["mean_confidence"] = step_level["mean_confidence"]

        results[model] = trial_level
    return results


def print_summary(results: dict) -> None:
    """Print a readable summary table."""
    header = f"{'Model':<25} {'n':>3} {'cov':>5} {'mean_CE':>8} {'med_CE':>8} {'ECE':>8} {'Brier':>8} {'HRR':>6} {'SR':>6}"
    print("\n" + "=" * len(header))
    print("HalluMaze Confidence Calibration Analysis")
    print("=" * len(header))
    print(header)
    print("-" * len(header))
    for model, data in sorted(results.items(), key=lambda x: (x[1].get("mean_ce") or 999)):
        cov_pct = f"{data['coverage']*100:.0f}%"
        mean_ce = f"{data['mean_ce']:.4f}" if data['mean_ce'] is not None else "N/A"
        med_ce = f"{data['median_ce']:.4f}" if data['median_ce'] is not None else "N/A"
        ece = f"{data['ece_trial_level']:.4f}" if data['ece_trial_level'] is not None else "N/A"
        brier = f"{data['brier_proxy']:.4f}" if data['brier_proxy'] is not None else "N/A"
        hrr = f"{data['mean_hrr']:.3f}" if data.get('mean_hrr') is not None else "N/A"
        sr = f"{data['mean_sr']:.3f}" if data.get('mean_sr') is not None else "N/A"
        print(f"{model:<25} {data['n_total']:>3} {cov_pct:>5} {mean_ce:>8} {med_ce:>8} {ece:>8} {brier:>8} {hrr:>6} {sr:>6}")
    print("=" * len(header))
    print("\nLegend:")
    print("  cov: % of trials with confidence data")
    print("  mean_CE: mean per-trial Calibration Error (lower = better calibrated)")
    print("  ECE: Expected Calibration Error (trial-level binned)")
    print("  Brier: Brier Score proxy = mean(CE^2)")
    print("  HRR: Hallucination Recovery Rate")
    print("  SR: Solve Rate")


def main() -> None:
    print("Loading trial data...")
    by_model = load_all_records()
    total = sum(len(v) for v in by_model.values())
    print(f"Loaded {total} valid trials across {len(by_model)} models")

    results = analyze_calibration(by_model)
    print_summary(results)

    outpath = BASE / "calibration.json"
    with open(outpath, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nSaved to {outpath}")


if __name__ == "__main__":
    main()
