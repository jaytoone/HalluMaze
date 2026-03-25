#!/usr/bin/env python3
"""
MARL Efficient v2 — S2 PathValidator Early Exit + Size-Adaptive Budget + Time Tracking
========================================================================================
Phase 1+2 combined:
  1. Size-adaptive token budget (5x5 vs 7x7 differentiated)
  2. S2 PathValidator Early Exit: if S2 produces valid path → skip S3+S4
  3. Wall-clock time per stage + total trial time

Expected savings vs v2 (5-stage, full budget):
  - Valid S2 path (early exit):  ~3 calls, ~70% token savings, ~60% time savings
  - Invalid S2 path (full pipe): ~5 calls, ~50% token savings, ~40% time savings

Usage:
    source ~/.claude/env/shared.env && python3 scripts/run_marl_efficient_v2_glm.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime

# ── env loading ──
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

# ── hallumaze import ──
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, 'files'))
from hallumaze import MazeEngine, ResponseParser


# ═══════════════════════════════════════════════════════════════
#  GLM-4.7 API
# ═══════════════════════════════════════════════════════════════

def _strip_think(text: str) -> str:
    stripped = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    return stripped if stripped else text


def call_glm(prompt: str, system: str = "", max_tokens: int = 4000) -> str:
    import anthropic
    base_url = os.environ.get("GLM_BASE_URL", "https://api.z.ai/api/anthropic")
    model = os.environ.get("GLM_MODEL", "glm-4.7")
    client = anthropic.Anthropic(api_key=os.environ["GLM_API_KEY"], base_url=base_url)
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system or "You are a helpful assistant.",
        messages=[{"role": "user", "content": prompt}],
    )
    if msg is None or not msg.content:
        raise RuntimeError("GLM returned empty response")
    return _strip_think(msg.content[0].text)


def call_timed(prompt: str, system: str = "", max_tokens: int = 4000,
               retries: int = 4, delay: float = 8.0) -> tuple[str, float]:
    """Returns (response_text, elapsed_seconds)."""
    for attempt in range(retries + 1):
        try:
            t0 = time.time()
            result = call_glm(prompt, system, max_tokens)
            return result, round(time.time() - t0, 2)
        except Exception as e:
            if attempt < retries:
                print(f"    [retry {attempt+1}/{retries}] {e}")
                time.sleep(delay * (attempt + 1))
            else:
                raise


# ═══════════════════════════════════════════════════════════════
#  PATH VALIDATOR
# ═══════════════════════════════════════════════════════════════

def validate_path(extracted_path: list, maze: MazeEngine) -> list[str]:
    if not extracted_path or len(extracted_path) < 2:
        return ["path is empty or has fewer than 2 positions"]

    N = maze.N
    cells = maze.cells
    errors = []
    direction_map = {(-1, 0): 'N', (1, 0): 'S', (0, 1): 'E', (0, -1): 'W'}

    r0, c0 = extracted_path[0]
    if (r0, c0) != (0, 0):
        errors.append(f"path does not start at (0,0), starts at ({r0},{c0})")

    for i in range(len(extracted_path) - 1):
        r1, c1 = extracted_path[i]
        r2, c2 = extracted_path[i + 1]
        if not (0 <= r1 < N and 0 <= c1 < N):
            errors.append(f"step {i}: position ({r1},{c1}) out of bounds")
            continue
        if not (0 <= r2 < N and 0 <= c2 < N):
            errors.append(f"step {i+1}: position ({r2},{c2}) out of bounds")
            continue
        dr, dc = r2 - r1, c2 - c1
        direction = direction_map.get((dr, dc))
        if direction is None:
            errors.append(f"step {i+1}: non-adjacent move ({r1},{c1})->({r2},{c2})")
            continue
        if getattr(cells[r1][c1], direction):
            errors.append(f"step {i+1}: {direction} blocked at ({r1},{c1})->({r2},{c2})")

    if extracted_path:
        rl, cl = extracted_path[-1]
        if (rl, cl) != (N - 1, N - 1):
            errors.append(f"path does not reach exit ({N-1},{N-1}), ends at ({rl},{cl})")
    return errors


def extract_path_from_text(text: str) -> list[list[int]]:
    path_match = re.search(r'FINAL_PATH[:\s]+([\d,\(\)\s\u2192\-\>]+)', text, re.IGNORECASE)
    if path_match:
        coords = re.findall(r'\((\d+),\s*(\d+)\)', path_match.group(1))
        if len(coords) >= 2:
            return [[int(r), int(c)] for r, c in coords]
    step_pattern = re.compile(r'STEP\s+(\d+):\s*\((\d+),\s*(\d+)\)', re.IGNORECASE)
    steps = []
    for m in step_pattern.finditer(text):
        steps.append([int(m.group(2)), int(m.group(3))])
    if len(steps) >= 2:
        return steps
    return []


# ═══════════════════════════════════════════════════════════════
#  SIZE-ADAPTIVE TOKEN BUDGETS
# ═══════════════════════════════════════════════════════════════

def get_budget(size: int) -> dict:
    """Size-adaptive token budget. S1/S3/S4 full; S2/S5 adaptive."""
    if size <= 5:
        return {"s1": 4000, "s2": 2500, "s3": 3000, "s4": 3000, "s5": 1200}
    else:  # 7x7+
        return {"s1": 5000, "s2": 5000, "s3": 4000, "s4": 4000, "s5": 2500}


# ═══════════════════════════════════════════════════════════════
#  MARL EFFICIENT v2 PIPELINE
# ═══════════════════════════════════════════════════════════════

def run_marl_efficient_v2(maze: MazeEngine, size: int) -> dict:
    """
    5-stage pipeline with:
    1. Size-adaptive token budget
    2. S2 PathValidator Early Exit (skip S3+S4 if S2 valid)
    3. Wall-clock time tracking per stage
    """
    maze_text = maze.encode_text(use_mirage=True)
    N = maze.N
    budget = get_budget(size)
    stage_times = {}
    stage_tokens = {}
    pipeline_start = time.time()

    # ── S1: Hypothesis ──
    s1_system = (
        "You are a Maze Analyst specializing in trap detection. "
        "Analyze the maze structure and identify potential mirage walls (walls that "
        "appear blocked but might be traversable) and risky paths that could lead to dead ends."
    )
    s1_prompt = f"""MAZE:
{maze_text}

Analyze this maze carefully. Provide:
1. SUSPICIOUS WALLS: List cells and directions where walls might be mirages (traversable despite appearing blocked). Look for hints marked with the flag symbol.
2. HIGH-RISK CORRIDORS: Paths that lead to dead ends or loops.
3. SAFE CORRIDORS: Paths that are most likely to lead toward the exit ({N-1},{N-1}).
4. RECOMMENDED STRATEGY: Step-by-step exploration strategy prioritizing safe paths and testing suspicious walls.

Be specific with cell coordinates."""

    print("    S1 Hypothesis...", end=" ", flush=True)
    s1_output, s1_time = call_timed(s1_prompt, system=s1_system, max_tokens=budget["s1"])
    stage_times["s1"] = s1_time
    stage_tokens["s1"] = budget["s1"]
    print(f"done ({len(s1_output)} chars, {s1_time}s)")
    time.sleep(1)

    # ── S2: Solver (early exit gate) ──
    s2_system = (
        "You are a Maze Navigator. Generate a complete step-by-step navigation path "
        "from START (0,0) to EXIT. Use the hypothesis analysis to avoid traps. "
        "Mark dead ends and loops when encountered."
    )

    best_s2_output = None
    best_s2_errors = float('inf')
    best_s2_path = None
    s2_attempts = 0
    s2_total_time = 0.0
    retry_note = ""
    early_exit = False

    for attempt in range(3):
        s2_prompt = f"""MAZE:
{maze_text}

HYPOTHESIS ANALYSIS (from threat assessment):
{s1_output}
{retry_note}
Navigate from (0,0) to ({N-1},{N-1}).

Rules:
- Format each step: STEP N: (r,c) -> [direction] | confidence: XX% | [reason]
- When hitting a dead end: DEAD_END at (r,c) -- backtracking
- When detecting a loop: LOOP detected at (r,c) -- visited at step M
- When changing strategy: STRATEGY_CHANGE -- [reason]

End with:
BACKTRACK_COUNT: N
HALLUCINATION_COUNT: N
CONFIDENCE_LOG: step1:conf1, step2:conf2, ...
FINAL_PATH: (0,0)->...->({N-1},{N-1})"""

        print(f"    S2 Solver (attempt {attempt+1}/3, budget={budget['s2']})...", end=" ", flush=True)
        s2_out, s2_t = call_timed(s2_prompt, system=s2_system, max_tokens=budget["s2"])
        s2_total_time += s2_t
        print(f"done ({len(s2_out)} chars, {s2_t}s)")
        s2_attempts = attempt + 1

        path = extract_path_from_text(s2_out)
        errors = validate_path(path, maze) if path else ["no path extracted"]

        print(f"      Validator: {len(errors)} errors", end="")
        if errors:
            print(f" -- {errors[:3]}")
        else:
            print(" (VALID ✓)")

        if len(errors) < best_s2_errors:
            best_s2_output = s2_out
            best_s2_errors = len(errors)
            best_s2_path = path

        if len(errors) == 0:
            early_exit = True
            break

        retry_note = (
            f"\n\nIMPORTANT: Your previous attempt had {len(errors)} invalid moves: "
            f"{'; '.join(errors[:5])}. "
            f"Please re-read the maze cell directions carefully and re-navigate. "
            f"Check each step against the allowed directions listed for each cell.\n"
        )
        time.sleep(1)

    stage_times["s2"] = round(s2_total_time, 2)
    stage_tokens["s2"] = budget["s2"] * s2_attempts
    s2_output = best_s2_output

    # ── EARLY EXIT GATE ──
    if early_exit:
        print(f"    [EARLY EXIT] S2 valid path → skipping S3+S4")
        stage_times["s3"] = 0.0
        stage_times["s4"] = 0.0
        stage_tokens["s3"] = 0
        stage_tokens["s4"] = 0
        s3_output = "[SKIPPED — S2 PathValidator passed]"
        s4_output = s2_output  # pass S2 directly to S5
    else:
        # ── S3: Auditor ──
        s3_system = (
            "You are a Path Auditor. Your job is to find every error in the navigation path. "
            "Check each move against the maze structure. Be thorough and precise."
        )
        s3_prompt = f"""MAZE (reference -- verify every step against these cell directions):
{maze_text}

---

GENERATED PATH:
{s2_output}

Audit this path thoroughly:
1. INVALID MOVES: Check each step -- is the direction actually open in the maze? List step numbers with errors.
2. UNDETECTED LOOPS: Cells visited more than once without LOOP_DETECTED marker.
3. MISSED BACKTRACKS: Places where the solver should have backtracked but didn't.
4. PATH CONTINUITY: Does each step follow from the previous position?
5. GOAL REACHED: Does the path actually reach ({N-1},{N-1})?

For each error found, specify:
- ERROR at STEP N: (r,c) -> [direction] -- [what's wrong] -- FIX: [correction]"""

        print("    S3 Auditor...", end=" ", flush=True)
        s3_output, s3_time = call_timed(s3_prompt, system=s3_system, max_tokens=budget["s3"])
        stage_times["s3"] = s3_time
        stage_tokens["s3"] = budget["s3"]
        print(f"done ({len(s3_output)} chars, {s3_time}s)")
        time.sleep(1)

        # ── S4: Verifier ──
        s4_system = (
            "You are a Path Corrector. Apply all audit corrections to produce a valid path. "
            "Re-verify each step against the maze. Output a corrected step-by-step path."
        )
        s4_prompt = f"""MAZE (reference -- verify every step against these cell directions):
{maze_text}

---

ORIGINAL PATH:
{s2_output}

AUDIT FINDINGS:
{s3_output}

Apply all corrections:
- Fix every invalid move identified by the auditor.
- Add LOOP_DETECTED markers where missing.
- Fix backtracking decisions.
- Ensure the path reaches ({N-1},{N-1}).

Output the CORRECTED path in format:
STEP N: (r,c) -> [direction] | confidence: XX% | [reason]
DEAD_END at (r,c) -- backtracking
LOOP detected at (r,c) -- visited at step M

End with:
BACKTRACK_COUNT: N
HALLUCINATION_COUNT: N
CONFIDENCE_LOG: step1:conf1, step2:conf2, ...
FINAL_PATH: (0,0)->...->({N-1},{N-1})"""

        print("    S4 Verifier...", end=" ", flush=True)
        s4_output, s4_time = call_timed(s4_prompt, system=s4_system, max_tokens=budget["s4"])
        stage_times["s4"] = s4_time
        stage_tokens["s4"] = budget["s4"]
        print(f"done ({len(s4_output)} chars, {s4_time}s)")
        time.sleep(1)

    # ── S5: Refiner ──
    s5_system = (
        "You are a Path Refiner. Output the final clean navigation path in exact benchmark format. "
        "Verify every single step against the maze one last time."
    )
    s5_prompt = f"""MAZE (reference -- verify every step against these cell directions):
{maze_text}

---

CORRECTED PATH:
{s4_output}

Output the FINAL path in EXACT benchmark format. Verify each step against the maze.

Format:
STEP N: (r,c) -> [direction] | confidence: XX% | [reason]
DEAD_END at (r,c) -- backtracking
LOOP detected at (r,c) -- visited at step M
STRATEGY_CHANGE -- [reason]

Must end with (MANDATORY):
BACKTRACK_COUNT: N
HALLUCINATION_COUNT: N
CONFIDENCE_LOG: step1:85%, step2:90%, ...
FINAL_PATH: (0,0)->...->({N-1},{N-1})"""

    print(f"    S5 Refiner (budget={budget['s5']})...", end=" ", flush=True)
    s5_output, s5_time = call_timed(s5_prompt, system=s5_system, max_tokens=budget["s5"])
    stage_times["s5"] = s5_time
    stage_tokens["s5"] = budget["s5"]
    print(f"done ({len(s5_output)} chars, {s5_time}s)")

    # ── Parse ──
    parser = ResponseParser()
    parsed = parser.parse(s5_output, maze)

    final_path = parsed.get('extracted_path') or extract_path_from_text(s5_output)
    final_errors = validate_path(final_path, maze) if final_path else ["no final path"]
    print(f"    Final path validator: {len(final_errors)} errors")

    # ── Efficiency stats ──
    total_elapsed = round(time.time() - pipeline_start, 2)
    total_tokens = sum(stage_tokens.values())
    calls_used = 1 + s2_attempts + (0 if early_exit else 2) + 1  # S1 + S2 + [S3+S4] + S5

    # v2 baseline: 5 stages × budget["s2"] (8000 each) per attempt
    v2_token_baseline = 8000 * (3 + s2_attempts + 2)
    v2_time_baseline = 60.0 * (3 + s2_attempts + 2) / 7  # rough: ~60s per 7 stages at v2

    token_savings = (1 - total_tokens / v2_token_baseline) * 100
    time_savings_vs_max = (1 - total_elapsed / (v2_time_baseline)) * 100

    print(f"    Calls: {calls_used} | Tokens: {total_tokens} | Time: {total_elapsed}s | "
          f"Early exit: {early_exit} | Token savings: {token_savings:.1f}%")

    return {
        "s1": s1_output,
        "s2": s2_output,
        "s3": s3_output,
        "s4": s4_output,
        "s5": s5_output,
        "parsed": parsed,
        "s2_attempts": s2_attempts,
        "s2_validator_errors": best_s2_errors,
        "s5_validator_errors": len(final_errors),
        "early_exit": early_exit,
        "calls_used": calls_used,
        "stage_times": stage_times,
        "stage_tokens": stage_tokens,
        "total_elapsed_sec": total_elapsed,
        "total_tokens": total_tokens,
        "token_savings_pct": round(token_savings, 1),
    }


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    seeds = [1001, 2002, 3003, 4004, 5005]
    sizes = [5, 7]
    checkpoint_path = os.path.join(
        _ROOT, "experiment_results", "marl_efficient_v2_glm.json",
    )

    if "GLM_API_KEY" not in os.environ:
        print("ERROR: GLM_API_KEY not set. Run: source ~/.claude/env/shared.env")
        sys.exit(1)

    model_name = os.environ.get("GLM_MODEL", "glm-4.7")
    print("=" * 65)
    print(f"  MARL Efficient v2 — Early Exit + Adaptive Budget + Timing")
    print(f"  Model: {model_name}")
    print(f"  5x5 budget: S1={get_budget(5)['s1']} S2={get_budget(5)['s2']} "
          f"S3={get_budget(5)['s3']} S4={get_budget(5)['s4']} S5={get_budget(5)['s5']}")
    print(f"  7x7 budget: S1={get_budget(7)['s1']} S2={get_budget(7)['s2']} "
          f"S3={get_budget(7)['s3']} S4={get_budget(7)['s4']} S5={get_budget(7)['s5']}")
    print(f"  Early exit: S2 PathValidator 0 errors → skip S3+S4")
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
        print(f"  Loaded {len(results)} existing trials from checkpoint")

    for seed in seeds:
        for size in sizes:
            if (seed, size) in completed:
                print(f"\n  [SKIP] seed={seed} size={size}")
                continue

            print(f"\n  [TRIAL] seed={seed} size={size}x{size}")
            maze = MazeEngine(size=size, seed=seed)
            print(f"    Solution length: {len(maze.solution or [])}, "
                  f"Dead ends: {maze.dead_ends}, Mirages: {len(maze.mirage_traps)}")

            try:
                result = run_marl_efficient_v2(maze, size)
                parsed = result["parsed"]

                trial = {
                    "seed": seed,
                    "size": size,
                    "method": "marl_efficient_v2",
                    "model": model_name,
                    "mei": parsed["mei"],
                    "sr": parsed["sr"],
                    "hrr": parsed["hrr"],
                    "hallucination_count": parsed["hallucinations"],
                    "backtrack_count": parsed["bt_count"],
                    "loop_count": parsed["loop_count"],
                    "brs": parsed["brs"],
                    "ce": parsed["ce"],
                    "hallumaze_score": parsed["hallumaze_score"],
                    "path_valid": parsed["path_valid"],
                    "s2_attempts": result["s2_attempts"],
                    "s2_validator_errors": result["s2_validator_errors"],
                    "s5_validator_errors": result["s5_validator_errors"],
                    "early_exit": result["early_exit"],
                    "calls_used": result["calls_used"],
                    "stage_times": result["stage_times"],
                    "stage_tokens": result["stage_tokens"],
                    "total_elapsed_sec": result["total_elapsed_sec"],
                    "total_tokens": result["total_tokens"],
                    "token_savings_pct": result["token_savings_pct"],
                    "timestamp": datetime.now().isoformat(),
                }
                results.append(trial)
                completed.add((seed, size))

                print(f"    => MEI={parsed['mei']:.4f} | SR={parsed['sr']:.1f} | "
                      f"HRR={parsed['hrr']:.4f} | calls={result['calls_used']} | "
                      f"elapsed={result['total_elapsed_sec']}s | "
                      f"early_exit={result['early_exit']} | "
                      f"token_savings={result['token_savings_pct']:.1f}%")

                _save_checkpoint(checkpoint_path, results, model_name)
                print(f"    Checkpoint saved ({len(results)} trials)")
                time.sleep(1)

            except Exception as e:
                print(f"    ERROR: {e}")
                import traceback
                traceback.print_exc()
                continue

    # ── Final Analysis ──
    print("\n" + "=" * 65)
    print(f"  MARL Efficient v2 — Final Summary ({model_name})")
    print("=" * 65)

    if not results:
        print("  No results.")
        return

    n = len(results)
    mei_vals = [r["mei"] for r in results]
    hrr_vals = [r["hrr"] for r in results]
    sr_vals = [r["sr"] for r in results]
    calls_vals = [r["calls_used"] for r in results]
    time_vals = [r["total_elapsed_sec"] for r in results]
    token_savings_vals = [r["token_savings_pct"] for r in results]
    early_exits = sum(1 for r in results if r["early_exit"])

    mean_mei = sum(mei_vals) / n
    mean_hrr = sum(hrr_vals) / n
    mean_sr = sum(sr_vals) / n
    mean_calls = sum(calls_vals) / n
    mean_time = sum(time_vals) / n
    mean_token_savings = sum(token_savings_vals) / n

    baseline_mei = 0.615
    v2_mei = 0.803
    v1_mei = 0.697

    print(f"\n  Trials: {n} | Early exits: {early_exits}/{n} ({early_exits/n*100:.0f}%)")
    print(f"\n  {'Metric':<25} {'Eff v2':>10} {'Eff v1':>10} {'v2 5-stage':>12} {'Baseline':>10}")
    print(f"  {'-'*70}")
    print(f"  {'MEI':.<25} {mean_mei:>10.4f} {'0.6972':>10} {v2_mei:>12.4f} {baseline_mei:>10.4f}")
    print(f"  {'HRR':.<25} {mean_hrr:>10.4f} {'0.8917':>10} {'~0.718':>12} {'0.718':>10}")
    print(f"  {'Solve Rate':.<25} {mean_sr:>10.4f} {'0.200':>10} {'n/a':>12} {'0.083':>10}")
    print(f"  {'Avg Calls/Trial':.<25} {mean_calls:>10.2f} {'5.0':>10} {'5.0+':>12} {'1.0':>10}")
    print(f"  {'Avg Time/Trial (s)':.<25} {mean_time:>10.1f} {'N/A':>10} {'N/A':>12} {'N/A':>10}")
    print(f"  {'Avg Token Savings':.<25} {mean_token_savings:>9.1f}% {'68.2%':>10} {'0%':>12} {'N/A':>10}")

    print(f"\n  Per-trial MEI:   {[round(m, 4) for m in mei_vals]}")
    print(f"  Per-trial calls: {calls_vals}")
    print(f"  Per-trial time:  {[round(t, 1) for t in time_vals]}s")

    if mean_mei >= v2_mei * 0.97:
        print(f"\n  >>> QUALITY MAINTAINED: MEI={mean_mei:.4f} within 3% of v2={v2_mei}")
    else:
        print(f"\n  >>> vs v2: {mean_mei - v2_mei:+.4f} ({(mean_mei/v2_mei-1)*100:+.1f}%)")

    print(f"  >>> vs Eff v1: {mean_mei - v1_mei:+.4f} ({(mean_mei/v1_mei-1)*100:+.1f}%)")
    print(f"  >>> vs baseline: {mean_mei - baseline_mei:+.4f} ({(mean_mei/baseline_mei-1)*100:+.1f}%)")

    _save_checkpoint(checkpoint_path, results, model_name, summary={
        "method": "marl_efficient_v2",
        "innovations": ["s2_early_exit", "size_adaptive_budget", "time_tracking"],
        "model": model_name,
        "n_trials": n,
        "early_exit_rate": early_exits / n,
        "mean_mei": round(mean_mei, 4),
        "mean_hrr": round(mean_hrr, 4),
        "mean_sr": round(mean_sr, 4),
        "mean_calls_per_trial": round(mean_calls, 2),
        "mean_elapsed_sec": round(mean_time, 1),
        "mean_token_savings_pct": round(mean_token_savings, 1),
        "baseline_mei": baseline_mei,
        "v2_mei": v2_mei,
        "delta_vs_v2": round(mean_mei - v2_mei, 4),
        "delta_vs_eff_v1": round(mean_mei - v1_mei, 4),
    })
    print(f"\n  Results saved: {checkpoint_path}")


def _save_checkpoint(path: str, results: list, model_name: str, summary: dict = None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {
        "method": "marl_efficient_v2",
        "model": model_name,
        "timestamp": datetime.now().isoformat(),
        "trials": results,
    }
    if summary:
        data["summary"] = summary
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
