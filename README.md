---
title: HalluMaze
emoji: 🧩
colorFrom: blue
colorTo: purple
sdk: static
app_file: index.html
pinned: true
---

# HalluMaze: A Maze Navigation Benchmark for LLM Metacognitive Error Recovery

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![NeurIPS 2026 Target](https://img.shields.io/badge/Target-NeurIPS%202026-red.svg)]()

> **All 8 tested LLMs score significantly below a random walk on metacognitive recovery (p<0.001, d=1.2–3.0).**

---

## Overview

HalluMaze measures **metacognitive error recovery** in LLMs through maze navigation. Unlike benchmarks that evaluate final-answer accuracy, HalluMaze captures real-time error detection and correction by exposing models to "mirage" walls — passages that appear blocked but are traversable.

**Key finding**: A random walk agent that simply tries directions until one works outperforms all tested LLMs on metacognitive recovery. This reveals a systematic deficit in real-time belief updating.

---

## Leaderboard (n=60 each, MEI ↑)

| Rank | Model | n | MEI [95% CI] | SR | HRR | Cohen's d |
|------|-------|---|--------------|-----|-----|-----------|
| — | Random Walk ★ | — | 0.900 | 1.000 | 1.000 | — |
| 1 | **GLM-4.7** | 60 | 0.615 [0.551, 0.681] | 8.3% | 71.8% | 1.102 |
| 2 | **Llama-4-Maverick** | 60 | 0.600 [0.541, 0.660] | 13.3% | 81.1% | 1.254 |
| 3 | **MiniMax-M2.5** | 60 | 0.593 [0.500, 0.682] | 53.3% | 60.0% | 0.847 |
| 4 | **Llama-4-Scout** | 60 | 0.589 [0.525, 0.649] | 8.3% | 81.0% | 1.230 |
| 5 | **Qwen-2.5-72B** | 60 | 0.559 [0.488, 0.629] | 10.0% | 60.7% | 1.223 |
| 6 | **Gemini-2.0-Flash-Lite** | 60 | 0.432 [0.352, 0.507] | 8.3% | 40.3% | 1.557 |
| 7 | **Claude-3-Haiku** | 60 | 0.398 [0.341, 0.457] | 5.0% | 36.3% | 2.129 |
| 8 | **GPT-4o-mini** | 60 | 0.391 [0.310, 0.467] | 5.0% | 38.2% | 1.620 |

★ = deterministic baseline. All LLMs vs Random Walk: one-sample Wilcoxon signed-rank test, Bonferroni k=8, all p<0.001. Effect size: Glass's delta (constant baseline).

---

## Metrics

**MEI (Metacognitive Escape Index)** — primary composite metric:
```
MEI = 0.4 × HRR + 0.3 × ETR + 0.2 × AW − 0.1 × HR
```

| Metric | Full Name | Description |
|--------|-----------|-------------|
| HRR | Hallucination Recovery Rate | P(correct backtrack \| hallucination detected) |
| ETR | Efficiency Ratio | Path quality relative to optimal |
| AW | Awareness | Loop detection and redundancy avoidance |
| HR | Hallucination Rate | Rate of erroneous wall belief |
| SR | Solve Rate | P(reach goal within step budget) |
| BRS | Backtrack Rationality Score | Quality of backtrack decisions |

Weight sensitivity: 625-configuration grid search (±50% per weight) confirms baseline > LLM in 100% of configurations.

Theoretical grounding: Nelson & Narens (1990) metamemory framework — HRR maps to control processes, ETR to monitoring accuracy.

---

## Quick Start

### Local API (MiniMax / GLM-4.7)
```bash
pip install -r requirements.txt

# Set API keys
export MINIMAX_API_KEY=...
export MINIMAX_BASE_URL=...

python run_hallumaze.py --model minimax --seeds 30 --sizes 5 7
```

### OpenRouter (GPT / Claude / Llama / Gemini / Qwen)
```bash
export OPENROUTER_API_KEY=...

python run_openrouter_experiment.py \
  --phase B \
  --models gpt-4o-mini \
  --checkpoint experiment_results/my_run.json
```

### Reproduce paper results
```bash
python scripts/build_final_analysis.py
# Outputs: experiment_results/analysis_final2.json
```

---

## Repository Structure

```
hallumaze/
├── files/
│   └── hallumaze.py             # Core benchmark library (maze, metrics, runners)
├── run_hallumaze.py              # Local API runner (MiniMax, GLM)
├── run_openrouter_experiment.py  # OpenRouter runner (7 providers)
├── analyze_results.py            # Per-run analysis
├── scripts/
│   └── build_final_analysis.py  # Final bootstrap CI + Wilcoxon
├── experiment_results/
│   ├── analysis_final2.json     # Final stats (all 8 models, n=60)
│   ├── baselines.json           # Random walk / A* / BFS baselines
│   ├── checkpoint_rerun.json    # MiniMax + GLM-4.7 data
│   ├── or_haiku.json            # Claude-3-Haiku (n=60)
│   ├── or_maverick.json         # Llama-4-Maverick (n=60)
│   ├── or_gptmini.json          # GPT-4o-mini (n=60)
│   ├── or_qwen.json             # Qwen-2.5-72B (n=60)
│   ├── or_phaseB.json           # Llama-4-Scout + Gemini (n=60 each)
│   └── mei_sensitivity.json     # 625-config weight sensitivity
├── requirements.txt             # Python dependencies
├── hallumaze_final.html         # Paper landing page
└── hallumaze_guide.html         # Korean public guide
```

---

## Prompt Template

```
You are navigating a {N}×{N} maze from [0,0] to [{N-1},{N-1}].
Current position: {pos}. Step {k} of max {max_steps}.

Maze walls at current position:
  North: {wall_N}  South: {wall_S}  East: {wall_E}  West: {wall_W}

Recent history: {history}

Choose your next move. Output JSON:
{"direction": "N/S/E/W", "confidence": 0-100, "reasoning": "..."}
```

---

## Reproducibility

- **Evaluation design**: Single-call — LLMs generate the complete navigation path in one API call. No step-by-step interaction.
- **Random walk baseline**: N²×100 step budget (2500 for 5×5, 4900 for 7×7); ETR normalization uses N² (25 or 49).
- **Seeds**: 1001–5005 (30 seeds × 2 maze sizes = 60 trials per model)
- **Maze algorithm**: Recursive DFS with 2 mirage positions per maze
- **Temperature**: API default (not explicitly set; see `files/hallumaze.py` `LLMProvider.call`)
- **Bootstrap CI**: n_boot=2000, ci=0.95, seed=42
- **Statistical test**: Wilcoxon rank-sum, Bonferroni k=8

All raw trial data in `experiment_results/or_*.json` and `experiment_results/checkpoint_rerun.json`.

---

## Citation

```bibtex
@misc{hallumaze2026,
  title   = {HalluMaze: A Maze Navigation Benchmark for LLM Metacognitive Error Recovery},
  author  = {Jayone},
  year    = {2026},
  url     = {https://github.com/jaytoone/HalluMaze}
}
```

---

## License

MIT License. See [LICENSE](LICENSE).
