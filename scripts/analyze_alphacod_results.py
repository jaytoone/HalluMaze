#!/usr/bin/env python3
"""Quick McNemar analysis for AlphaCodium-style experiment results."""
import json, sys
from math import comb

def load(path):
    with open(path) as f:
        return json.load(f)

def mcnemar_exact(n01, n10):
    """Two-sided exact binomial McNemar p-value."""
    n = n01 + n10
    if n == 0: return 1.0
    min_val = min(n01, n10)
    p = 2 * sum(comb(n, k) * (0.5**n) for k in range(min_val + 1))
    return min(p, 1.0)

def analyze(baseline_path, alphacod_path):
    bl = load(baseline_path)
    ac = load(alphacod_path)

    bl_map = {r["task_id"]: r["passed"] for r in bl["results"] if "error" not in r}
    ac_map = {r["task_id"]: r["passed"] for r in ac["results"] if "error" not in r}

    common = set(bl_map) & set(ac_map)
    print(f"Matched pairs: {len(common)}")

    TT = FF = TF = FT = 0
    for tid in common:
        b, a = bl_map[tid], ac_map[tid]
        if b and a: TT += 1
        elif not b and not a: FF += 1
        elif b and not a: TF += 1
        else: FT += 1

    print(f"TT={TT} FF={FF} TF(bl_pass,ac_fail)={TF} FT(bl_fail,ac_pass)={FT}")
    print(f"n01 (alphacod-only pass): {FT}")
    print(f"n10 (baseline-only pass): {TF}")

    bl_rate = sum(1 for v in bl_map.values() if v) / len(bl_map)
    ac_rate = sum(1 for v in ac_map.values() if v) / len(ac_map)
    bl_matched = sum(1 for tid in common if bl_map[tid]) / len(common)
    ac_matched = sum(1 for tid in common if ac_map[tid]) / len(common)

    print(f"\nBaseline pass@1 (all):     {bl_rate:.4f} ({bl['passed']}/{bl['n_valid']})")
    print(f"AlphaCod pass@1 (all):     {ac_rate:.4f} ({ac['passed']}/{ac['n_valid']})")
    print(f"Baseline pass@1 (matched): {bl_matched:.4f}")
    print(f"AlphaCod pass@1 (matched): {ac_matched:.4f}")
    print(f"Delta (matched):           {ac_matched - bl_matched:+.4f}")

    p = mcnemar_exact(FT, TF)
    print(f"\nMcNemar exact 2-sided p = {p:.4f}")
    print(f"Significant (alpha=0.05)? {'YES ***' if p < 0.05 else 'NO'}")

    if ac["results"]:
        alphacod_results = [r for r in ac["results"] if "repairs_used" in r]
        if alphacod_results:
            avg_rep = sum(r["repairs_used"] for r in alphacod_results) / len(alphacod_results)
            avg_tests = sum(r.get("n_synthetic_tests", 0) for r in alphacod_results) / len(alphacod_results)
            print(f"\nAlphaCod stats:")
            print(f"  Avg repairs used:    {avg_rep:.2f}")
            print(f"  Avg synthetic tests: {avg_tests:.1f}")
            recovered = [r for r in alphacod_results if r["passed"] and r["repairs_used"] > 0]
            print(f"  Repairs that helped: {len(recovered)} problems recovered via repair")

if __name__ == "__main__":
    import glob, os
    baseline = sys.argv[1] if len(sys.argv) > 1 else None
    alphacod = sys.argv[2] if len(sys.argv) > 2 else None

    if not baseline:
        files = sorted(glob.glob("experiment_results/alphacod_bcb_hard_qwen25_baseline_n*.json"))
        baseline = files[-1] if files else None
    if not alphacod:
        files = sorted(glob.glob("experiment_results/alphacod_bcb_hard_qwen25_alphacod_n*.json"))
        alphacod = files[-1] if files else None

    if not baseline or not alphacod:
        print(f"Usage: python3 {sys.argv[0]} <baseline.json> <alphacod.json>")
        print(f"Or run experiment first with: python3 scripts/run_alphacod_bigcodebench.py --mode both")
        sys.exit(1)

    print(f"Baseline: {baseline}")
    print(f"AlphaCod: {alphacod}")
    print("=" * 50)
    analyze(baseline, alphacod)
