# HalluMaze — Miro Project

**프로젝트**: HalluMaze — Maze Navigation Benchmark for LLM Metacognitive Error Recovery
**GitHub**: https://github.com/jaytoone/HalluMaze
**Target**: NeurIPS 2026

---

## Project Status (2026-03-24)

### Experiment Results (FINAL)
- **10 models × 60 trials = 600 total**
- Source of truth: `experiment_results/analysis_final2.json`
- All stats: Bootstrap CI n_boot=2000, Wilcoxon signed-rank + Bonferroni k=10, all p<0.001

### Leaderboard (MEI ↑)

| Rank | Model | MEI | SR | HRR | d |
|------|-------|-----|-----|-----|---|
| — | Random Walk ★ | 0.900 | 100% | 100% | — |
| 1 | **Claude-Sonnet-4.5** † | **0.783** | 36.7% | 89.2% | 0.586 |
| 2 | Claude-3.7-Sonnet | 0.774 | 56.7% | 87.5% | 0.554 |
| 3 | GLM-4.7 | 0.615 | 8.3% | 71.8% | 1.102 |
| 4 | Llama-4-Maverick | 0.600 | 13.3% | 81.1% | 1.254 |
| 5 | MiniMax-M2.5 | 0.593 | 53.3% | 60.0% | 0.847 |
| 6 | Llama-4-Scout | 0.589 | 8.3% | 81.0% | 1.230 |
| 7 | Qwen-2.5-72B | 0.559 | 10.0% | 60.7% | 1.223 |
| 8 | Claude-Sonnet-4.6 † | 0.545 | 60.0% | 58.3% | 0.825 |
| 9 | Gemini-2.0-Flash-Lite | 0.432 | 8.3% | 40.3% | 1.557 |
| 10 | Claude-3-Haiku | 0.398 | 5.0% | 36.3% | 2.129 |
| 11 | GPT-4o-mini | 0.391 | 5.0% | 38.2% | 1.620 |
| 12 | Claude-Haiku-4.5 † | 0.376 | 5.0% | 38.3% | 1.965 |
| 13 | GPT-4o | 0.315 | 6.7% | 35.3% | 1.917 |

† Extended: Claude 4.x family (n=60 each, same protocol)

---

## Key Metrics

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

---

## Repository Structure

```
Miro/
├── run_hallumaze.py              # Local API runner (MiniMax, GLM)
├── run_openrouter_experiment.py  # OpenRouter runner (7 providers)
├── analyze_results.py            # Per-run analysis
├── visualize_maze.py             # Maze visualization
├── run_experiment.py             # Multi-model experiment runner
├── scripts/
│   ├── build_final_analysis.py  # Final bootstrap CI + Wilcoxon
│   └── auto_finalize_qwen.py    # Qwen completion monitor
├── experiment_results/           # All raw + analyzed data (20 files)
├── hallumaze_final.html          # Paper landing page (MAIN)
├── hallumaze_guide.html          # Korean public guide
├── hallumaze_visual_*.html       # Seed-specific visualizations
├── docs/research/
│   └── 20260323-hallumaze-paper-draft.md  # Full paper draft
└── .gitignore
```

---

## Next Steps

1. **HuggingFace Space** — static hosting of hallumaze_final.html
2. **HuggingFace Dataset** — upload experiment_results/ JSONs
3. **arXiv submission** — paper draft at docs/research/20260323-hallumaze-paper-draft.md
4. **Additional models** — extend leaderboard (Gemini-2.0-Pro, Claude-3.5-Sonnet, etc.)

---

## Development Commands

```bash
# Run new experiment (OpenRouter)
python run_openrouter_experiment.py --phase B --models gpt-4o-mini --checkpoint experiment_results/my_run.json

# Run local API (MiniMax/GLM)
python run_hallumaze.py --model minimax --seeds 30 --sizes 5 7

# Rebuild final analysis
python scripts/build_final_analysis.py
# Output: experiment_results/analysis_final2.json

# Visualize a maze
python visualize_maze.py
```

---

## API Keys

```bash
# OpenRouter
export OPENROUTER_API_KEY=...

# MiniMax
export MINIMAX_API_KEY=...
export MINIMAX_BASE_URL=...

# Or use shared env
source ~/.claude/env/shared.env
```

---

## Git Workflow

- Remote: https://github.com/jaytoone/HalluMaze.git
- Branch: main
- Commit format: see ~/.claude/CLAUDE.md (global)
