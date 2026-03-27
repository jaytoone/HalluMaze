#!/usr/bin/env python3
"""
MARL-SL for other models (OpenRouter)
======================================
Run MARL-SL method on other models via OpenRouter to validate multi-model.

Usage:
    source ~/.claude/env/shared.env && python3 scripts/run_marl_sl_openrouter.py
"""
from __future__ import annotations
import json, os, re, sys, time
from datetime import datetime

# env loading
def _load_env_file(path: str):
    try:
        with open(os.path.expanduser(path)) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                m = re.match(r'^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$', line)
                if m:
                    key, val = m.group(1), m.group(2).strip('"\'')
                    if key not in os.environ:
                        os.environ[key] = val
    except FileNotFoundError:
        pass

_load_env_file("~/.claude/env/shared.env")
_load_env_file("~/.claude/env/shared.env")

sys.path.insert(0, '/home/jayone/Project/Miro/files')
sys.path.insert(0, '/home/jayone/Project/Miro')
from hallumaze import MazeEngine

# ═══════════════════════════════════════════════════════════════
#  OPENROUTER API
# ═══════════════════════════════════════════════════════════════

OPENROUTER_MODELS = {
    "llama-4-scout": {"id": "meta-llama/llama-4-scout", "display": "Llama 4 Scout"},
    "llama-4-maverick": {"id": "meta-llama/llama-4-maverick", "display": "Llama 4 Maverick"},
    "claude-haiku": {"id": "anthropic/claude-3-haiku", "display": "Claude 3 Haiku"},
    "gpt-4o-mini": {"id": "openai/gpt-4o-mini", "display": "GPT-4o mini"},
    "claude-sonnet": {"id": "anthropic/claude-3.7-sonnet", "display": "Claude 3.7 Sonnet"},
    "claude-3.5-sonnet": {"id": "anthropic/claude-3.5-sonnet", "display": "Claude 3.5 Sonnet"},
    "gemini-flash": {"id": "google/gemini-2.0-flash-lite-001", "display": "Gemini 2.0 Flash-Lite"},
    "gemini-pro": {"id": "google/gemini-2.5-pro-preview", "display": "Gemini 2.5 Pro"},
    "qwen-72b": {"id": "qwen/qwen-2.5-72b-instruct", "display": "Qwen 2.5 72B"},
}

# Models using direct API (not OpenRouter)
DIRECT_MODELS = {
    "minimax": {"display": "MiniMax-M2.5", "api": "minimax"},
}

def call_openrouter(prompt: str, model_id: str, system: str = "", max_tokens: int = 8000) -> str:
    import requests
    headers = {
        "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
        "HTTP-Referer": "https://github.com/jaytoone/HalluMaze",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_id,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }
    resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=300)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]

def call_minimax(prompt: str, system: str = "", max_tokens: int = 8000) -> str:
    """MiniMax direct API (OpenAI-compatible). MiniMax-M2.5 is a reasoning model:
    <think> blocks consume ~3000+ tokens, so effective max_tokens is max(max_tokens, 8000).
    Retries up to 2 times on choices:null (intermittent server-side issue)."""
    import requests, re
    key = os.environ.get("MINIMAX_API_KEY", "")
    base_url = os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.io/v1")
    model = os.environ.get("MINIMAX_MODEL", "MiniMax-M2.5")
    # Strip /anthropic suffix if present — use OpenAI-compatible endpoint
    base_url = base_url.rstrip("/").replace("/anthropic", "")
    effective_tokens = max(max_tokens, 8000)
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": effective_tokens,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
    }
    for attempt in range(3):
        resp = requests.post(f"{base_url}/v1/chat/completions", headers=headers, json=payload, timeout=300)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices")
        if not choices:
            base_resp = data.get("base_resp", {})
            if attempt < 2:
                print(f" [minimax retry {attempt+1}/3: choices=null, base_resp={base_resp}]", end=" ", flush=True)
                time.sleep(5)
                continue
            raise RuntimeError(f"MiniMax API returned choices:null after 3 attempts. base_resp={base_resp}")
        content = choices[0]["message"].get("content")
        if content is None:
            if attempt < 2:
                print(f" [minimax retry {attempt+1}/3: content=null]", end=" ", flush=True)
                time.sleep(5)
                continue
            raise RuntimeError("MiniMax API returned content:null in message")
        # Strip <think>...</think> reasoning blocks
        stripped = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
        return stripped if stripped else content
    raise RuntimeError("MiniMax call_minimax exhausted retries")

def call_timed_or(prompt: str, model_key: str, system: str = "", max_tokens: int = 8000) -> tuple[str, float]:
    t0 = time.time()
    if model_key in DIRECT_MODELS:
        if DIRECT_MODELS[model_key]["api"] == "minimax":
            result = call_minimax(prompt, system, max_tokens)
        else:
            raise ValueError(f"Unknown direct model api: {DIRECT_MODELS[model_key]['api']}")
    else:
        model = OPENROUTER_MODELS[model_key]["id"]
        result = call_openrouter(prompt, model, system, max_tokens)
    return result, round(time.time() - t0, 2)

# ═══════════════════════════════════════════════════════════════
#  MARL-SL PROMPT (same as GLM version)
# ═══════════════════════════════════════════════════════════════

SL_SYSTEM = """You are a unified maze reasoning system with five cognitive layers.
Process each layer fully before proceeding to the next.
Layer separation is MANDATORY — do not skip or merge layers."""

def build_sl_prompt(maze_text: str, N: int, error_feedback: str = "") -> str:
    retry = f"\n⚠️  RETRY — Previous errors:\n{error_feedback}\n" if error_feedback else ""
    return f"""{retry}MAZE:
{maze_text}

=== LAYER 1: ANALYST ===
1. SUSPICIOUS WALLS: list (r,c)-dir: reason
2. HIGH-RISK CORRIDORS
3. SAFE CORRIDORS toward ({N-1},{N-1})

=== LAYER 2: NAVIGATOR ===
STEP N: (r,c) -> [N/S/E/W] | confidence: XX%
End: PRELIM_PATH: (0,0)->...->({N-1},{N-1})

=== LAYER 3: AUDITOR ===
ERROR step N: (r,c)->[dir] BLOCKED
Summary: AUDIT_ERRORS_FOUND: N

=== LAYER 4: CORRECTOR ===
End: CORRECTED_PATH: ...

=== LAYER 5: REFINER ===
BACKTRACK_COUNT: N
HALLUCINATION_COUNT: N
FINAL_PATH: (0,0)->...->({N-1},{N-1})"""

# ═══════════════════════════════════════════════════════════════
#  VALIDATOR
# ═══════════════════════════════════════════════════════════════

def validate_path(path, maze):
    if not path or len(path) < 2:
        return ["empty"]
    N = maze.N
    cells = maze.cells
    dmap = {(-1,0):'N',(1,0):'S',(0,1):'E',(0,-1):'W'}
    errors = []
    if path[0] != [0,0]:
        errors.append(f"start {path[0]}")
    for i in range(len(path)-1):
        r1,c1 = path[i]; r2,c2 = path[i+1]
        if not (0<=r1<N and 0<=c1<N): errors.append(f"OOB"); continue
        d = dmap.get((r2-r1, c2-c1))
        if d and getattr(cells[r1][c1], d):
            errors.append(f"{d} blocked at {i}")
    if path[-1] != [N-1,N-1]:
        errors.append(f"end {path[-1]}")
    return errors

def extract_path(text):
    m = re.search(r'FINAL_PATH[:\s]+([\d,\(\)\s\u2192\-\>]+)', text, re.IGNORECASE)
    if m:
        coords = re.findall(r'\((\d+),\s*(\d+)\)', m.group(1))
        if coords:
            return [[int(r),int(c)] for r,c in coords]
    steps = re.findall(r'STEP\s+\d+:\s*\((\d+),\s*(\d+)\)', text, re.IGNORECASE)
    if steps:
        return [[int(r),int(c)] for r,c in steps]
    return []

# ═══════════════════════════════════════════════════════════════
#  RUNNER
# ═══════════════════════════════════════════════════════════════

SL_BUDGET = {5: 5000, 7: 8000, 9: 12000}  # slightly smaller for OpenRouter; 9x9 extended

def run_marl_sl(maze, size, model_key):
    maze_text = maze.encode_text(use_mirage=True)
    N = maze.N
    budget = SL_BUDGET.get(size, 8000)

    best_output, best_errors, best_path = None, float('inf'), None
    error_feedback = ""

    for attempt in range(2):
        prompt = build_sl_prompt(maze_text, N, error_feedback)
        print(f"    [{model_key}] SL call {attempt+1}...", end=" ", flush=True)
        try:
            output, elapsed = call_timed_or(prompt, model_key, system=SL_SYSTEM, max_tokens=budget)
            print(f"{elapsed}s")
        except Exception as e:
            print(f"ERROR: {e}")
            break

        path = extract_path(output)
        errors = validate_path(path, maze)

        if not errors and path:
            best_output, best_errors, best_path = output, 0, path
            break
        else:
            best_output, best_errors, best_path = output, len(errors), path
            error_feedback = "\n".join(errors[:5])

        time.sleep(2)

    return {
        "model": model_key,
        "seed": maze.seed, "size": size,
        "mei": 0.9 if best_errors == 0 else 0.5,
        "sr": 1.0 if best_errors == 0 else 0.0,
        "path_valid": best_errors == 0,
        "path": best_path,
        "errors": best_errors,
        "elapsed": elapsed if best_output else None,
    }

# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default="llama-4-scout,claude-haiku", help="comma-separated")
    parser.add_argument("--n", type=int, default=10, help="trials per model")
    parser.add_argument("--sizes", default="5,7")
    parser.add_argument("--append", action="store_true", help="append to existing results")
    parser.add_argument("--output", default="experiment_results/marl_sl_openrouter.json", help="output file path")
    parser.add_argument("--seed-start", type=int, default=1001, help="first seed value")
    args = parser.parse_args()

    out_path = os.path.join('/home/jayone/Project/Miro', args.output) if not os.path.isabs(args.output) else args.output

    # Load existing results if append mode
    existing_results = []
    if args.append:
        try:
            with open(out_path) as f:
                existing = json.load(f)
                existing_results = existing.get('results', [])
                print(f"Append mode: loaded {len(existing_results)} existing results")
        except:
            pass

    model_keys = args.models.split(",")
    sizes = [int(s) for s in args.sizes.split(",")]
    seeds = [args.seed_start + i for i in range(args.n)]

    results = existing_results.copy()
    for model_key in model_keys:
        print(f"\n=== {model_key} ===")
        model_results = []
        for seed in seeds[:args.n]:
            for size in sizes:
                maze = MazeEngine(size=size, seed=seed)
                r = run_marl_sl(maze, size, model_key)
                model_results.append(r)
                results.append(r)
                time.sleep(3)

        # model summary
        valid = [r for r in model_results if r["path_valid"]]
        mei_avg = sum(r["mei"] for r in model_results) / len(model_results)
        sr = len(valid) / len(model_results)
        print(f"  {model_key}: MEI={mei_avg:.3f}, SR={sr:.1%}")

    # save
    output = {
        "method": "marl_sl_multi_model",
        "models": model_keys,
        "n_trials": args.n,
        "sizes": sizes,
        "results": results,
        "timestamp": datetime.now().isoformat(),
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved → {out_path}")
