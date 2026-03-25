#!/usr/bin/env python3
"""
run_9x9_experiment.py — HalluMaze 9×9 크기 스케일링 실험

Purpose:
    기존 5×5, 7×7에 더해 9×9 조건 추가 — 크기 스케일링 효과 측정
    NeurIPS 2026 한계 해결: "9×9 크기 조건 없음"

Usage:
    python3 scripts/run_9x9_experiment.py --models claude-3.7-sonnet,glm-4.7 --seeds 30
    python3 scripts/run_9x9_experiment.py --pilot          # n=5, 무료 모델만
    python3 scripts/run_9x9_experiment.py --resume         # 중단 재개

Output:
    experiment_results/9x9_experiment.json
"""
from __future__ import annotations

import sys, os, json, re, time, argparse, random
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
from hallumaze import LLMProvider, MazeConfig, MazeEngine, BenchmarkRunner, console

import openai

OPENROUTER_BASE = "https://openrouter.ai/api/v1"

# 9×9 실험 대상 모델 (MEI 상위 + 하위 대표)
MODELS_9X9 = {
    "claude-3.7-sonnet": {
        "id": "anthropic/claude-3.7-sonnet",
        "display": "Claude-3.7-Sonnet",
        "cost_per_m_in": 3.0,
    },
    "glm-4.7": {
        "id": "thudm/glm-4.7",
        "display": "GLM-4.7",
        "cost_per_m_in": 0.0,
    },
    "llama-4-maverick": {
        "id": "meta-llama/llama-4-maverick",
        "display": "Llama-4-Maverick",
        "cost_per_m_in": 0.22,
    },
    "gpt-4o-mini": {
        "id": "openai/gpt-4o-mini",
        "display": "GPT-4o-mini",
        "cost_per_m_in": 0.15,
    },
    "gpt-4o": {
        "id": "openai/gpt-4o",
        "display": "GPT-4o",
        "cost_per_m_in": 2.5,
    },
}

# 9×9 파라미터
SIZE_9X9 = 9
MAX_STEPS_9X9 = 81      # N^2 = 81 (vs 5×5=30, 7×7=50)
SEED_POOL_9X9 = list(range(1001, 9999))


def make_provider(model_key: str) -> LLMProvider:
    cfg = MODELS_9X9[model_key]
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    client = openai.OpenAI(base_url=OPENROUTER_BASE, api_key=api_key)

    class OpenRouterProvider(LLMProvider):
        def __init__(self):
            super().__init__(provider="openrouter", model=cfg["display"])
            self._client = client
            self._model_id = cfg["id"]

        def generate(self, prompt: str, max_tokens: int = 2500) -> str:
            resp = self._client.chat.completions.create(
                model=self._model_id,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.7,
            )
            return resp.choices[0].message.content or ""

    return OpenRouterProvider()


def run_9x9(args):
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY not set. Run: source ~/.claude/env/shared.env")
        sys.exit(1)

    n_seeds = 5 if args.pilot else args.seeds
    target_models = (
        [k for k in MODELS_9X9 if MODELS_9X9[k]["cost_per_m_in"] == 0.0]
        if args.pilot
        else (args.models.split(",") if args.models else list(MODELS_9X9.keys()))
    )

    checkpoint_path = Path("experiment_results/9x9_experiment.json")
    checkpoint_path.parent.mkdir(exist_ok=True)

    results = []
    if args.resume and checkpoint_path.exists():
        with open(checkpoint_path) as f:
            existing = json.load(f)
        results = existing.get("results", [])
        print(f"[resume] loaded {len(results)} completed trials")

    seeds = random.sample(SEED_POOL_9X9, n_seeds)

    config = MazeConfig(
        size=SIZE_9X9,
        use_mirage=True,
        use_confidence=True,
        ariadne_mode="A",
        max_tokens=2500,
    )

    for model_key in target_models:
        if model_key not in MODELS_9X9:
            print(f"[skip] unknown model: {model_key}")
            continue

        done_seeds = {r["seed"] for r in results if r["model"] == MODELS_9X9[model_key]["display"]}
        remaining = [s for s in seeds if s not in done_seeds]
        if not remaining:
            print(f"[{model_key}] already complete ({len(done_seeds)} trials)")
            continue

        provider = make_provider(model_key)
        print(f"\n[{model_key}] {len(remaining)} trials × 9×9 (max_steps={MAX_STEPS_9X9})")

        for seed in remaining:
            maze = MazeEngine(size=SIZE_9X9, seed=seed, algo="dfs")
            runner = BenchmarkRunner(config)
            result = runner.run_single(provider, maze)
            row = {
                "model": MODELS_9X9[model_key]["display"],
                "seed": seed,
                "size": SIZE_9X9,
                "mei": result.mei,
                "hrr": result.hrr,
                "sr": result.sr,
                "hallucination_count": result.hallucination_count,
                "backtrack_count": result.backtrack_count,
                "brs": result.brs,
            }
            results.append(row)
            print(f"  seed={seed} MEI={result.mei:.3f} HRR={result.hrr:.3f} SR={result.sr:.0f}")

            # 중간 저장
            with open(checkpoint_path, "w") as f:
                json.dump({"meta": {"size": SIZE_9X9, "n_seeds": n_seeds}, "results": results}, f, indent=2)

    # 모델별 집계
    summary = {}
    for model_key in target_models:
        if model_key not in MODELS_9X9:
            continue
        display = MODELS_9X9[model_key]["display"]
        rows = [r for r in results if r["model"] == display]
        if not rows:
            continue
        summary[display] = {
            "n": len(rows),
            "mei_mean": sum(r["mei"] for r in rows) / len(rows),
            "hrr_mean": sum(r["hrr"] for r in rows) / len(rows),
            "sr_mean":  sum(r["sr"]  for r in rows) / len(rows),
        }

    print("\n── 9×9 요약 ──────────────────────────────")
    print(f"{'Model':<25} {'n':>4} {'MEI':>7} {'HRR':>7} {'SR':>7}")
    for display, s in sorted(summary.items(), key=lambda x: -x[1]["mei_mean"]):
        print(f"{display:<25} {s['n']:>4} {s['mei_mean']:>7.3f} {s['hrr_mean']:>7.3f} {s['sr_mean']:>7.3f}")

    with open(checkpoint_path, "w") as f:
        json.dump({
            "meta": {"size": SIZE_9X9, "created": datetime.now().isoformat()},
            "summary": summary,
            "results": results,
        }, f, indent=2)
    print(f"\nSaved → {checkpoint_path}")


def main():
    parser = argparse.ArgumentParser(description="HalluMaze 9×9 scaling experiment")
    parser.add_argument("--models", help="comma-separated model keys (default: all)")
    parser.add_argument("--seeds", type=int, default=30, help="trials per model (default: 30)")
    parser.add_argument("--pilot", action="store_true", help="n=5 free models only")
    parser.add_argument("--resume", action="store_true", help="resume from checkpoint")
    args = parser.parse_args()
    run_9x9(args)


if __name__ == "__main__":
    main()
