#!/usr/bin/env python3
"""
HalluCode Full Experiment — Merge + CodeMEI Statistics
=======================================================
파일럿 + 전체 실험 결과를 합산하여 experiment_results/hallucode_full.json 생성.
CodeMEI, SR, HRR을 trap_type별 × 모델별로 집계.

Usage:
    python3 scripts/build_hallucode_full.py
"""
import json
import os
import statistics
from datetime import datetime
from collections import defaultdict

BASE = "/home/jayone/Project/Miro"

# ─── Source files (pilot + full runs) ──────────────────────────────────────────
SOURCES = [
    # GLM-free
    "experiment_results/hallucode_pilot.json",        # GLM+LFM HC001-005 nonexistent_api
    "experiment_results/hallucode_glm_nonexist.json", # GLM HC006-010 (HC006-007 429)
    "experiment_results/hallucode_glm_retry67.json",  # GLM HC006-007 retry (valid)
    "experiment_results/hallucode_wrong_sig_glm.json",# GLM HC013 pilot valid (152s, MEI=0.30)
    "experiment_results/hallucode_glm_wsig_dep.json", # GLM HC011-020 (HC013/018/020 errors → kept from above)
    "experiment_results/hallucode_glm_retry18.json",  # GLM HC018 retry (valid, CodeMEI=0.40)
    # HC020: consistently times out (>300s) — excluded, GLM deprecated n=4
    # LFM-1b-free
    "experiment_results/hallucode_pilot_lfm.json",    # HC001-005 nonexistent_api
    "experiment_results/hallucode_wrong_sig.json",    # HC011-013 wrong_sig (early pilot)
    "experiment_results/hallucode_lfm_full.json",     # HC006-020 all types (overrides pilot)
]

def load_results():
    """Load all results, deduplicating by (model, problem_id). Later files override earlier."""
    seen = {}  # (model, problem_id) -> result
    for src in SOURCES:
        path = os.path.join(BASE, src)
        if not os.path.exists(path):
            print(f"  [SKIP] {src} not found")
            continue
        try:
            d = json.load(open(path))
            results = d.get("results", [])
            n_new = 0
            n_skip_429 = 0
            for r in results:
                # Skip 429 error results (elapsed=None or <5s with MEI=0 SR=0)
                elapsed = r.get("elapsed")
                if (elapsed is None or elapsed < 5) and r.get("code_mei", 0) == 0 and r.get("sr", 0) == 0:
                    n_skip_429 += 1
                    continue
                key = (r["model"], r["problem_id"])
                if key not in seen:
                    n_new += 1
                seen[key] = r
            print(f"  [OK] {src}: {len(results)} results, +{n_new} new, {n_skip_429} skipped (429)")
        except Exception as e:
            print(f"  [ERR] {src}: {e}")
    return list(seen.values())

def compute_stats(results):
    """Compute per-model and per-trap-type statistics."""
    by_model = defaultdict(list)
    for r in results:
        by_model[r["model"]].append(r)

    model_stats = {}
    for model, items in sorted(by_model.items()):
        by_type = defaultdict(list)
        for r in items:
            by_type[r["trap_type"]].append(r)

        trap_stats = {}
        for tt, rr in sorted(by_type.items()):
            n = len(rr)
            trap_stats[tt] = {
                "n": n,
                "code_mei_mean": round(sum(r["code_mei"] for r in rr) / n, 4),
                "sr_mean":       round(sum(r["sr"]       for r in rr) / n, 4),
                "hrr_mean":      round(sum(r["hrr"]      for r in rr) / n, 4),
                "hr_mean":       round(sum(r["hr"]       for r in rr) / n, 4),
                "detect_rate":   round(sum(1 for r in rr if r["mirage_detected"]) / n, 4),
            }

        n_total = len(items)
        model_stats[model] = {
            "n_total": n_total,
            "code_mei_overall": round(sum(r["code_mei"] for r in items) / n_total, 4),
            "sr_overall":       round(sum(r["sr"]       for r in items) / n_total, 4),
            "hrr_overall":      round(sum(r["hrr"]      for r in items) / n_total, 4),
            "hr_overall":       round(sum(r["hr"]       for r in items) / n_total, 4),
            "detect_overall":   round(sum(1 for r in items if r["mirage_detected"]) / n_total, 4),
            "by_trap_type":     trap_stats,
        }

    return model_stats

def print_summary(model_stats):
    print("\n" + "="*70)
    print("HalluCode Full Experiment — Summary")
    print("="*70)
    for model, stats in model_stats.items():
        print(f"\n  {model} (n={stats['n_total']})")
        print(f"    Overall  → CodeMEI={stats['code_mei_overall']:.3f}  SR={stats['sr_overall']:.0%}  HRR={stats['hrr_overall']:.0%}  Detect={stats['detect_overall']:.0%}")
        for tt, ts in stats["by_trap_type"].items():
            print(f"    [{tt:<20}] n={ts['n']}  MEI={ts['code_mei_mean']:.3f}  SR={ts['sr_mean']:.0%}  HRR={ts['hrr_mean']:.0%}  Detect={ts['detect_rate']:.0%}")

def main():
    print("Loading results...")
    results = load_results()
    print(f"\nTotal valid results: {len(results)}")

    if len(results) == 0:
        print("No results to process.")
        return

    model_stats = compute_stats(results)
    print_summary(model_stats)

    out = {
        "method": "HalluCode-MVP-v1-full",
        "timestamp": datetime.now().isoformat(),
        "n_total": len(results),
        "model_stats": model_stats,
        "raw_results": sorted(results, key=lambda r: (r["model"], r["problem_id"])),
    }

    out_path = os.path.join(BASE, "experiment_results/hallucode_full.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\nSaved → {out_path}")

if __name__ == "__main__":
    main()
