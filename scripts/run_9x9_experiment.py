#!/usr/bin/env python3
"""
run_9x9_experiment.py — HalluMaze 9×9 크기 스케일링 실험

Purpose:
    기존 5×5, 7×7에 더해 9×9 조건 추가 — 크기 스케일링 효과 측정
    NeurIPS 2026 한계 해결: "9×9 크기 조건 없음"

Usage:
    python3 scripts/run_9x9_experiment.py --models claude-3.7-sonnet,glm-4.7 --seeds 30
    python3 scripts/run_9x9_experiment.py --pilot          # n=5, GLM 무료 모델
    python3 scripts/run_9x9_experiment.py --resume         # 중단 재개

Output:
    experiment_results/9x9_experiment.json
"""
from __future__ import annotations

import sys, os, json, re, argparse, random
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
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from hallumaze import LLMProvider, MazeConfig, MazeEngine, BenchmarkRunner, PromptBuilder
from scripts._openrouter_patch import patch_providers, make_provider

patch_providers(LLMProvider, PromptBuilder)

# (display, model_id, provider_type)
MODELS_9X9 = {
    "claude-3.7-sonnet": ("Claude-3.7-Sonnet", "anthropic/claude-3.7-sonnet", "openrouter"),
    "glm-4.7":           ("GLM-4.7",           "glm-4.7",                     "glm"),
    "llama-4-maverick":  ("Llama-4-Maverick",  "meta-llama/llama-4-maverick", "openrouter"),
    "gpt-4o-mini":       ("GPT-4o-mini",       "openai/gpt-4o-mini",          "openrouter"),
    "gpt-4o":            ("GPT-4o",            "openai/gpt-4o",               "openrouter"),
}

PILOT_MODELS = ["glm-4.7"]  # ZAI 무료 사용

SIZE_9X9   = 9
MAX_STEPS  = 81
SEED_POOL  = list(range(1001, 9999))


def run_9x9(args):
    n_seeds       = 5 if args.pilot else args.seeds
    target_models = PILOT_MODELS if args.pilot else (
        args.models.split(",") if args.models else list(MODELS_9X9.keys())
    )

    out_path = Path("experiment_results/9x9_experiment.json")
    out_path.parent.mkdir(exist_ok=True)

    results = []
    if args.resume and out_path.exists():
        with open(out_path) as f:
            existing = json.load(f)
        results = existing.get("results", [])
        print(f"[resume] {len(results)} trials loaded")

    random.seed(42)
    seeds = random.sample(SEED_POOL, n_seeds)

    config = MazeConfig(size=SIZE_9X9, use_mirage=True, use_confidence=True)

    for model_key in target_models:
        if model_key not in MODELS_9X9:
            print(f"[skip] unknown: {model_key}")
            continue
        display, model_id, ptype = MODELS_9X9[model_key]

        done = {r["seed"] for r in results if r["model"] == display}
        remaining = [s for s in seeds if s not in done]
        if not remaining:
            print(f"[{model_key}] already complete")
            continue

        provider = make_provider(LLMProvider, ptype, display, model_id)
        print(f"\n[{model_key}] {len(remaining)} trials × 9×9 (via {ptype})")

        for seed in remaining:
            maze = MazeEngine(size=SIZE_9X9, seed=seed, algo="dfs")
            runner = BenchmarkRunner(config)
            result = runner.run_single(provider, maze)
            row = {
                "model": display,
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

            with open(out_path, "w") as f:
                json.dump({"meta": {"size": SIZE_9X9}, "results": results}, f, indent=2)

    # Summary
    summary = {}
    for model_key in target_models:
        if model_key not in MODELS_9X9:
            continue
        display = MODELS_9X9[model_key][0]
        rows = [r for r in results if r["model"] == display]
        if rows:
            summary[display] = {
                "n": len(rows),
                "mei_mean": round(sum(r["mei"] for r in rows) / len(rows), 4),
                "hrr_mean": round(sum(r["hrr"] for r in rows) / len(rows), 4),
                "sr_mean":  round(sum(r["sr"]  for r in rows) / len(rows), 4),
            }

    print("\n── 9×9 요약 ──────────────────────────────")
    print(f"{'Model':<25} {'n':>4} {'MEI':>7} {'HRR':>7} {'SR':>7}")
    for disp, s in sorted(summary.items(), key=lambda x: -x[1]["mei_mean"]):
        print(f"{disp:<25} {s['n']:>4} {s['mei_mean']:>7.3f} {s['hrr_mean']:>7.3f} {s['sr_mean']:>7.3f}")

    with open(out_path, "w") as f:
        json.dump({
            "meta": {"size": SIZE_9X9, "created": datetime.now().isoformat()},
            "summary": summary,
            "results": results,
        }, f, indent=2)
    print(f"\nSaved → {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", help="comma-separated model keys")
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--pilot", action="store_true", help="n=5 GLM only")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    run_9x9(args)

if __name__ == "__main__":
    main()
