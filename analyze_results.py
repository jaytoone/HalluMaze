#!/usr/bin/env python3
"""
analyze_results.py — Statistical analysis for HalluMaze paper

Produces:
  1. Per-model summary table (mean ± 95% CI)
  2. Pairwise Wilcoxon rank-sum tests (+ Bonferroni correction)
  3. Cohen's d effect sizes
  4. Baseline comparison table
  5. Paper-ready JSON summary

Usage:
  python3 analyze_results.py \
    --llm experiment_results/checkpoint_rerun.json \
    --baselines experiment_results/baselines.json \
    --out experiment_results/analysis_final.json
"""

import json
import math
import argparse
import random
from pathlib import Path
from itertools import combinations


# ─── Bootstrap CI ──────────────────────────────────────────────────────────

def bootstrap_ci(values: list[float], stat=None, n_boot=2000, alpha=0.05, seed=42) -> tuple[float, float, float]:
    """Returns (mean, lower, upper) bootstrap 95% CI."""
    rng = random.Random(seed)
    n = len(values)
    if n == 0:
        return 0.0, 0.0, 0.0
    if stat is None:
        stat = lambda x: sum(x) / len(x)
    obs = stat(values)
    boots = []
    for _ in range(n_boot):
        sample = [rng.choice(values) for _ in range(n)]
        boots.append(stat(sample))
    boots.sort()
    lo = boots[int(alpha/2 * n_boot)]
    hi = boots[int((1 - alpha/2) * n_boot)]
    return round(obs, 4), round(lo, 4), round(hi, 4)


# ─── Wilcoxon rank-sum (Mann-Whitney U) ─────────────────────────────────────

def mannwhitney_u(x: list[float], y: list[float]) -> tuple[float, float]:
    """Returns (U-statistic, p-value approx via normal approximation)."""
    nx, ny = len(x), len(y)
    if nx == 0 or ny == 0:
        return float('nan'), 1.0
    # Rank combined
    combined = [(v, 0) for v in x] + [(v, 1) for v in y]
    combined.sort()
    ranks = [0.0] * len(combined)
    i = 0
    while i < len(combined):
        j = i
        while j < len(combined) and combined[j][0] == combined[i][0]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[k] = avg_rank
        i = j
    u1 = 0.0
    xi_idx = [k for k, (_, g) in enumerate(combined) if g == 0]
    for k in xi_idx:
        u1 += ranks[k]
    u1 -= nx * (nx + 1) / 2.0
    u2 = nx * ny - u1
    u = min(u1, u2)
    # Normal approximation
    mu = nx * ny / 2.0
    sigma = math.sqrt(nx * ny * (nx + ny + 1) / 12.0)
    if sigma == 0:
        return u, 1.0
    z = (u - mu) / sigma
    p = 2 * _norm_cdf(abs(z))  # two-tailed, p-value = 2*(1-CDF)
    return round(u, 1), round(p, 6)


def _norm_cdf(z: float) -> float:
    """Complementary standard normal CDF."""
    t = 1 / (1 + 0.2316419 * abs(z))
    d = 0.3989423 * math.exp(-z*z/2)
    p = d*t*(0.3193815 + t*(-0.3565638 + t*(1.7814779 + t*(-1.8212560 + t*1.3302744))))
    return p  # P(Z > z)


# ─── Cohen's d ──────────────────────────────────────────────────────────────

def cohens_d(x: list[float], y: list[float]) -> float:
    """Hedges' g variant: uses max(sd_x, sd_y) when one group has near-zero variance
    to avoid inflated d when comparing against a constant baseline."""
    nx, ny = len(x), len(y)
    if nx < 2 or ny < 2:
        return float('nan')
    mx, my = sum(x)/nx, sum(y)/ny
    vx = sum((v-mx)**2 for v in x) / (nx-1)
    vy = sum((v-my)**2 for v in y) / (ny-1)
    # If either group is nearly constant, use the SD of the variable group
    if min(vx, vy) < 1e-8:
        sd = math.sqrt(max(vx, vy, 1e-10))
        if sd < 1e-6:
            return float('nan')  # both constant, d undefined
        return round((mx - my) / sd, 4)
    pooled_var = ((nx-1)*vx + (ny-1)*vy) / (nx+ny-2)
    return round((mx - my) / math.sqrt(pooled_var), 4)


def cohens_d_ci(x: list[float], y: list[float], n_boot: int = 2000, seed: int = 42) -> tuple[float, float, float]:
    """Bootstrap 95% CI for Cohen's d. Returns (d, lo, hi)."""
    rng = random.Random(seed)
    d = cohens_d(x, y)
    if math.isnan(d):
        return d, float('nan'), float('nan')
    boots = []
    for _ in range(n_boot):
        bx = [rng.choice(x) for _ in range(len(x))]
        by = [rng.choice(y) for _ in range(len(y))]
        bd = cohens_d(bx, by)
        if not math.isnan(bd):
            boots.append(bd)
    if not boots:
        return d, float('nan'), float('nan')
    boots.sort()
    lo = boots[int(0.025 * len(boots))]
    hi = boots[int(0.975 * len(boots))]
    return round(d, 4), round(lo, 4), round(hi, 4)


# ─── Main analysis ──────────────────────────────────────────────────────────

def summarize_model(trials: list[dict], key: str = "hallumaze_score") -> dict:
    vals = [t[key] for t in trials if key in t]
    if not vals:
        return {}
    mean, lo, hi = bootstrap_ci(vals)
    return {
        "n": len(vals),
        "mean": mean,
        "ci_lo": lo,
        "ci_hi": hi,
        "std": round(math.sqrt(sum((v-mean)**2 for v in vals)/max(len(vals)-1,1)), 4),
        "min": round(min(vals), 4),
        "max": round(max(vals), 4),
    }


def analyze(llm_path: str, baselines_path: str, out_path: str):
    with open(llm_path) as f:
        llm_trials = json.load(f)
    with open(baselines_path) as f:
        baseline_trials = json.load(f)

    all_trials = llm_trials + baseline_trials

    # Group by model
    groups: dict[str, list[dict]] = {}
    for t in all_trials:
        groups.setdefault(t["model"], []).append(t)

    model_order = sorted(groups.keys(), key=lambda m:
        -sum(t.get("hallumaze_score", 0) for t in groups[m]) / max(len(groups[m]), 1))

    # ── Table 1: Summary stats ───────────────────────────────────────────
    print("\n" + "="*90)
    print(f"{'Model':<22} {'n':>4}  {'SR':>7}  {'MEI':>7}  {'HRR':>7}  {'BRS':>7}  {'Score':>7}")
    print("-"*90)

    summary = {}
    for model in model_order:
        ts = groups[model]
        n = len(ts)
        def avg(k): return sum(t.get(k, 0) for t in ts) / n

        sr_mean, sr_lo, sr_hi = bootstrap_ci([t.get("sr", 0) for t in ts])
        mei_mean, mei_lo, mei_hi = bootstrap_ci([t.get("mei", 0) for t in ts])
        score_mean, score_lo, score_hi = bootstrap_ci([t.get("hallumaze_score", 0) for t in ts])

        print(f"{model:<22} {n:>4}  "
              f"{sr_mean:.3f}[{sr_lo:.3f}-{sr_hi:.3f}]  "
              f"{mei_mean:.3f}  "
              f"{avg('hrr'):.3f}  "
              f"{avg('brs'):.3f}  "
              f"{score_mean:.3f}[{score_lo:.3f}-{score_hi:.3f}]")

        # OCE/UCE: only for models that express confidence (non-None values)
        oce_vals = [t["oce"] for t in ts if t.get("oce") is not None]
        uce_vals = [t["uce"] for t in ts if t.get("uce") is not None]
        oce_mean = round(sum(oce_vals)/len(oce_vals), 4) if oce_vals else None
        uce_mean = round(sum(uce_vals)/len(uce_vals), 4) if uce_vals else None

        summary[model] = {
            "n": n,
            "sr": {"mean": sr_mean, "ci_lo": sr_lo, "ci_hi": sr_hi},
            "mei": summarize_model(ts, "mei"),
            "hrr": summarize_model(ts, "hrr"),
            "brs": summarize_model(ts, "brs"),
            "score": {"mean": score_mean, "ci_lo": score_lo, "ci_hi": score_hi},
            "oce": oce_mean,
            "uce": uce_mean,
        }

    print("="*90)

    # ── By size breakdown ─────────────────────────────────────────────
    print("\n── By maze size ──")
    for size in [5, 7]:
        print(f"\n  {size}×{size}:")
        for model in model_order:
            ts = [t for t in groups[model] if t.get("size") == size]
            if not ts:
                continue
            n = len(ts)
            def avg(k): return sum(t.get(k,0) for t in ts)/n
            sr_m, sr_lo, sr_hi = bootstrap_ci([t.get("sr",0) for t in ts])
            score_m, sc_lo, sc_hi = bootstrap_ci([t.get("hallumaze_score",0) for t in ts])
            print(f"    {model:<22} n={n}  SR={sr_m:.3f}[{sr_lo:.3f}-{sr_hi:.3f}]  "
                  f"score={score_m:.3f}[{sc_lo:.3f}-{sc_hi:.3f}]")

    # ── Table 2: Pairwise Wilcoxon + Bonferroni ──────────────────────────
    llm_models = [m for m in model_order if m not in ("astar", "bfs")]
    pairs = list(combinations(llm_models, 2))
    n_tests = len(pairs)

    print(f"\n── Pairwise Wilcoxon rank-sum (Bonferroni α=0.05/{n_tests}={0.05/max(n_tests,1):.4f}) ──")
    print(f"{'A':<22} {'B':<22} {'U':>8} {'p_raw':>10} {'p_bonf':>10} {'d [95% CI]':>20} {'sig':>5}")
    print("-"*100)

    pairwise = []
    for m1, m2 in pairs:
        x = [t.get("hallumaze_score", 0) for t in groups[m1]]
        y = [t.get("hallumaze_score", 0) for t in groups[m2]]
        u, p = mannwhitney_u(x, y)
        p_bonf = min(1.0, p * n_tests)
        d, d_lo, d_hi = cohens_d_ci(x, y)
        d_str = f"{d:.3f}[{d_lo:.3f},{d_hi:.3f}]" if not math.isnan(d) else "nan"
        sig = "*" if p_bonf < 0.05 else ("†" if p < 0.05 else "")
        print(f"{m1:<22} {m2:<22} {u:>8.1f} {p:>10.4f} {p_bonf:>10.4f} {d_str:>20} {sig:>5}")
        pairwise.append({
            "model_a": m1, "model_b": m2,
            "U": u, "p_raw": p, "p_bonferroni": round(p_bonf, 6),
            "cohens_d": d if not math.isnan(d) else None,
            "cohens_d_ci_lo": d_lo if not math.isnan(d_lo) else None,
            "cohens_d_ci_hi": d_hi if not math.isnan(d_hi) else None,
            "significant": p_bonf < 0.05
        })

    print("* p_bonf < 0.05  † p_raw < 0.05 (not Bonferroni-corrected)")

    # ── Benjamini-Hochberg FDR ────────────────────────────────────────
    p_raws = [pw["p_raw"] for pw in pairwise]
    bh_thresholds = [(i+1) * 0.05 / n_tests for i in range(n_tests)]
    sorted_p_idx = sorted(range(n_tests), key=lambda i: p_raws[i])
    bh_reject = [False] * n_tests
    last_reject = -1
    for rank, idx in enumerate(sorted_p_idx):
        if p_raws[idx] <= bh_thresholds[rank]:
            last_reject = rank
    for rank in range(last_reject + 1):
        bh_reject[sorted_p_idx[rank]] = True
    for i, pw in enumerate(pairwise):
        pw["bh_fdr_reject"] = bh_reject[i]

    print(f"\n── BH-FDR (q=0.05) summary ──")
    for pw in pairwise:
        mark = "✓" if pw["bh_fdr_reject"] else "✗"
        print(f"  {mark} {pw['model_a']:<20} vs {pw['model_b']:<20} p={pw['p_raw']:.4f}")

    # ── CE-free primary metrics (SR + MEI) ────────────────────────────
    print("\n── Primary metrics: SR and MEI (CE-free) ──")
    for model in model_order:
        ts = groups[model]
        n = len(ts)
        sr_m, sr_lo, sr_hi = bootstrap_ci([t.get("sr", 0) for t in ts])
        mei_m, mei_lo, mei_hi = bootstrap_ci([t.get("mei", 0) for t in ts])
        print(f"  {model:<22} SR={sr_m:.3f}[{sr_lo:.3f}-{sr_hi:.3f}]  MEI={mei_m:.3f}[{mei_lo:.3f}-{mei_hi:.3f}]")

    # ── OCE / UCE calibration decomposition ──────────────────────────
    print("\n── Calibration decomposition: OCE (overconfidence) vs UCE (underconfidence) ──")
    print(f"  {'Model':<22}  {'OCE':>7}  {'UCE':>7}  {'CE':>7}  note")
    print("  " + "-"*65)
    for model in model_order:
        ts = groups[model]
        oce_vals = [t["oce"] for t in ts if t.get("oce") is not None]
        uce_vals = [t["uce"] for t in ts if t.get("uce") is not None]
        ce_vals  = [t["ce"]  for t in ts if t.get("ce")  is not None]
        if oce_vals:
            oce_m = sum(oce_vals)/len(oce_vals)
            uce_m = sum(uce_vals)/len(uce_vals)
            ce_m  = sum(ce_vals)/len(ce_vals)
            dom = "OVERCONF" if oce_m > uce_m else "UNDERCONF"
            print(f"  {model:<22}  {oce_m:.4f}  {uce_m:.4f}  {ce_m:.4f}  [{dom}]")
        else:
            print(f"  {model:<22}  {'N/A':>7}  {'N/A':>7}  {'N/A':>7}  [no confidence expressed → CE=None]")

    # ── LLM vs baselines ──────────────────────────────────────────────
    print("\n── LLM vs Random Walk baseline ──")
    rw_scores = [t.get("hallumaze_score", 0) for t in groups.get("random_walk", [])]
    for model in [m for m in model_order if m not in ("astar", "bfs", "random_walk")]:
        llm_scores = [t.get("hallumaze_score", 0) for t in groups[model]]
        if not llm_scores or not rw_scores:
            continue
        u, p = mannwhitney_u(llm_scores, rw_scores)
        d = cohens_d(llm_scores, rw_scores)
        llm_m = sum(llm_scores)/len(llm_scores)
        rw_m = sum(rw_scores)/len(rw_scores)
        direction = ">" if llm_m > rw_m else "<"
        sig = "**" if p < 0.01 else ("*" if p < 0.05 else "ns")
        print(f"  {model:<22} {direction} random_walk  p={p:.4f} {sig}  d={d:.3f}")

    # ── Save ─────────────────────────────────────────────────────────────
    result = {
        "summary": summary,
        "pairwise_tests": pairwise,
        "metadata": {
            "n_boot": 2000,
            "alpha": 0.05,
            "n_tests_bonferroni": n_tests,
            "corrections": ["Bonferroni", "BH-FDR"],
            "primary_metrics": ["sr", "mei"],
            "composite_metric": "hallumaze_score",
            "ce_note": "CE=None imputed as 0.5 for baselines. Use SR+MEI as primary paper metrics. CE decomposed into OCE (overconfidence, confident+wrong) and UCE (underconfidence, unconfident+right). OCE+UCE=CE by construction.",
        }
    }
    Path(out_path).parent.mkdir(exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n→ Saved analysis to {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm",        default="experiment_results/checkpoint_rerun.json")
    ap.add_argument("--baselines",  default="experiment_results/baselines.json")
    ap.add_argument("--out",        default="experiment_results/analysis_final.json")
    args = ap.parse_args()
    analyze(args.llm, args.baselines, args.out)


if __name__ == "__main__":
    main()
