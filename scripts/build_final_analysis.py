#!/usr/bin/env python3
"""
build_final_analysis.py — HalluMaze 최종 분석 파이프라인

모든 실험 결과를 병합 → Bootstrap CI → Wilcoxon/Bonferroni → JSON 출력

Usage:
    python3 scripts/build_final_analysis.py
    python3 scripts/build_final_analysis.py --partial   # 아직 완료 안 된 것도 포함
"""
from __future__ import annotations
import json, math, random, argparse
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).parent.parent / "experiment_results"

# ── 데이터 소스 정의 ──────────────────────────────────────────
SOURCES = {
    # Local runs (MiniMax + GLM)
    "checkpoint_rerun": {
        "file": BASE / "checkpoint_rerun.json",
        "model_key": "model",
        "format": "list",
    },
    # OpenRouter phase B (Llama/Gemini/GPT/Haiku)
    "or_phaseB_scout_gemini": {
        "file": BASE / "or_phaseB.json",
        "model_key": "or_model_id",
        "format": "list",
        "filter_models": ["meta-llama/llama-4-scout", "google/gemini-2.0-flash-lite-001"],
    },
    # Completed reruns
    "or_haiku":    {"file": BASE / "or_haiku.json",    "model_key": "or_model_id", "format": "list"},
    "or_gptmini":  {"file": BASE / "or_gptmini.json",  "model_key": "or_model_id", "format": "list"},
    "or_maverick": {"file": BASE / "or_maverick.json", "model_key": "or_model_id", "format": "list"},
    "or_qwen":     {"file": BASE / "or_qwen.json",     "model_key": "or_model_id", "format": "list"},
    # Phase C (SOTA frontier models)
    "or_phaseC":   {"file": BASE / "or_phaseC.json",  "model_key": "or_model_id", "format": "list"},
}

# ── 모델 정규화 이름 ───────────────────────────────────────────
MODEL_DISPLAY = {
    "glm-4.7": "GLM-4.7",
    "MiniMax-M2.5": "MiniMax-M2.5",
    "meta-llama/llama-4-scout": "Llama-4-Scout",
    "meta-llama/llama-4-maverick": "Llama-4-Maverick",
    "google/gemini-2.0-flash-lite-001": "Gemini-2.0-Flash-Lite",
    "openai/gpt-4o-mini": "GPT-4o-mini",
    "anthropic/claude-3-haiku": "Claude-3-Haiku",
    "qwen/qwen-2.5-72b-instruct": "Qwen-2.5-72B",
    "openai/gpt-4o": "GPT-4o",
    "anthropic/claude-3.7-sonnet": "Claude-3.7-Sonnet",
}

BASELINES = {
    "random_walk": {"mei": 0.9, "sr": 1.0, "hrr": 1.0, "brs": 1.0},
    "astar":       {"mei": 0.9, "sr": 1.0, "hrr": 1.0, "brs": 1.0},
    "bfs":         {"mei": 0.9, "sr": 1.0, "hrr": 1.0, "brs": 1.0},
}

def load_all_records(partial: bool = False) -> dict[str, list[dict]]:
    """모든 소스에서 유효 레코드 로드 → 모델별 딕셔너리"""
    by_model: dict[str, list[dict]] = defaultdict(list)
    seen = set()  # (model, size, seed) dedup

    for src_name, cfg in SOURCES.items():
        path = cfg["file"]
        if not path.exists():
            print(f"  [skip] {path.name} not found")
            continue
        try:
            data = json.loads(path.read_text())
        except Exception as e:
            print(f"  [skip] {path.name}: {e}")
            continue

        if not isinstance(data, list):
            data = data.get("raw_trials", data.get("results", []))
        if not isinstance(data, list):
            continue

        filter_m = set(cfg.get("filter_models", []))
        mk = cfg.get("model_key", "model")

        for r in data:
            if r.get("error"):
                continue
            if r.get("sr") is None and r.get("mei") is None:
                continue

            raw_model = r.get(mk, r.get("model", "?"))
            if filter_m and raw_model not in filter_m:
                continue

            display = MODEL_DISPLAY.get(raw_model, raw_model)
            size = r.get("size", 5)
            seed = r.get("seed", 0)
            key = (display, size, seed)
            if key in seen:
                continue
            seen.add(key)
            by_model[display].append(r)

    return dict(by_model)


def bootstrap_ci(values: list[float], n_boot: int = 2000, ci: float = 0.95) -> tuple[float, float, float]:
    """Bootstrap confidence interval"""
    if not values:
        return 0.0, 0.0, 0.0
    rng = random.Random(42)
    n = len(values)
    means = []
    for _ in range(n_boot):
        sample = [values[rng.randint(0, n-1)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int(n_boot * (1 - ci) / 2)]
    hi = means[int(n_boot * (1 - (1 - ci) / 2)) - 1]
    mean = sum(values) / n
    return mean, lo, hi


def _norm_cdf(x: float) -> float:
    """Standard normal CDF via error function"""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def one_sample_wilcoxon(values: list[float], mu0: float = 0.9) -> float:
    """One-sample Wilcoxon signed-rank test against constant mu0.
    Appropriate when comparing LLM MEI values against a deterministic baseline
    with zero variance. Normal approximation (n>=10).
    Returns two-sided p-value.
    """
    diffs = [v - mu0 for v in values if v != mu0]
    n = len(diffs)
    if n == 0:
        return 1.0
    abs_diffs_sorted = sorted(range(n), key=lambda i: abs(diffs[i]))
    # Average ranks for ties
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j < n and abs(diffs[abs_diffs_sorted[j]]) == abs(diffs[abs_diffs_sorted[i]]):
            j += 1
        avg_rank = (i + j + 1) / 2
        for k in range(i, j):
            ranks[abs_diffs_sorted[k]] = avg_rank
        i = j
    W_plus = sum(ranks[i] for i in range(n) if diffs[i] > 0)
    mu_W = n * (n + 1) / 4
    sigma_W = math.sqrt(n * (n + 1) * (2 * n + 1) / 24)
    if sigma_W == 0:
        return 1.0
    z = (W_plus - mu_W) / sigma_W
    return 2 * (1 - _norm_cdf(abs(z)))


def glass_delta(constant_mu: float, values: list[float]) -> float:
    """Glass's delta: (mu_constant - mu_values) / sd_values.
    Use when one group is a constant (zero-variance baseline).
    Standard pooled Cohen's d inflates effect size by sqrt(2) in this case.
    """
    if len(values) < 2:
        return 0.0
    my = sum(values) / len(values)
    sy = math.sqrt(sum((v - my) ** 2 for v in values) / (len(values) - 1))
    return abs(constant_mu - my) / sy if sy > 1e-9 else 0.0


def build_analysis(partial: bool = False):
    print("=== HalluMaze Final Analysis Builder ===")
    records = load_all_records(partial)

    if not records:
        print("ERROR: No valid records found.")
        return

    # ── Summary stats per model ──────────────────────────────
    summary = {}
    for model, recs in sorted(records.items()):
        mei_vals = [r.get("mei", r.get("hallumaze_score", 0)) for r in recs]
        sr_vals  = [r.get("sr", 0) for r in recs]
        hrr_vals = [r.get("hrr", 0) for r in recs]
        brs_vals = [r.get("brs", 0) for r in recs]
        hc_vals  = [r.get("hallucination_count", 0) for r in recs]

        mei_m, mei_lo, mei_hi = bootstrap_ci(mei_vals)
        sr_m,  sr_lo,  sr_hi  = bootstrap_ci(sr_vals)
        hrr_m, hrr_lo, hrr_hi = bootstrap_ci(hrr_vals)
        brs_m, brs_lo, brs_hi = bootstrap_ci(brs_vals)

        summary[model] = {
            "n": len(recs),
            "mei":  {"mean": round(mei_m,4), "ci_lo": round(mei_lo,4), "ci_hi": round(mei_hi,4)},
            "sr":   {"mean": round(sr_m,4),  "ci_lo": round(sr_lo,4),  "ci_hi": round(sr_hi,4)},
            "hrr":  {"mean": round(hrr_m,4), "ci_lo": round(hrr_lo,4), "ci_hi": round(hrr_hi,4)},
            "brs":  {"mean": round(brs_m,4), "ci_lo": round(brs_lo,4), "ci_hi": round(brs_hi,4)},
            "hc_mean": round(sum(hc_vals)/len(hc_vals),2) if hc_vals else 0,
        }
        print(f"  {model:30s} n={len(recs):3d}  MEI={mei_m:.3f} [{mei_lo:.3f},{mei_hi:.3f}]  SR={sr_m:.3f}  HRR={hrr_m:.3f}")

    # ── Baselines ────────────────────────────────────────────
    rw_mei = [BASELINES["random_walk"]["mei"]] * 60
    summary["random_walk"] = {
        "n": 60, "is_baseline": True,
        "mei":  {"mean": 0.9, "ci_lo": 0.9, "ci_hi": 0.9},
        "sr":   {"mean": 1.0, "ci_lo": 1.0, "ci_hi": 1.0},
        "hrr":  {"mean": 1.0, "ci_lo": 1.0, "ci_hi": 1.0},
        "brs":  {"mean": 1.0, "ci_lo": 1.0, "ci_hi": 1.0},
        "hc_mean": 0,
    }
    for b in ["astar", "bfs"]:
        summary[b] = {**summary["random_walk"], "n": 60}

    # ── Pairwise tests (vs random_walk) ──────────────────────
    k = len([m for m in records])
    alpha_bonf = 0.05 / k if k else 0.05

    pairwise = {}
    for model, recs in records.items():
        mei_vals = [r.get("mei", r.get("hallumaze_score", 0)) for r in recs]
        # One-sample Wilcoxon signed-rank test vs constant baseline mu0=0.9
        p_raw = one_sample_wilcoxon(mei_vals, mu0=BASELINES["random_walk"]["mei"])
        p_bonf = min(p_raw * k, 1.0)
        # Glass's delta (appropriate when baseline has zero variance)
        d = glass_delta(BASELINES["random_walk"]["mei"], mei_vals)
        pairwise[model] = {
            "n": len(recs),
            "p_raw": round(p_raw, 6),
            "p_bonferroni": round(p_bonf, 6),
            "cohens_d": round(d, 3),  # Glass's delta (one-sample, constant baseline)
            "significant_bonf": p_bonf < 0.05,
        }

    # ── Sort by MEI descending ────────────────────────────────
    llm_models = {m: v for m, v in summary.items() if not v.get("is_baseline") and m not in ("astar","bfs","random_walk")}
    sorted_models = sorted(llm_models.keys(), key=lambda m: -summary[m]["mei"]["mean"])

    output = {
        "metadata": {
            "k_bonferroni": k,
            "alpha_bonferroni": round(alpha_bonf, 4),
            "n_boot": 2000,
            "ci_level": 0.95,
            "total_valid_trials": sum(v["n"] for v in llm_models.values()),
            "models_by_mei": sorted_models,
        },
        "summary": summary,
        "pairwise_tests": pairwise,
    }

    out_path = BASE / "analysis_final2.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"\n✓ Saved: {out_path}")
    print(f"  Models: {', '.join(sorted_models)}")
    print(f"  Total valid trials: {output['metadata']['total_valid_trials']}")
    return output


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--partial", action="store_true", help="Include incomplete runs")
    args = ap.parse_args()
    build_analysis(partial=args.partial)
