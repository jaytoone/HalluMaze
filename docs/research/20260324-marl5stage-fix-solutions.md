# [expert-research-v2] MARL 5-Stage 성능 저하 해결책
**Date**: 2026-03-24  **Skill**: expert-research-v2

## Original Question
MARL 5-stage 미로 풀이 파이프라인 MEI -7.6% 저하 해결책 (MiniMax-M2.5, n=9, 0.593→0.548)

## Web Facts
- [FACT-1] LLMs Cannot Self-Correct Reasoning intrinsically (Huang et al., ICLR 2024) https://arxiv.org/abs/2310.01798
- [FACT-2] AlphaMaze SFT+GRPO: 0%→86%→93% maze accuracy https://arxiv.org/html/2502.14669
- [FACT-3] FTR (Feedback-Triggered Regeneration): 부정 피드백 시 원본 재처리, GSM8K +75% https://arxiv.org/html/2509.07676
- [FACT-4] SCoRe (ICLR 2025): RL 기반 자기수정 MATH +15.6%
- [FACT-5] SMRC: MCTS로 최적 수정 경로 탐색 https://arxiv.org/html/2511.14684
- [FACT-6] SuperCorrect: 대형 모델로 소형 모델 감독 https://arxiv.org/abs/2410.09008

## Final Conclusion

### 해결책 순위 (구현 난이도 × 예상 효과)

| 순위 | 해결책 | 난이도 | 효과 |
|------|--------|--------|------|
| 1 | Path Validator Gate | Low | High |
| 2 | Conditional Pipeline (S2 confidence gate) | Low-Medium | High |
| 3 | Maze Context Re-injection (S3-S5 앞에 원본 미로 강제 삽입) | Low | Medium |
| 4 | Best-of-N S2 (N=3 재실행 + Validator) | Medium | High |
| 5 | S3 역할 전환 (서술형→구체적 오류 위치+수정 지시) | Medium | Medium-High |
| 6 | FTR 완전 구현 | Medium | High |
| 7 | SCoRe/GRPO fine-tuning | High | Very High |

### 권장 구현 조합 (1+2+3)
S1 → S2 → [Path Validator] → 통과 & confidence high → S3(maze-anchored) → S4 → S5
                            → fail or low → S2 재실행 (max 2회) → 실패 시 best-of-3

## Sources
- https://arxiv.org/abs/2310.01798
- https://arxiv.org/html/2502.14669
- https://arxiv.org/html/2509.07676
- https://arxiv.org/html/2511.14684
- https://arxiv.org/abs/2410.09008
