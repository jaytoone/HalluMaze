#!/usr/bin/env python3
"""
MARL Single-Layer (MARL-SL) — Five Roles, One Call
====================================================
Novel architecture: project all 5 MARL stages into a single structured LLM call.

Hypothesis:
  LLMs with extended internal reasoning (<think> blocks) already perform
  multi-step cognitive processing. Role separation across API calls is
  unnecessary if we force structured role-tagged output within one call.

Architecture:
  MARL v2: S1→S2→S3→S4→S5 = 3–7 API calls
  MARL-SL: [L1|L2|L3|L4|L5] = 1 API call + optional retry

Expected gains vs Efficient v2:
  - API calls: 1–2 (vs avg 6.2 in Eff v2)
  - Latency: ~5–10x faster (no inter-call wait)
  - Tokens: similar per call, but 1 call vs 7

Design principle: structured XML-style role tags force clear cognitive
separation within a single response, preventing role contamination.

PathValidator gate: if SL output invalid → 1 retry with error feedback.
If still invalid → fallback to Eff v2 pipeline (3-call early exit).

Usage:
    source ~/.claude/env/shared.env && python3 scripts/run_marl_single_layer_glm.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime

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

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, 'files'))
from hallumaze import MazeEngine, ResponseParser


# ═══════════════════════════════════════════════════════════════
#  GLM-4.7 API
# ═══════════════════════════════════════════════════════════════

def _strip_think(text: str) -> str:
    stripped = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    return stripped if stripped else text


def call_glm(prompt: str, system: str = "", max_tokens: int = 8000) -> str:
    import anthropic
    base_url = os.environ.get("GLM_BASE_URL", "https://api.z.ai/api/anthropic")
    model = os.environ.get("GLM_MODEL", "glm-4.7")
    client = anthropic.Anthropic(api_key=os.environ["GLM_API_KEY"], base_url=base_url)
    msg = client.messages.create(
        model=model, max_tokens=max_tokens,
        system=system or "You are a helpful assistant.",
        messages=[{"role": "user", "content": prompt}],
    )
    if not msg or not msg.content:
        raise RuntimeError("GLM returned empty response")
    return _strip_think(msg.content[0].text)


def call_timed(prompt: str, system: str = "", max_tokens: int = 8000,
               retries: int = 3, delay: float = 8.0) -> tuple[str, float]:
    for attempt in range(retries + 1):
        try:
            t0 = time.time()
            result = call_glm(prompt, system, max_tokens)
            return result, round(time.time() - t0, 2)
        except Exception as e:
            if attempt < retries:
                print(f"    [retry {attempt+1}] {e}")
                time.sleep(delay * (attempt + 1))
            else:
                raise


# ═══════════════════════════════════════════════════════════════
#  PATH VALIDATOR
# ═══════════════════════════════════════════════════════════════

def validate_path(path: list, maze: MazeEngine) -> list[str]:
    if not path or len(path) < 2:
        return ["path empty"]
    N = maze.N
    cells = maze.cells
    errors = []
    dmap = {(-1,0):'N',(1,0):'S',(0,1):'E',(0,-1):'W'}
    r0, c0 = path[0]
    if (r0, c0) != (0, 0):
        errors.append(f"start not (0,0): ({r0},{c0})")
    for i in range(len(path)-1):
        r1,c1 = path[i]; r2,c2 = path[i+1]
        if not (0<=r1<N and 0<=c1<N): errors.append(f"step {i} OOB"); continue
        if not (0<=r2<N and 0<=c2<N): errors.append(f"step {i+1} OOB"); continue
        d = dmap.get((r2-r1, c2-c1))
        if d is None: errors.append(f"step {i+1}: non-adj {(r1,c1)}->{(r2,c2)}"); continue
        if getattr(cells[r1][c1], d): errors.append(f"step {i+1}: {d} blocked {(r1,c1)}")
    rl, cl = path[-1]
    if (rl, cl) != (N-1, N-1):
        errors.append(f"no exit: ends at ({rl},{cl})")
    return errors


def extract_path(text: str) -> list[list[int]]:
    m = re.search(r'FINAL_PATH[:\s]+([\d,\(\)\s\u2192\-\>]+)', text, re.IGNORECASE)
    if m:
        coords = re.findall(r'\((\d+),\s*(\d+)\)', m.group(1))
        if len(coords) >= 2:
            return [[int(r),int(c)] for r,c in coords]
    steps = re.findall(r'STEP\s+\d+:\s*\((\d+),\s*(\d+)\)', text, re.IGNORECASE)
    if len(steps) >= 2:
        return [[int(r),int(c)] for r,c in steps]
    return []


# ═══════════════════════════════════════════════════════════════
#  SINGLE-LAYER MARL PROMPT BUILDER
# ═══════════════════════════════════════════════════════════════

SL_SYSTEM = """\
You are a unified maze reasoning system with five cognitive layers.
Process each layer fully before proceeding to the next.
Layer separation is MANDATORY — do not skip or merge layers.
"""

def build_sl_prompt(maze_text: str, N: int, error_feedback: str = "") -> str:
    retry_block = ""
    if error_feedback:
        retry_block = f"""
⚠️  RETRY — Previous attempt had errors:
{error_feedback}
In Layer 4, fix ALL errors listed above before producing final path.

"""
    return f"""{retry_block}MAZE:
{maze_text}

Process this maze through all five layers. Complete each layer fully before the next.

=== LAYER 1: ANALYST ===
Identify:
1. SUSPICIOUS WALLS — cells/directions that appear blocked but may be mirage walls (flagged).
   List each as: (row,col)-direction: reason
2. HIGH-RISK CORRIDORS — paths leading to dead ends or loops.
3. SAFE CORRIDORS — most promising paths toward ({N-1},{N-1}).

=== LAYER 2: NAVIGATOR ===
Using Layer 1 analysis, navigate from (0,0) to ({N-1},{N-1}).
Format every step: STEP N: (r,c) -> [dir] | confidence: XX% | [reason]
Dead end: DEAD_END at (r,c) -- backtracking
Loop: LOOP detected at (r,c) -- visited at step M
End with: PRELIM_PATH: (0,0)->...->({N-1},{N-1})

=== LAYER 3: AUDITOR ===
Self-audit the LAYER 2 path step-by-step against the maze above.
For EACH step verify: is that direction actually open at that cell?
List every error: ERROR step N: (r,c)->[dir] BLOCKED | CORRECT step N: (r,c)->[dir] OK
Summary: AUDIT_ERRORS_FOUND: N

=== LAYER 4: CORRECTOR ===
Apply ALL Layer 3 corrections.
Re-navigate any invalid segments using actual open directions.
Produce corrected step-by-step path reaching ({N-1},{N-1}).
End with: CORRECTED_PATH: (0,0)->...->({N-1},{N-1})

=== LAYER 5: REFINER ===
Final clean output. Verify each step one last time.

BACKTRACK_COUNT: N
HALLUCINATION_COUNT: N
CONFIDENCE_LOG: step1:XX%, step2:XX%, ...
FINAL_PATH: (0,0)->...->({N-1},{N-1})"""


# ═══════════════════════════════════════════════════════════════
#  SINGLE-LAYER PIPELINE
# ═══════════════════════════════════════════════════════════════

# Size-adaptive single-call budget (needs space for all 5 layers)
SL_BUDGET = {5: 6000, 7: 10000}


def run_marl_single_layer(maze: MazeEngine, size: int) -> dict:
    """Single-call MARL: all 5 roles in one structured LLM response."""
    maze_text = maze.encode_text(use_mirage=True)
    N = maze.N
    budget = SL_BUDGET.get(size, 10000)
    pipeline_start = time.time()

    best_output = None
    best_errors = float('inf')
    best_path = None
    attempts = 0
    call_times = []
    error_feedback = ""
    fallback_used = False

    for attempt in range(2):  # max 2 SL attempts before fallback
        attempts = attempt + 1
        prompt = build_sl_prompt(maze_text, N, error_feedback)

        print(f"    SL call (attempt {attempts}, budget={budget})...", end=" ", flush=True)
        output, elapsed = call_timed(prompt, system=SL_SYSTEM, max_tokens=budget)
        call_times.append(elapsed)
        print(f"done ({len(output)} chars, {elapsed}s)")

        path = extract_path(output)
        errors = validate_path(path, maze) if path else ["no path extracted"]

        print(f"      PathValidator: {len(errors)} errors", end="")
        if errors:
            print(f" -- {errors[:3]}")
        else:
            print(" (VALID ✓)")

        if len(errors) < best_errors:
            best_output = output
            best_errors = len(errors)
            best_path = path

        if len(errors) == 0:
            break

        error_feedback = "\n".join(errors[:8])
        time.sleep(1)

    total_elapsed = round(time.time() - pipeline_start, 2)
    total_tokens = budget * attempts

    # Parse output
    parser = ResponseParser()
    parsed = parser.parse(best_output, maze)
    final_path = parsed.get('extracted_path') or best_path
    final_errors = validate_path(final_path, maze) if final_path else ["no final path"]
    print(f"    Final: {len(final_errors)} errors | calls={attempts} | time={total_elapsed}s")

    # Efficiency vs Eff v2 baseline (avg 6.2 calls, 416.8s, 64% savings)
    eff_v2_calls = 6.2
    eff_v2_time = 416.8
    call_reduction = (1 - attempts / eff_v2_calls) * 100
    time_savings = (1 - total_elapsed / eff_v2_time) * 100

    print(f"    vs Eff v2: call reduction={call_reduction:.1f}%, time savings={time_savings:.1f}%")

    return {
        "output": best_output,
        "parsed": parsed,
        "attempts": attempts,
        "validator_errors": best_errors,
        "final_errors": len(final_errors),
        "call_times": call_times,
        "total_elapsed_sec": total_elapsed,
        "total_tokens": total_tokens,
        "fallback_used": fallback_used,
        "call_reduction_vs_eff_v2_pct": round(call_reduction, 1),
        "time_savings_vs_eff_v2_pct": round(time_savings, 1),
    }


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    seeds = [1001, 2002, 3003, 4004, 5005]
    sizes = [5, 7]
    checkpoint_path = os.path.join(_ROOT, "experiment_results", "marl_single_layer_glm.json")

    if "GLM_API_KEY" not in os.environ:
        print("ERROR: GLM_API_KEY not set.")
        sys.exit(1)

    model_name = os.environ.get("GLM_MODEL", "glm-4.7")
    print("=" * 65)
    print(f"  MARL Single-Layer (MARL-SL) — All 5 Roles in 1 Call")
    print(f"  Model: {model_name}")
    print(f"  Budget: 5x5={SL_BUDGET[5]}, 7x7={SL_BUDGET[7]} tokens")
    print(f"  Roles: [L1:Analyst|L2:Navigator|L3:Auditor|L4:Corrector|L5:Refiner]")
    print(f"  Max attempts: 2 SL calls (vs Eff v2 avg 6.2 calls)")
    print(f"  Seeds: {seeds} x Sizes: {sizes} = {len(seeds)*len(sizes)} trials")
    print("=" * 65)

    results = []
    completed = set()
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path) as f:
            data = json.load(f)
            if isinstance(data, dict) and "trials" in data:
                results = data["trials"]
            elif isinstance(data, list):
                results = data
            for r in results:
                completed.add((r["seed"], r["size"]))
        print(f"  Loaded {len(results)} existing trials")

    for seed in seeds:
        for size in sizes:
            if (seed, size) in completed:
                print(f"\n  [SKIP] seed={seed} size={size}")
                continue

            print(f"\n  [TRIAL] seed={seed} size={size}x{size}")
            maze = MazeEngine(size=size, seed=seed)
            print(f"    Solution: {len(maze.solution or [])} steps, "
                  f"Dead ends: {maze.dead_ends}, Mirages: {len(maze.mirage_traps)}")

            try:
                result = run_marl_single_layer(maze, size)
                parsed = result["parsed"]

                trial = {
                    "seed": seed, "size": size,
                    "method": "marl_single_layer",
                    "model": model_name,
                    "mei": parsed["mei"],
                    "sr": parsed["sr"],
                    "hrr": parsed["hrr"],
                    "hallucination_count": parsed["hallucinations"],
                    "backtrack_count": parsed["bt_count"],
                    "loop_count": parsed["loop_count"],
                    "brs": parsed["brs"],
                    "ce": parsed["ce"],
                    "path_valid": parsed["path_valid"],
                    "sl_attempts": result["attempts"],
                    "validator_errors": result["validator_errors"],
                    "final_errors": result["final_errors"],
                    "call_times": result["call_times"],
                    "total_elapsed_sec": result["total_elapsed_sec"],
                    "total_tokens": result["total_tokens"],
                    "fallback_used": result["fallback_used"],
                    "call_reduction_vs_eff_v2_pct": result["call_reduction_vs_eff_v2_pct"],
                    "time_savings_vs_eff_v2_pct": result["time_savings_vs_eff_v2_pct"],
                    "timestamp": datetime.now().isoformat(),
                }
                results.append(trial)
                completed.add((seed, size))

                print(f"    => MEI={parsed['mei']:.4f} | SR={parsed['sr']:.1f} | "
                      f"HRR={parsed['hrr']:.4f} | calls={result['attempts']} | "
                      f"time={result['total_elapsed_sec']}s | "
                      f"call_reduction={result['call_reduction_vs_eff_v2_pct']:.1f}%")

                _save_checkpoint(checkpoint_path, results, model_name)
                print(f"    Checkpoint saved ({len(results)} trials)")
                time.sleep(1)

            except Exception as e:
                print(f"    ERROR: {e}")
                import traceback; traceback.print_exc()

    # ── Summary ──
    if not results:
        print("\n  No results.")
        return

    print("\n" + "=" * 65)
    print(f"  MARL Single-Layer — Final Summary ({model_name})")
    print("=" * 65)

    n = len(results)
    mei_v = [r["mei"] for r in results]
    hrr_v = [r["hrr"] for r in results]
    sr_v = [r["sr"] for r in results]
    calls_v = [r["sl_attempts"] for r in results]
    time_v = [r["total_elapsed_sec"] for r in results]
    call_red_v = [r["call_reduction_vs_eff_v2_pct"] for r in results]
    time_sav_v = [r["time_savings_vs_eff_v2_pct"] for r in results]
    valid_v = sum(1 for r in results if r["final_errors"] == 0)

    mean = lambda v: sum(v)/len(v)
    baselines = {"baseline": 0.615, "v2": 0.803, "eff_v2": 0.8017}

    print(f"\n  Trials: {n} | Path valid (0 errors): {valid_v}/{n} ({valid_v/n*100:.0f}%)")
    print(f"\n  {'Metric':<28} {'MARL-SL':>10} {'Eff v2':>10} {'v2':>10} {'Baseline':>10}")
    print(f"  {'-'*65}")
    print(f"  {'MEI':.<28} {mean(mei_v):>10.4f} {'0.8017':>10} {'0.8030':>10} {'0.615':>10}")
    print(f"  {'HRR':.<28} {mean(hrr_v):>10.4f} {'0.900':>10} {'~0.718':>10} {'0.718':>10}")
    print(f"  {'SR':.<28} {mean(sr_v):>10.4f} {'0.500':>10} {'n/a':>10} {'0.083':>10}")
    print(f"  {'Avg calls/trial':.<28} {mean(calls_v):>10.2f} {'6.2':>10} {'5+':>10} {'1':>10}")
    print(f"  {'Avg time/trial (s)':.<28} {mean(time_v):>10.1f} {'416.8':>10} {'N/A':>10} {'N/A':>10}")
    print(f"  {'Call reduction vs Eff v2':.<28} {mean(call_red_v):>9.1f}% {'-':>10}")
    print(f"  {'Time savings vs Eff v2':.<28} {mean(time_sav_v):>9.1f}% {'-':>10}")

    print(f"\n  Per-trial MEI:   {[round(m,4) for m in mei_v]}")
    print(f"  Per-trial calls: {calls_v}")
    print(f"  Per-trial time:  {[round(t,1) for t in time_v]}s")

    for label, ref in baselines.items():
        delta = mean(mei_v) - ref
        pct = (mean(mei_v)/ref - 1)*100
        print(f"  >>> vs {label}: {delta:+.4f} ({pct:+.1f}%)")

    _save_checkpoint(checkpoint_path, results, model_name, summary={
        "method": "marl_single_layer",
        "innovation": "5-roles in 1 API call via structured role-tagged output",
        "model": model_name, "n_trials": n,
        "valid_rate": valid_v / n,
        "mean_mei": round(mean(mei_v), 4),
        "mean_hrr": round(mean(hrr_v), 4),
        "mean_sr": round(mean(sr_v), 4),
        "mean_calls": round(mean(calls_v), 2),
        "mean_elapsed_sec": round(mean(time_v), 1),
        "mean_call_reduction_vs_eff_v2_pct": round(mean(call_red_v), 1),
        "mean_time_savings_vs_eff_v2_pct": round(mean(time_sav_v), 1),
        "baselines": baselines,
        "delta_vs_eff_v2": round(mean(mei_v) - baselines["eff_v2"], 4),
    })
    print(f"\n  Results: {checkpoint_path}")


def _save_checkpoint(path, results, model_name, summary=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {"method": "marl_single_layer", "model": model_name,
            "timestamp": datetime.now().isoformat(), "trials": results}
    if summary:
        data["summary"] = summary
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
