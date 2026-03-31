#!/usr/bin/env python3
"""
UACG (Uncertainty-Aware Code Generation) Booster — Targeted Experiment
=======================================================================
Hypothesis: Having a model explicitly tag uncertain code regions before
execution enables more targeted, effective repair than blind error-feedback.

Method:
  1. System prompt: "tag uncertain regions with # [UNCERTAIN: reason]"
  2. Generate initial solution with uncertainty markers
  3. Execute: if fail, extract uncertain lines as repair targets
  4. Targeted repair: "fix specifically the [UNCERTAIN] sections"
  5. Max 3 repair attempts

Experiment design:
  - Target: 7 EFB-resistant problems (failed even after 3 EFB retries)
  - Baseline comparison: EFB recovery=0/7 (0%) on these exact problems
  - UACG target: >0/7 on these hard cases = meaningful differentiation
  - Model: Qwen2.5-Coder-32B (NIPA port 19001)

NIPA 실행:
    python3 run_uacg_booster.py

Research basis:
  - UACG concept: pre-hoc uncertainty tagging vs post-hoc error recovery
  - Self-calibration: Guo et al. ICML 2017 (calibration of neural networks)
  - Targeted repair: specific failure locus vs blind regeneration
"""
from __future__ import annotations
import json, os, re, sys, time, subprocess, tempfile
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

# ===== TARGET PROBLEMS =====
# These 7 problems failed baseline AND failed all 3 EFB retries
# EFB recovery on these: 0/7 (0%)
EFB_RESISTANT_IDS = [
    "HumanEval/127",
    "HumanEval/130",
    "HumanEval/132",
    "HumanEval/134",
    "HumanEval/145",
    "HumanEval/32",
    "HumanEval/76",
]

# ===== EVALPLUS LOADER =====
def load_target_problems() -> list[dict]:
    try:
        from evalplus.data import get_human_eval_plus
        raw = get_human_eval_plus()
        print(f"  [OK] evalplus: {len(raw)} problems total")
    except ImportError:
        from datasets import load_dataset
        ds = load_dataset("evalplus/humanevalplus", split="test", trust_remote_code=False)
        raw = {p["task_id"]: p for p in ds}
        print(f"  [OK] HF dataset: {len(raw)} problems total")

    problems = []
    for tid in EFB_RESISTANT_IDS:
        if tid in raw:
            p = raw[tid]
            problems.append({
                "task_id": p["task_id"],
                "entry_point": p["entry_point"],
                "prompt": p["prompt"],
                "canonical_solution": p["canonical_solution"],
                "test": p["test"],
            })
            print(f"  [LOAD] {tid} ({p['entry_point']})")
        else:
            print(f"  [WARN] {tid} not found — skipping")
    return problems


# ===== UACG SYSTEM PROMPT =====
UACG_SYSTEM = """You are an expert Python programmer. When generating code, mark any lines or blocks
where you are uncertain about the correct implementation with an inline comment:
  # [UNCERTAIN: reason]

Place this marker at the END of the uncertain line, or on a separate comment line above the uncertain block.
Examples:
  result = some_complex_logic(x, y)  # [UNCERTAIN: not sure about edge case for empty input]
  # [UNCERTAIN: this sorting approach may be incorrect for negative numbers]
  arr.sort(key=lambda x: -x)

Be honest about your uncertainty — tag every line where you are less than fully confident.
This helps with targeted debugging."""

UACG_REPAIR_SYSTEM = """You are an expert Python programmer fixing a code solution.
The failing solution contains [UNCERTAIN] markers indicating where the original author was unsure.
Focus your fix on the uncertain regions — these are the most likely sources of bugs."""


# ===== PROMPTS =====
def build_uacg_prompt(problem: dict) -> str:
    return f"""{problem["prompt"]}

Complete the function implementation in Python.
Mark any uncertain lines with `# [UNCERTAIN: reason]` at the end of the line.

```python
# Complete the function below (mark uncertain lines):
```"""


def build_uacg_repair_prompt(problem: dict, prev_code: str, error: str, uncertain_lines: list[str]) -> str:
    uncertain_section = ""
    if uncertain_lines:
        uncertain_section = f"""
The following lines were marked as UNCERTAIN (most likely sources of bugs):
{chr(10).join(f'  Line: {l.strip()}' for l in uncertain_lines[:10])}
"""
    return f"""{problem["prompt"]}

Your previous solution failed. Here is the failing code:
```python
{prev_code}
```

Error:
```
{error[:500]}
```
{uncertain_section}
Please fix the implementation. Focus especially on the [UNCERTAIN] regions.
Write the complete corrected function:

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


def extract_uncertain_lines(code: str) -> list[str]:
    """Extract lines containing [UNCERTAIN] markers."""
    uncertain = []
    for line in code.split('\n'):
        if '[UNCERTAIN' in line or '[UNCERTAIN:' in line:
            uncertain.append(line)
    return uncertain


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
def run_uacg(output_path: str, max_retries: int = 3):
    print(f"\n[UACG Booster — EFB-Resistant Hard Problems]")
    print(f"  Model: {MODEL['display']}")
    print(f"  Target: {len(EFB_RESISTANT_IDS)} EFB-resistant problems")
    print(f"  EFB baseline on these: 0/7 (0% recovery)")
    print(f"  Max repair attempts: {max_retries}")
    print(f"  Output: {output_path}")
    print("=" * 60)

    problems = load_target_problems()
    if not problems:
        print("[ERROR] No problems loaded!")
        return

    results = []
    recovered = 0

    for i, prob in enumerate(problems):
        task_id, ep = prob["task_id"], prob["entry_point"]
        print(f"\n[{i+1}/{len(problems)}] {task_id} ({ep})", flush=True)

        # ── Turn 0: UACG initial generation ──
        response = None
        for attempt in range(3):
            try:
                response = call_local(
                    build_uacg_prompt(prob),
                    system=UACG_SYSTEM,
                )
                break
            except Exception as e:
                print(f"  [API_ERR] {e}", flush=True)
                if attempt < 2: time.sleep(5)

        if response is None:
            print(f"  [SKIP] API failure", flush=True)
            results.append({
                "task_id": task_id, "entry_point": ep,
                "passed": False, "retries": 0,
                "uncertain_lines": [], "error": "API failure",
                "note": "skipped"
            })
            continue

        code = extract_code(response, ep)
        uncertain_lines = extract_uncertain_lines(code)
        print(f"  Uncertain tags: {len(uncertain_lines)}", flush=True)
        if uncertain_lines:
            for ul in uncertain_lines[:3]:
                print(f"    {ul.strip()[:80]}", flush=True)

        ok, exec_err = execute(code, prob["test"], ep)
        print(f"  Turn 0: {'PASS' if ok else 'FAIL'}", flush=True)

        retries_used = 0
        # ── Targeted repair loop ──
        while not ok and retries_used < max_retries:
            retries_used += 1
            print(f"  [repair {retries_used}/{max_retries}]", end=" ", flush=True)

            repair_resp = None
            for attempt in range(2):
                try:
                    repair_resp = call_local(
                        build_uacg_repair_prompt(prob, code, exec_err, uncertain_lines),
                        system=UACG_REPAIR_SYSTEM,
                    )
                    break
                except Exception as e:
                    if attempt < 1: time.sleep(5)

            if repair_resp is None:
                print("[API_ERR]", flush=True)
                break

            new_code = extract_code(repair_resp, ep)
            new_uncertain = extract_uncertain_lines(new_code)
            new_ok, new_err = execute(new_code, prob["test"], ep)
            print(f"{'PASS' if new_ok else 'FAIL'} (uncertain tags: {len(new_uncertain)})", flush=True)

            if f'def {ep}' in new_code:
                code = new_code
                uncertain_lines = new_uncertain
                ok = new_ok
                exec_err = new_err

        if ok:
            recovered += 1
            print(f"  ✓ RECOVERED (retries={retries_used})", flush=True)
        else:
            print(f"  ✗ STILL FAILING after {retries_used} repairs", flush=True)

        results.append({
            "task_id": task_id, "entry_point": ep,
            "passed": ok, "retries": retries_used,
            "uncertain_lines": uncertain_lines,
            "uncertain_count": len(uncertain_lines),
            "exec_error": exec_err if not ok else "",
        })
        time.sleep(0.5)

    # ── Summary ──
    n = len(problems)
    print(f"\n{'='*60}")
    print(f"  UACG Results: {recovered}/{n} recovered ({recovered/n:.1%})")
    print(f"  EFB baseline: 0/{n} recovered (0.0%) — same hard problems")
    print(f"  Improvement:  +{recovered}/{n} problems")
    print(f"\n  Per-problem breakdown:")
    for r in results:
        status = "RECOVERED" if r["passed"] else "FAIL"
        print(f"    {r['task_id']}: {status} (retries={r['retries']}, uncertain_tags={r.get('uncertain_count',0)})")

    data = {
        "experiment": "UACG (Uncertainty-Aware Code Generation) Booster",
        "method": "system prompt tags uncertain regions → targeted repair on [UNCERTAIN] lines",
        "hypothesis": "H_UACG: Pre-hoc uncertainty tagging enables more effective targeted repair vs blind EFB",
        "model": MODEL["display"],
        "target": "7 EFB-resistant failures (failed after 3 EFB retries)",
        "efb_baseline_on_these": {"recovered": 0, "total": n, "rate": 0.0},
        "uacg_results": {"recovered": recovered, "total": n, "rate": round(recovered/n, 4)},
        "improvement": recovered,
        "max_retries": max_retries,
        "timestamp": datetime.now().isoformat(),
        "results": results,
    }
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved: {output_path}")
    return recovered, n


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--output", default="experiment_results/uacg_efb_resistant_qwen25coder.json")
    args = parser.parse_args()
    run_uacg(output_path=args.output, max_retries=args.max_retries)
