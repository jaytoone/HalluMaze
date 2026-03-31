# arXiv Submission Checklist — HalluMaze

**Target**: arXiv cs.LG / cs.AI / cs.CL
**Paper**: `docs/hallumaze_arxiv.tex`
**Status**: PAPER COMPLETE — 5 action items before submission

---

## Critical Blockers

### 1. `neurips_2024.sty` MISSING
**Status**: ❌ CRITICAL
The paper uses `\usepackage[preprint]{neurips_2024}` but the style file is not in `docs/`.
arXiv LaTeX compilation will FAIL without it.

**Fix**: Download from https://neurips.cc/Conferences/2024/PaperInformation/StyleFiles
Copy `neurips_2024.sty` to `docs/` directory before creating submission zip.

> Note: For NeurIPS 2026 submission, update to `neurips_2026.sty` when available.

### 2. GitHub push (diverged history)
**Status**: ❌ PENDING USER ACTION
Local branch is ahead of `origin/main` with diverged history (iters 14-18 not pushed).

**Fix**:
```bash
git push origin main --force-with-lease
```
(Confirm no one else has pushed — safe to force given sole contributor)

---

## Pre-Submission Steps

### 3. Create submission zip
**Status**: ⏳ Pending neurips_2024.sty
```bash
cd /home/jayone/Project/Miro/docs
cp /path/to/neurips_2024.sty .
zip -r hallumaze_arxiv_submission.zip \
  hallumaze_arxiv.tex \
  hallumaze.bib \
  neurips_2024.sty \
  figures/
```

### 4. arXiv metadata
**Title**: HalluMaze: A Benchmark for LLM Metacognitive Error Recovery via Maze Navigation

**Authors**: [Add full author name(s)]

**arXiv categories**:
- Primary: cs.LG (Machine Learning)
- Cross-list: cs.AI (Artificial Intelligence), cs.CL (Computation and Language)

**Abstract** (ready — from `\begin{abstract}` in .tex):
> We introduce HalluMaze, a benchmark measuring large language model (LLM) metacognitive error recovery through maze navigation...

### 5. Verify compilation locally (optional but recommended)
```bash
# If LaTeX available:
cd docs/
pdflatex hallumaze_arxiv.tex
bibtex hallumaze_arxiv
pdflatex hallumaze_arxiv.tex
pdflatex hallumaze_arxiv.tex
```

---

## Paper Status (as of 2026-03-31)

| Component | Status |
|-----------|--------|
| Sections (11) | ✅ Complete |
| Word count (~4130) | ✅ Appropriate |
| Citations (23) | ✅ All resolved |
| Cross-references (8) | ✅ All valid |
| Figures (3) | ✅ Present |
| Experiment data | ✅ Committed |
| EFB section | ✅ Added (iter 17) |
| H_AB domain-specificity | ✅ Confirmed + documented |
| neurips_2024.sty | ❌ MISSING |

---

## Key Results Summary (for arXiv abstract page)

```
HalluMaze: 13 LLMs × 60 trials = 780 total
  - All below random walk (MEI 0.900), p<0.001 Bonferroni-corrected
  - Best: Claude-Sonnet-4.5 (MEI=0.783), Worst: GPT-4o (MEI=0.315)
  - SR ⊥ MEI: Claude-Sonnet-4.6 SR#1 (60%) but MEI#8 (0.545)

HalluCode: AP Booster vs MARL-SL
  - GLM CodeMEI: 0.821 (AP) vs 0.737 (MARL-SL), Δ=+0.084, p<0.001
  - HumanEval-Trap: Δ=+0.575 (GLM), p<0.001
  - MBPP-Easy-Trap: Δ=+0.235, p=0.031

AI Booster domain specificity:
  - Standard EvalPlus: Δ=0.000, p=0.69 (H_AB rejected)
  - EFB execution feedback: Δ=+0.030, p=0.19 (ceiling-limited)
```

---

## Submission URL
https://arxiv.org/submit
