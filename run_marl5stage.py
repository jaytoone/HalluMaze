#!/usr/bin/env python3
"""
MARL 5-Stage Maze Solver — HalluMaze Benchmark
================================================
One LLM performs 5 sequential roles per maze trial:
  S1 Hypothesis: Identify potential mirages/traps
  S2 Solver: Generate full navigation path
  S3 Auditor: Audit path for errors
  S4 Verifier: Apply structured corrections
  S5 Refiner: Output final clean path

Usage:
    python run_marl5stage.py
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
from hallumaze import MazeEngine, ResponseParser, PromptBuilder


# ═══════════════════════════════════════════════════════════════
#  MiniMax API
# ═══════════════════════════════════════════════════════════════

def _strip_think(text: str) -> str:
    stripped = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    return stripped if stripped else text


def call_minimax(prompt: str, system: str = "", max_tokens: int = 8000) -> str:
    import openai
    client = openai.OpenAI(
        api_key=os.environ["MINIMAX_API_KEY"],
        base_url=os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.io/v1"),
    )
    resp = client.chat.completions.create(
        model=os.environ.get("MINIMAX_MODEL", "MiniMax-M2.5"),
        max_tokens=max(max_tokens, 8000),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    if resp is None or resp.choices is None or len(resp.choices) == 0:
        raise RuntimeError("MiniMax returned empty response")
    msg = resp.choices[0].message
    if msg is None or msg.content is None:
        raise RuntimeError("MiniMax returned None content")
    return _strip_think(msg.content)


def call_with_retry(prompt: str, system: str = "", max_tokens: int = 8000,
                    retries: int = 4, delay: float = 8.0) -> str:
    for attempt in range(retries + 1):
        try:
            return call_minimax(prompt, system, max_tokens)
        except Exception as e:
            if attempt < retries:
                print(f"    [retry {attempt+1}/{retries}] {e}")
                time.sleep(delay * (attempt + 1))  # exponential backoff
            else:
                raise


# ═══════════════════════════════════════════════════════════════
#  MARL 5-STAGE PIPELINE
# ═══════════════════════════════════════════════════════════════

def run_marl5stage(maze: MazeEngine, size: int) -> dict:
    """Run 5-stage pipeline on a single maze. Returns dict with all stage outputs + parsed metrics."""
    maze_text = maze.encode_text(use_mirage=True)
    N = maze.N

    # ── S1: Hypothesis — identify mirages and risk zones ──
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

    # ── S2: Solver — generate path using S1 analysis ──
    s2_system = (
        "You are a Maze Navigator. Generate a complete step-by-step navigation path "
        "from START (0,0) to EXIT. Use the hypothesis analysis to avoid traps. "
        "Mark dead ends and loops when encountered."
    )
    s2_prompt = f"""MAZE:
{maze_text}

HYPOTHESIS ANALYSIS (from threat assessment):
{s1_output}

Navigate from (0,0) to ({N-1},{N-1}).

Rules:
- Format each step: STEP N: (r,c) -> [direction] | confidence: XX% | [reason]
- When hitting a dead end: DEAD_END at (r,c) — backtracking
- When detecting a loop: LOOP detected at (r,c) — visited at step M
- When changing strategy: STRATEGY_CHANGE — [reason]

End with:
BACKTRACK_COUNT: N
HALLUCINATION_COUNT: N
CONFIDENCE_LOG: step1:conf1, step2:conf2, ...
FINAL_PATH: (0,0)->...->({N-1},{N-1})"""

    print("    S2 Solver...", end=" ", flush=True)
    s2_output = call_with_retry(s2_prompt, system=s2_system)
    print(f"done ({len(s2_output)} chars)")
    time.sleep(2)

    # ── S3: Auditor — review path for errors ──
    s3_system = (
        "You are a Path Auditor. Your job is to find every error in the navigation path. "
        "Check each move against the maze structure. Be thorough and precise."
    )
    s3_prompt = f"""MAZE:
{maze_text}

GENERATED PATH:
{s2_output}

Audit this path thoroughly:
1. INVALID MOVES: Check each step — is the direction actually open in the maze? List step numbers with errors.
2. UNDETECTED LOOPS: Cells visited more than once without LOOP_DETECTED marker.
3. MISSED BACKTRACKS: Places where the solver should have backtracked but didn't.
4. PATH CONTINUITY: Does each step follow from the previous position?
5. GOAL REACHED: Does the path actually reach ({N-1},{N-1})?

For each error found, specify:
- ERROR at STEP N: (r,c) -> [direction] — [what's wrong] — FIX: [correction]"""

    print("    S3 Auditor...", end=" ", flush=True)
    s3_output = call_with_retry(s3_prompt, system=s3_system)
    print(f"done ({len(s3_output)} chars)")
    time.sleep(2)

    # ── S4: Verifier — apply corrections ──
    s4_system = (
        "You are a Path Corrector. Apply all audit corrections to produce a valid path. "
        "Re-verify each step against the maze. Output a corrected step-by-step path."
    )
    s4_prompt = f"""MAZE:
{maze_text}

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
DEAD_END at (r,c) — backtracking
LOOP detected at (r,c) — visited at step M

End with:
BACKTRACK_COUNT: N
HALLUCINATION_COUNT: N
CONFIDENCE_LOG: step1:conf1, step2:conf2, ...
FINAL_PATH: (0,0)->...->({N-1},{N-1})"""

    print("    S4 Verifier...", end=" ", flush=True)
    s4_output = call_with_retry(s4_prompt, system=s4_system)
    print(f"done ({len(s4_output)} chars)")
    time.sleep(2)

    # ── S5: Refiner — final clean output ──
    s5_system = (
        "You are a Path Refiner. Output the final clean navigation path in exact benchmark format. "
        "Verify every single step against the maze one last time."
    )
    s5_prompt = f"""MAZE:
{maze_text}

CORRECTED PATH:
{s4_output}

Output the FINAL path in EXACT benchmark format. Verify each step against the maze.

Format:
STEP N: (r,c) -> [direction] | confidence: XX% | [reason]
DEAD_END at (r,c) — backtracking
LOOP detected at (r,c) — visited at step M
STRATEGY_CHANGE — [reason]

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

    return {
        "s1": s1_output,
        "s2": s2_output,
        "s3": s3_output,
        "s4": s4_output,
        "s5": s5_output,
        "parsed": parsed,
    }


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    seeds = [1001, 2002, 3003, 4004, 5005]
    sizes = [5, 7]
    checkpoint_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "experiment_results", "marl5stage_minimax.json",
    )

    # Check for API key
    if "MINIMAX_API_KEY" not in os.environ:
        print("ERROR: MINIMAX_API_KEY not set. Run: source ~/.claude/env/shared.env")
        sys.exit(1)

    model_name = os.environ.get("MINIMAX_MODEL", "MiniMax-M2.5")
    print("=" * 60)
    print(f"  MARL 5-Stage Maze Solver — {model_name}")
    print(f"  Seeds: {seeds} x Sizes: {sizes} = {len(seeds)*len(sizes)} trials")
    print(f"  API calls: {len(seeds)*len(sizes)*5} total (5 stages each)")
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
                result = run_marl5stage(maze, size)
                parsed = result["parsed"]

                trial = {
                    "seed": seed,
                    "size": size,
                    "method": "marl5stage",
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
                      f"BT={parsed['bt_count']} | Loops={parsed['loop_count']}")

                # Save checkpoint
                _save_checkpoint(checkpoint_path, results)
                print(f"    Checkpoint saved ({len(results)} trials)")

                time.sleep(2)

            except Exception as e:
                print(f"    ERROR: {e}")
                continue

    # ── Final Analysis ──
    print("\n" + "=" * 60)
    print("  MARL 5-Stage Results Summary")
    print("=" * 60)

    if not results:
        print("  No results to analyze.")
        return

    mei_vals = [r["mei"] for r in results]
    hrr_vals = [r["hrr"] for r in results]
    sr_vals = [r["sr"] for r in results]
    hall_vals = [r["hallucination_count"] for r in results]
    bt_vals = [r["backtrack_count"] for r in results]

    n = len(results)
    mean_mei = sum(mei_vals) / n
    mean_hrr = sum(hrr_vals) / n
    mean_sr = sum(sr_vals) / n
    mean_hall = sum(hall_vals) / n
    mean_bt = sum(bt_vals) / n

    baseline_mei = 0.593

    print(f"\n  Trials: {n}")
    print(f"  {'Metric':<20} {'MARL 5-Stage':>14} {'Baseline':>14} {'Delta':>10}")
    print(f"  {'-'*58}")
    print(f"  {'MEI':.<20} {mean_mei:>14.4f} {baseline_mei:>14.4f} {mean_mei - baseline_mei:>+10.4f}")
    print(f"  {'HRR':.<20} {mean_hrr:>14.4f} {'0.600':>14} {''}")
    print(f"  {'Solve Rate':.<20} {mean_sr:>14.4f} {'0.533':>14} {''}")
    print(f"  {'Hallucinations':.<20} {mean_hall:>14.2f} {''}")
    print(f"  {'Backtracks':.<20} {mean_bt:>14.2f} {''}")

    print(f"\n  Per-trial MEI: {[round(m, 4) for m in mei_vals]}")

    if mean_mei > baseline_mei:
        print(f"\n  >>> MARL 5-Stage IMPROVES MEI by {mean_mei - baseline_mei:+.4f} ({(mean_mei/baseline_mei - 1)*100:+.1f}%)")
    else:
        print(f"\n  >>> MARL 5-Stage DEGRADES MEI by {mean_mei - baseline_mei:+.4f} ({(mean_mei/baseline_mei - 1)*100:+.1f}%)")

    # Save final with summary
    _save_checkpoint(checkpoint_path, results, summary={
        "method": "marl5stage",
        "model": model_name,
        "n_trials": n,
        "mean_mei": round(mean_mei, 4),
        "mean_hrr": round(mean_hrr, 4),
        "mean_sr": round(mean_sr, 4),
        "mean_hallucinations": round(mean_hall, 2),
        "mean_backtracks": round(mean_bt, 2),
        "baseline_mei": baseline_mei,
        "delta_mei": round(mean_mei - baseline_mei, 4),
    })
    print(f"\n  Results saved to: {checkpoint_path}")


def _save_checkpoint(path: str, results: list, summary: dict = None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {
        "method": "marl5stage",
        "model": os.environ.get("MINIMAX_MODEL", "MiniMax-M2.5"),
        "timestamp": datetime.now().isoformat(),
        "trials": results,
    }
    if summary:
        data["summary"] = summary
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
