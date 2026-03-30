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

> **All 13 tested LLMs fall significantly below a random walk on metacognitive recovery (p<0.001, δ=0.6–2.1). Spearman ρ(HumanEval, MEI)=+0.30, p=0.32 — metacognitive recovery is independent of coding ability.**

---

## Overview

HalluMaze measures **metacognitive error recovery** in LLMs through maze navigation. Unlike benchmarks that evaluate final-answer accuracy, HalluMaze captures real-time error detection and correction by exposing models to "mirage" walls — passages that the model incorrectly believes are blocked.

**Key findings:**
1. All 13 LLMs fall below a random walk baseline (p<0.001, δ=0.6–2.1)
2. **SR and MEI are orthogonal**: Claude-Sonnet-4.6 leads on SR (60%) but ranks 8th on MEI (0.545)
3. **Newer ≠ better**: Sonnet-4.6 < Sonnet-4.5 < 3.7-Sonnet on MEI despite recency
4. **MEI is independent of coding ability**: Spearman ρ=+0.30 (p=0.32, n=13) — GPT-4o (HumanEval 90.2%) ranks last on MEI

---

## Leaderboard (n=60 each, MEI ↑)

| Rank | Model | MEI [95% CI] | SR | HRR | δ |
|------|-------|--------------|-----|-----|---|
| — | Random Walk ★ | 0.900 | 100% | 100% | — |
| 1 | **Claude-Sonnet-4.5** † | **0.783** [0.731, 0.836] | 36.7% | 89.2% | 0.586 |
| 2 | Claude-3.7-Sonnet | 0.774 [0.720, 0.827] | 56.7% | 87.5% | 0.554 |
| 3 | GLM-4.7 | 0.615 [0.551, 0.681] | 8.3% | 71.8% | 1.102 |
| 4 | Llama-4-Maverick | 0.600 [0.541, 0.660] | 13.3% | 81.1% | 1.254 |
| 5 | MiniMax-M2.5 | 0.593 [0.500, 0.682] | 53.3% | 60.0% | 0.847 |
| 6 | Llama-4-Scout | 0.589 [0.525, 0.649] | 8.3% | 81.0% | 1.230 |
| 7 | Qwen-2.5-72B | 0.559 [0.488, 0.629] | 10.0% | 60.7% | 1.223 |
| 8 | Claude-Sonnet-4.6 † | 0.545 [0.480, 0.610] | 60.0% | 58.3% | 0.825 |
| 9 | Gemini-2.0-Flash-Lite | 0.432 [0.352, 0.507] | 8.3% | 40.3% | 1.557 |
| 10 | Claude-3-Haiku | 0.398 [0.341, 0.457] | 5.0% | 36.3% | 2.129 |
| 11 | GPT-4o-mini | 0.391 [0.310, 0.467] | 5.0% | 38.2% | 1.620 |
| 12 | Claude-Haiku-4.5 † | 0.376 [0.317, 0.436] | 5.0% | 38.3% | 1.965 |
| 13 | **GPT-4o** | **0.315** [0.251, 0.380] | 6.7% | 35.3% | 1.917 |

† Claude 4.x family (n=60 each, same protocol). ★ Deterministic baseline.
Original 10 models vs. Random Walk: Wilcoxon signed-rank, Bonferroni k=10, all p<0.001.
Claude 4.x family (†): same protocol, separate extended evaluation, all p<0.001.

---

## Metrics

**MEI (Metacognitive Escape Index)** — primary composite:
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

Weight sensitivity: 625-config grid search (±50% per weight) confirms baseline > LLM ranking in 100% of configurations.

---

## HalluCode: Coding Metacognitive Recovery

HalluCode extends HalluMaze to coding via **false API hint injection** (19 problems, 3 trap types).

| Model | Condition | CodeMEI | SR | HRR |
|-------|-----------|---------|-----|-----|
| GLM-4.5-Air | Baseline | 0.579 | 78.9% | 68.4% |
| GLM-4.5-Air | MARL-SL | 0.737 | 100% | 84.2% |
| **GLM-4.5-Air** | **AP Booster** | **0.821*** | **100%** | **84.2%** |
| LFM-1.2B | Baseline | 0.274 | 68.4% | 0% |
| LFM-1.2B | MARL-SL | 0.215 | 5% | 25% |
| **LFM-1.2B** | **AP Booster** | **0.371*** | **57%** | **24%** |

*p<0.05 vs MARL-SL. AP Booster = 80-token system prompt flagging malicious hints.

**GLM AP vs MARL-SL**: Δ=+0.084, 95% CI=[+0.068,+0.100], d=+2.25, p<0.001
**LFM AP vs MARL-SL**: Δ=+0.182, 95% CI=[+0.029,+0.324], d=+0.57, p=0.038

### External Validity

| Benchmark | Model | Condition | pass@1 | Trap detection |
|-----------|-------|-----------|--------|---------------|
| HumanEval-Trap | GLM-4.5-Air | AP Booster | **0.875** | 87.5% |
| HumanEval-Trap | GLM-4.5-Air | Baseline | 0.300 | 0% |
| MBPP-Trap (full) | GLM-4.5-Air | AP Booster | 0.000 | **85.7%** |
| MBPP-Trap (full) | GLM-4.5-Air | Baseline | 0.000 | — |
| **MBPP-Easy-Trap** | **Qwen3.5-122B** | **AP Booster v2** | **0.524*** | **92.9%** |
| MBPP-Easy-Trap | Qwen3.5-122B | Baseline | 0.289 | 0% |

AP detection consistently ≥85% across all models and benchmarks. Pass@1 benefit is difficulty-moderated: HumanEval (medium difficulty) → large effect; MBPP-Full (hard) → difficulty blocks pass@1; MBPP-Easy (filtered ≤7 lines) → detection persists and pass@1 improves significantly (+0.235, h=0.484, OR=2.71, p=0.031, n=42/45 pooled).

*p=0.031 (Fisher exact, pooled n=42 AP / n=45 baseline, 95% CI=[+0.030, +0.422]).

---

## Quick Start

```bash
pip install -r requirements.txt
export OPENROUTER_API_KEY=...

# Run benchmark
python run_openrouter_experiment.py --phase B --models gpt-4o-mini \
  --checkpoint experiment_results/my_run.json

# Rebuild final analysis
python scripts/build_final_analysis.py

# HalluCode AP Booster
python scripts/run_hallucode_booster.py --model glm-free --prompt-type ap_booster --n 19

# AP Booster v2 + MBPP-Easy (3-step prompt, difficulty-filtered subset)
python scripts/run_mbpp_easy_trap.py --model glm-free --prompt-type ap_v2 --n 15
python scripts/run_mbpp_easy_trap.py --model glm-free --prompt-type baseline --n 15
```

---

## Repository Structure

```
HalluMaze/
├── run_hallumaze.py              # Local API runner (MiniMax, GLM)
├── run_openrouter_experiment.py  # OpenRouter runner (13 providers)
├── scripts/
│   ├── build_final_analysis.py       # Bootstrap CI + Wilcoxon
│   ├── run_hallucode_booster.py       # HalluCode AP Booster experiment
│   ├── run_humaneval_trap.py          # HumanEval-Trap experiment
│   ├── run_mbpp_trap.py               # MBPP-Trap experiment (AP v1)
│   ├── run_mbpp_easy_trap.py          # AP Booster v2 + difficulty-filtered MBPP
│   └── analyze_hallumaze_coding_spearman.py  # MEI × HumanEval Spearman
├── experiment_results/
│   ├── analysis_final2.json      # Source of truth (13 models, n=60)
│   ├── hallucode_stats.json      # HalluCode Bootstrap CI + Cohen's d
│   └── hallumaze_spearman_analysis.json  # Spearman ρ=+0.30, p=0.32
├── docs/
│   ├── hallumaze_arxiv.tex       # arXiv paper draft
│   └── hallumaze.bib             # References
├── hallumaze_final.html          # Paper landing page
└── hallumaze_arxiv_submit.tar.gz # arXiv submission package
```

---

## Reproducibility

- **Seeds**: 0–59 (60 seeds per model)
- **Maze algorithm**: Recursive DFS, mirage rate 20%
- **Bootstrap CI**: n_boot=2000, α=0.05, seed=42
- **Statistical test**: Wilcoxon signed-rank + Bonferroni k=10
- **Source of truth**: `experiment_results/analysis_final2.json`

---

## Citation

```bibtex
@misc{hallumaze2026,
  title   = {HalluMaze: A Maze Navigation Benchmark for LLM Metacognitive Error Recovery},
  author  = {Be2Jay},
  year    = {2026},
  note    = {NeurIPS 2026 Datasets \& Benchmarks Track (under submission)},
  url     = {https://github.com/jaytoone/HalluMaze}
}
```

---

## License

MIT License. See [LICENSE](LICENSE).
