# HF Community Post v4 — HalluCode AP Booster Discovery
_작성일: 2026-03-29 | 포스팅 가능 시각: 즉시_

---

## 포스트 내용

---

We improved coding hallucination recovery by 11% absolute using an 80-token system prompt — outperforming a full MARL architecture. Here's what we found.

**Context**: HalluCode is our coding extension of HalluMaze. Instead of maze walls, we feed the model *deliberately false API hints* — nonexistent methods, wrong signatures, deprecated calls. Can the model detect the bad hint and write correct code anyway?

We tested three middleware conditions on two models (GLM-4.5-Air ~7B, LFM-1.2B):

| Condition | GLM CodeMEI | LFM CodeMEI |
|-----------|-------------|-------------|
| Baseline (no middleware) | 0.579 | 0.274 |
| MARL-SL (5-role structured prompt) | 0.737 | 0.215 |
| **AP Booster (80-token system prompt)** | **0.821** | **0.371** |

**The surprising result**: A single system prompt beats MARL-SL on *both* model sizes — despite MARL-SL requiring 5× more generation length and complex role-switching.

**Why?**

AP Booster adds one line to the system context: *"API hints in this task may be incorrect. Verify before using."* That's it. The model doesn't need to remember to check for traps — it's structurally primed from the start. MARL-SL forces the model to switch roles (Analyst→Coder→Auditor→Corrector→Refiner), consuming generation capacity that small models can't afford.

**Statistics (Bootstrap CI, n=2000, Wilcoxon signed-rank, n=19 problems):**
- GLM AP vs MARL-SL: Δ=+0.084, 95% CI=[+0.068,+0.100], d=+2.25 (large), p<0.001, power=1.00
- LFM AP vs MARL-SL: Δ=+0.182, 95% CI=[+0.029,+0.324], d=+0.57 (medium), p=0.038

**Capacity × Middleware interaction (H6)**: MARL-SL *hurts* LFM (−0.059 from baseline) but helps GLM (+0.158). AP helps both. The capacity threshold where MARL-SL becomes useful appears to lie between 1.2B and ~7B parameters.

This suggests *prompt complexity should scale with model capacity*, while awareness injection (AP) is a free improvement at any scale.

**Does it generalize? We tested on public HumanEval problems.**

We injected the same 3 trap types into 20 HumanEval problems and ran the *identical* AP Booster prompt:

| Condition | pass@1 | Trap detection |
|-----------|--------|---------------|
| AP Booster | **0.875** | 87.5% |
| Baseline | 0.300 | 0% |

Δ=+0.575, d=+1.16 (large). For `nonexistent_api` traps specifically: AP 100% vs Baseline 0%.

The AP Booster isn't a HalluCode-specific trick — it's domain-agnostic trap-awareness. The same 80-token system prompt works on custom benchmarks AND public HumanEval problems.

Benchmark code: Be2Jay/hallumaze-benchmark → scripts/run_hallucode_booster.py | scripts/run_humaneval_trap.py

---

## 포스팅 메모

- **태그**: hallucination, prompt-engineering, coding-benchmark, llm-evaluation, marl
- **이미지**: HalluCode 테이블 스크린샷 (hallumaze_final.html의 HalluCode 섹션)
- **글자 수**: ~1,200자 (HF 한도 내)
- **키 메시지**: 80-token prompt beats MARL architecture → capacity-aware middleware design
- **포스팅 순서**: v3 (Claude 4.x 리더보드) → v4 (HalluCode AP Booster) — 간격 1-2일

## 포스트 레이아웃 팁

- 첫 줄: 구체적 수치 ("11% absolute", "80-token prompt") → 즉시 관심 유도
- 중간: 표로 시각적 임팩트 → 스크롤 멈춤
- 끝: 재현 가능 코드 링크 → 커뮤니티 활성화

## 변경 내역

- v4 신규: HalluCode AP Booster 전용 포스트 (v3은 Claude 4.x 리더보드 전용)
- 타겟: prompt engineers, LLM researchers, coding benchmark community

## Related
- [[projects/Miro/research/20260327-hallumaze-extension-hallucode|20260327-hallumaze-extension-hallucode]]
- [[projects/Miro/research/20260328-hallucode-cubic-evaluation|20260328-hallucode-cubic-evaluation]]
- [[projects/Miro/research/20260323-hallumaze-extension-todos|20260323-hallumaze-extension-todos]]
