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
Mirage walls: (1,2)→E, (3,1)→S
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
MEI = 0.4 × HRR + 0.3 × ETR + 0.2 × AW − 0.1 × HR
```

- **HRR** (Hallucination Recovery Rate): P(correct backtrack | hallucination detected) — the core metacognition signal
- **ETR** (Efficiency Ratio): Path quality relative to optimal
- **AW** (Awareness): Loop detection and redundancy avoidance
- **HR** (Hallucination Rate): Rate of erroneous wall beliefs (penalty term)

The **Random Walk baseline** (MEI = 0.900) serves as an upper bound for comparison — a random agent recovers from mirage walls trivially because it has no false beliefs to begin with.

---

## Results: All Models Significantly Underperform Random Walk

We ran 60 trials per model (30 seeds × 2 maze sizes: 5×5 and 7×7), with Bootstrap CI at n_boot=2000. All p<0.001 vs Random Walk (Wilcoxon signed-rank + Bonferroni correction, k=8).

| Rank | Model | MEI | SR | HRR | Glass's d |
|------|-------|-----|-----|-----|-----------|
| — | Random Walk | 0.900 | 100% | 100% | — |
| 1 | GLM-4.7 | 0.615 | 8.3% | 71.8% | 1.559 |
| 2 | Llama-4-Maverick | 0.600 | 13.3% | 81.1% | 1.774 |
| 3 | MiniMax-M2.5 | 0.593 | 53.3% | 60.0% | 1.197 |
| 4 | Llama-4-Scout | 0.589 | 8.3% | 81.0% | 1.739 |
| 5 | Qwen-2.5-72B | 0.559 | 10.0% | 60.7% | 1.730 |
| 6 | Gemini-2.0-Flash-Lite | 0.432 | 8.3% | 40.3% | 2.202 |
| 7 | Claude-3-Haiku | 0.398 | 5.0% | 36.3% | 3.011 |
| 8 | GPT-4o-mini | 0.391 | 5.0% | 38.2% | 2.291 |

Three findings stand out:

**1. The metacognition gap is large and consistent.** Even the best model (GLM-4.7, MEI=0.615) sits 0.285 points below Random Walk. Effect sizes range from d=1.2 to d=3.0 — these are not marginal differences.

**2. Solve Rate does not predict metacognitive quality.** MiniMax-M2.5 achieves the highest Solve Rate (53.3%) but only ranks 3rd in MEI. Models that complete the maze often do so despite poor error recovery, not because of it.

**3. Standard capability rankings don't transfer.** GPT-4o-mini and Claude-3-Haiku — models that perform well on many benchmarks — rank last here. GLM-4.7, which rarely solves the maze (SR=8.3%), leads on metacognition. HalluMaze measures something orthogonal to general capability.

---

## Pushing MEI Further: Multi-Agent Reasoning

We are exploring structured multi-agent reasoning pipelines applied on top of the base benchmark. Early results on MiniMax-M2.5 show significant improvement over the single-call baseline:

| Method | MEI | SR | HRR |
|--------|-----|-----|-----|
| Single-call baseline | 0.593 | 53.3% | 0.600 |
| Multi-agent pipeline | **0.803** | **80.0%** | **0.900** |

Details are not yet public. For related MARL infrastructure, see [VIDraft/MARL](https://huggingface.co/spaces/VIDraft/MARL).

---

## Try It

**Live simulator**: [HuggingFace Space](https://huggingface.co/spaces/Be2Jay/hallumaze) — watch 6 models navigate the same maze in real-time and compare their recovery behavior step by step.

**Dataset**: All 480 trial records (raw responses, step logs, per-trial metrics) are available at `Be2Jay/hallumaze-benchmark` on HuggingFace.

**Code**: [github.com/jaytoone/HalluMaze](https://github.com/jaytoone/HalluMaze) — run your own model with one command. New maze seeds are generated on demand, so there is no risk of test set contamination.

**We are actively extending the leaderboard.** If you want to submit a model or have questions about the evaluation protocol, open an issue on GitHub or leave a comment below.

---

*HalluMaze is a research benchmark targeting NeurIPS 2026. Methodology details, full statistical appendix, and paper draft are available in the repository.*

## Related
- [[projects/Miro/research/20260323-hallumaze-paper-draft|20260323-hallumaze-paper-draft]]
