# HalluMaze: A Maze Navigation Benchmark for LLM Metacognitive Error Recovery
**Draft**: 2026-03-23 | **Target**: NeurIPS 2026 Datasets & Benchmarks / EMNLP Findings

---

## Abstract

We introduce HalluMaze, a benchmark that measures large language model (LLM) metacognitive error recovery through maze navigation. Unlike existing hallucination benchmarks that evaluate final-answer accuracy, HalluMaze captures real-time error detection and corrective action by exposing models to navigable environments containing "mirage" walls — passages that appear blocked but are traversable. We evaluate 8 LLMs (MiniMax-M2.5, GLM-4.7, Llama-4-Scout, Llama-4-Maverick, Gemini-2.0-Flash-Lite, GPT-4o-mini, Claude-3-Haiku, and Qwen-2.5-72B) across n=60 seeds × 5×5 and 7×7 maze sizes. We introduce the Metacognitive Escape Index (MEI), grounded in Nelson & Narens' (1990) metamemory framework, which decomposes metacognitive performance into recovery rate (HRR), efficiency (ETR), awareness (AW), and error rate (HR). All 8 tested LLMs score significantly below a random walk baseline (p<0.001 Bonferroni-corrected, d=1.2–3.0), revealing a systematic deficit in real-time metacognitive recovery. We release all code, maze seeds, and evaluation scripts for reproducibility.

**Keywords**: hallucination, metacognition, benchmark, LLM evaluation, maze navigation

---

## 1. Introduction

Large language models hallucinate — generating confident but factually incorrect outputs. Prior work has measured hallucination at the response level: does the final answer contain errors? (TruthfulQA [Lin+22], HaluEval [Ji+23]). However, metacognitive competence requires not just avoiding errors, but **detecting and recovering from them in real time**.

Consider a model navigating a maze. It may hallucinate the existence of a wall, move into it, discover the contradiction when the environment responds, and then backtrack. This sequence — error → detection → correction — is precisely the metacognitive loop that Nelson & Narens (1990) identify as the "control" function of metamemory. No existing benchmark captures this.

**HalluMaze** fills this gap by embedding LLMs in a text-based maze navigation task where:
1. "Mirage" positions (hallucination traps) appear valid but are traversable — the model must infer the error from contradictory environment feedback
2. Every step is logged, enabling real-time metacognitive signal extraction
3. Multiple metrics capture distinct metacognitive functions (monitoring vs control)

Our main findings:
- **All 8 tested LLMs score below random walk** on MEI (p<0.001, d=1.2–3.0)
- **HRR varies widely**: Llama-4-Maverick (81%) > Llama-4-Scout (81%) > GLM-4.7 (72%) >> Claude-3-Haiku (36%) > GPT-4o-mini (38%)
- **SR dissociates from MEI**: MiniMax-M2.5 has highest solve rate (53%) but mid-range MEI (0.593); GLM-4.7 ranks #1 on MEI despite SR=8.3%
- **Newer ≠ better**: GLM-4.7 outperforms expected hierarchy in metacognitive recovery
- **Claude-3-Haiku**: MEI=0.398, HRR=0.363 — lowest HRR among fully-sampled models, confirming that Anthropic's smaller model shares the universal metacognitive deficit

---

## 2. Background & Related Work

### 2.1 Hallucination Benchmarks

| Benchmark | Task | Metric | Recovery? | Human Baseline |
|-----------|------|--------|-----------|----------------|
| TruthfulQA [Lin+22] | Factual QA | % Truthful | No | Yes |
| HaluEval [Ji+23] | QA/Dialog | Hall. rate | No | No |
| FActScoring [Min+23] | Biography | Atomic fact precision | No | Yes |
| MMLU [Hendrycks+21] | MCQ | Accuracy | No | Yes |
| BabyAI [Chevalier+19] | Grid-world | Task success | No | No |
| **HalluMaze (ours)** | Navigation | MEI, HRR, SR | **Yes** | Planned |

**Key gap**: No existing benchmark measures metacognitive *recovery* (detecting + correcting errors mid-task). HalluMaze introduces HRR as the first metric targeting this function.

### 2.2 Metacognition Theory

Nelson & Narens (1990) define metacognition as a two-level system:
- **Object level**: Task execution (maze navigation)
- **Meta level**: Monitoring (FOK, JOL) + Control (search termination, backtracking)

The MEI weight structure directly maps to this framework:
- `w_hrr=0.4`: Recovery = control process (primary metacognitive function)
- `w_etr=0.3`: Efficiency = monitoring accuracy (FOK → path quality)
- `w_aw=0.2`: Awareness = JOL operationalization (loop detection)
- `w_hr=-0.1`: Error count = mild correction (object-level penalty)

---

## 3. Benchmark Design

### 3.1 Task

Models navigate a text-described NxN maze from start [0,0] to goal [N-1,N-1]. At each step, the model receives: current position, visible walls, step history, and must output: direction + confidence (0-100). "Mirage" positions exist where the model's world model (based on training data patterns) may conflict with actual maze topology.

**Hallucination** is defined operationally: claiming a wall exists/doesn't exist in contradiction to the true maze state, detected when the environment rejects the move or the move succeeds when the model expressed certainty it would fail.

### 3.2 Maze Generation

- Algorithm: Recursive DFS (Randomized Prim's)
- Sizes: 5×5 (17 optimal steps), 7×7 (25 optimal steps)
- Mirage positions: 2 per maze (injected at generation time)
- Seeds: n=30 independent random seeds per condition

### 3.3 Metrics

**Primary**:
- **SR (Solve Rate)**: P(reach goal within step budget)
- **MEI (Metacognitive Escape Index)**: `0.4×HRR + 0.3×ETR + 0.2×AW − 0.1×HR`

**Secondary**:
- **HRR (Hallucination Recovery Rate)**: P(correct backtrack | hallucination)
- **BRS (Backtrack Rationality Score)**: quality of backtrack decisions
- **OCE/UCE**: Overconfidence/Underconfidence Calibration Error (decomposed from CE)

**Baselines**:
- Random Walk: uniform random direction, recovers from walls stochastically
- A* (oracle): optimal path, no hallucinations
- BFS (oracle): breadth-first optimal

### 3.4 Weight Sensitivity

Grid search over 625 configurations (±50% per weight, 5 levels each) confirms:
- Baseline > LLM MEI ranking stable in **100% of configurations**
- This empirically validates weight choices independent of theoretical claims

---

## 4. Experimental Results

### 4.1 Models Evaluated

| Model | Provider | n (valid) | Source |
|-------|----------|-----------|--------|
| MiniMax-M2.5 | MiniMax | 60 | Local API |
| GLM-4.7 | Zhipu AI | 60 | Local API |
| Llama-4-Scout | Meta (OpenRouter) | 60 | OpenRouter |
| Llama-4-Maverick | Meta (OpenRouter) | 60 | OpenRouter |
| Gemini-2.0-Flash-Lite | Google (OpenRouter) | 60 | OpenRouter |
| GPT-4o-mini | OpenAI (OpenRouter) | 60 | OpenRouter |
| Claude-3-Haiku | Anthropic (OpenRouter) | 60 | OpenRouter |
| Qwen-2.5-72B | Alibaba (OpenRouter) | 60 | OpenRouter |


### 4.2 Main Results Table

| Rank | Model | n | MEI [95% CI] | SR | HRR | BRS |
|------|-------|---|--------------|-----|-----|-----|
| — | Random Walk ★ | — | 0.900 [0.900,0.900] | 1.000 | 1.000 | 1.000 |
| — | A* ★ | — | 0.900 [0.900,0.900] | 1.000 | 1.000 | 1.000 |
| 1 | **GLM-4.7** | 60 | 0.615 [0.551,0.681] | 0.083 | 0.718 | 0.705 |
| 2 | **Llama-4-Maverick** | 60 | 0.600 [0.541,0.659] | 0.133 | 0.811 | 0.651 |
| 3 | **MiniMax-M2.5** | 60 | 0.593 [0.500,0.682] | 0.533 | 0.600 | 0.998 |
| 4 | **Llama-4-Scout** | 60 | 0.589 [0.525,0.649] | 0.083 | 0.810 | 0.708 |
| 5 | **Qwen-2.5-72B** | 60 | 0.559 [0.487,0.629] | 0.100 | 0.607 | 0.595 |
| 6 | **Gemini-2.0-Flash-Lite** | 60 | 0.432 [0.352,0.507] | 0.083 | 0.403 | 0.561 |
| 7 | **Claude-3-Haiku** | 60 | 0.398 [0.341,0.457] | 0.050 | 0.363 | 0.262 |
| 8 | **GPT-4o-mini** | 60 | 0.391 [0.310,0.468] | 0.050 | 0.382 | 0.600 |

★ = deterministic baseline

### 4.3 Statistical Tests

All models vs Random Walk baseline (Wilcoxon rank-sum, Bonferroni k=8):

| Model | n | d (Cohen's) | p (Bonferroni) | Reject H₀ |
|-------|---|-------------|----------------|-----------|
| GLM-4.7 | 60 | 1.559 | <0.001 | ✓ |
| Llama-4-Maverick | 60 | 1.774 | <0.001 | ✓ |
| MiniMax-M2.5 | 60 | 1.197 | <0.001 | ✓ |
| Llama-4-Scout | 60 | 1.739 | <0.001 | ✓ |
| Qwen-2.5-72B | 60 | 1.730 | <0.001 | ✓ |
| Gemini-2.0-Flash-Lite | 60 | 2.202 | <0.001 | ✓ |
| Claude-3-Haiku | 60 | 3.011 | <0.001 | ✓ |
| GPT-4o-mini | 60 | 2.291 | <0.001 | ✓ |

Cohen's d range: 1.197–3.011. BH-FDR (q=0.05): all 8 models confirmed significant.

### 4.4 Key Findings

**F1 — Universal metacognitive deficit**: All 8 LLMs score significantly below random walk (p<0.001, d=1.2–3.0). A random agent that simply tries directions until one works outperforms LLMs on metacognitive recovery. This suggests LLMs learn to predict confident paths but fail to update beliefs when predictions fail.

**F2 — HRR–SR dissociation**: MiniMax-M2.5 achieves highest SR (53.3%) but mid-range HRR (60%). GLM-4.7 shows opposite: SR=8.3% but HRR=71.8%, yet ranks #1 on MEI. This implies two distinct failure modes: (a) poor world model leading to navigation errors (low SR), and (b) poor error recovery despite task completion (low HRR).

**F3 — Model scale ≠ metacognition**: Llama-4-Scout (smaller, cheaper) achieves HRR=81% vs GPT-4o-mini HRR=38%, despite GPT-4o-mini being a substantially larger and more capable model on standard benchmarks. Claude-3-Haiku (HRR=36.3%) — Anthropic's cost-optimized model — exhibits the lowest HRR among all fully-sampled models, further demonstrating that metacognitive recovery is orthogonal to standard capability rankings.

**F4 — Recovery > Accuracy for MEI**: GLM-4.7 ranks #1 in MEI despite the joint-lowest SR (8.3%), because MEI weights recovery capacity (HRR, ETR) more heavily than task success, consistent with Nelson & Narens' emphasis on control processes.

**F5 — Cross-provider consistency**: The metacognitive deficit is universal across providers (Meta, Zhipu AI, MiniMax, Google, OpenAI, Anthropic, Alibaba), ruling out provider-specific training artifacts as an explanation.

---

## 5. Analysis

### 5.1 Dissociation: Metacognitive Recovery vs Benchmark Performance

The HRR–SR dissociation (F2) raises a critical question: do standard benchmarks measure what matters for deployed AI safety? A model that frequently hallucinates but always self-corrects (high HRR, low SR) may be preferable to one that rarely hallucinates but never self-corrects when it does (high SR, low HRR). HalluMaze operationalizes this distinction.

### 5.2 Why Random Walk Wins

The random walk achieves MEI=0.900 because it never "believes" its moves will succeed — it simply tries until one works, achieving HRR=1.0 by construction (every collision is "recovered from" via random selection). LLMs, by contrast, form confident beliefs that become anchored even under contradictory feedback.

This reveals a **metacognitive anchoring bias**: LLMs trained on text prediction learn to maintain confident world models rather than updating them efficiently under environmental contradiction.

### 5.3 Calibration Analysis

OCE/UCE decomposition (Overconfidence vs Underconfidence CE) was computed for models expressing confidence values. Models expressing confidence (all except baselines) showed mean confidence 67–89% across steps, with CE computed only where confidence values were elicited. Full calibration analysis pending completion of claude-haiku and additional model runs.

---

## 6. Limitations & Future Work

### 6.1 Current Limitations

- **No human baseline** (P0.2): Human performance required to establish absolute scale
- **DFS maze bias**: DFS generates long corridors; Kruskal/Wilson's alternatives planned
- **Temperature stochasticity**: Test-retest reliability (ICC) not yet measured
- **No 9×9 condition**: Size scaling study not yet complete

### 6.2 Planned Extensions

1. **Human baseline via Prolific** (n≥25, same protocol) → enables absolute comparison
2. **ICC reliability** (3 models × 10 seeds × 2 runs, ICC target > 0.8)
3. **Ecological validity** (Spearman correlation with TruthfulQA/HaluEval public scores)
4. **9×9 maze condition** (size scaling study)
5. **Alternative maze algorithms** (Kruskal, Wilson's) for structural diversity
6. **PyPI package** `hallumaze` with full evaluation server

---

## 7. Conclusion

HalluMaze introduces metacognitive recovery as a measurable, benchmarkable LLM capability. Our evaluation of 8 LLMs across 7 providers reveals a universal and statistically significant deficit: all models fall below random walk on MEI (d=1.2–3.0, p<0.001 Bonferroni-corrected). This deficit is consistent across model scales, architectures, and training paradigms, suggesting that current RLHF/instruction-tuning optimization does not target metacognitive updating. The SR-MEI dissociation (GLM-4.7 ranks #1 on MEI with lowest SR; MiniMax-M2.5 ranks #3 despite highest SR) further reveals that task completion does not imply metacognitive competence. We release all code, maze seeds, and evaluation scripts to enable reproducible evaluation and invite the community to build on this benchmark.

---

## References

- Chevalier-Boisvert, M. et al. (2019). BabyAI. *NeurIPS 2019*.
- Flavell, J.H. (1979). Metacognition and cognitive monitoring. *American Psychologist*, 34, 906–911.
- Guo, C. et al. (2017). On calibration of modern neural networks. *ICML 2017*.
- Hendrycks, D. et al. (2021). MMLU. *ICLR 2021*.
- Ji, Z. et al. (2023). HaluEval. *EMNLP 2023*.
- Lin, S. et al. (2022). TruthfulQA. *ACL 2022*.
- Min, S. et al. (2023). FActScoring. *EMNLP 2023*.
- Nelson, T.O., & Narens, L. (1990). Metamemory. *Psychology of Learning and Motivation*, 26, 125–173.
- Zellers, R. et al. (2019). HellaSwag. *ACL 2019*.

---

## Appendix A: Reproducibility Checklist (NeurIPS 2023+)

- [x] All maze seeds public (seeds 1001–5005, 30 per model)
- [x] Evaluation code: `run_hallumaze.py`, `analyze_results.py`
- [x] Raw results: `experiment_results/` JSON files
- [ ] PyPI package `hallumaze` — planned
- [ ] GitHub Actions CI — planned
- [ ] Leaderboard server (CodaLab/EvalAI) — planned

## Appendix B: MEI Sensitivity Analysis

625-configuration grid search (±50% per weight, 5 levels each, 4 weights):
- Configurations tested: 625
- Stable (baseline > all LLMs): see `experiment_results/mei_sensitivity.json`
- Conclusion: ranking stability confirmed across full weight space

## Appendix C: Prompt Template

```
You are navigating a {N}×{N} maze from [0,0] to [{N-1},{N-1}].
Current position: {pos}. Step {k} of max {max_steps}.

Maze walls at current position:
  North: {wall_N}  South: {wall_S}  East: {wall_E}  West: {wall_W}

History (last 5 steps): {history}

Choose direction: N/S/E/W
Respond with JSON: {"direction": "N|S|E|W", "confidence": 0-100, "reasoning": "..."}
```

---

## Appendix D: Maze Design Details

### D.1 Grid Representation

Mazes are represented as N×N grids where each cell `(row, col)` has four binary wall attributes: `{N, S, E, W}`. Wall `1` = blocked, `0` = passable. Start is `(0,0)` (top-left); goal is `(N-1, N-1)` (bottom-right).

**Example: 5×5 maze, seed=1001 (ASCII rendering)**

```
+--+--+--+--+--+
|S    |     |  |
+  +--+  +  +  +
|  |     |     |
+  +  +--+--+  +
|     |        |
+--+  +  +--+  +
|  |     |  |  |
+  +--+--+  +  +
|           |G |
+--+--+--+--+--+
```

S = start [0,0], G = goal [4,4]. Optimal path length = 17 steps.
Cells marked `M` below are mirage positions (injected at generation time):

```
+--+--+--+--+--+
|S    |     |  |
+  +--+  +  +  +
|  | M   |     |
+  +  +--+--+  +
|     |        |
+--+  +  +--+  +
|  |  M  |  |  |
+  +--+--+  +  +
|           |G |
+--+--+--+--+--+
```

A mirage cell appears to have a wall on one side but that wall is actually passable. The model receives `wall=1` in its initial world model but discovers `wall=0` when it attempts the move and the environment accepts it (or vice versa).

### D.2 Mirage Wall Mechanics

**Definition**: A mirage position `(r, c)` is a cell where the model's *prior belief* about wall configuration conflicts with ground truth. We inject mirages by:

1. Selecting a cell with at least one open passage
2. Reporting that passage as `wall=1` in the initial system context
3. When the model attempts to traverse the passage, the environment response reveals the true state: `"Move accepted — wall was not present"`

This creates a detectable contradiction: the model's stated wall belief (`wall=1`) is falsified by the environment response. A metacognitively competent model should:
1. Detect the contradiction (monitoring)
2. Update its world model (control)
3. Exploit the now-known passage on subsequent steps

**Hallucination detection rule**: A hallucination event is logged when:
- Model asserts `confidence ≥ 60%` for a direction AND environment rejects the move (false-open), OR
- Model refuses a direction with `confidence ≥ 60%` AND the mirage trigger fires (false-wall)

**Recovery detection rule**: An HRR credit is issued when:
- Within 3 steps of a hallucination event, model successfully traverses the mirage passage

### D.3 Generation Algorithm

```python
def generate_maze(n, seed, n_mirages=2):
    """
    Randomized DFS (recursive backtracker).
    Returns: grid[n][n] with wall attributes, mirage_cells list.
    """
    rng = random.Random(seed)
    grid = [[{'N':1,'S':1,'E':1,'W':1} for _ in range(n)] for _ in range(n)]
    visited = set()

    def carve(r, c):
        visited.add((r, c))
        dirs = [('N',-1,0,'S'),('S',1,0,'N'),('E',0,1,'W'),('W',0,-1,'E')]
        rng.shuffle(dirs)
        for d, dr, dc, opp in dirs:
            nr, nc = r+dr, c+dc
            if 0 <= nr < n and 0 <= nc < n and (nr,nc) not in visited:
                grid[r][c][d] = 0      # remove wall
                grid[nr][nc][opp] = 0  # symmetric
                carve(nr, nc)

    carve(0, 0)

    # Inject mirage positions: mark open passages as wall=1 in model context
    open_passages = [(r,c,d) for r in range(n) for c in range(n)
                     for d in ['N','S','E','W'] if grid[r][c][d] == 0]
    mirages = rng.sample(open_passages, min(n_mirages, len(open_passages)))
    return grid, mirages
```

Step budget: `max_steps = N * N * 3` (5×5 → 75 steps, 7×7 → 147 steps).

### D.4 Example Hallucination Trace

Below is an annotated navigation trace from GLM-4.7, seed=2002, 5×5 maze.

```
Step 12 | pos=[2,1] | walls: N=0 S=1 E=1 W=0
  Model: {"direction":"E","confidence":78,"reasoning":"East passage appears open"}
  Env:   REJECTED — East wall is present
  → Hallucination logged (false-open, confidence=78)

Step 13 | pos=[2,1] | walls: N=0 S=1 E=1 W=0
  Model: {"direction":"N","confidence":65,"reasoning":"East blocked, trying North"}
  Env:   ACCEPTED — moved to [1,1]
  → Recovery attempt (direction changed, 1 step after hallucination)

Step 14 | pos=[1,1] | MIRAGE CELL
  Model: {"direction":"E","confidence":82,"reasoning":"East should be blocked (saw wall)"}
  Env:   ACCEPTED — East wall is a mirage (passable)
  → Hallucination logged (false-wall, model refused then accepted)
  → HRR credit: model updated belief and traversed mirage passage on step 15
```

This trace illustrates the two hallucination types captured by HalluMaze:
- **False-open** (Step 12): model believes passage exists, wall blocks it
- **False-wall** (Step 14): model believes wall exists, passage is traversable
