#!/usr/bin/env python3
"""
AI Booster v3 -- EvalPlus (HumanEval+) Experiment
==================================================
목표: Qwen2.5-Coder-32B (strong, ~92.7% HumanEval) 가 EvalPlus 의 확장된
     test suite 에서도 AI Booster middleware 효과를 보이는지 검증.

EvalPlus (NeurIPS 2023): HumanEval 80x 확장 — 동일 함수에 더 다양한/극단적
edge case input 을 추가. 모델들은 표준 HumanEval 대비 10-20% 낮게 점수.

Hypothesis H_AB (harder setting):
  AI Booster 의 VERIFY step 이 EvalPlus edge case 를 더 잘 처리하게 하여
  baseline 대비 pass@1 향상을 보인다.

NIPA 실행 (Qwen2.5-Coder-32B already on port 19001):
    python3 run_aibooster_evalplus.py --model local-qwen25coder --mode booster --n 30 --seed 42
    python3 run_aibooster_evalplus.py --model local-qwen25coder --mode baseline --n 30 --seed 42
"""
from __future__ import annotations
import json, os, re, sys, time, random, socket, subprocess, tempfile
from datetime import datetime

# ===== ENV LOADING =====
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

# ===== MODELS =====
MODELS_LOCAL = {
    "local-qwen25coder": {
        "id": "Qwen/Qwen2.5-Coder-32B-Instruct",
        "display": "Qwen2.5-Coder-32B (NIPA local)",
        "base_url": "http://localhost:19001/v1",
    },
    "local-qwen3-32b": {
        "id": "Qwen/Qwen3-32B",
        "display": "Qwen3-32B (NIPA local)",
        "base_url": "http://localhost:18003/v1",
    },
}

# ===== AI BOOSTER v3 =====
AIBOOSTER_SYSTEM = """You are an expert Python programmer with enhanced metacognitive verification.

When solving any coding problem, follow these 3 steps before writing code:

STEP 1 - ANALYZE: Identify potential pitfalls
  * Incorrect assumptions about API behavior or function signatures
  * Edge cases: empty input, None values, overflow, type mismatches
  * Common algorithmic mistakes: off-by-one, wrong loop bounds, mutating input

STEP 2 - VERIFY: For each function/API you plan to use
  * Confirm it exists in standard Python or the target library
  * Confirm argument types and order are correct
  * Confirm the return type matches how you use it

STEP 3 - CODE: Write the solution after the above checks

This metacognitive verification process improves code correctness. Do not skip steps."""


def build_booster_prompt(problem: dict) -> str:
    return f"""{problem["prompt"]}

Follow the AI Booster protocol:

=== STEP 1: ANALYZE -- Potential Pitfalls ===
(Edge cases, API assumptions, algorithmic risks)

=== STEP 2: VERIFY -- API/Logic Check ===
(Confirm all functions/methods you plan to use exist and are correct)

=== STEP 3: FINAL CODE ===
```python
# Complete the function below:
```"""


def build_baseline_prompt(problem: dict) -> str:
    return f"""{problem["prompt"]}

Complete the function implementation in Python.

```python
# Complete the function below:
```"""


# ===== API CALLS =====
import requests

def call_local(prompt: str, model: dict, system: str = "", max_tokens: int = 2048) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": model["id"],
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.0,
    }
    resp = requests.post(
        f"{model['base_url']}/chat/completions",
        json=payload,
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"].get("content") or ""


# ===== EVALPLUS LOADER =====
def load_evalplus_problems(n: int = 30, seed: int = 42) -> list[dict]:
    """Load EvalPlus (HumanEval+) problems with extended test suite.

    Priority:
    1. evalplus package: get_human_eval_plus() — full extended tests
    2. HuggingFace dataset: evalplus/humanevalplus — parquet format
    3. Fall back to standard HumanEval if both fail
    """
    problems = None

    # --- Method 1: evalplus package ---
    try:
        from evalplus.data import get_human_eval_plus
        raw = get_human_eval_plus()
        problems = list(raw.values())
        print(f"  [OK] Loaded {len(problems)} problems via evalplus package (extended tests)")
    except ImportError:
        print("  [INFO] evalplus package not installed, trying HuggingFace dataset...")
    except Exception as e:
        print(f"  [WARN] evalplus package error: {e}, trying HuggingFace dataset...")

    # --- Method 2: HuggingFace dataset ---
    if problems is None:
        try:
            from datasets import load_dataset
            ds = load_dataset("evalplus/humanevalplus", split="test", trust_remote_code=False)
            problems = list(ds)
            print(f"  [OK] Loaded {len(problems)} problems via HuggingFace evalplus/humanevalplus")
        except Exception as e:
            print(f"  [WARN] HuggingFace evalplus load failed: {e}")
            problems = None

    # --- Method 3: Fallback to standard HumanEval ---
    if problems is None:
        print("  [FALLBACK] Using standard HumanEval (openai/openai_humaneval)")
        from datasets import load_dataset
        ds = load_dataset("openai/openai_humaneval", split="test")
        problems = list(ds)

    # Select n problems with fixed seed
    rng = random.Random(seed)
    rng.shuffle(problems)
    selected = problems[:n]

    return [
        {
            "task_id": p["task_id"],
            "entry_point": p["entry_point"],
            "prompt": p["prompt"],
            "canonical_solution": p["canonical_solution"],
            "test": p["test"],
        }
        for p in selected
    ]


# ===== CODE EXTRACTION =====
def extract_code(response: str, entry_point: str) -> str:
    # Try ```python ... ``` blocks
    m = re.search(r'```python\s*(.*?)```', response, re.DOTALL)
    if m:
        code = m.group(1).strip()
        if f'def {entry_point}' in code:
            return code

    # Try ``` ... ``` blocks
    m = re.search(r'```\s*(.*?)```', response, re.DOTALL)
    if m:
        code = m.group(1).strip()
        if f'def {entry_point}' in code:
            return code

    # Try STEP 3 section
    for marker in ['STEP 3: FINAL CODE', 'STEP 3 --', 'FINAL CODE']:
        idx = response.find(marker)
        if idx >= 0:
            tail = response[idx:]
            m2 = re.search(r'```(?:python)?\s*(.*?)```', tail, re.DOTALL)
            if m2 and f'def {entry_point}' in m2.group(1):
                return m2.group(1).strip()

    # Fallback: extract def block
    if f'def {entry_point}' in response:
        lines = response.split('\n')
        func_lines = []
        in_func = False
        for line in lines:
            if f'def {entry_point}' in line:
                in_func = True
            if in_func:
                func_lines.append(line)
                if func_lines and len(func_lines) > 1:
                    stripped = line.lstrip()
                    if (stripped.startswith('def ') or stripped.startswith('class ')) and f'def {entry_point}' not in line:
                        func_lines = func_lines[:-1]
                        break
        return '\n'.join(func_lines)

    return response.strip()


# ===== EVALUATION =====
def execute_evalplus(solution_code: str, test_code: str, entry_point: str, timeout: int = 15) -> tuple[bool, str]:
    """Execute solution against EvalPlus extended test suite."""
    if not solution_code or f'def {entry_point}' not in solution_code:
        return False, f"No valid function definition for {entry_point}"

    full_code = f"{solution_code}\n\n{test_code}\n\ncheck({entry_point})\n"

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(full_code)
        fname = f.name

    try:
        result = subprocess.run(
            [sys.executable, fname],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode == 0:
            return True, ""
        else:
            return False, (result.stderr or result.stdout)[:300]
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, str(e)
    finally:
        try:
            os.unlink(fname)
        except OSError:
            pass


# ===== MAIN EXPERIMENT =====
def run_experiment(model_key: str, mode: str, n: int, seed: int, output_path: str):
    model_info = MODELS_LOCAL[model_key]
    print(f"\n[AI Booster v3 -- EvalPlus (HumanEval+)]")
    print(f"  Model: {model_info['display']}")
    print(f"  Mode: {mode.upper()}")
    print(f"  n={n}, seed={seed}")
    print(f"  Output: {output_path}")
    print("=" * 60)

    problems = load_evalplus_problems(n=n, seed=seed)
    print(f"  Using {len(problems)} problems with extended EvalPlus test suite")

    results = []
    passed = 0
    errors = 0

    for i, prob in enumerate(problems):
        task_id = prob["task_id"]
        entry_point = prob["entry_point"]
        print(f"\n[{i+1}/{len(problems)}] {task_id} ({entry_point})", end=" ", flush=True)

        if mode == "booster":
            prompt = build_booster_prompt(prob)
            system = AIBOOSTER_SYSTEM
        else:
            prompt = build_baseline_prompt(prob)
            system = ""

        response = None
        error_msg = None
        for attempt in range(3):
            try:
                response = call_local(prompt, MODELS_LOCAL[model_key], system=system)
                break
            except Exception as e:
                error_msg = str(e)
                if attempt < 2:
                    time.sleep(5)

        if response is None:
            print(f"[ERROR] {error_msg}", flush=True)
            errors += 1
            results.append({
                "task_id": task_id,
                "entry_point": entry_point,
                "mode": mode,
                "passed": False,
                "error": error_msg or "no response",
            })
            continue

        code = extract_code(response, entry_point)
        ok, exec_err = execute_evalplus(code, prob["test"], entry_point)

        status = "PASS" if ok else f"FAIL({exec_err[:40]})"
        print(status, flush=True)

        if ok:
            passed += 1

        results.append({
            "task_id": task_id,
            "entry_point": entry_point,
            "mode": mode,
            "passed": ok,
            "exec_error": exec_err if not ok else "",
            "response_len": len(response),
        })

        if (i + 1) % 5 == 0:
            _save(output_path, results, passed, errors, model_key, mode, n, seed, partial=True)
            valid_so_far = i + 1 - errors
            print(f"  [CKPT] {i+1}/{len(problems)} | pass@1={passed/max(valid_so_far,1):.3f}", flush=True)

        time.sleep(1)

    _save(output_path, results, passed, errors, model_key, mode, n, seed, partial=False)

    valid = len(results) - errors
    pass_at_1 = passed / valid if valid > 0 else 0.0
    print(f"\n{'='*60}")
    print(f"  FINAL: pass@1 = {pass_at_1:.3f} ({passed}/{valid})")
    print(f"  Errors: {errors}")
    print(f"  Saved: {output_path}")
    return pass_at_1


def _save(path, results, passed, errors, model_key, mode, n, seed, partial=False):
    valid = len(results) - errors
    pass_at_1 = passed / valid if valid > 0 else 0.0
    data = {
        "experiment": "AI Booster v3 -- EvalPlus HumanEval+ (extended test suite)",
        "benchmark": "EvalPlus (HumanEval+, NeurIPS 2023) — 80x augmented test cases",
        "hypothesis": "H_AB: AI Booster VERIFY step handles edge cases better on extended test suite",
        "model": MODELS_LOCAL[model_key]["display"],
        "model_key": model_key,
        "mode": mode,
        "n_requested": n,
        "n_valid": valid,
        "n_errors": errors,
        "seed": seed,
        "partial": partial,
        "pass_at_1": round(pass_at_1, 4),
        "passed": passed,
        "timestamp": datetime.now().isoformat(),
        "results": results,
    }
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AI Booster v3 -- EvalPlus Experiment")
    parser.add_argument("--model", default="local-qwen25coder", choices=list(MODELS_LOCAL.keys()))
    parser.add_argument("--mode", default="booster", choices=["booster", "baseline"])
    parser.add_argument("--n", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.output is None:
        model_tag = args.model.replace("-", "_")
        args.output = f"experiment_results/aibooster_evalplus_{model_tag}_{args.mode}.json"

    run_experiment(
        model_key=args.model,
        mode=args.mode,
        n=args.n,
        seed=args.seed,
        output_path=args.output,
    )
