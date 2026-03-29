#!/usr/bin/env python3
"""
HalluCode Statistical Analysis — NeurIPS-grade
Bootstrap CI (n_boot=2000) + Cohen's d + Wilcoxon signed-rank
Outputs: console report + hallucode_stats.json
"""
import json, os, sys
import numpy as np
from scipy import stats as scipy_stats
from collections import defaultdict

np.random.seed(42)
N_BOOT = 2000
ALPHA = 0.05
PROBLEMS = [f"HC{i:03d}" for i in range(1, 20)]  # HC001-HC019

# ─── Data Loading ─────────────────────────────────────────────────────────────

def load_scores_by_problem(fname, filter_errors=True):
    """Returns dict {problem_id: code_mei} from a results file."""
    with open(fname) as f:
        d = json.load(f)
    results = d.get('results', []) or d.get('raw_results', [])
    out = {}
    for r in results:
        if filter_errors and r.get('error'):
            continue
        pid = r.get('problem_id')
        mei = r.get('code_mei') if r.get('code_mei') is not None else r.get('codemei')
        if pid and mei is not None:
            out[pid] = float(mei)
    return out


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(BASE_DIR, "experiment_results")

# GLM data
glm_baseline_raw = load_scores_by_problem(os.path.join(RESULTS_DIR, "hallucode_baseline_glm.json"))
glm_ap_raw = load_scores_by_problem(os.path.join(RESULTS_DIR, "hallucode_booster_glm.json"))

# GLM MARL-SL from hallucode_full.json
with open(os.path.join(RESULTS_DIR, "hallucode_full.json")) as f:
    full = json.load(f)
rr = full.get('raw_results', [])
glm_marl_raw = {r['problem_id']: float(r['code_mei']) for r in rr if r.get('model') == 'glm-free'}
lfm_marl_raw = {r['problem_id']: float(r['code_mei']) for r in rr if r.get('model') == 'lfm-1b-free'}

# LFM data
lfm_baseline_raw = load_scores_by_problem(os.path.join(RESULTS_DIR, "hallucode_baseline_lfm.json"))
lfm_ap_raw = load_scores_by_problem(os.path.join(RESULTS_DIR, "hallucode_booster_lfm.json"))

# Also get per-problem trap type info
TRAP_TYPE_MAP = {}
for r in rr:
    TRAP_TYPE_MAP[r['problem_id']] = r.get('trap_type', 'unknown')
# Fill from booster file too
with open(os.path.join(RESULTS_DIR, "hallucode_booster_glm.json")) as f:
    bg = json.load(f)
for r in bg.get('results', []):
    TRAP_TYPE_MAP[r['problem_id']] = r.get('trap_type', TRAP_TYPE_MAP.get(r['problem_id'], 'unknown'))


# ─── Bootstrap CI ─────────────────────────────────────────────────────────────

def bootstrap_mean_ci(scores, n_boot=N_BOOT, alpha=ALPHA):
    """Bootstrap 95% CI for mean. scores: list of floats."""
    arr = np.array(scores)
    means = [np.mean(np.random.choice(arr, size=len(arr), replace=True)) for _ in range(n_boot)]
    lo = np.percentile(means, 100 * alpha / 2)
    hi = np.percentile(means, 100 * (1 - alpha / 2))
    return np.mean(arr), lo, hi


def bootstrap_diff_ci(a, b, n_boot=N_BOOT, alpha=ALPHA):
    """Bootstrap 95% CI for mean(a) - mean(b). Paired if same length."""
    a, b = np.array(a), np.array(b)
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    diffs = []
    for _ in range(n_boot):
        idx = np.random.randint(0, n, n)
        diffs.append(np.mean(a[idx]) - np.mean(b[idx]))
    lo = np.percentile(diffs, 100 * alpha / 2)
    hi = np.percentile(diffs, 100 * (1 - alpha / 2))
    return np.mean(a) - np.mean(b), lo, hi


# ─── Cohen's d ────────────────────────────────────────────────────────────────

def cohens_d(a, b):
    """Cohen's d for two independent samples (pooled SD)."""
    a, b = np.array(a), np.array(b)
    pooled_sd = np.sqrt((np.std(a, ddof=1)**2 + np.std(b, ddof=1)**2) / 2)
    if pooled_sd == 0:
        return float('inf') if np.mean(a) != np.mean(b) else 0.0
    return (np.mean(a) - np.mean(b)) / pooled_sd


def cohens_d_paired(diff):
    """Cohen's d for paired differences."""
    diff = np.array(diff)
    sd = np.std(diff, ddof=1)
    if sd == 0:
        return float('inf') if np.mean(diff) != 0 else 0.0
    return np.mean(diff) / sd


# ─── Aligned problem sets ─────────────────────────────────────────────────────

def align(a_dict, b_dict):
    """Return aligned arrays over common problems."""
    common = sorted(set(a_dict) & set(b_dict))
    return [a_dict[p] for p in common], [b_dict[p] for p in common], common


def wilcoxon(a, b):
    """Wilcoxon signed-rank p-value (paired)."""
    a, b = np.array(a), np.array(b)
    diff = a - b
    if np.all(diff == 0):
        return 1.0
    try:
        _, p = scipy_stats.wilcoxon(diff, alternative='two-sided')
        return p
    except Exception:
        return float('nan')


# ─── Comparison function ──────────────────────────────────────────────────────

def compare(name, a_dict, b_dict, label_a, label_b):
    a, b, common = align(a_dict, b_dict)
    n = len(common)
    mean_a = np.mean(a)
    mean_b = np.mean(b)
    delta = mean_a - mean_b
    diff_est, lo, hi = bootstrap_diff_ci(a, b)
    p_val = wilcoxon(a, b)
    d = cohens_d_paired([x - y for x, y in zip(a, b)])
    return {
        "comparison": f"{label_a} vs {label_b}",
        "model": name,
        "n_problems": n,
        "mean_a": round(float(mean_a), 4),
        "mean_b": round(float(mean_b), 4),
        "delta": round(float(delta), 4),
        "bootstrap_ci_95": [round(float(lo), 4), round(float(hi), 4)],
        "p_wilcoxon": round(float(p_val), 6) if not np.isnan(p_val) else None,
        "cohens_d": round(float(d), 3),
        "sig": bool(p_val < ALPHA) if not np.isnan(p_val) else None,
        "label_a": label_a,
        "label_b": label_b
    }


# ─── Per-trap-type breakdown ──────────────────────────────────────────────────

def per_trap_stats(scores_dict):
    by_trap = defaultdict(list)
    for pid, mei in scores_dict.items():
        trap = TRAP_TYPE_MAP.get(pid, 'unknown')
        by_trap[trap].append(mei)
    return {
        trap: {
            "n": len(vals),
            "mean_mei": round(float(np.mean(vals)), 4),
            "sd": round(float(np.std(vals, ddof=1) if len(vals) > 1 else 0), 4)
        }
        for trap, vals in sorted(by_trap.items())
    }


# ─── Main Analysis ────────────────────────────────────────────────────────────

results = {}

print("=" * 70)
print("HalluCode Statistical Analysis — NeurIPS grade")
print("=" * 70)

# GLM comparisons
print("\n[GLM-4.5-Air]")
for cmp in [
    compare("GLM", glm_ap_raw, glm_baseline_raw, "AP Booster", "Baseline"),
    compare("GLM", glm_marl_raw, glm_baseline_raw, "MARL-SL", "Baseline"),
    compare("GLM", glm_ap_raw, glm_marl_raw, "AP Booster", "MARL-SL"),
]:
    sig_str = f"p={cmp['p_wilcoxon']:.4f}{'*' if cmp['sig'] else ''}"
    print(f"  {cmp['comparison']:30s}  Δ={cmp['delta']:+.4f}  "
          f"95%CI=[{cmp['bootstrap_ci_95'][0]:+.4f},{cmp['bootstrap_ci_95'][1]:+.4f}]  "
          f"d={cmp['cohens_d']:+.3f}  {sig_str}  n={cmp['n_problems']}")
    results[f"glm_{cmp['comparison'].replace(' ', '_').replace('/', '-')}"] = cmp

# LFM comparisons
print("\n[LFM-1.2B-Thinking]")
for cmp in [
    compare("LFM", lfm_ap_raw, lfm_baseline_raw, "AP Booster", "Baseline"),
    compare("LFM", lfm_marl_raw, lfm_baseline_raw, "MARL-SL", "Baseline"),
    compare("LFM", lfm_ap_raw, lfm_marl_raw, "AP Booster", "MARL-SL"),
]:
    sig_str = f"p={cmp['p_wilcoxon']:.4f}{'*' if cmp['sig'] else ''}" if cmp['p_wilcoxon'] else "p=N/A"
    print(f"  {cmp['comparison']:30s}  Δ={cmp['delta']:+.4f}  "
          f"95%CI=[{cmp['bootstrap_ci_95'][0]:+.4f},{cmp['bootstrap_ci_95'][1]:+.4f}]  "
          f"d={cmp['cohens_d']:+.3f}  {sig_str}  n={cmp['n_problems']}")
    results[f"lfm_{cmp['comparison'].replace(' ', '_').replace('/', '-')}"] = cmp

# Per-condition descriptive stats with CI
print("\n[Per-Condition Bootstrap CI]")
conditions = {
    "GLM Baseline": list(glm_baseline_raw.values()),
    "GLM MARL-SL": list(glm_marl_raw.values()),
    "GLM AP Booster": list(glm_ap_raw.values()),
    "LFM Baseline": list(lfm_baseline_raw.values()),
    "LFM MARL-SL": [v for v in lfm_marl_raw.values() if v is not None],
    "LFM AP Booster": list(lfm_ap_raw.values()),
}
desc_stats = {}
for name, scores in conditions.items():
    if not scores:
        continue
    mean, lo, hi = bootstrap_mean_ci(scores)
    n = len(scores)
    print(f"  {name:22s}  n={n:2d}  mean={mean:.4f}  95%CI=[{lo:.4f},{hi:.4f}]")
    desc_stats[name] = {"n": n, "mean": round(float(mean),4), "ci_lo": round(float(lo),4), "ci_hi": round(float(hi),4)}

# Per-trap-type breakdown
print("\n[Per-Trap-Type Breakdown — GLM AP Booster]")
trap_breakdown = per_trap_stats(glm_ap_raw)
for trap, stats in trap_breakdown.items():
    print(f"  {trap:25s}  n={stats['n']}  mean={stats['mean_mei']:.4f}  sd={stats['sd']:.4f}")

print("\n[Per-Trap-Type Breakdown — LFM AP Booster]")
lfm_trap_breakdown = per_trap_stats(lfm_ap_raw)
for trap, stats in lfm_trap_breakdown.items():
    print(f"  {trap:25s}  n={stats['n']}  mean={stats['mean_mei']:.4f}  sd={stats['sd']:.4f}")

# Save
output = {
    "comparisons": results,
    "descriptive": desc_stats,
    "trap_breakdown": {
        "GLM_AP": trap_breakdown,
        "LFM_AP": lfm_trap_breakdown,
        "GLM_MARL": per_trap_stats(glm_marl_raw),
        "LFM_MARL": per_trap_stats(lfm_marl_raw),
        "GLM_Baseline": per_trap_stats(glm_baseline_raw),
        "LFM_Baseline": per_trap_stats(lfm_baseline_raw),
    },
    "n_bootstrap": N_BOOT,
    "alpha": ALPHA
}
out_path = os.path.join(RESULTS_DIR, "hallucode_stats.json")
with open(out_path, 'w') as f:
    json.dump(output, f, indent=2)
print(f"\nSaved → {out_path}")
