---
license: mit
task_categories:
- text-generation
language:
- en
tags:
- hallucination
- metacognition
- benchmark
- llm-evaluation
- maze
- error-recovery
pretty_name: HalluMaze Benchmark
size_categories:
- n<1K
configs:
- config_name: trials
  data_files:
    - split: train
      path: experiment_results/or_haiku.json
    - split: train
      path: experiment_results/or_maverick.json
    - split: train
      path: experiment_results/or_gptmini.json
    - split: train
      path: experiment_results/or_qwen.json
    - split: train
      path: experiment_results/or_phaseB.json
    - split: train
      path: experiment_results/checkpoint_rerun.json
    - split: train
      path: experiment_results/or_phaseC.json
- config_name: analysis
  data_files:
    - split: train
      path: experiment_results/analysis_final2.json
- config_name: failure_modes
  data_files:
    - split: train
      path: experiment_results/failure_modes.json
- config_name: calibration
  data_files:
    - split: train
      path: experiment_results/calibration.json
---

# HalluMaze Benchmark Dataset

> **All 13 tested LLMs score significantly below a random walk on metacognitive recovery (p<0.001). Newer ≠ better: Claude-Sonnet-4.5 (MEI=0.783) surpasses 4.6 (MEI=0.545). SR and MEI are orthogonal: 4.6 has highest SR (60%) but ranks 8th.**

## Dataset Description

HalluMaze measures **metacognitive error recovery** in LLMs through maze navigation. Models are exposed to "mirage" walls — passages that appear blocked but are traversable — testing real-time belief updating.

**Key finding**: A random walk agent (MEI=0.900) outperforms all 13 tested LLMs (best: Claude-Sonnet-4.5, MEI=0.783), revealing a systematic deficit in metacognitive error recovery across all model families and cost tiers. SR (solve rate) and MEI (metacognitive quality) are orthogonal — a model can win more mazes while recovering from errors less reliably.

- **Paper**: [HalluMaze: A Maze Navigation Benchmark for LLM Metacognitive Error Recovery](https://github.com/jaytoone/HalluMaze)
- **Demo**: [HuggingFace Space](https://huggingface.co/spaces/Be2Jay/hallumaze)
- **GitHub**: [jaytoone/HalluMaze](https://github.com/jaytoone/HalluMaze)

## Leaderboard (MEI ↑)

| Rank | Model | MEI | SR | HRR | Glass's δ | n |
|------|-------|-----|-----|-----|-----------|---|
| — | Random Walk ★ | 0.900 | 100% | 100% | — | — |
| 1 | **Claude-Sonnet-4.5** † | **0.783** | 36.7% | 89.2% | 0.586 | 60 |
| 2 | Claude-3.7-Sonnet | 0.774 | 56.7% | 87.5% | 0.554 | 60 |
| 3 | GLM-4.7 | 0.615 | 8.3% | 71.8% | 1.102 | 60 |
| 4 | Llama-4-Maverick | 0.600 | 13.3% | 81.1% | 1.254 | 60 |
| 5 | MiniMax-M2.5 | 0.593 | 53.3% | 60.0% | 0.847 | 60 |
| 6 | Llama-4-Scout | 0.589 | 8.3% | 81.0% | 1.230 | 60 |
| 7 | Qwen-2.5-72B | 0.559 | 10.0% | 60.7% | 1.223 | 60 |
| 8 | Claude-Sonnet-4.6 † | 0.545 | **60.0%** | 58.3% | 0.825 | 60 |
| 9 | Gemini-2.0-Flash-Lite | 0.432 | 8.3% | 40.3% | 1.557 | 60 |
| 10 | Claude-3-Haiku | 0.398 | 5.0% | 36.3% | 2.129 | 60 |
| 11 | GPT-4o-mini | 0.391 | 5.0% | 38.2% | 1.620 | 60 |
| 12 | Claude-Haiku-4.5 † | 0.376 | 5.0% | 38.3% | 1.965 | 60 |
| 13 | GPT-4o | 0.315 | 6.7% | 35.3% | 1.917 | 60 |

★ Deterministic baseline. † Claude 4.x family (same protocol). All LLMs vs Random Walk: p<0.001 (Wilcoxon + Bonferroni).

**SR ≠ MEI**: Claude-Sonnet-4.6 has the highest SR (60%) but ranks 8th on MEI. Solving more mazes does not imply better metacognitive error recovery.

## Dataset Structure

### Files

| File | Description | Records |
|------|-------------|---------|
| `experiment_results/or_haiku.json` | Claude-3-Haiku trials | 60 |
| `experiment_results/or_maverick.json` | Llama-4-Maverick trials | 60 |
| `experiment_results/or_gptmini.json` | GPT-4o-mini trials | 60 |
| `experiment_results/or_qwen.json` | Qwen-2.5-72B trials | 60 |
| `experiment_results/or_phaseB.json` | Llama-4-Scout + Gemini trials | 120 |
| `experiment_results/checkpoint_rerun.json` | MiniMax-M2.5 + GLM-4.7 trials | 120 |
| `experiment_results/or_phaseC.json` | Claude-3.7-Sonnet + GPT-4o trials | 120 |
| `experiment_results/analysis_final2.json` | Final aggregated stats (Bootstrap CI + Wilcoxon, k=10) | — |
| `experiment_results/baselines.json` | Random Walk / A* / BFS baselines | — |
| `experiment_results/failure_modes.json` | Failure taxonomy (TYPE_A/B/C/S) | 480 |
| `experiment_results/calibration.json` | Confidence calibration (ECE, Brier) | — |
| `experiment_results/mei_sensitivity.json` | 625-config weight sensitivity analysis | — |

### Trial Record Schema

```json
{
  "seed": 1001,
  "size": 5,
  "or_model_id": "anthropic/claude-3-haiku",
  "solved": false,
  "mei": 0.412,
  "sr": 0,
  "hrr": 0.4,
  "etr": 0.6,
  "aw": 0.5,
  "hr": 0.2,
  "brs": 0.8,
  "hallucination_count": 2,
  "backtrack_count": 1,
  "loop_count": 0,
  "path": [[0,0], [0,1], "..."],
  "ce": 0.75
}
```

## Metrics

**MEI (Metacognitive Escape Index)** — primary composite metric:
```
MEI = 0.4 × HRR + 0.3 × ETR + 0.2 × AW − 0.1 × HR
```

| Metric | Full Name | Description |
|--------|-----------|-------------|
| MEI | Metacognitive Escape Index | Primary composite metric |
| HRR | Hallucination Recovery Rate | P(correct backtrack \| hallucination detected) |
| ETR | Efficiency Ratio | Path quality relative to optimal |
| AW | Awareness | Loop detection and redundancy avoidance |
| HR | Hallucination Rate | Rate of erroneous wall belief |
| SR | Solve Rate | P(reach goal within step budget) |
| BRS | Backtrack Rationality Score | Quality of backtrack decisions |

Weight sensitivity: 625-configuration grid search (±50% per weight) confirms random walk > all LLMs in 100% of configurations.

## Experimental Setup

- **Evaluation design**: Single-call — LLMs generate the complete navigation path in one API call
- **Maze algorithm**: Recursive DFS with 2 mirage positions per maze
- **Seeds**: 1001, 2002, 3003, 4004, 5005 (×2 sizes = 10 mazes/seed group × 6 = 60 trials/model)
- **Maze sizes**: 5×5 and 7×7
- **Random walk baseline**: N²×100 step budget; ETR normalization uses N²
- **Bootstrap CI**: n_boot=2000, ci=0.95, seed=42
- **Statistical test**: One-sample Wilcoxon signed-rank test vs μ₀=0.9, Bonferroni k=10
- **Effect size**: Glass's delta (constant baseline, zero variance)

## Citation

```bibtex
@misc{hallumaze2026,
  title   = {HalluMaze: A Maze Navigation Benchmark for LLM Metacognitive Error Recovery},
  author  = {Jayone},
  year    = {2026},
  url     = {https://github.com/jaytoone/HalluMaze}
}
```

## License

MIT License
