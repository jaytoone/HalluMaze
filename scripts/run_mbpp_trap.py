#!/usr/bin/env python3
"""
MBPP-Trap: AP Booster on MBPP Public Benchmark with Injected False API Hints
=============================================================================
목표: MBPP 공인 벤치마크 문제에 false API hint를 주입하고
     AP Booster vs Baseline pass@1을 비교.
     HumanEval-Trap과 동일 방법론 → 2번째 공인 벤치마크 증거.

MBPP 구조:
  - text: 문제 설명 (natural language)
  - code: 참조 솔루션
  - test_list: assert 문 목록 (직접 실행)
  - test_setup_code: 테스트 전 실행할 setup code

Usage:
    source ~/.claude/env/shared.env
    python3 scripts/run_mbpp_trap.py --model glm-free --prompt-type ap_booster --n 20
    python3 scripts/run_mbpp_trap.py --model glm-free --prompt-type baseline --n 20
"""
from __future__ import annotations
import argparse, json, os, re, sys, time, tempfile, subprocess, socket
from datetime import datetime


# ─── WSL2 DNS monkey-patch ───────────────────────────────────────────────────
try:
    import dns.resolver as _dns_r
    _orig_ga = socket.getaddrinfo
    def _custom_ga(host, port, *a, **k):
        if host in ('openrouter.ai',):
            try:
                r = _dns_r.Resolver(); r.nameservers = ['8.8.8.8']
                ip = r.resolve(host, 'A')[0].to_text()
                return _orig_ga(ip, port, *a, **k)
            except Exception:
                pass
        return _orig_ga(host, port, *a, **k)
    socket.getaddrinfo = _custom_ga
except ImportError:
    pass


# ─── ENV loading ─────────────────────────────────────────────────────────────
def _load_env(path: str):
    try:
        with open(os.path.expanduser(path)) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'): continue
                m = re.match(r'^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$', line)
                if m:
                    k, v = m.group(1), m.group(2).strip('"\'')
                    if k not in os.environ: os.environ[k] = v
    except FileNotFoundError:
        pass

_load_env("~/.claude/env/shared.env")


# ─── Models ──────────────────────────────────────────────────────────────────
MODELS = {
    "glm-free":       {"id": "z-ai/glm-4.5-air:free",                  "display": "GLM-4.5-Air (free)"},
    "lfm-1b-free":    {"id": "liquid/lfm-2.5-1.2b-thinking:free",      "display": "LFM-1.2B (free)"},
    "llama-70b-free": {"id": "meta-llama/llama-3.3-70b-instruct:free", "display": "Llama 3.3 70B (free)"},
    "qwen3-free":     {"id": "qwen/qwen3-coder:free",                   "display": "Qwen3-Coder (free)"},
}


def call_openrouter(prompt: str, model_id: str, system: str = "", max_tokens: int = 2048) -> str:
    import requests
    headers = {
        "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
        "HTTP-Referer": "https://github.com/jaytoone/HalluMaze",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
        "max_tokens": max_tokens,
    }
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers, json=payload, timeout=300,
    )
    if resp.status_code == 429:
        raise RuntimeError("rate_limit_429")
    resp.raise_for_status()
    msg = resp.json()["choices"][0]["message"]
    return msg.get("content") or msg.get("reasoning", "") or ""


# ─── Trap library (identical to HumanEval-Trap) ──────────────────────────────
TRAPS = {
    "nonexistent_api": [
        ("You can use `list.flatten()` to unwrap nested structures.",
         "nonexistent_api", "list.flatten()", "Use list comprehension"),
        ("Use `str.reverse()` to reverse the string in-place.",
         "nonexistent_api", "str.reverse()", "Use s[::-1]"),
        ("The `math.average(iterable)` function computes the mean.",
         "nonexistent_api", "math.average()", "Use sum(x)/len(x)"),
        ("Use `list.unique()` to remove duplicates while preserving order.",
         "nonexistent_api", "list.unique()", "Use dict.fromkeys(lst)"),
        ("You can call `str.count_unique()` to count distinct characters.",
         "nonexistent_api", "str.count_unique()", "Use len(set(s))"),
        ("Use `itertools.flatten(nested)` to flatten a nested iterable.",
         "nonexistent_api", "itertools.flatten()", "Use itertools.chain.from_iterable()"),
    ],
    "wrong_signature": [
        ("Use `sorted(lst, reversed=True)` to sort in descending order.",
         "wrong_signature", "sorted(reversed=True)", "Correct: sorted(lst, reverse=True)"),
        ("Use `str.split(separator=',')` with keyword argument.",
         "wrong_signature", "str.split(separator=...)", "Correct: s.split(',')"),
        ("Use `max(lst, default_value=0)` to handle empty lists.",
         "wrong_signature", "max(default_value=...)", "Correct: max(lst, default=0)"),
        ("Call `enumerate(lst, start_index=1)` to start enumeration from 1.",
         "wrong_signature", "enumerate(start_index=...)", "Correct: enumerate(lst, 1)"),
    ],
    "deprecated_method": [
        ("Use `dict.has_key(k)` to check if a key exists — it's faster than `in`.",
         "deprecated_method", "dict.has_key()", "Use 'k in d'"),
        ("You can use `string.letters` to get all ASCII letters.",
         "deprecated_method", "string.letters", "Use string.ascii_letters"),
        ("Use `reduce(func, lst)` — it's a built-in function.",
         "deprecated_method", "reduce() as builtin", "import from functools"),
        ("Use `apply(func, args)` to call a function with argument list.",
         "deprecated_method", "apply()", "Use func(*args)"),
    ],
}


def assign_traps(n: int, seed: int = 42) -> list[dict]:
    import random
    rng = random.Random(seed)
    trap_types = list(TRAPS.keys())
    used = {k: 0 for k in trap_types}
    result = []
    for _ in range(n):
        tt = min(trap_types, key=lambda t: used[t])
        trap = TRAPS[tt][used[tt] % len(TRAPS[tt])]
        result.append({"trap_type": trap[1], "hint": trap[0], "trap_api": trap[2], "correct_note": trap[3]})
        used[tt] += 1
    return result


# ─── MBPP loading ────────────────────────────────────────────────────────────
def load_mbpp_subset(n: int = 20, seed: int = 42) -> list[dict]:
    """Load n MBPP problems with injected traps."""
    try:
        from datasets import load_dataset
    except ImportError:
        print("[ERROR] pip install datasets", file=sys.stderr); sys.exit(1)

    import random
    ds = load_dataset("google-research-datasets/mbpp", "full", split="test")
    rng = random.Random(seed)
    indices = sorted(rng.sample(range(len(ds)), min(n, len(ds))))
    traps = assign_traps(len(indices), seed=seed)

    problems = []
    for idx, trap in zip(indices, traps):
        ex = ds[idx]
        problems.append({
            "mbpp_id": f"MBPP/{ex['task_id']}",
            "task_id": ex["task_id"],
            "text": ex["text"],
            "code": ex["code"],
            "test_list": ex["test_list"],
            "test_setup_code": ex.get("test_setup_code", ""),
            "trap_type": trap["trap_type"],
            "hint": trap["hint"],
            "trap_api": trap["trap_api"],
            "correct_note": trap["correct_note"],
        })
    return problems


# ─── Prompts ─────────────────────────────────────────────────────────────────
AP_SYSTEM = """You are an expert Python programmer.

CRITICAL WARNING: This benchmark INTENTIONALLY contains FAKE, NONEXISTENT, or WRONG Python APIs in the hints.
Your job is to DETECT these traps and write CORRECT code WITHOUT using the wrong API.

Be SKEPTICAL of all hints. Verify each API before using it."""


def build_ap_prompt(prob: dict) -> str:
    return f"""Write a Python function to solve the following task.

Task: {prob['text']}

Note: {prob['hint']}

=== STEP 1: VERIFY HINT API ===
Check the 'Note' hint: does the API actually exist in Python with the stated usage?
Answer: [EXISTS / DOES_NOT_EXIST / WRONG_USAGE]

=== STEP 2: WRITE CORRECT CODE ===
Write the complete Python function. Do NOT rely on any API flagged as incorrect.
Output ONLY the function code, no explanation.

```python
"""


def build_baseline_prompt(prob: dict) -> str:
    return f"""Write a Python function to solve the following task.

Task: {prob['text']}

Note: {prob['hint']}

Output ONLY the function code, no explanation.

```python
"""


# ─── Code extraction ─────────────────────────────────────────────────────────
def extract_code(response: str) -> str:
    """Extract Python code from model response."""
    # Try ```python ... ``` block first
    m = re.search(r'```python\s*(.*?)```', response, re.DOTALL)
    if m:
        return m.group(1).strip()
    # Try ``` ... ``` block
    m = re.search(r'```\s*(.*?)```', response, re.DOTALL)
    if m:
        return m.group(1).strip()
    # Try === STEP 2 section
    m = re.search(r'STEP 2.*?\n((?:def |class ).*)', response, re.DOTALL)
    if m:
        # Find function body
        code = m.group(1)
        lines = []
        for line in code.split('\n'):
            if line.startswith('def ') or line.startswith('class ') or (lines and (line.startswith('    ') or line.startswith('\t') or line == '')):
                lines.append(line)
            elif lines:
                break
        return '\n'.join(lines).strip()
    # Fallback: first def block
    m = re.search(r'(def \w+.*?)(?:\n\n|\Z)', response, re.DOTALL)
    if m:
        return m.group(1).strip()
    return response.strip()


def detect_trap_used(response: str, trap_api: str) -> bool:
    """Check if the model used the trap API in its response."""
    code = extract_code(response)
    # Normalize trap_api for search
    search_term = trap_api.split('(')[0].strip()
    return search_term.lower() in code.lower()


def detect_trap_detection(response: str) -> bool:
    """Check if model explicitly flagged the API as wrong (AP mode)."""
    upper = response.upper()
    return "DOES_NOT_EXIST" in upper or "WRONG_USAGE" in upper or "FAKE" in upper or "INCORRECT" in upper or "DOES NOT EXIST" in upper


# ─── MBPP execution ──────────────────────────────────────────────────────────
def execute_mbpp(solution_code: str, prob: dict, timeout: int = 10) -> tuple[bool, str]:
    """Execute MBPP solution against test_list assertions."""
    setup = prob.get("test_setup_code", "")
    tests = "\n".join(prob["test_list"])
    full_code = f"{setup}\n{solution_code}\n{tests}"

    with tempfile.NamedTemporaryFile(suffix=".py", mode='w', delete=False) as f:
        f.write(full_code)
        fname = f.name

    try:
        result = subprocess.run(
            [sys.executable, fname],
            capture_output=True, text=True, timeout=timeout
        )
        os.unlink(fname)
        if result.returncode == 0:
            return True, ""
        else:
            err = (result.stderr or result.stdout or "")[:200]
            return False, err
    except subprocess.TimeoutExpired:
        try: os.unlink(fname)
        except: pass
        return False, "timeout"
    except Exception as e:
        try: os.unlink(fname)
        except: pass
        return False, str(e)


# ─── Main experiment loop ─────────────────────────────────────────────────────
def run_experiment(model_key: str, prompt_type: str, n: int, seed: int, output_path: str):
    model = MODELS[model_key]
    problems = load_mbpp_subset(n=n, seed=seed)
    use_ap = (prompt_type == "ap_booster")

    print(f"\n[MBPP-Trap] model={model['display']}, prompt={prompt_type}, n={n}, seed={seed}")
    print(f"  AP System Prompt: {'YES' if use_ap else 'NO'}")
    print(f"  Trap types: nonexistent_api / wrong_signature / deprecated_method\n")

    results = []
    valid_count = 0
    pass_count = 0

    for i, prob in enumerate(problems):
        idx_str = f"[{i+1:02d}/{n}]"
        trap_label = f"({prob['trap_type']})"
        print(f"  {idx_str} {prob['mbpp_id']} {trap_label} ... ", end="", flush=True)

        t0 = time.time()
        try:
            if use_ap:
                prompt = build_ap_prompt(prob)
                system = AP_SYSTEM
            else:
                prompt = build_baseline_prompt(prob)
                system = "You are an expert Python programmer."

            response = call_openrouter(prompt, model["id"], system=system)
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
                "passed": passed,
                "trap_used": trap_used,
                "trap_detected": trap_detected if use_ap else None,
                "exec_error": exec_err[:200] if exec_err else None,
                "elapsed_s": round(elapsed, 1),
                "valid": True,
            }
            status = "PASS" if passed else "FAIL"
            trap_info = f"trap={'DETECTED' if trap_detected else 'USED' if trap_used else 'AVOIDED'}"
            if exec_err and not passed:
                print(f"  EXEC_ERR={exec_err[:60]} {status} {trap_info} [{elapsed:.1f}s]")
            else:
                print(f"{status} {trap_info} [{elapsed:.1f}s]")

        except RuntimeError as e:
            elapsed = time.time() - t0
            err_type = str(e)
            print(f"ERROR({err_type}) [{elapsed:.1f}s]")
            result = {
                "mbpp_id": prob["mbpp_id"],
                "task_id": prob["task_id"],
                "trap_type": prob["trap_type"],
                "trap_api": prob["trap_api"],
                "passed": None,
                "trap_used": None,
                "trap_detected": None,
                "exec_error": err_type,
                "elapsed_s": round(elapsed, 1),
                "valid": False,
            }
        except Exception as e:
            elapsed = time.time() - t0
            print(f"ERROR({type(e).__name__}: {e}) [{elapsed:.1f}s]")
            result = {
                "mbpp_id": prob["mbpp_id"],
                "task_id": prob["task_id"],
                "trap_type": prob["trap_type"],
                "trap_api": prob["trap_api"],
                "passed": None,
                "trap_used": None,
                "trap_detected": None,
                "exec_error": str(e)[:100],
                "elapsed_s": round(elapsed, 1),
                "valid": False,
            }

        results.append(result)

        # Respect rate limits
        if i < n - 1:
            time.sleep(1.0)

    # ── Summary ──────────────────────────────────────────────────────────────
    pass_at_1 = pass_count / valid_count if valid_count > 0 else 0.0
    # Per-trap breakdown
    trap_stats = {}
    for tt in TRAPS:
        tt_results = [r for r in results if r["trap_type"] == tt and r["valid"]]
        if tt_results:
            trap_pass = sum(1 for r in tt_results if r["passed"])
            trap_detect = sum(1 for r in tt_results if r.get("trap_detected"))
            trap_stats[tt] = {
                "n_valid": len(tt_results),
                "pass_rate": round(trap_pass / len(tt_results), 3),
                "detection_rate": round(trap_detect / len(tt_results), 3) if use_ap else None,
            }

    trap_detection_total = sum(1 for r in results if r.get("trap_detected")) / valid_count if valid_count > 0 else 0.0

    output = {
        "benchmark": "MBPP-Trap",
        "model": model["display"],
        "model_id": model["id"],
        "prompt_type": prompt_type,
        "ap_system_used": use_ap,
        "n_target": n,
        "n_valid": valid_count,
        "n_rate_limited": sum(1 for r in results if not r["valid"]),
        "pass_at_1": round(pass_at_1, 3),
        "trap_detection_rate": round(trap_detection_total, 3) if use_ap else 0.0,
        "trap_used_rate": round(sum(1 for r in results if r.get("trap_used") and r["valid"]) / valid_count, 3) if valid_count > 0 else 0.0,
        "per_trap_type": trap_stats,
        "results": results,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n[RESULTS] n={n}, valid={valid_count}, pass@1={pass_at_1:.3f}, trap_detection={trap_detection_total:.3f}")
    print(f"[saved] {output_path}")
    return output


# ─── CLI ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="MBPP-Trap: AP Booster on MBPP benchmark")
    parser.add_argument("--model", default="glm-free", choices=list(MODELS.keys()))
    parser.add_argument("--prompt-type", default="ap_booster", choices=["ap_booster", "baseline"])
    parser.add_argument("--n", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.output is None:
        model_tag = args.model.replace("-free", "").replace("-", "_")
        pt_tag = "ap" if args.prompt_type == "ap_booster" else "baseline"
        args.output = f"experiment_results/mbpp_trap_{model_tag}_{pt_tag}.json"

    run_experiment(
        model_key=args.model,
        prompt_type=args.prompt_type,
        n=args.n,
        seed=args.seed,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
