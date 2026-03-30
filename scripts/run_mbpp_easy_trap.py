#!/usr/bin/env python3
"""
MBPP-Easy-Trap: AP Booster v2 on MBPP-Easy subset
==================================================
AP Booster v2 improvements over v1:
  1. 3-step prompt: DETECT → IDENTIFY ALTERNATIVE → WRITE CODE
  2. Explicit "name the correct stdlib alternative" step
  3. Easy filter: reference solution ≤7 non-empty lines, ≤2 test assertions
     → removes difficulty as a confound, isolates trap-awareness effect

AP v1 result (MBPP full, n=14 valid): detection=85.7%, pass@1=0.000
Expected AP v2 (MBPP-Easy): detection≥80%, pass@1>0 (difficulty unblocked)

Usage:
    # OpenRouter (requires OPENROUTER_API_KEY)
    python3 scripts/run_mbpp_easy_trap.py --model glm-free --prompt-type ap_v2 --n 15

    # NIPA GPU local server (Qwen3.5-122B via localhost:18000)
    python3 scripts/run_mbpp_easy_trap.py --model local-qwen35 --prompt-type ap_v2 --n 15
    python3 scripts/run_mbpp_easy_trap.py --model local-qwen35 --prompt-type baseline --n 15
    python3 scripts/run_mbpp_easy_trap.py --model local-nemotron --prompt-type ap_v2 --n 15

    # NIPA vLLM via reverse-tunnel (requires: ssh -R 8010:localhost:8010 nipa)
    # or: ssh nipa -L 18010:localhost:8010  → localhost:18010
"""
from __future__ import annotations
import argparse, json, os, sys, time, requests
from datetime import datetime

# Reuse infrastructure from run_mbpp_trap
sys.path.insert(0, os.path.dirname(__file__))
from run_mbpp_trap import (
    MODELS as MODELS_OR, TRAPS, call_openrouter, assign_traps,
    extract_code, detect_trap_used, detect_trap_detection, execute_mbpp,
)

# ─── Local NIPA GPU models ────────────────────────────────────────────────────
MODELS_LOCAL = {
    "local-qwen35": {
        "id": "qwen3.5-122b-a10b",
        "display": "Qwen3.5-122B (NIPA local)",
        "base_url": "http://localhost:18000/v1",
    },
    "local-nemotron": {
        "id": "nemotron-cascade-2",
        "display": "Nemotron-Cascade-2 (NIPA vLLM)",
        "base_url": "http://localhost:18010/v1",  # ssh -L 18010:localhost:8010 nipa
    },
}

MODELS = {**MODELS_OR, **MODELS_LOCAL}


def call_local(prompt: str, model: dict, system: str = "", max_tokens: int = 2048) -> str:
    """Call a locally-served model via OpenAI-compatible API."""
    payload = {
        "model": model["id"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
    }
    resp = requests.post(
        f"{model['base_url']}/chat/completions",
        json=payload,
        timeout=180,
    )
    if resp.status_code == 429:
        raise RuntimeError("rate_limit_429")
    resp.raise_for_status()
    msg = resp.json()["choices"][0]["message"]
    return msg.get("content") or ""


def call_model(prompt: str, model_key: str, system: str = "", max_tokens: int = 2048) -> str:
    """Route to local or OpenRouter based on model key."""
    model = MODELS[model_key]
    if model_key.startswith("local-"):
        return call_local(prompt, model, system=system, max_tokens=max_tokens)
    return call_openrouter(prompt, model["id"], system=system, max_tokens=max_tokens)


# ─── Easy filter ─────────────────────────────────────────────────────────────
def is_easy(code: str, test_list: list[str]) -> bool:
    """True if reference solution is short.
    MBPP test_list always has 3 entries (min), so code length is the only meaningful filter.
    ≤7 non-empty lines keeps ~66% of MBPP-test; these are the simpler string/list/math tasks.
    """
    non_empty = [l for l in code.strip().split('\n') if l.strip()]
    return len(non_empty) <= 7


def load_mbpp_easy_subset(n: int = 15, seed: int = 42, min_pool: int = 60) -> list[dict]:
    """Load n easy MBPP problems with injected traps.

    Easy = reference solution ≤7 non-empty lines AND ≤2 test assertions.
    Filters from a larger pool (min_pool problems) to find enough easy ones.
    """
    try:
        from datasets import load_dataset
    except ImportError:
        print("[ERROR] pip install datasets", file=sys.stderr); sys.exit(1)

    import random
    ds = load_dataset("google-research-datasets/mbpp", "full", split="test")
    rng = random.Random(seed)

    # Sample a larger pool and filter
    pool_size = min(min_pool, len(ds))
    indices = sorted(rng.sample(range(len(ds)), pool_size))

    easy = []
    for idx in indices:
        ex = ds[idx]
        if is_easy(ex["code"], ex["test_list"]):
            easy.append(ex)
        if len(easy) >= n:
            break

    if len(easy) < n:
        print(f"[WARN] Only {len(easy)} easy problems found in pool of {pool_size}; using all.")

    traps = assign_traps(len(easy), seed=seed)
    problems = []
    for ex, trap in zip(easy, traps):
        # Extract expected function name from test assertions
        fn_name = _extract_fn_name(ex["test_list"])
        problems.append({
            "mbpp_id": f"MBPP/{ex['task_id']}",
            "task_id": ex["task_id"],
            "text": ex["text"],
            "code": ex["code"],
            "test_list": ex["test_list"],
            "test_setup_code": ex.get("test_setup_code", ""),
            "expected_fn_name": fn_name,
            "trap_type": trap["trap_type"],
            "hint": trap["hint"],
            "trap_api": trap["trap_api"],
            "correct_note": trap["correct_note"],
        })
    return problems


def _extract_fn_name(test_list: list[str]) -> str:
    """Extract expected function name from MBPP test assertions."""
    import re
    for t in test_list:
        m = re.search(r'assert\s+(\w+)\s*\(', t)
        if m:
            return m.group(1)
    return ""


# ─── AP Booster v2 Prompts ───────────────────────────────────────────────────
AP_SYSTEM_V2 = """You are an expert Python programmer.

CRITICAL: This benchmark INTENTIONALLY plants FAKE, NONEXISTENT, or WRONG Python API hints.

Your task has 3 mandatory steps:
  1. DETECT whether the hinted API exists and works as described
  2. If wrong: NAME the correct Python stdlib/builtin alternative explicitly
  3. WRITE correct code using ONLY verified APIs from step 1 or step 2"""


def build_ap_v2_prompt(prob: dict) -> str:
    fn_clause = f"\nIMPORTANT: The function MUST be named `{prob['expected_fn_name']}`." if prob.get("expected_fn_name") else ""
    return f"""Write a Python function to solve the following task.{fn_clause}

Task: {prob['text']}

Hint: {prob['hint']}

=== STEP 1: VERIFY HINT API ===
Does the API in the 'Hint' actually exist in Python with that exact usage?
Answer: [EXISTS / DOES_NOT_EXIST / WRONG_USAGE]

=== STEP 2: NAME CORRECT ALTERNATIVE ===
If DOES_NOT_EXIST or WRONG_USAGE: what is the correct Python stdlib function/expression?
State it explicitly (e.g., "The correct way is: sorted(lst, reverse=True)").
If EXISTS: write "No correction needed."

=== STEP 3: WRITE CORRECT CODE ===
Write the complete Python function using ONLY the verified API from step 1 or the correct
alternative from step 2. Do NOT use any API you flagged as wrong.
Output ONLY the function code, no explanation.

```python
"""


def build_baseline_v2_prompt(prob: dict) -> str:
    fn_clause = f"\nIMPORTANT: The function MUST be named `{prob['expected_fn_name']}`." if prob.get("expected_fn_name") else ""
    return f"""Write a Python function to solve the following task.{fn_clause}

Task: {prob['text']}

Note: {prob['hint']}

Output ONLY the function code, no explanation.

```python
"""


# ─── Experiment runner ────────────────────────────────────────────────────────
def run_experiment(model_key: str, prompt_type: str, n: int, seed: int, output_path: str):
    model = MODELS[model_key]
    problems = load_mbpp_easy_subset(n=n, seed=seed, min_pool=max(150, n * 5))
    use_ap = (prompt_type in ("ap_v2", "ap_booster_v2"))

    print(f"\n[MBPP-Easy-Trap] model={model['display']}, prompt={prompt_type}, n={n}, seed={seed}")
    print(f"  AP v2 System Prompt: {'YES' if use_ap else 'NO'}")
    print(f"  Problems loaded: {len(problems)} (easy-filtered)")
    print()

    results = []
    valid_count = 0
    pass_count = 0

    for i, prob in enumerate(problems):
        idx_str = f"[{i+1:02d}/{len(problems)}]"
        trap_label = f"({prob['trap_type']})"
        code_lines = len([l for l in prob['code'].strip().split('\n') if l.strip()])
        print(f"  {idx_str} {prob['mbpp_id']} {trap_label} lines={code_lines} ... ", end="", flush=True)

        t0 = time.time()
        try:
            if use_ap:
                prompt = build_ap_v2_prompt(prob)
                system = AP_SYSTEM_V2
            else:
                prompt = build_baseline_v2_prompt(prob)
                system = "You are an expert Python programmer."

            response = call_model(prompt, model_key, system=system)
            elapsed = time.time() - t0

            code = extract_code(response)
            passed, exec_err = execute_mbpp(code, prob)
            trap_used = detect_trap_used(response, prob["trap_api"])
            trap_detected = detect_trap_detection(response) if use_ap else False

            valid_count += 1
            if passed:
                pass_count += 1

            result = {
                "mbpp_id": prob["mbpp_id"],
                "task_id": prob["task_id"],
                "trap_type": prob["trap_type"],
                "trap_api": prob["trap_api"],
                "code_lines": code_lines,
                "n_tests": len(prob["test_list"]),
                "passed": passed,
                "trap_used": trap_used,
                "trap_detected": trap_detected if use_ap else None,
                "exec_error": exec_err[:200] if exec_err else None,
                "elapsed_s": round(elapsed, 1),
                "valid": True,
            }
            status = "PASS" if passed else "FAIL"
            trap_info = f"trap={'DETECTED' if trap_detected else 'USED' if trap_used else 'AVOIDED'}"
            print(f"{status} {trap_info} [{elapsed:.1f}s]")

        except RuntimeError as e:
            elapsed = time.time() - t0
            print(f"ERROR({e}) [{elapsed:.1f}s]")
            result = {
                "mbpp_id": prob["mbpp_id"],
                "task_id": prob["task_id"],
                "trap_type": prob["trap_type"],
                "trap_api": prob["trap_api"],
                "code_lines": code_lines,
                "n_tests": len(prob["test_list"]),
                "passed": None, "trap_used": None, "trap_detected": None,
                "exec_error": str(e), "elapsed_s": round(elapsed, 1), "valid": False,
            }
        except Exception as e:
            elapsed = time.time() - t0
            print(f"ERROR({type(e).__name__}: {e}) [{elapsed:.1f}s]")
            result = {
                "mbpp_id": prob["mbpp_id"],
                "task_id": prob["task_id"],
                "trap_type": prob["trap_type"],
                "trap_api": prob["trap_api"],
                "code_lines": code_lines,
                "n_tests": len(prob["test_list"]),
                "passed": None, "trap_used": None, "trap_detected": None,
                "exec_error": str(e)[:100], "elapsed_s": round(elapsed, 1), "valid": False,
            }

        results.append(result)
        if i < len(problems) - 1:
            time.sleep(1.5)

    # ── Summary ──────────────────────────────────────────────────────────────
    pass_at_1 = pass_count / valid_count if valid_count > 0 else 0.0
    trap_detection_total = (
        sum(1 for r in results if r.get("trap_detected")) / valid_count
        if use_ap and valid_count > 0 else 0.0
    )

    per_trap_stats = {}
    for tt in TRAPS:
        tt_results = [r for r in results if r["trap_type"] == tt and r["valid"]]
        if tt_results:
            per_trap_stats[tt] = {
                "n_valid": len(tt_results),
                "pass_rate": round(sum(1 for r in tt_results if r["passed"]) / len(tt_results), 3),
                "detection_rate": round(sum(1 for r in tt_results if r.get("trap_detected")) / len(tt_results), 3) if use_ap else None,
            }

    output = {
        "benchmark": "MBPP-Easy-Trap",
        "variant": "ap_v2" if use_ap else "baseline",
        "model": model["display"],
        "model_id": model["id"],
        "prompt_type": prompt_type,
        "ap_v2_used": use_ap,
        "easy_filter": {"max_code_lines": 7, "note": "MBPP test_list always >=3; filter by code length only"},
        "n_target": n,
        "n_valid": valid_count,
        "n_rate_limited": sum(1 for r in results if not r["valid"]),
        "pass_at_1": round(pass_at_1, 3),
        "trap_detection_rate": round(trap_detection_total, 3) if use_ap else 0.0,
        "trap_used_rate": round(
            sum(1 for r in results if r.get("trap_used") and r["valid"]) / valid_count, 3
        ) if valid_count > 0 else 0.0,
        "per_trap_type": per_trap_stats,
        "results": results,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n[RESULTS] easy_filter=True, n_valid={valid_count}")
    print(f"  pass@1={pass_at_1:.3f}  trap_detection={trap_detection_total:.3f}")
    print(f"[saved] {output_path}")
    return output


# ─── CLI ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="MBPP-Easy-Trap: AP Booster v2 on difficulty-filtered MBPP")
    parser.add_argument("--model", default="local-qwen35", choices=list(MODELS.keys()))
    parser.add_argument("--prompt-type", default="ap_v2", choices=["ap_v2", "baseline"])
    parser.add_argument("--n", type=int, default=15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.output is None:
        model_tag = args.model.replace("-free", "").replace("-", "_")
        pt_tag = "ap_v2" if args.prompt_type in ("ap_v2", "ap_booster_v2") else "baseline"
        args.output = f"experiment_results/mbpp_easy_trap_{model_tag}_{pt_tag}.json"

    run_experiment(
        model_key=args.model,
        prompt_type=args.prompt_type,
        n=args.n,
        seed=args.seed,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
