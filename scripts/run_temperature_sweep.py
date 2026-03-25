#!/usr/bin/env python3
"""
run_temperature_sweep.py — HalluMaze Temperature Sensitivity Sweep

Purpose:
    temperature 변화가 MEI/HRR에 미치는 영향 측정
    NeurIPS 2026 한계 해결: "Temperature stochasticity"

Protocol:
    3 models × 10 seeds × 4 temperatures = 120 trials
    Temperatures: 0.0, 0.3, 0.7, 1.0

Usage:
    python3 scripts/run_temperature_sweep.py
    python3 scripts/run_temperature_sweep.py --models glm-4.7 --seeds 5
    python3 scripts/run_temperature_sweep.py --temps 0.0,0.7,1.0 --resume

Output:
    experiment_results/temperature_sweep.json
"""
from __future__ import annotations

import sys, os, json, re, argparse
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
SWEEP_MODELS = {
    "claude-3.7-sonnet": ("Claude-3.7-Sonnet", "anthropic/claude-3.7-sonnet",  "openrouter"),
    "glm-4.7":           ("GLM-4.7",           "glm-4.7",                      "glm"),
    "llama-4-maverick":  ("Llama-4-Maverick",  "meta-llama/llama-4-maverick",  "openrouter"),
}

DEFAULT_TEMPS = [0.0, 0.3, 0.7, 1.0]
DEFAULT_SEEDS = [1001, 1002, 2001, 2002, 3001, 3002, 4001, 4002, 5001, 5002]


def run_sweep(args):
    if not os.environ.get("OPENROUTER_API_KEY") and not os.environ.get("GLM_API_KEY"):
        print("ERROR: no API keys found")
        sys.exit(1)

    target_models = args.models.split(",") if args.models else list(SWEEP_MODELS.keys())
    temps = [float(t) for t in args.temps.split(",")] if args.temps else DEFAULT_TEMPS
    seeds = DEFAULT_SEEDS[:args.seeds]

    out_path = Path("experiment_results/temperature_sweep.json")
    out_path.parent.mkdir(exist_ok=True)

    results = []
    if args.resume and out_path.exists():
        with open(out_path) as f:
            existing = json.load(f)
        results = existing.get("results", [])
        print(f"[resume] {len(results)} trials loaded")

    config = MazeConfig(size=7, use_mirage=True, use_confidence=True)

    for model_key in target_models:
        if model_key not in SWEEP_MODELS:
            print(f"[skip] unknown: {model_key}")
            continue
        display, model_id, ptype = SWEEP_MODELS[model_key]

        for temp in temps:
            done = {r["seed"] for r in results
                    if r["model"] == model_key and abs(r["temperature"] - temp) < 0.01}
            remaining = [s for s in seeds if s not in done]
            if not remaining:
                print(f"[{model_key}@t={temp:.1f}] already complete")
                continue

            provider = make_provider(LLMProvider, ptype, display, model_id, temperature=temp)
            print(f"\n[{model_key} | t={temp:.1f} | {ptype}] {len(remaining)} seeds")

            for seed in remaining:
                maze = MazeEngine(size=7, seed=seed, algo="dfs")
                runner = BenchmarkRunner(config)
                result = runner.run_single(provider, maze)
                row = {
                    "model": model_key,
                    "temperature": temp,
                    "seed": seed,
                    "mei": result.mei,
                    "hrr": result.hrr,
                    "sr": result.sr,
                    "hallucination_count": result.hallucination_count,
                    "backtrack_count": result.backtrack_count,
                }
                results.append(row)
                print(f"  seed={seed} MEI={result.mei:.3f} HRR={result.hrr:.3f}")

                with open(out_path, "w") as f:
                    json.dump({"meta": {"temps": temps, "seeds": seeds}, "results": results}, f, indent=2)

    # Summary
    print("\n── Temperature Sweep 요약 ───────────────────────────────────────────")
    print(f"{'Model':<25} {'Temp':>5}  {'n':>4}  {'MEI':>7}  {'HRR':>7}  {'SR':>7}")
    summary = {}
    for model_key in target_models:
        if model_key not in SWEEP_MODELS:
            continue
        summary[model_key] = {}
        for temp in temps:
            rows = [r for r in results if r["model"] == model_key and abs(r["temperature"] - temp) < 0.01]
            if not rows:
                continue
            mei_m = sum(r["mei"] for r in rows) / len(rows)
            hrr_m = sum(r["hrr"] for r in rows) / len(rows)
            sr_m  = sum(r["sr"]  for r in rows) / len(rows)
            summary[model_key][str(temp)] = {"n": len(rows), "mei_mean": round(mei_m, 4),
                                              "hrr_mean": round(hrr_m, 4), "sr_mean": round(sr_m, 4)}
            print(f"{model_key:<25} {temp:>5.1f}  {len(rows):>4}  {mei_m:>7.3f}  {hrr_m:>7.3f}  {sr_m:>7.3f}")

    with open(out_path, "w") as f:
        json.dump({
            "meta": {"temps": temps, "seeds": seeds, "created": datetime.now().isoformat()},
            "summary": summary,
            "results": results,
        }, f, indent=2)
    print(f"\nSaved → {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", help="comma-separated model keys")
    parser.add_argument("--temps", help="comma-separated temperatures")
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    run_sweep(args)

if __name__ == "__main__":
    main()
