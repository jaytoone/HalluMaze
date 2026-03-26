#!/usr/bin/env python3
"""
run_openrouter_experiment.py — HalluMaze multi-model expansion via OpenRouter

Phase A (Pilot): n=5 seeds, 5×5 only, free+cheap models
Phase B (Full):  n=30 seeds, 5×5 + 7×7, filtered top models
Phase C (SOTA):  GPT-4o or Claude Sonnet (optional, NeurIPS P0.1)

Usage:
    python3 run_openrouter_experiment.py --phase A          # free pilot (n=5, 5x5)
    python3 run_openrouter_experiment.py --phase B          # full run (n=30, both sizes)
    python3 run_openrouter_experiment.py --phase C          # SOTA models only
    python3 run_openrouter_experiment.py --phase A --models llama-4-scout,gemini-flash
    python3 run_openrouter_experiment.py --list-models      # show available models + cost
    python3 run_openrouter_experiment.py --resume           # resume from checkpoint
"""
from __future__ import annotations

import sys, os, json, re, time, argparse, random, math
from datetime import datetime
from pathlib import Path
import openai

# ── env loading ───────────────────────────────────────────────────────────────
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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'files'))
from hallumaze import (
    LLMProvider, MazeConfig, MazeEngine, BenchmarkRunner,
    PromptBuilder, console, RICH
)


# ═══════════════════════════════════════════════════════════════
#  OPENROUTER MODEL REGISTRY
# ═══════════════════════════════════════════════════════════════

OPENROUTER_MODELS = {
    # ── FREE tier ─────────────────────────────────────────────
    "minimax-m2.5-free": {
        "id": "minimax/minimax-m2.5:free",
        "display": "MiniMax-M2.5 (free)",
        "cost_per_m_in": 0.0,
        "cost_per_m_out": 0.0,
        "phase": ["A", "B"],
        "notes": "무료, rate-limited",
    },
    # ── Cheap tier ($0.08–$0.30/M) ────────────────────────────
    "llama-4-scout": {
        "id": "meta-llama/llama-4-scout",
        "display": "Llama 4 Scout (17B active)",
        "cost_per_m_in": 0.08,
        "cost_per_m_out": 0.30,
        "phase": ["A", "B"],
        "notes": "Meta flagship open model",
    },
    "gemini-flash": {
        "id": "google/gemini-2.0-flash-lite-001",
        "display": "Gemini 2.0 Flash-Lite",
        "cost_per_m_in": 0.075,
        "cost_per_m_out": 0.30,
        "phase": ["A", "B"],
        "notes": "Google 최저가",
    },
    # ── Mid tier ($0.15–$1.25/M) ───────────────────────────────
    "llama-4-maverick": {
        "id": "meta-llama/llama-4-maverick",
        "display": "Llama 4 Maverick (17B active/400B total)",
        "cost_per_m_in": 0.15,
        "cost_per_m_out": 0.60,
        "phase": ["A", "B"],
        "notes": "Llama 4 대형 MoE",
    },
    "gpt-4o-mini": {
        "id": "openai/gpt-4o-mini",
        "display": "GPT-4o mini",
        "cost_per_m_in": 0.15,
        "cost_per_m_out": 0.60,
        "phase": ["A", "B"],
        "notes": "OpenAI 소형 flagship",
    },
    "claude-haiku": {
        "id": "anthropic/claude-3-haiku",
        "display": "Claude 3 Haiku",
        "cost_per_m_in": 0.25,
        "cost_per_m_out": 1.25,
        "phase": ["A", "B"],
        "notes": "Anthropic 최저가",
    },
    "qwen-72b": {
        "id": "qwen/qwen-2.5-72b-instruct",
        "display": "Qwen 2.5 72B",
        "cost_per_m_in": 0.12,
        "cost_per_m_out": 0.39,
        "phase": ["B"],
        "notes": "Alibaba 오픈 대형",
    },
    # ── SOTA tier ($2.5–$15/M) ─────────────────────────────────
    "gpt-4o": {
        "id": "openai/gpt-4o",
        "display": "GPT-4o",
        "cost_per_m_in": 2.5,
        "cost_per_m_out": 10.0,
        "phase": ["C"],
        "notes": "OpenAI flagship — NeurIPS P0.1",
    },
    "claude-sonnet": {
        "id": "anthropic/claude-3.7-sonnet",
        "display": "Claude 3.7 Sonnet",
        "cost_per_m_in": 3.0,
        "cost_per_m_out": 15.0,
        "phase": ["C"],
        "notes": "Anthropic flagship — NeurIPS P0.1",
    },
    # ── Claude 4.x line ────────────────────────────────────────
    "claude-haiku-4.5": {
        "id": "anthropic/claude-haiku-4.5",
        "display": "Claude Haiku 4.5",
        "cost_per_m_in": 1.0,
        "cost_per_m_out": 5.0,
        "phase": ["B", "C"],
        "notes": "Anthropic 4th gen compact — NeurIPS extended",
    },
    "claude-sonnet-4.5": {
        "id": "anthropic/claude-sonnet-4.5",
        "display": "Claude Sonnet 4.5",
        "cost_per_m_in": 3.0,
        "cost_per_m_out": 15.0,
        "phase": ["C"],
        "notes": "Anthropic 4th gen mid — NeurIPS extended",
    },
    "claude-sonnet-4.6": {
        "id": "anthropic/claude-sonnet-4.6",
        "display": "Claude Sonnet 4.6",
        "cost_per_m_in": 3.0,
        "cost_per_m_out": 15.0,
        "phase": ["C"],
        "notes": "Anthropic latest flagship — NeurIPS extended",
    },
}

PHASE_A_SEEDS = [1001, 2002, 3003, 4004, 5005]  # n=5 pilot
SEED_POOL = [
    1001, 2002, 3003, 4004, 5005, 6006, 7007, 8008, 9009, 1010,
    1111, 1234, 1357, 2222, 2345, 2468, 3333, 3456, 4444, 4567,
    5555, 5678, 6666, 6789, 7777, 7890, 8888, 8901, 9012, 9999,
]
assert len(SEED_POOL) == 30


# ═══════════════════════════════════════════════════════════════
#  OPENROUTER PROVIDER PATCH
# ═══════════════════════════════════════════════════════════════

def _strip_think(text: str) -> str:
    stripped = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    return stripped if stripped else text


def _call_openrouter(self, prompt: str, max_tokens: int, system: str = "") -> str:
    """OpenRouter unified call — works for all models via OpenAI-compatible API."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    client = openai.OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": "https://github.com/hallumaze",
            "X-Title": "HalluMaze Benchmark",
        }
    )
    # Reasoning models may need more tokens for think blocks
    effective_tokens = max(max_tokens, 6000) if "thinking" in self.model else max_tokens

    resp = client.chat.completions.create(
        model=self.model,
        max_tokens=effective_tokens,
        messages=[
            {"role": "system", "content": system or PromptBuilder.SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ]
    )
    raw = resp.choices[0].message.content or ""
    return _strip_think(raw)


# Monkey-patch LLMProvider
_orig_call = LLMProvider.call
def _patched_call(self, prompt, max_tokens, system=""):
    if self.provider == "openrouter":
        return _call_openrouter(self, prompt, max_tokens, system)
    return _orig_call(self, prompt, max_tokens, system)
LLMProvider.call = _patched_call


# ═══════════════════════════════════════════════════════════════
#  COST ESTIMATOR
# ═══════════════════════════════════════════════════════════════

def estimate_cost(model_keys: list[str], sizes: list[int], n_seeds: int) -> float:
    """토큰 수 기반 비용 추정 (보수적 상한)."""
    total = 0.0
    # Per trial: avg input ~8000 tokens (growing context), output ~2000
    tokens_per_trial = {5: (8_000, 2_000), 7: (15_000, 3_500)}
    for mk in model_keys:
        m = OPENROUTER_MODELS.get(mk, {})
        ci = m.get("cost_per_m_in", 0)
        co = m.get("cost_per_m_out", 0)
        for sz in sizes:
            inp, out = tokens_per_trial.get(sz, (8000, 2000))
            cost = n_seeds * (inp * ci + out * co) / 1_000_000
            total += cost
    return total


# ═══════════════════════════════════════════════════════════════
#  RUN SINGLE TRIAL
# ═══════════════════════════════════════════════════════════════

def run_single_trial(provider: LLMProvider, size: int, seed: int,
                     config: MazeConfig) -> dict:
    maze = MazeEngine(size=size, seed=seed)
    runner = BenchmarkRunner(config)
    result = runner.run_single(provider, maze)
    return {
        "provider": "openrouter",
        "model": result.model,
        "size": size,
        "seed": seed,
        "sr": result.sr,
        "mei": result.mei,
        "ce": result.ce,
        "oce": getattr(result, 'oce', None),
        "uce": getattr(result, 'uce', None),
        "brs": result.brs,
        "hallumaze_score": result.hallumaze_score,
        "hallucination_count": result.hallucination_count,
        "backtrack_count": result.backtrack_count,
        "loop_count": result.loop_count,
        "hrr": result.hrr,
        "path_valid": result.path_valid,
        "latency_s": result.latency_s,
        "error": result.error,
        "metacog_signals": result.metacog_signals,
        "solution_length": len(maze.solution or []),
        "dead_ends": maze.dead_ends,
        "or_model_id": provider.model,  # OpenRouter model ID 보존
    }


# ═══════════════════════════════════════════════════════════════
#  MAIN RUNNER
# ═══════════════════════════════════════════════════════════════

def run_phase(phase: str, model_keys: list[str], checkpoint_file: Path,
              dry_run: bool = False) -> list[dict]:
    sizes = [5] if phase == "A" else [5, 7]
    seeds = PHASE_A_SEEDS if phase == "A" else SEED_POOL

    # Build providers
    or_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not or_key:
        print("ERROR: OPENROUTER_API_KEY 환경변수 없음. ~/.claude/env/shared.env 확인")
        sys.exit(1)

    providers = []
    for mk in model_keys:
        m = OPENROUTER_MODELS[mk]
        providers.append(LLMProvider(
            provider="openrouter",
            api_key=or_key,
            model=m["id"],
        ))

    # Cost estimate
    est = estimate_cost(model_keys, sizes, len(seeds))
    print(f"\n{'='*60}")
    print(f"Phase {phase} — {len(model_keys)} models × {len(sizes)} sizes × {len(seeds)} seeds")
    print(f"총 trials: {len(providers)*len(sizes)*len(seeds)}")
    print(f"예상 비용: ~${est:.2f}")
    print(f"체크포인트: {checkpoint_file}")
    print(f"{'='*60}\n")
    for mk in model_keys:
        m = OPENROUTER_MODELS[mk]
        print(f"  {m['display']:<40} ${m['cost_per_m_in']:.3f}/${m['cost_per_m_out']:.3f}/M  {m['notes']}")
    print()

    if dry_run:
        print("[DRY RUN] 실제 실행 없음. --dry-run 제거 후 재실행.")
        return []

    # Load checkpoint
    completed = []
    if checkpoint_file.exists():
        with open(checkpoint_file) as f:
            completed = json.load(f)
        print(f"[재개] 기존 {len(completed)}개 결과 로드")

    completed_keys = {(r["or_model_id"], r["size"], r["seed"]) for r in completed}
    config = MazeConfig(max_tokens=8192, use_confidence=True)

    total = len(providers) * len(sizes) * len(seeds)
    done = len(completed)

    for provider in providers:
        for size in sizes:
            for seed in seeds:
                key = (provider.model, size, seed)
                if key in completed_keys:
                    done += 1
                    continue

                done += 1
                label = f"[{done}/{total}] {provider.model.split('/')[-1]} | {size}×{size} | seed={seed}"
                print(f"  ▶ {label}")
                t0 = time.time()
                try:
                    trial = run_single_trial(provider, size, seed, config)
                    elapsed = time.time() - t0
                    status = "✓" if trial["path_valid"] else "✗"
                    print(
                        f"  {status} SR={trial['sr']:.1f} MEI={trial['mei']:.3f} "
                        f"Hall={trial['hallucination_count']} BT={trial['backtrack_count']} "
                        f"Score={trial['hallumaze_score']:.3f} | {elapsed:.1f}s"
                    )
                except Exception as e:
                    trial = {
                        "provider": "openrouter", "model": provider.model.split("/")[-1],
                        "or_model_id": provider.model,
                        "size": size, "seed": seed, "error": str(e),
                        "sr": 0, "mei": 0, "ce": None, "oce": None, "uce": None,
                        "brs": 0, "hallumaze_score": 0,
                        "hallucination_count": 0, "backtrack_count": 0,
                        "loop_count": 0, "hrr": 0, "path_valid": False,
                        "latency_s": 0, "metacog_signals": [], "solution_length": 0, "dead_ends": 0,
                    }
                    print(f"  ✗ 오류: {e}")

                completed.append(trial)
                with open(checkpoint_file, 'w') as f:
                    json.dump(completed, f, ensure_ascii=False, indent=2)

    return completed


def print_summary(trials: list[dict]):
    by_model: dict[str, list] = {}
    for t in trials:
        if not t.get("error"):
            model = t.get("model", t.get("or_model_id", "?")).split("/")[-1]
            by_model.setdefault(model, []).append(t)

    print(f"\n{'='*75}")
    print(f"{'Model':<30} {'n':>4} {'SR':>6} {'MEI':>7} {'Score':>7} {'HRR':>6}")
    print(f"{'-'*75}")
    for model, ts in sorted(by_model.items(), key=lambda x: -sum(t['mei'] for t in x[1])/len(x[1])):
        n = len(ts)
        avg = lambda k: sum(t.get(k, 0) for t in ts) / n
        print(f"{model:<30} {n:>4} {avg('sr'):>6.3f} {avg('mei'):>7.3f} {avg('hallumaze_score'):>7.3f} {avg('hrr'):>6.3f}")
    print(f"{'='*75}\n")


def list_models(phase_filter: str | None = None):
    print(f"\n{'모델키':<22} {'display':<40} {'in/M':>7} {'out/M':>7} {'Phase':<8} {'비고'}")
    print("-"*100)
    for key, m in OPENROUTER_MODELS.items():
        if phase_filter and phase_filter not in m["phase"]:
            continue
        free = "★" if m["cost_per_m_in"] == 0 else ""
        print(f"{key:<22} {m['display']:<40} ${m['cost_per_m_in']:>5.3f}  ${m['cost_per_m_out']:>5.3f}  {','.join(m['phase']):<8} {free}{m['notes']}")
    print()


# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(description="HalluMaze OpenRouter Multi-Model Experiment")
    ap.add_argument("--phase", choices=["A", "B", "C"], default="A",
                    help="A=pilot(n=5,5x5), B=full(n=30,5x5+7x7), C=SOTA")
    ap.add_argument("--models", type=str, default=None,
                    help="쉼표 구분 모델키 (기본: 해당 Phase 전체)")
    ap.add_argument("--checkpoint", type=str, default=None,
                    help="체크포인트 파일 경로 (기본: experiment_results/or_phase{X}.json)")
    ap.add_argument("--resume", action="store_true", help="체크포인트에서 재개")
    ap.add_argument("--dry-run", action="store_true", help="실행 없이 비용/계획만 출력")
    ap.add_argument("--list-models", action="store_true", help="모델 목록 출력")
    args = ap.parse_args()

    if args.list_models:
        list_models()
        return

    # 모델 선택
    if args.models:
        model_keys = [k.strip() for k in args.models.split(",")]
        for k in model_keys:
            if k not in OPENROUTER_MODELS:
                print(f"ERROR: 알 수 없는 모델키 '{k}'. --list-models 로 확인")
                sys.exit(1)
    else:
        # Phase 기본 모델
        phase_defaults = {
            "A": ["minimax-m2.5-free", "llama-4-scout", "gemini-flash", "gpt-4o-mini", "claude-haiku"],
            "B": ["llama-4-scout", "gemini-flash", "llama-4-maverick", "gpt-4o-mini", "claude-haiku", "qwen-72b"],
            "C": ["gpt-4o", "claude-sonnet"],
        }
        model_keys = phase_defaults[args.phase]

    checkpoint = Path(args.checkpoint or f"experiment_results/or_phase{args.phase}.json")
    checkpoint.parent.mkdir(exist_ok=True)

    trials = run_phase(
        phase=args.phase,
        model_keys=model_keys,
        checkpoint_file=checkpoint,
        dry_run=args.dry_run,
    )

    if trials and not args.dry_run:
        print_summary(trials)
        print(f"\n결과 저장: {checkpoint}")
        print("분석 실행: python3 analyze_results.py --llm " + str(checkpoint) + " --baselines experiment_results/baselines.json")


if __name__ == "__main__":
    main()
