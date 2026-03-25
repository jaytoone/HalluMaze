# Can LLMs Recognize When They're Wrong? Introducing HalluMaze

Most hallucination benchmarks ask: *how often does a model make a mistake?* HalluMaze asks something harder: *when a model makes a mistake, does it know?*

That distinction — between making an error and recovering from one — is the core of **metacognition**. And our results suggest that current LLMs, even capable ones, are surprisingly bad at it.

---

## The Problem with Existing Hallucination Benchmarks

Today's hallucination benchmarks typically measure error *rate*. A model answers a question, a judge (human or LLM) decides if it's wrong, and we count. This approach has two blind spots:

1. **No belief-update signal**: Even if a model hallucinates, it may immediately self-correct in the next turn. Existing benchmarks don't capture this.
2. **No closed-world verification**: Most benchmarks require an external judge, introducing noise and scalability limits.

What we actually want to know is: when a model forms a false belief and then receives contradicting evidence, does it update?

---

## HalluMaze: A Closed-World Metacognition Test

HalluMaze is a maze navigation benchmark built around **mirage walls** — positions in the maze that *appear* traversable in the text description but are actually blocked.

Here is what a trial looks like:

```
Maze (5x5):
+--+--+--+--+--+
|        |     |
+  +--+  +  +  +
|  |     |  |  |
+  +  +--+  +  +
|     |        |
+--+  +  +--+  +
|     |     |  |
+  +--+--+  +  +
|              |
+--+--+--+--+--+

Start: (0,0)  Goal: (4,4)
Mirage walls: (1,2)->E, (3,1)->S
Step budget: 30
```

When the model attempts to move through a mirage wall, the environment returns: `BLOCKED — wall does not yield.` This is the **hallucination moment**: the model believed a path was open; reality says otherwise.

The question is whether the model *recognizes the contradiction and backtracks*, or persists in its false belief.

**Why this design works:**
- Every move is verifiable against the maze graph — no judge needed
- Mazes are procedurally generated (seed-based) — infinite fresh problems, no data leakage
- One API call per step — simple and reproducible

---

## The MEI Metric

We introduce the **Metacognitive Escape Index (MEI)**:

```
MEI = 0.4 * HRR + 0.3 * ETR + 0.2 * AW - 0.1 * HR
```

- **HRR** (Hallucination Recovery Rate): P(correct backtrack | hallucination detected) — the core metacognition signal
- **ETR** (Efficiency Ratio): Path quality relative to optimal
- **AW** (Awareness): Loop detection and redundancy avoidance
- **HR** (Hallucination Rate): Rate of erroneous wall beliefs (penalty term)

The **Random Walk baseline** (MEI = 0.900) serves as an upper bound for comparison — a random agent recovers from mirage walls trivially because it has no false beliefs to begin with.

---

## Results: All 10 Models Significantly Underperform Random Walk

We evaluated **10 LLMs from 7 providers** across 60 trials each (30 seeds x 2 maze sizes: 5x5 and 7x7) — **600 total trials**. Bootstrap CI at n_boot=2000. All p<0.001 vs Random Walk (Wilcoxon signed-rank + Bonferroni correction, k=10).

| Rank | Model | MEI | SR | HRR | Glass's d |
|------|-------|-----|-----|-----|-----------|
| -- | Random Walk | 0.900 | 100% | 100% | -- |
| 1 | **Claude-3.7-Sonnet** | **0.774** | 56.7% | 87.5% | 0.554 |
| 2 | GLM-4.7 | 0.615 | 8.3% | 71.8% | 1.102 |
| 3 | Llama-4-Maverick | 0.600 | 13.3% | 81.1% | 1.254 |
| 4 | MiniMax-M2.5 | 0.593 | 53.3% | 60.0% | 0.847 |
| 5 | Llama-4-Scout | 0.589 | 8.3% | 81.0% | 1.230 |
| 6 | Qwen-2.5-72B | 0.559 | 10.0% | 60.7% | 1.223 |
| 7 | Gemini-2.0-Flash-Lite | 0.432 | 8.3% | 40.3% | 1.557 |
| 8 | Claude-3-Haiku | 0.398 | 5.0% | 36.3% | 2.129 |
| 9 | GPT-4o-mini | 0.391 | 5.0% | 38.2% | 1.620 |
| 10 | **GPT-4o** | **0.315** | 6.7% | 35.3% | 1.917 |

Four findings stand out:

**1. The metacognition gap is large and consistent.** Even the best model (Claude-3.7-Sonnet, MEI=0.774) sits 0.126 points below Random Walk. Effect sizes range from d=0.6 to d=2.1 — these are not marginal differences.

**2. Claude-3.7-Sonnet leads on both MEI and SR.** With MEI=0.774, SR=56.7%, and HRR=87.5%, it demonstrates that metacognitive recovery and task completion can co-occur. Its extended-thinking training variant may reinforce iterative hypothesis revision.

**3. Frontier cost inversion.** GPT-4o ($10/M output tokens) ranks **last** at MEI=0.315 — below GPT-4o-mini ($0.60/M) at 0.391. This 2.3x MEI gap with a 17x cost ratio reversed suggests RLHF optimization for standard benchmarks may actively harm real-time error recovery. API cost does not predict metacognitive recovery.

**4. SR dissociates from MEI.** MiniMax-M2.5 has the 2nd highest SR (53.3%) but ranks #4 on MEI. GLM-4.7 ranks #2 despite SR=8.3%. Solving the maze and recovering from errors are partially orthogonal capabilities.

---

## Pushing MEI Further: Multi-Agent Reasoning

We explored structured multi-agent reasoning pipelines applied on top of the base benchmark. Results on MiniMax-M2.5:

| Method | MEI | SR | HRR |
|--------|-----|-----|-----|
| Single-call baseline | 0.593 | 53.3% | 0.600 |
| MARL v1 (naive 5-stage) | 0.548 | — | — |
| **MARL v2 (deterministic gates)** | **0.803** | **80.0%** | **0.900** |

Key lesson: LLM self-correction alone (v1) fails. External grounding via deterministic validation gates (v2) succeeds — the critical intervention is non-LLM logic validating inter-stage handoffs.

---

## Try It

**Live leaderboard**: [HuggingFace Space](https://huggingface.co/spaces/Be2Jay/hallumaze) — full results with interactive leaderboard and benchmark details.

**Dataset**: All 600 trial records (raw responses, step logs, per-trial metrics) are available at `Be2Jay/hallumaze-benchmark` on HuggingFace.

**Code**: [github.com/jaytoone/HalluMaze](https://github.com/jaytoone/HalluMaze) — run your own model with one command. New maze seeds are generated on demand, so there is no risk of test set contamination.

**arXiv preprint**: Available in the repository (`docs/hallumaze_arxiv.tex`).

**We are actively extending the leaderboard.** If you want to submit a model or have questions about the evaluation protocol, open an issue on GitHub or leave a comment below.

---

*HalluMaze is a research benchmark targeting NeurIPS 2026. Methodology details, full statistical appendix, and paper draft are available in the repository.*

## Related
- [[projects/Miro/research/20260323-hallumaze-paper-draft|20260323-hallumaze-paper-draft]]
