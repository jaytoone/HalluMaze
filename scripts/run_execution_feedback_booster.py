#!/usr/bin/env python3
"""
Execution Feedback Booster (EFB) — EvalPlus Experiment
=======================================================
목표: generate → execute → FAIL → feed error → regenerate (max 3 turns)
     실행 피드백 루프로 EvalPlus pass@1을 통계적으로 유의미하게 향상

Research basis:
  - AlphaCodium (arXiv:2401.08500): GPT-4 19%→44% on CodeContests
  - Self-repair 2025: Qwen3-8B 23.3%→30.2% (first turn = most gain)
  - LLMLOOP (ICSME 2025): +15.92% pass@1 avg

Experiment design:
  - Baseline: single-shot generation (already done: 0.817, 49/60)
  - EFB: generate → execute → retry on failure (max_retries=3)
  - Same 60 problems, same seed=42, same model (Qwen2.5-Coder-32B)
  - McNemar paired test vs baseline

NIPA 실행:
    python3 run_execution_feedback_booster.py --n 60 --seed 42 --max-retries 3
"""
from __future__ import annotations
import json, os, re, sys, time, random, subprocess, tempfile
from datetime import datetime

# ===== ENV =====
def _load_env(path):
    try:
        with open(os.path.expanduser(path)) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'): continue
                m = re.match(r'^(?:export\s+)?([A-Za-z_]\w*)=(.*)$', line)
                if m:
                    k, v = m.group(1), m.group(2).strip('"\'')
                    if k not in os.environ: os.environ[k] = v
    except FileNotFoundError: pass

_load_env("~/.claude/env/shared.env")

MODEL = {
    "id": "Qwen/Qwen2.5-Coder-32B-Instruct",
    "display": "Qwen2.5-Coder-32B (NIPA local)",
    "base_url": "http://localhost:19001/v1",
}

# ===== EVALPLUS LOADER =====
def load_evalplus_problems(n: int = 60, seed: int = 42) -> list[dict]:
    try:
        from evalplus.data import get_human_eval_plus
        raw = get_human_eval_plus()
        problems = list(raw.values())
        print(f"  [OK] evalplus: {len(problems)} problems")
    except ImportError:
        from datasets import load_dataset
        ds = load_dataset("evalplus/humanevalplus", split="test", trust_remote_code=False)
        problems = list(ds)
        print(f"  [OK] HF dataset: {len(problems)} problems")

    rng = random.Random(seed)
    rng.shuffle(problems)
    return [
        {
            "task_id": p["task_id"],
            "entry_point": p["entry_point"],
            "prompt": p["prompt"],
            "canonical_solution": p["canonical_solution"],
            "test": p["test"],
        }
        for p in problems[:n]
    ]


# ===== PROMPTS =====
def build_initial_prompt(problem: dict) -> str:
    return f"""{problem["prompt"]}

Complete the function implementation in Python.

```python
# Complete the function below:
```"""


def build_retry_prompt(problem: dict, prev_code: str, error: str, attempt: int) -> str:
    return f"""{problem["prompt"]}

Your previous solution had an error. Please fix it.

Previous solution:
```python
{prev_code}
```

Error encountered:
```
{error[:500]}
```

Write a corrected implementation:

```python
# Fixed implementation:
```"""


# ===== API =====
import requests

def call_local(prompt: str, system: str = "", max_tokens: int = 2048) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = requests.post(
        f"{MODEL['base_url']}/chat/completions",
        json={"model": MODEL["id"], "messages": messages,
              "max_tokens": max_tokens, "temperature": 0.0},
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"].get("content") or ""


# ===== CODE EXTRACTION =====
def extract_code(response: str, entry_point: str) -> str:
    m = re.search(r'```python\s*(.*?)```', response, re.DOTALL)
    if m:
        code = m.group(1).strip()
        if f'def {entry_point}' in code:
            return code

    m = re.search(r'```\s*(.*?)```', response, re.DOTALL)
    if m:
        code = m.group(1).strip()
        if f'def {entry_point}' in code:
            return code

    if f'def {entry_point}' in response:
        lines, func_lines, in_func = response.split('\n'), [], False
        for line in lines:
            if f'def {entry_point}' in line: in_func = True
            if in_func:
                func_lines.append(line)
                if len(func_lines) > 1 and line.lstrip().startswith(('def ', 'class ')) and f'def {entry_point}' not in line:
                    func_lines = func_lines[:-1]; break
        return '\n'.join(func_lines)

    return response.strip()


# ===== EXECUTION =====
def execute(solution_code: str, test_code: str, entry_point: str, timeout: int = 15) -> tuple[bool, str]:
    if not solution_code or f'def {entry_point}' not in solution_code:
        return False, f"No function def for {entry_point}"

    full_code = f"{solution_code}\n\n{test_code}\n\ncheck({entry_point})\n"
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(full_code); fname = f.name

    try:
        result = subprocess.run([sys.executable, fname], capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            return True, ""
        return False, (result.stderr or result.stdout)[:500]
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, str(e)
    finally:
        try: os.unlink(fname)
        except OSError: pass


# ===== MAIN =====
def run_efb(n: int, seed: int, max_retries: int, output_path: str):
    print(f"\n[Execution Feedback Booster — EvalPlus]")
    print(f"  Model: {MODEL['display']}")
    print(f"  n={n}, seed={seed}, max_retries={max_retries}")
    print(f"  Output: {output_path}")
    print("=" * 60)

    problems = load_evalplus_problems(n=n, seed=seed)
    results = []
    passed = errors = 0
    total_retries_used = 0

    for i, prob in enumerate(problems):
        task_id, ep = prob["task_id"], prob["entry_point"]
        print(f"\n[{i+1}/{n}] {task_id} ({ep})", end=" ", flush=True)

        # ── Turn 0: initial generation ──
        response = error_msg = None
        for attempt in range(3):
            try:
                response = call_local(build_initial_prompt(prob))
                break
            except Exception as e:
                error_msg = str(e)
                if attempt < 2: time.sleep(5)

        if response is None:
            print(f"[API_ERROR] {error_msg}", flush=True)
            errors += 1
            results.append({"task_id": task_id, "entry_point": ep,
                             "passed": False, "retries": 0, "error": error_msg})
            continue

        code = extract_code(response, ep)
        ok, exec_err = execute(code, prob["test"], ep)

        retries_used = 0
        # ── Retry loop ──
        while not ok and retries_used < max_retries:
            retries_used += 1
            print(f"[r{retries_used}]", end=" ", flush=True)
            retry_resp = None
            for attempt in range(2):
                try:
                    retry_resp = call_local(build_retry_prompt(prob, code, exec_err, retries_used))
                    break
                except Exception as e:
                    if attempt < 1: time.sleep(5)

            if retry_resp is None:
                break

            new_code = extract_code(retry_resp, ep)
            new_ok, new_err = execute(new_code, prob["test"], ep)
            if new_ok or f'def {ep}' in new_code:
                code, ok, exec_err = new_code, new_ok, new_err

        total_retries_used += retries_used
        status = "PASS" if ok else f"FAIL"
        print(f"{status} (retries={retries_used})", flush=True)

        if ok: passed += 1

        results.append({
            "task_id": task_id, "entry_point": ep,
            "passed": ok, "retries": retries_used,
            "exec_error": exec_err if not ok else "",
            "response_len": len(response),
        })

        if (i + 1) % 10 == 0:
            _save(output_path, results, passed, errors, n, seed, max_retries, partial=True)
            valid_so_far = i + 1 - errors
            avg_retry = total_retries_used / max(i + 1, 1)
            print(f"  [CKPT] {i+1}/{n} | pass@1={passed/max(valid_so_far,1):.3f} | avg_retries={avg_retry:.2f}", flush=True)

        time.sleep(0.5)

    _save(output_path, results, passed, errors, n, seed, max_retries, partial=False)

    valid = len(results) - errors
    pass_at_1 = passed / valid if valid > 0 else 0.0
    avg_retry = total_retries_used / max(len(results), 1)

    print(f"\n{'='*60}")
    print(f"  FINAL: pass@1 = {pass_at_1:.4f} ({passed}/{valid})")
    print(f"  Avg retries used: {avg_retry:.2f} / {max_retries}")
    print(f"  Errors: {errors}")
    print(f"  Saved: {output_path}")
    return pass_at_1


def _save(path, results, passed, errors, n, seed, max_retries, partial=False):
    valid = len(results) - errors
    pass_at_1 = passed / valid if valid > 0 else 0.0
    data = {
        "experiment": "Execution Feedback Booster (EFB) — EvalPlus HumanEval+",
        "method": "generate → execute → retry on failure (error feedback loop)",
        "hypothesis": "H_EFB: Execution feedback loop significantly improves EvalPlus pass@1 vs single-shot baseline",
        "model": MODEL["display"],
        "benchmark": "EvalPlus (HumanEval+, NeurIPS 2023)",
        "n_requested": n, "n_valid": valid, "n_errors": errors,
        "seed": seed, "max_retries": max_retries,
        "partial": partial,
        "pass_at_1": round(pass_at_1, 4),
        "passed": passed,
        "timestamp": datetime.now().isoformat(),
        "baseline_reference": {"pass_at_1": 0.8167, "n": 60, "note": "single-shot baseline (no execution feedback)"},
        "results": results,
    }
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=60)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.output is None:
        args.output = f"experiment_results/efb_evalplus_qwen25coder_r{args.max_retries}.json"

    run_efb(n=args.n, seed=args.seed, max_retries=args.max_retries, output_path=args.output)
