#!/usr/bin/env python3
"""
MARL 5-Stage Efficient v1 — Adaptive Token Budgeting (Phase 1)
==============================================================
Phase 1 implementation: S2+S5 adaptive token budgeting based on S1 mirage flag.

Key change vs v2:
  - call_glm no longer enforces min(max_tokens, 8000) floor
  - After S1, detect mirage complexity (mirage walls found or not)
  - Simple maze (no mirage found): S2=1500 tokens, S5=800 tokens
  - Complex maze (mirage walls found): S2=3000 tokens, S5=1500 tokens
  - S1/S3/S4 unchanged (analysis stages need full context)

Expected: 40-55% token reduction with minimal MEI impact.

Usage:
    source ~/.claude/env/shared.env && python scripts/run_marl_efficient_glm.py
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
#  GLM-4.7 API — token budget enabled (no 8000-floor)
# ═══════════════════════════════════════════════════════════════

def _strip_think(text: str) -> str:
    stripped = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    return stripped if stripped else text


def call_glm(prompt: str, system: str = "", max_tokens: int = 4000) -> str:
    """Call GLM-4.7. max_tokens is respected without a minimum floor."""
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


def call_with_retry(prompt: str, system: str = "", max_tokens: int = 4000,
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
#  PATH VALIDATOR (identical to v2)
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
#  PHASE 1: S1 MIRAGE COMPLEXITY DETECTOR
# ═══════════════════════════════════════════════════════════════

# Token budget configs
BUDGET = {
    "simple": {"s2": 1500, "s5": 800},   # no mirage suspects found
    "complex": {"s2": 3000, "s5": 1500},  # mirage walls identified
}
# S1/S3/S4 always need full analysis context
FIXED_TOKENS = {"s1": 4000, "s3": 3000, "s4": 3000}


def detect_mirage_complexity(s1_output: str) -> str:
    """
    Detect if S1 found suspicious/mirage walls.
    Returns 'complex' if mirage walls identified, 'simple' otherwise.

    Uses S1 objective state features (not S2 self-confidence):
    - Presence of specific mirage wall candidates
    - Number of suspicious wall mentions
    """
    # Indicators of mirage detection (S1 found actual suspects)
    mirage_indicators = [
        r'suspicious wall',
        r'mirage wall',
        r'flagged',
        r'traversable.*despite',
        r'appears blocked.*might',
        r'might be traversable',
        r'SUSPICIOUS.*\(\d+,\s*\d+\)',   # coordinates in suspicious walls section
        r'flag symbol',
    ]

    output_lower = s1_output.lower()
    hits = sum(
        1 for pattern in mirage_indicators
        if re.search(pattern, output_lower)
    )

    # Also check: does S1 list actual cell coordinates as suspicious?
    coord_in_suspicious = re.search(
        r'suspicious.{0,200}\(\d+,\s*\d+\)',
        s1_output,
        re.IGNORECASE | re.DOTALL
    )

    if hits >= 2 or coord_in_suspicious:
        return "complex"
    return "simple"


# ═══════════════════════════════════════════════════════════════
#  MARL EFFICIENT PIPELINE
# ═══════════════════════════════════════════════════════════════

def run_marl_efficient(maze: MazeEngine, size: int) -> dict:
    """Run 5-stage pipeline with Phase 1 adaptive token budgeting."""
    maze_text = maze.encode_text(use_mirage=True)
    N = maze.N
    token_log = {}

    # ── S1: Hypothesis (full budget — analysis stage) ──
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
    s1_output = call_with_retry(s1_prompt, system=s1_system, max_tokens=FIXED_TOKENS["s1"])
    token_log["s1"] = FIXED_TOKENS["s1"]
    print(f"done ({len(s1_output)} chars)")
    time.sleep(2)

    # ── PHASE 1 GATE: Detect complexity from S1 objective state ──
    complexity = detect_mirage_complexity(s1_output)
    s2_budget = BUDGET[complexity]["s2"]
    s5_budget = BUDGET[complexity]["s5"]
    print(f"    [GATE] complexity={complexity} -> S2={s2_budget} tokens, S5={s5_budget} tokens")

    # ── S2: Solver (adaptive token budget) ──
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

        print(f"    S2 Solver (attempt {attempt+1}/3, budget={s2_budget})...", end=" ", flush=True)
        s2_out = call_with_retry(s2_prompt, system=s2_system, max_tokens=s2_budget)
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
    token_log["s2"] = s2_budget * s2_attempts

    # ── S3: Auditor (full budget — audit stage) ──
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
    s3_output = call_with_retry(s3_prompt, system=s3_system, max_tokens=FIXED_TOKENS["s3"])
    token_log["s3"] = FIXED_TOKENS["s3"]
    print(f"done ({len(s3_output)} chars)")
    time.sleep(2)

    # ── S4: Verifier (full budget — correction stage) ──
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
    s4_output = call_with_retry(s4_prompt, system=s4_system, max_tokens=FIXED_TOKENS["s4"])
    token_log["s4"] = FIXED_TOKENS["s4"]
    print(f"done ({len(s4_output)} chars)")
    time.sleep(2)

    # ── S5: Refiner (adaptive token budget) ──
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

    print(f"    S5 Refiner (budget={s5_budget})...", end=" ", flush=True)
    s5_output = call_with_retry(s5_prompt, system=s5_system, max_tokens=s5_budget)
    token_log["s5"] = s5_budget
    print(f"done ({len(s5_output)} chars)")

    # ── Parse S5 output ──
    parser = ResponseParser()
    parsed = parser.parse(s5_output, maze)

    final_path = parsed.get('extracted_path') or extract_path_from_text(s5_output)
    final_errors = validate_path(final_path, maze) if final_path else ["no final path"]
    print(f"    Final path validator: {len(final_errors)} errors")

    # ── Token efficiency stats ──
    total_budgeted = sum(token_log.values())
    v2_baseline_tokens = 8000 * (3 + s2_attempts + 2)  # S1+S2(retries)+S3+S4+S5 at 8000 each
    token_savings_pct = (1 - total_budgeted / v2_baseline_tokens) * 100 if v2_baseline_tokens > 0 else 0

    print(f"    Token budget: {token_log} | total={total_budgeted} | "
          f"vs v2 baseline={v2_baseline_tokens} | savings={token_savings_pct:.1f}%")

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
        "complexity": complexity,
        "token_log": token_log,
        "total_tokens_budgeted": total_budgeted,
        "v2_baseline_tokens": v2_baseline_tokens,
        "token_savings_pct": round(token_savings_pct, 1),
    }


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    seeds = [1001, 2002, 3003, 4004, 5005]
    sizes = [5, 7]
    checkpoint_path = os.path.join(
        _ROOT, "experiment_results", "marl_efficient_glm.json",
    )

    if "GLM_API_KEY" not in os.environ:
        print("ERROR: GLM_API_KEY not set. Run: source ~/.claude/env/shared.env")
        sys.exit(1)

    model_name = os.environ.get("GLM_MODEL", "glm-4.7")
    print("=" * 60)
    print(f"  MARL Efficient v1 (Phase 1 Token Budgeting) -- {model_name}")
    print(f"  Method: Adaptive S2/S5 token budget via S1 mirage gate")
    print(f"  Simple: S2={BUDGET['simple']['s2']}, S5={BUDGET['simple']['s5']} tokens")
    print(f"  Complex: S2={BUDGET['complex']['s2']}, S5={BUDGET['complex']['s5']} tokens")
    print(f"  Seeds: {seeds} x Sizes: {sizes} = {len(seeds)*len(sizes)} trials")
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
                result = run_marl_efficient(maze, size)
                parsed = result["parsed"]

                trial = {
                    "seed": seed,
                    "size": size,
                    "method": "marl_efficient_v1",
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
                    "complexity": result["complexity"],
                    "token_log": result["token_log"],
                    "total_tokens_budgeted": result["total_tokens_budgeted"],
                    "token_savings_pct": result["token_savings_pct"],
                    "timestamp": datetime.now().isoformat(),
                }
                results.append(trial)
                completed.add((seed, size))

                print(f"    => MEI={parsed['mei']:.4f} | SR={parsed['sr']:.1f} | "
                      f"HRR={parsed['hrr']:.4f} | complexity={result['complexity']} | "
                      f"token_savings={result['token_savings_pct']:.1f}%")

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
    print(f"  MARL Efficient v1 Results Summary ({model_name})")
    print("=" * 60)

    if not results:
        print("  No results to analyze.")
        return

    mei_vals = [r["mei"] for r in results]
    hrr_vals = [r["hrr"] for r in results]
    sr_vals = [r["sr"] for r in results]
    savings_vals = [r["token_savings_pct"] for r in results]
    complexity_counts = {"simple": 0, "complex": 0}
    for r in results:
        complexity_counts[r.get("complexity", "complex")] += 1

    n = len(results)
    mean_mei = sum(mei_vals) / n
    mean_hrr = sum(hrr_vals) / n
    mean_sr = sum(sr_vals) / n
    mean_savings = sum(savings_vals) / n

    # Baselines from v2 experiment
    baseline_mei = 0.615    # GLM-4.7 single-call
    v2_mei = 0.803          # MARL v2

    print(f"\n  Trials: {n}")
    print(f"  Complexity: simple={complexity_counts['simple']}, "
          f"complex={complexity_counts['complex']}")
    print(f"\n  {'Metric':<25} {'Efficient v1':>14} {'v2 (5-stage)':>14} {'Baseline':>10}")
    print(f"  {'-'*65}")
    print(f"  {'MEI':.<25} {mean_mei:>14.4f} {v2_mei:>14.4f} {baseline_mei:>10.4f}")
    print(f"  {'HRR':.<25} {mean_hrr:>14.4f} {'0.803 (v2)':>14} {'0.718':>10}")
    print(f"  {'Solve Rate':.<25} {mean_sr:>14.4f} {'n/a':>14} {'0.083':>10}")
    print(f"  {'Avg Token Savings':.<25} {mean_savings:>13.1f}% {'0%':>14} {'N/A':>10}")

    print(f"\n  Per-trial MEI: {[round(m, 4) for m in mei_vals]}")
    print(f"  Per-trial savings: {[round(s, 1) for s in savings_vals]}%")

    if mean_mei >= v2_mei * 0.97:
        print(f"\n  >>> Efficient v1 MAINTAINS v2 quality "
              f"(MEI={mean_mei:.4f} vs v2={v2_mei:.4f}, {(mean_mei/v2_mei-1)*100:+.1f}%)")
    else:
        print(f"\n  >>> Efficient v1 vs v2: {mean_mei - v2_mei:+.4f} "
              f"({(mean_mei/v2_mei - 1)*100:+.1f}%)")

    print(f"  >>> Efficient v1 vs baseline: {mean_mei - baseline_mei:+.4f} "
          f"({(mean_mei/baseline_mei - 1)*100:+.1f}%)")

    _save_checkpoint(checkpoint_path, results, model_name, summary={
        "method": "marl_efficient_v1",
        "phase": "Phase 1 — Adaptive Token Budgeting",
        "model": model_name,
        "n_trials": n,
        "mean_mei": round(mean_mei, 4),
        "mean_hrr": round(mean_hrr, 4),
        "mean_sr": round(mean_sr, 4),
        "mean_token_savings_pct": round(mean_savings, 1),
        "complexity_counts": complexity_counts,
        "baseline_mei": baseline_mei,
        "v2_mei": v2_mei,
        "delta_vs_baseline": round(mean_mei - baseline_mei, 4),
        "delta_vs_v2": round(mean_mei - v2_mei, 4),
        "budget_config": BUDGET,
        "fixed_tokens": FIXED_TOKENS,
    })
    print(f"\n  Results saved to: {checkpoint_path}")


def _save_checkpoint(path: str, results: list, model_name: str, summary: dict = None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {
        "method": "marl_efficient_v1",
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
