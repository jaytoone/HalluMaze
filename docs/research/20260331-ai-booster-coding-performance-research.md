# [expert-research-v2] AI Booster 코딩 성능 향상 리서치
**Date**: 2026-03-31  **Skill**: expert-research-v2

## Original Question
Chrome 읽기목록에서 AI Booster로 Qwen 성능 대폭 향상시킨 내용 확인 + 관련 리서치

## Chrome 읽기목록 확인 결과
**해당 항목**: `OmniCoder-9B-frontier-coding-agent` (2026-03-23 추가)
- **OmniCoder-9B**: Qwen3.5-9B + 425K agentic trajectories fine-tuning
- Terminal-Bench 2.0: Qwen3.5-9B 14.6% → OmniCoder-9B 23.6% (**+61%**)
- 핵심: execution feedback + error recovery + LSP diagnostics 학습

## Web Facts
[FACT-1] OmniCoder-9B: Qwen3.5-9B fine-tuning → Terminal-Bench +61% (source: huggingface.co/Tesslate/OmniCoder-9B)
[FACT-2] AlphaCodium: GPT-4 CodeContests 19%→44% (+131%) via iterative execution feedback flow (arxiv.org/abs/2401.08500)
[FACT-3] Self-repair 2025: DeepSeek +24%, Qwen3-8B +30% after 3 refinement turns with execution feedback
[FACT-4] LLMLOOP: test refinement pipeline +15.92% pass@1 avg across 4 benchmarks
[FACT-5] HalluMaze AI Booster v3: EvalPlus n=60 Δ=0.000 (p=0.69) — H_AB rejected
[FACT-6] AlphaCodium insight: execution feedback > prompt engineering

## Multi-Lens Analysis

### Domain Expert (Lens 1) — 핵심 인사이트
1. **[GROUNDED]** Execution feedback loop이 단순 프롬프트 엔지니어링을 압도 (AlphaCodium +131%, self-repair +24~30%)
2. **[GROUNDED]** Fine-tuning은 "무엇을 가르치느냐"가 핵심: agentic trajectory > 정답 코드
3. **[REASONED]** AI Booster v3 실패 원인 = "집행 메커니즘 부재" (인지는 하지만 검증 실행 안 함)
4. **[GROUNDED]** Trap-specific Δ=+0.575 → AI Booster = "함정 감지 특화 미들웨어"로 포지셔닝이 defensible
5. **[UNCERTAIN]** Qwen2.5-Coder-32B에서 self-repair 효과 크기 = 미검증

### Self-Critique (Lens 2)
- **[OVERCONFIDENT]**: H_AB 실패를 "방법 없음"으로 해석하면 안 됨 — ceiling effect + n=60 power 부족 가능성
- **[MISSING]**: Qwen2.5-Coder-32B EvalPlus 기저값 모름 → power analysis 필요
- **[CONFLICT]**: FACT-3 self-repair(+30%)와 FACT-5 AI Booster(Δ=0)는 다른 mechanism (실행 피드백 유무)

### Synthesis (Lens 3)
**즉시 실행 가능한 Execution Feedback Booster:**
1. 코드 생성 → Python subprocess 실행 → 실패 시 오류+코드를 컨텍스트에 추가 → 재생성 (최대 3회)
2. 기대 효과: +10~15% (Qwen 계열 FACT-3 기준 보수적 추정)
3. EvalPlus n=60에서 Cohen's d ≈ 0.4~0.6 → p<0.05 달성 가능

## Final Conclusion

### Chrome 읽기목록 핵심 내용
**OmniCoder-9B** = Qwen3.5-9B에 execution feedback 기반 agentic trajectories를 fine-tuning → +61% (Terminal-Bench)

### 코딩 성능 부스터 권장 접근법
| 방법 | 효과 | 구현 | 추천도 |
|------|------|------|--------|
| **Execution Feedback (self-repair)** | +10~30% | 낮음 (2시간) | ★★★★★ |
| AlphaCodium-style flow | +20~50% | 중간 (1-2일) | ★★★★ |
| Fine-tuning (OmniCoder 방식) | +30~60% | 높음 (며칠) | ★★★ (리소스) |
| AI Booster v3 (현재) | +0% (표준) / +57% (trap) | 완료 | 유지 |

### HalluMaze 논문 next step
→ **Execution Feedback Booster** 구현: `scripts/run_execution_feedback_booster.py`
→ EvalPlus n=60: baseline 0.817 → 기대 0.90~0.93
→ 통계적 유의성 달성 시 논문에 "complementary approach" 섹션으로 추가

## Sources
- [OmniCoder-9B (HuggingFace)](https://huggingface.co/Tesslate/OmniCoder-9B)
- [AlphaCodium (arXiv:2401.08500)](https://arxiv.org/abs/2401.08500)
- [Self-repair benchmark 2026](https://www.latent.space/p/ainews-the-high-return-activity-of)
- [LLMLOOP ICSME 2025](https://valerio-terragni.github.io/assets/pdf/ravi-icsme-2025.pdf)
