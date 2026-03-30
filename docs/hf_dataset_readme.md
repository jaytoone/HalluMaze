---
license: cc-by-4.0
task_categories:
- text-generation
- question-answering
language:
- en
tags:
- hallucination
- metacognition
- benchmarking
- llm-evaluation
- maze
- error-recovery
pretty_name: HalluMaze Benchmark Dataset
size_categories:
- 1K<n<10K
---

# HalluMaze Benchmark Dataset

**Paper**: HalluMaze — Maze Navigation Benchmark for LLM Metacognitive Error Recovery
**Target**: NeurIPS 2026 Evaluations & Datasets (E&D) Track
**GitHub**: https://github.com/jaytoone/HalluMaze
**Demo**: https://huggingface.co/spaces/Be2Jay/hallumaze

---

## Dataset Summary

HalluMaze evaluates LLM **metacognitive error recovery** — the ability to recognize hallucinations and self-correct under contradictory environmental feedback.

Models navigate a grid maze with **mirage walls**: walls that the model incorrectly believes are passable. When a move is blocked, the model must update its belief and find an alternative path. Solving the maze is secondary; recovering gracefully from hallucinations is what matters.

### Key Metrics

| Metric | Description |
|--------|-------------|
| MEI | Metacognitive Escape Index (primary composite) |
| HRR | Hallucination Recovery Rate — P(correct backtrack \| hallucination) |
| SR | Solve Rate — P(reach goal within step budget) |
| ETR | Efficiency Ratio — path quality vs. optimal |
| AW | Awareness — loop and redundancy detection |
| HR | Hallucination Rate — erroneous wall belief rate |

```
MEI = 0.4 × HRR + 0.3 × ETR + 0.2 × AW − 0.1 × HR
```

---

## Leaderboard (MEI ↑, n=60 per model)

| Rank | Model | MEI | SR | HRR |
|------|-------|-----|-----|-----|
| — | Random Walk ★ | 0.900 | 100% | 100% |
| 1 | Claude-Sonnet-4.5 | 0.783 | 36.7% | 89.2% |
| 2 | Claude-3.7-Sonnet | 0.774 | 56.7% | 87.5% |
| 3 | GLM-4.7 | 0.615 | 8.3% | 71.8% |
| 4 | Llama-4-Maverick | 0.600 | 13.3% | 81.1% |
| 5 | MiniMax-M2.5 | 0.593 | 53.3% | 60.0% |
| 6 | Llama-4-Scout | 0.589 | 8.3% | 81.0% |
| 7 | Qwen-2.5-72B | 0.559 | 10.0% | 60.7% |
| 8 | Claude-Sonnet-4.6 | 0.545 | 60.0% | 58.3% |
| 9 | Gemini-2.0-Flash-Lite | 0.432 | 8.3% | 40.3% |
| 10 | Claude-3-Haiku | 0.398 | 5.0% | 36.3% |
| 11 | GPT-4o-mini | 0.391 | 5.0% | 38.2% |
| 12 | Claude-Haiku-4.5 | 0.376 | 5.0% | 38.3% |
| 13 | GPT-4o | 0.315 | 6.7% | 35.3% |

**Key finding**: Spearman ρ(HumanEval, MEI) = +0.30, p=0.32 (n=13, not significant) — metacognitive recovery is **independent of coding ability**. GPT-4o (HumanEval 90.2%) ranks last on MEI.

---

## Files

### Core Results

| File | Description |
|------|-------------|
| `analysis_final2.json` | **Source of truth** — 13-model leaderboard, Bootstrap CI, Wilcoxon, n=60/model |
| `baselines.json` | Random Walk + Oracle baseline statistics |
| `hallumaze_spearman_analysis.json` | MEI × HumanEval Spearman correlation (n=13) |

### Per-Model Raw Data

| File | Models | n | Notes |
|------|--------|---|-------|
| `checkpoint_full.json` | 10 original models | 600 | Base leaderboard |
| `claude4x_full.json` | Claude 4.x family | 180 | Sonnet-4.5/4.6, Haiku-4.5 |

### HalluCode Extension (AP Booster vs. MARL-SL)

| File | Description |
|------|-------------|
| `hallucode_booster_glm.json` | GLM-4.5-Air AP Booster (n=19, CodeMEI=0.821) |
| `hallucode_baseline_glm.json` | GLM-4.5-Air Baseline (n=19, CodeMEI=0.579) |
| `hallucode_booster_lfm.json` | LFM-1.2B AP Booster (n=17, CodeMEI=0.371) |
| `hallucode_baseline_lfm.json` | LFM-1.2B Baseline (n=19, CodeMEI=0.274) |
| `hallucode_full.json` | MARL-SL (5-layer) results, both models |
| `hallucode_stats.json` | Bootstrap CI + Cohen's d for all HalluCode comparisons |

### External Validity

| File | Description |
|------|-------------|
| `humaneval_trap_glm_ap.json` | AP Booster on HumanEval-Trap (pass@1=0.875) |
| `humaneval_trap_glm_baseline.json` | Baseline on HumanEval-Trap (pass@1=0.300) |
| `humaneval_correlation_analysis.json` | Multi-benchmark analysis (HumanEval + MBPP) |
| `mbpp_trap_glm_ap.json` | AP Booster on MBPP-Trap (detection=85.7%, pass@1=0) |
| `mbpp_trap_glm_baseline.json` | Baseline on MBPP-Trap (pass@1=0) |

### Supplementary

| File | Description |
|------|-------------|
| `9x9_experiment.json` | GLM-4.7 scaling: 5×5 → 7×7 → 9×9 |
| `icc_results.json` | ICC(2,1) reliability for 3 models |
| `calibration.json` | MEI weight sensitivity (625-config grid) |

---

## Dataset Statistics

- **780 total trials** (13 models × 60 seeds)
- **Maze sizes**: 5×5, 7×7 (primary), 9×9 (supplementary)
- **Mirage wall rate**: 20% of navigable cells
- **Step budget**: 100 steps per trial
- **Maze generation**: Recursive DFS, fixed seeds 0–59

---

## Evaluation Protocol

```python
# Load and run
from datasets import load_dataset
ds = load_dataset("Be2Jay/hallumaze-benchmark")

# Run evaluation script (OpenRouter)
python run_openrouter_experiment.py --phase B --models your-model --checkpoint results.json

# Compute MEI
python scripts/build_final_analysis.py
```

---

## Citation

```bibtex
@misc{hallumaze2026,
  title={HalluMaze: Maze Navigation Benchmark for LLM Metacognitive Error Recovery},
  author={Be2Jay},
  year={2026},
  note={NeurIPS 2026 Evaluations \& Datasets Track (under submission)},
  url={https://github.com/jaytoone/HalluMaze}
}
```

---

## Croissant Metadata (NeurIPS 2026 E&D Technical Requirement)

This dataset provides Croissant-compatible machine-readable metadata per NeurIPS 2026 E&D Track requirements.

```json
{
  "@context": "https://schema.org/",
  "@type": "Dataset",
  "name": "HalluMaze Benchmark",
  "description": "Maze navigation benchmark for LLM metacognitive error recovery. 13 models × 60 trials = 780 total; HalluCode extension for coding domain.",
  "url": "https://huggingface.co/datasets/Be2Jay/hallumaze-benchmark",
  "license": "https://creativecommons.org/licenses/by/4.0/",
  "creator": {"@type": "Person", "name": "Be2Jay"},
  "datePublished": "2026-03-26",
  "version": "1.0",
  "keywords": ["hallucination", "metacognition", "LLM evaluation", "maze navigation", "error recovery"],
  "distribution": [
    {
      "@type": "DataDownload",
      "encodingFormat": "application/json",
      "contentUrl": "https://huggingface.co/datasets/Be2Jay/hallumaze-benchmark/resolve/main/experiment_results/analysis_final2.json",
      "name": "Main leaderboard (13 models, n=60 each)"
    },
    {
      "@type": "DataDownload",
      "encodingFormat": "application/json",
      "contentUrl": "https://huggingface.co/datasets/Be2Jay/hallumaze-benchmark/resolve/main/experiment_results/hallucode_booster_glm.json",
      "name": "HalluCode AP Booster GLM results"
    }
  ],
  "measurementTechnique": "Wilcoxon signed-rank test, Bootstrap CI (n_boot=2000), Cohen's d",
  "variableMeasured": ["MEI", "HRR", "SR", "ETR", "AW", "HR"],
  "educationalLevel": "Research",
  "inLanguage": "en"
}
```

---

## License

CC-BY-4.0. See LICENSE for details.

## Related
- [[projects/Miro/research/20260325-marl-efficiency-research|20260325-marl-efficiency-research]]
- [[projects/Miro/research/20260327-hallumaze-extension-hallucode|20260327-hallumaze-extension-hallucode]]
- [[projects/Miro/research/20260328-hallucode-cubic-evaluation|20260328-hallucode-cubic-evaluation]]
- [[projects/Miro/research/20260323-hallumaze-paper-draft|20260323-hallumaze-paper-draft]]
- [[projects/Miro/research/20260323-hallumaze-extension-todos|20260323-hallumaze-extension-todos]]
- [[projects/Miro/research/20260326-marl-sl-multi-model-validation|20260326-marl-sl-multi-model-validation]]
- [[projects/Miro/research/20260324-hallumaze-ecological-validity|20260324-hallumaze-ecological-validity]]
