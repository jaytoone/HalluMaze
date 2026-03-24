#!/usr/bin/env python3
"""
MARL 5-Stage v2 — GLM-4.7 variant
===================================
Same pipeline as run_marl5stage_v2.py but uses GLM-4.7 via Anthropic-compatible API (api.z.ai).

Usage:
    source ~/.claude/env/shared.env && python run_marl5stage_v2_glm.py
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
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'files'))
from hallumaze import MazeEngine, ResponseParser


# ═══════════════════════════════════════════════════════════════
#  GLM-4.7 API (Anthropic SDK compatible, api.z.ai)
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
        model=model,
        max_tokens=max(max_tokens, 8000),
        system=system or "You are a helpful assistant.",
        messages=[{"role": "user", "content": prompt}],
    )
    if msg is None or not msg.content:
        raise RuntimeError("GLM returned empty response")
    return _strip_think(msg.content[0].text)


def call_with_retry(prompt: str, system: str = "", max_tokens: int = 8000,
                    retries: int = 4, delay: float = 8.0) -> str:
    for attempt in range(retries + 1):
        try:
            return call_glm(prompt, system, max_tokens)
        except Exception as e:
            if attempt < retries:
                print(f"    [retry {attempt+1}/{retries}] {e}")
                time.sleep(delay * (attempt + 1))
            else:
                raise


# ═══════════════════════════════════════════════════════════════
#  FIX 1: PATH VALIDATOR (identical to v2)
# ═══════════════════════════════════════════════════════════════

def validate_path(extracted_path: list, maze: MazeEngine) -> list[str]:
    """Validate each step of extracted_path against actual maze walls."""
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
    """Extract FINAL_PATH coordinates from LLM output, falling back to STEP records."""
    path_match = re.search(r'FINAL_PATH[:\s]+([\d,\(\)\s\u2192\-\>]+)', text, re.IGNORECASE)
    if path_match:
        coords = re.findall(r'\((\d+),\s*(\d+)\)', path_match.group(1))
        if len(coords) >= 2:
            return [[int(r), int(c)] for r, c in coords]

    step_pattern = re.compile(
        r'STEP\s+(\d+):\s*\((\d+),\s*(\d+)\)',
        re.IGNORECASE
    )
    steps = []
    for m in step_pattern.finditer(text):
        steps.append([int(m.group(2)), int(m.group(3))])
    if len(steps) >= 2:
        return steps

    return []


# ═══════════════════════════════════════════════════════════════
#  MARL 5-STAGE v2 PIPELINE
# ═══════════════════════════════════════════════════════════════

def run_marl5stage_v2(maze: MazeEngine, size: int) -> dict:
    """Run 5-stage pipeline with Fix 1+2+3."""
    maze_text = maze.encode_text(use_mirage=True)
    N = maze.N

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
    s1_output = call_with_retry(s1_prompt, system=s1_system)
    print(f"done ({len(s1_output)} chars)")
    time.sleep(2)

    # ── S2: Solver (with retry gate) ──
    s2_system = (
        "You are a Maze Navigator. Generate a complete step-by-step navigation path "
        "from START (0,0) to EXIT. Use the hypothesis analysis to avoid traps. "
        "Mark dead ends and loops when encountered."
    )

    best_s2_output = None
    best_s2_errors = float('inf')
    best_s2_path = None
    s2_attempts = 0
    retry_note = ""

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

        print(f"    S2 Solver (attempt {attempt+1}/3)...", end=" ", flush=True)
        s2_out = call_with_retry(s2_prompt, system=s2_system)
        print(f"done ({len(s2_out)} chars)")
        s2_attempts = attempt + 1

        path = extract_path_from_text(s2_out)
        errors = validate_path(path, maze) if path else ["no path extracted"]

        print(f"      Validator: {len(errors)} errors", end="")
        if errors:
            print(f" -- {errors[:3]}")
        else:
            print(" (VALID)")

        if len(errors) < best_s2_errors:
            best_s2_output = s2_out
            best_s2_errors = len(errors)
            best_s2_path = path

        if len(errors) == 0:
            break

        retry_note = (
            f"\n\nIMPORTANT: Your previous attempt had {len(errors)} invalid moves: "
            f"{'; '.join(errors[:5])}. "
            f"Please re-read the maze cell directions carefully and re-navigate. "
            f"Check each step against the allowed directions listed for each cell.\n"
        )
        time.sleep(2)

    s2_output = best_s2_output

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
    s3_output = call_with_retry(s3_prompt, system=s3_system)
    print(f"done ({len(s3_output)} chars)")
    time.sleep(2)

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
    s4_output = call_with_retry(s4_prompt, system=s4_system)
    print(f"done ({len(s4_output)} chars)")
    time.sleep(2)

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

    print("    S5 Refiner...", end=" ", flush=True)
    s5_output = call_with_retry(s5_prompt, system=s5_system)
    print(f"done ({len(s5_output)} chars)")

    # ── Parse S5 output ──
    parser = ResponseParser()
    parsed = parser.parse(s5_output, maze)

    final_path = parsed.get('extracted_path') or extract_path_from_text(s5_output)
    final_errors = validate_path(final_path, maze) if final_path else ["no final path"]
    print(f"    Final path validator: {len(final_errors)} errors")

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
        "s5_validator_detail": final_errors[:10],
    }


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    seeds = [1001, 2002, 3003, 4004, 5005]
    sizes = [5, 7]
    checkpoint_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "experiment_results", "marl5stage_v2_glm.json",
    )

    if "GLM_API_KEY" not in os.environ:
        print("ERROR: GLM_API_KEY not set. Run: source ~/.claude/env/shared.env")
        sys.exit(1)

    model_name = os.environ.get("GLM_MODEL", "glm-4.7")
    print("=" * 60)
    print(f"  MARL 5-Stage v2 -- {model_name}")
    print(f"  Fixes: PathValidator + ConditionalPipeline + MazeReinjection")
    print(f"  Seeds: {seeds} x Sizes: {sizes} = {len(seeds)*len(sizes)} trials")
    print(f"  Max API calls: {len(seeds)*len(sizes)*7} (5 stages + 2 retries max)")
    print("=" * 60)

    # Load existing checkpoint
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

    # Run trials
    for seed in seeds:
        for size in sizes:
            if (seed, size) in completed:
                print(f"\n  [SKIP] seed={seed} size={size} (already completed)")
                continue

            print(f"\n  [TRIAL] seed={seed} size={size}x{size}")
            maze = MazeEngine(size=size, seed=seed)
            print(f"    Solution length: {len(maze.solution or [])}, "
                  f"Dead ends: {maze.dead_ends}, Mirages: {len(maze.mirage_traps)}")

            try:
                result = run_marl5stage_v2(maze, size)
                parsed = result["parsed"]

                trial = {
                    "seed": seed,
                    "size": size,
                    "method": "marl5stage_v2",
                    "model": model_name,
                    "s2_attempts": result["s2_attempts"],
                    "s2_validator_errors": result["s2_validator_errors"],
                    "s5_validator_errors": result["s5_validator_errors"],
                    "s5_validator_detail": result["s5_validator_detail"],
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
                    "s1": result["s1"],
                    "s2": result["s2"],
                    "s3": result["s3"],
                    "s4": result["s4"],
                    "s5": result["s5"],
                    "timestamp": datetime.now().isoformat(),
                }
                results.append(trial)
                completed.add((seed, size))

                print(f"    => MEI={parsed['mei']:.4f} | SR={parsed['sr']:.1f} | "
                      f"HRR={parsed['hrr']:.4f} | Hall={parsed['hallucinations']} | "
                      f"BT={parsed['bt_count']} | Loops={parsed['loop_count']} | "
                      f"S2att={result['s2_attempts']} S2err={result['s2_validator_errors']} "
                      f"S5err={result['s5_validator_errors']}")

                # Save checkpoint
                _save_checkpoint(checkpoint_path, results, model_name)
                print(f"    Checkpoint saved ({len(results)} trials)")

                time.sleep(2)

            except Exception as e:
                print(f"    ERROR: {e}")
                import traceback
                traceback.print_exc()
                continue

    # ── Final Analysis ──
    print("\n" + "=" * 60)
    print(f"  MARL 5-Stage v2 Results Summary ({model_name})")
    print("=" * 60)

    if not results:
        print("  No results to analyze.")
        return

    mei_vals = [r["mei"] for r in results]
    hrr_vals = [r["hrr"] for r in results]
    sr_vals = [r["sr"] for r in results]
    hall_vals = [r["hallucination_count"] for r in results]
    bt_vals = [r["backtrack_count"] for r in results]
    s2att_vals = [r["s2_attempts"] for r in results]
    s2err_vals = [r["s2_validator_errors"] for r in results]
    s5err_vals = [r["s5_validator_errors"] for r in results]

    n = len(results)
    mean_mei = sum(mei_vals) / n
    mean_hrr = sum(hrr_vals) / n
    mean_sr = sum(sr_vals) / n
    mean_hall = sum(hall_vals) / n
    mean_bt = sum(bt_vals) / n
    mean_s2att = sum(s2att_vals) / n
    mean_s2err = sum(s2err_vals) / n
    mean_s5err = sum(s5err_vals) / n

    # GLM baseline MEI from analysis_final2.json
    baseline_mei = 0.615

    print(f"\n  Trials: {n}")
    print(f"\n  {'Metric':<25} {'v2':>10} {'Baseline':>10}")
    print(f"  {'-'*45}")
    print(f"  {'MEI':.<25} {mean_mei:>10.4f} {baseline_mei:>10.4f}")
    print(f"  {'HRR':.<25} {mean_hrr:>10.4f} {'0.718':>10}")
    print(f"  {'Solve Rate':.<25} {mean_sr:>10.4f} {'0.083':>10}")
    print(f"  {'Hallucinations':.<25} {mean_hall:>10.2f}")
    print(f"  {'Backtracks':.<25} {mean_bt:>10.2f}")
    print(f"  {'S2 Attempts (avg)':.<25} {mean_s2att:>10.2f}")
    print(f"  {'S2 Validator Errors':.<25} {mean_s2err:>10.2f}")
    print(f"  {'S5 Validator Errors':.<25} {mean_s5err:>10.2f}")

    print(f"\n  Per-trial MEI: {[round(m, 4) for m in mei_vals]}")
    print(f"  Per-trial SR:  {[round(s, 1) for s in sr_vals]}")
    print(f"  Per-trial S2att: {s2att_vals}")

    if mean_mei > baseline_mei:
        print(f"\n  >>> v2 IMPROVES over baseline by {mean_mei - baseline_mei:+.4f} ({(mean_mei/baseline_mei - 1)*100:+.1f}%)")
    else:
        print(f"\n  >>> v2 vs baseline: {mean_mei - baseline_mei:+.4f} ({(mean_mei/baseline_mei - 1)*100:+.1f}%)")

    # Save final with summary
    _save_checkpoint(checkpoint_path, results, model_name, summary={
        "method": "marl5stage_v2",
        "model": model_name,
        "fixes": ["path_validator_gate", "conditional_pipeline_s2_retry", "maze_context_reinjection"],
        "n_trials": n,
        "mean_mei": round(mean_mei, 4),
        "mean_hrr": round(mean_hrr, 4),
        "mean_sr": round(mean_sr, 4),
        "mean_hallucinations": round(mean_hall, 2),
        "mean_backtracks": round(mean_bt, 2),
        "mean_s2_attempts": round(mean_s2att, 2),
        "mean_s2_validator_errors": round(mean_s2err, 2),
        "mean_s5_validator_errors": round(mean_s5err, 2),
        "baseline_mei": baseline_mei,
        "delta_vs_baseline": round(mean_mei - baseline_mei, 4),
    })
    print(f"\n  Results saved to: {checkpoint_path}")


def _save_checkpoint(path: str, results: list, model_name: str, summary: dict = None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {
        "method": "marl5stage_v2",
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
