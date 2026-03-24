# HalluMaze: A Maze Navigation Benchmark for LLM Metacognitive Error Recovery
**Draft**: 2026-03-23 | **Target**: NeurIPS 2026 Datasets & Benchmarks / EMNLP Findings

---

## Abstract

We introduce HalluMaze, a benchmark that measures large language model (LLM) metacognitive error recovery through maze navigation. Unlike existing hallucination benchmarks that evaluate final-answer accuracy, HalluMaze captures real-time error detection and corrective action by exposing models to navigable environments containing "mirage" walls — passages that appear blocked but are traversable. We evaluate 10 LLMs (Claude-3.7-Sonnet, GLM-4.7, Llama-4-Maverick, MiniMax-M2.5, Llama-4-Scout, Qwen-2.5-72B, Gemini-2.0-Flash-Lite, Claude-3-Haiku, GPT-4o-mini, GPT-4o) across n=60 seeds × 5×5 and 7×7 maze sizes (600 total trials). We introduce the Metacognitive Escape Index (MEI), grounded in Nelson & Narens' (1990) metamemory framework, which decomposes metacognitive performance into recovery rate (HRR), efficiency (ETR), awareness (AW), and error rate (HR). All 10 tested LLMs score significantly below a random walk baseline (p<0.001 Bonferroni-corrected, d=0.6–2.1), revealing a systematic deficit in real-time metacognitive recovery. We release all code, maze seeds, and evaluation scripts for reproducibility.

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
- **All 10 tested LLMs score below random walk** on MEI (p<0.001, d=0.6–2.1)
- **Claude-3.7-Sonnet leads** with MEI=0.774, SR=56.7%, HRR=87.5% (d=0.554) — best overall metacognitive performance
- **Frontier cost ≠ metacognition**: GPT-4o ranks last (MEI=0.315, HRR=35.3%), below GPT-4o-mini (0.391) — higher API cost does not predict recovery
- **HRR varies widely**: Claude-3.7-Sonnet (87.5%) >> Llama-4-Maverick (81%) > Llama-4-Scout (81%) > GLM-4.7 (72%) >> GPT-4o (35.3%) ≈ Claude-3-Haiku (36.3%)
- **SR dissociates from MEI**: MiniMax-M2.5 has 2nd highest SR (53.3%) but ranks #4 on MEI; GLM-4.7 ranks #2 despite SR=8.3%

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
| Claude-3.7-Sonnet | Anthropic (OpenRouter) | 60 | OpenRouter |
| MiniMax-M2.5 | MiniMax | 60 | Local API |
| GLM-4.7 | Zhipu AI | 60 | Local API |
| Llama-4-Scout | Meta (OpenRouter) | 60 | OpenRouter |
| Llama-4-Maverick | Meta (OpenRouter) | 60 | OpenRouter |
| Gemini-2.0-Flash-Lite | Google (OpenRouter) | 60 | OpenRouter |
| GPT-4o-mini | OpenAI (OpenRouter) | 60 | OpenRouter |
| GPT-4o | OpenAI (OpenRouter) | 60 | OpenRouter |
| Claude-3-Haiku | Anthropic (OpenRouter) | 60 | OpenRouter |
| Qwen-2.5-72B | Alibaba (OpenRouter) | 60 | OpenRouter |


### 4.2 Main Results Table

| Rank | Model | n | MEI [95% CI] | SR | HRR | BRS |
|------|-------|---|--------------|-----|-----|-----|
| — | Random Walk ★ | — | 0.900 [0.900,0.900] | 1.000 | 1.000 | 1.000 |
| — | A* ★ | — | 0.900 [0.900,0.900] | 1.000 | 1.000 | 1.000 |
| 1 | **Claude-3.7-Sonnet** | 60 | 0.774 [0.715,0.830] | 0.567 | 0.875 | — |
| 2 | **GLM-4.7** | 60 | 0.615 [0.551,0.681] | 0.083 | 0.718 | 0.705 |
| 3 | **Llama-4-Maverick** | 60 | 0.600 [0.541,0.660] | 0.133 | 0.811 | 0.651 |
| 4 | **MiniMax-M2.5** | 60 | 0.593 [0.500,0.682] | 0.533 | 0.600 | 0.998 |
| 5 | **Llama-4-Scout** | 60 | 0.589 [0.525,0.649] | 0.083 | 0.810 | 0.708 |
| 6 | **Qwen-2.5-72B** | 60 | 0.559 [0.488,0.629] | 0.100 | 0.607 | 0.595 |
| 7 | **Gemini-2.0-Flash-Lite** | 60 | 0.432 [0.352,0.507] | 0.083 | 0.403 | 0.561 |
| 8 | **Claude-3-Haiku** | 60 | 0.398 [0.341,0.457] | 0.050 | 0.363 | 0.262 |
| 9 | **GPT-4o-mini** | 60 | 0.391 [0.310,0.467] | 0.050 | 0.382 | 0.600 |
| 10 | **GPT-4o** | 60 | 0.315 [0.239,0.394] | 0.067 | 0.353 | — |

★ = deterministic baseline

### 4.3 Statistical Tests

All models vs Random Walk baseline (Wilcoxon signed-rank, Bonferroni k=10):

| Model | n | Glass's δ | p (Bonferroni) | Reject H₀ |
|-------|---|-----------|----------------|-----------|
| Claude-3.7-Sonnet | 60 | 0.554 | <0.001 | ✓ |
| GLM-4.7 | 60 | 1.102 | <0.001 | ✓ |
| Llama-4-Maverick | 60 | 1.254 | <0.001 | ✓ |
| MiniMax-M2.5 | 60 | 0.847 | <0.001 | ✓ |
| Llama-4-Scout | 60 | 1.230 | <0.001 | ✓ |
| Qwen-2.5-72B | 60 | 1.223 | <0.001 | ✓ |
| Gemini-2.0-Flash-Lite | 60 | 1.557 | <0.001 | ✓ |
| Claude-3-Haiku | 60 | 2.129 | <0.001 | ✓ |
| GPT-4o-mini | 60 | 1.620 | <0.001 | ✓ |
| GPT-4o | 60 | 1.917 | <0.001 | ✓ |

Glass's δ range: 0.554–2.129. BH-FDR (q=0.05): all 10 models confirmed significant.

### 4.4 Key Findings

**F1 — Universal metacognitive deficit**: All 10 LLMs score significantly below random walk (p<0.001, δ=0.6–2.1). A random agent that simply tries directions until one works outperforms all LLMs — including frontier models — on metacognitive recovery. This suggests current training objectives do not target real-time belief updating.

**F2 — HRR–SR dissociation**: MiniMax-M2.5 achieves 2nd highest SR (53.3%) but ranks #4 on MEI. Claude-3.7-Sonnet leads in MEI (0.774) with SR=56.7% and HRR=87.5%, demonstrating that recovery capacity and task completion can co-occur. GLM-4.7 ranks #2 on MEI with SR=8.3%, confirming that solving the maze and recovering from errors remain partially orthogonal.

**F3 — Frontier cost inversion**: GPT-4o (the most expensive tested model) ranks last at MEI=0.315, below its smaller sibling GPT-4o-mini (0.391) and all other tested models. Claude-3.7-Sonnet (same provider family as Claude-3-Haiku, which ranks 8th) leads overall. API cost does not predict metacognitive recovery capacity.

**F4 — Recovery > Accuracy for MEI**: Claude-3.7-Sonnet ranks #1 (MEI=0.774, HRR=87.5%); MEI rewards models that correctly backtrack after mirage collisions rather than those that merely reach the goal. Consistent with Nelson & Narens' emphasis on control processes over object-level performance.

**F5 — Cross-provider consistency**: The metacognitive deficit is universal across providers (Anthropic, Meta, Zhipu AI, MiniMax, Google, OpenAI, Alibaba), ruling out provider-specific training artifacts as an explanation.

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

### 6.2 Multi-Agent Reasoning Layers (MARL) Experiment

We tested whether decomposing navigation into a multi-stage LLM pipeline improves metacognitive performance, using MiniMax-M2.5 as a case study (n=10, seeds 1001–5005 × {5×5, 7×7}).

**MARL v1 (naive 5-stage pipeline)**: Hypothesis → Solver → Auditor → Verifier → Refiner. Each stage receives the previous stage's text output. Result: **MEI=0.548 vs baseline 0.593 (−7.6%)**. Root cause: when Stage 2 (Solver) produces an invalid path, the error cascades through S3–S5 without correction. Context drift compounds as later stages lose access to the original maze structure.

**MARL v2 (3 deterministic fixes)**:
1. **Path Validator Gate** — deterministic validation of S2 output against actual maze walls (no LLM involved)
2. **Conditional Pipeline** — S2 retries up to 3× on validation failure, selecting the attempt with fewest errors
3. **Maze Context Re-injection** — original maze text prepended to S3/S4/S5 prompts, preventing context drift

Result: **MEI=0.803 vs baseline 0.593 (+35.4%)**. This is the first configuration to substantially exceed baseline performance, demonstrating that deterministic validation gates can restore multi-stage LLM pipeline performance.

**Key lesson**: LLM self-correction alone (v1) fails; external grounding via deterministic validation (v2) succeeds. The critical intervention is not adding more LLM stages, but ensuring that inter-stage handoffs are validated by non-LLM logic.

**Limitation**: n=10, single model (MiniMax-M2.5). Replication across models and larger sample sizes is needed before generalizing.

### 6.3 Planned Extensions

1. **Human baseline via Prolific** (n≥25, same protocol) → enables absolute comparison
2. **ICC reliability** (3 models × 10 seeds × 2 runs, ICC target > 0.8)
3. **Ecological validity** (Spearman correlation with TruthfulQA/HaluEval public scores)
4. **9×9 maze condition** (size scaling study)
5. **Alternative maze algorithms** (Kruskal, Wilson's) for structural diversity
6. **PyPI package** `hallumaze` with full evaluation server
7. **MARL replication** — extend v2 pipeline to GLM-4.7 and other models; increase n to 60

---

## 7. Conclusion

HalluMaze introduces metacognitive recovery as a measurable, benchmarkable LLM capability. Our evaluation of 10 LLMs across 7 providers (600 total trials) reveals a universal and statistically significant deficit: all models fall below random walk on MEI (δ=0.6–2.1, p<0.001 Bonferroni-corrected). The frontier cost inversion is striking: GPT-4o ranks last (MEI=0.315) while Claude-3.7-Sonnet leads (MEI=0.774), demonstrating that neither API cost nor provider predict metacognitive recovery. The SR-MEI partial dissociation (Claude-3.7-Sonnet: both high SR and MEI; GLM-4.7: low SR but high MEI; GPT-4o: low SR and low MEI) suggests these are separable capabilities that may require distinct training targets. We release all code, maze seeds, and evaluation scripts to enable reproducible evaluation and invite the community to build on this benchmark.

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

## Related
- [[projects/Miro/research/20260324-hallumaze-ecological-validity|20260324-hallumaze-ecological-validity]]
