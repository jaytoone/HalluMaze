#!/usr/bin/env python3
"""
run_icc_experiment.py — HalluMaze ICC (Intraclass Correlation) 재현성 측정

Purpose:
    동일 모델 × 동일 seed × 2회 실행 → ICC 계산
    NeurIPS 2026 한계 해결: "Temperature stochasticity — test-retest ICC not yet measured"
    목표: ICC > 0.8 (good reliability)

Protocol:
    - 3 models × 10 seeds × 2 runs = 60 total trials
    - 동일 파라미터 (temperature=0.7) 두 번 실행
    - ICC(2,1) two-way mixed, absolute agreement

Usage:
    python3 scripts/run_icc_experiment.py
    python3 scripts/run_icc_experiment.py --models claude-3.7-sonnet,glm-4.7
    python3 scripts/run_icc_experiment.py --seeds 10 --runs 2

Output:
    experiment_results/icc_results.json
"""
from __future__ import annotations

import sys, os, json, re, argparse, math
from datetime import datetime
from pathlib import Path

def _load_env(path):
    try:
        with open(os.path.expanduser(path)) as f:
            for line in f:
                m = re.match(r'^(?:export\s+)?([A-Za-z_]\w*)=(.+)$', line.strip())
                if m:
                    os.environ.setdefault(m.group(1), m.group(2).strip('"\''))
    except FileNotFoundError:
        pass

_load_env("~/.claude/env/shared.env")
_load_env(".envrc")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'files'))
from hallumaze import LLMProvider, MazeConfig, MazeEngine, BenchmarkRunner

import openai

OPENROUTER_BASE = "https://openrouter.ai/api/v1"

ICC_MODELS = {
    "claude-3.7-sonnet": "anthropic/claude-3.7-sonnet",
    "glm-4.7":           "thudm/glm-4.7",
    "llama-4-maverick":  "meta-llama/llama-4-maverick",
}

DEFAULT_SEEDS = [1001, 1002, 1003, 2001, 2002, 3001, 3002, 4001, 4002, 5001]


def compute_icc(ratings: list[tuple[float, float]]) -> dict:
    """
    ICC(2,1) Two-way mixed, absolute agreement.
    ratings: list of (run1_score, run2_score) per subject (seed).
    Returns: icc, ci_lower, ci_upper, interpretation
    """
    n = len(ratings)
    k = 2  # raters (runs)

    # Grand mean
    all_scores = [s for pair in ratings for s in pair]
    grand_mean = sum(all_scores) / len(all_scores)

    # Subject means
    subj_means = [(r1 + r2) / 2 for r1, r2 in ratings]

    # SS between subjects
    ssb = k * sum((m - grand_mean) ** 2 for m in subj_means)
    # SS within subjects
    ssw = sum((r1 - m) ** 2 + (r2 - m) ** 2 for (r1, r2), m in zip(ratings, subj_means))
    # SS between raters (consistency check)
    rater1_mean = sum(r[0] for r in ratings) / n
    rater2_mean = sum(r[1] for r in ratings) / n
    ssr = n * ((rater1_mean - grand_mean) ** 2 + (rater2_mean - grand_mean) ** 2)
    # SS error
    sse = ssw - ssr

    # Mean squares
    msb = ssb / (n - 1)
    mse = sse / ((n - 1) * (k - 1))
    msr = ssr / (k - 1)

    # ICC(2,1) absolute agreement
    icc = (msb - mse) / (msb + (k - 1) * mse + k * (msr - mse) / n)
    icc = max(0.0, min(1.0, icc))

    # Approximate 95% CI via Fisher Z (simplified)
    # F distribution degrees of freedom
    df1 = n - 1
    df2 = (n - 1) * (k - 1)
    # For CI: use F-based approximation
    # F_lower, F_upper at 0.025/0.975 (approximate with normal for large n)
    # Simple SE approximation
    se = math.sqrt(2 * (1 - icc) ** 2 * (1 + (k - 1) * icc) ** 2 / (k * n * (k - 1)))
    z = 1.96
    ci_lower = max(0.0, icc - z * se)
    ci_upper = min(1.0, icc + z * se)

    # Koo & Mae (2016) interpretation
    if icc >= 0.9:
        interp = "excellent"
    elif icc >= 0.75:
        interp = "good"
    elif icc >= 0.5:
        interp = "moderate"
    else:
        interp = "poor"

    return {
        "icc": round(icc, 4),
        "ci_95": [round(ci_lower, 4), round(ci_upper, 4)],
        "interpretation": interp,
        "n_subjects": n,
        "msb": round(msb, 6),
        "mse": round(mse, 6),
    }


def make_provider(model_key: str, model_id: str) -> LLMProvider:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    client = openai.OpenAI(base_url=OPENROUTER_BASE, api_key=api_key)

    class ORP(LLMProvider):
        def __init__(self):
            super().__init__(provider="openrouter", model=model_key)
            self._client = client
            self._model_id = model_id

        def generate(self, prompt: str, max_tokens: int = 2500) -> str:
            resp = self._client.chat.completions.create(
                model=self._model_id,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.7,
            )
            return resp.choices[0].message.content or ""

    return ORP()


def run_icc(args):
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY not set.")
        sys.exit(1)

    target_models = (
        args.models.split(",") if args.models
        else list(ICC_MODELS.keys())
    )
    seeds = DEFAULT_SEEDS[:args.seeds]
    n_runs = args.runs

    out_path = Path("experiment_results/icc_results.json")
    out_path.parent.mkdir(exist_ok=True)

    all_results = {}

    config = MazeConfig(size=7, use_mirage=True, use_confidence=True)

    for model_key in target_models:
        if model_key not in ICC_MODELS:
            print(f"[skip] unknown model: {model_key}")
            continue

        model_id = ICC_MODELS[model_key]
        print(f"\n[{model_key}] {len(seeds)} seeds × {n_runs} runs")

        per_seed_runs: dict[int, list[float]] = {}

        for run_idx in range(n_runs):
            provider = make_provider(model_key, model_id)
            for seed in seeds:
                maze = MazeEngine(size=7, seed=seed, algo="dfs")
                runner = BenchmarkRunner(config)
                result = runner.run_single(provider, maze)
                per_seed_runs.setdefault(seed, []).append(result.mei)
                print(f"  run={run_idx+1} seed={seed} MEI={result.mei:.3f}")

        # ICC 계산
        pairs = [(per_seed_runs[s][0], per_seed_runs[s][1]) for s in seeds if len(per_seed_runs.get(s, [])) >= 2]
        icc_stats = compute_icc(pairs) if pairs else {"error": "insufficient data"}

        all_results[model_key] = {
            "icc": icc_stats,
            "raw": {str(s): per_seed_runs[s] for s in seeds},
        }

        print(f"  ICC={icc_stats.get('icc', 'N/A')} [{icc_stats.get('ci_95', '?')}] — {icc_stats.get('interpretation', '?')}")

    with open(out_path, "w") as f:
        json.dump({
            "meta": {
                "protocol": "ICC(2,1) absolute agreement, Koo & Mae 2016",
                "n_seeds": len(seeds),
                "n_runs": n_runs,
                "created": datetime.now().isoformat(),
            },
            "results": all_results,
        }, f, indent=2)
    print(f"\nSaved → {out_path}")

    # Summary
    print("\n── ICC 요약 ─────────────────────────────────────────")
    print(f"{'Model':<25} {'ICC':>6} {'95% CI':>16} {'Interp'}")
    for mk, data in all_results.items():
        icc = data["icc"]
        ci = icc.get("ci_95", ["?", "?"])
        print(f"{mk:<25} {icc.get('icc', '?'):>6} [{ci[0]:.3f}, {ci[1]:.3f}]  {icc.get('interpretation', '?')}")


def main():
    parser = argparse.ArgumentParser(description="HalluMaze ICC reliability measurement")
    parser.add_argument("--models", help="comma-separated model keys")
    parser.add_argument("--seeds", type=int, default=10, help="seeds per model (default: 10)")
    parser.add_argument("--runs", type=int, default=2, help="runs per seed (default: 2)")
    args = parser.parse_args()
    run_icc(args)


if __name__ == "__main__":
    main()
