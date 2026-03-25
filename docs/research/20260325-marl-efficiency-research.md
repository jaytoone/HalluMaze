# [expert-research-v2] MARL 5-Stage 효율성 혁신 — 시간/토큰 최적화 방법론
**Date**: 2026-03-25  **Skill**: expert-research-v2

## Original Question
HalluMaze MARL 5-Stage Pipeline (MEI=0.803, +35.4% vs baseline)의 시간/토큰 효율성 혁신 방법론.
연구 질문: (1) 동일 MEI를 더 적은 호출로 달성? (2) Stage pruning/merging? (3) 창발적 방법론?

## Web Facts

[FACT-1] HELIOS Framework: Multi-model early-exit → 1.48× throughput, 15.14× batch size (arxiv 2504.10724)
[FACT-2] Early Exit Complementarity: 한 모델 실패 토큰이 다른 모델에서 빠르게 exit
[FACT-3] Greedy Token Exiting: low-confidence도 추가 레이어 후 동일 결과 → early exit 허용
[FACT-4] Speculative CoT: draft(소형)+verify(대형) → 48–66% 지연 감소 (arxiv 2504.19095)
[FACT-7] SelfBudgeter: 61% 응답 길이 압축, 79%+ 정확도 유지 (arxiv 2505.11274)
[FACT-9] TALE (ACL 2025): dynamic token-budget → 비용 감소, 성능 소폭 감소
[FACT-11] Adaptive Budget by Difficulty: 단순 문제 짧은 budget, 복잡 문제 긴 budget
[FACT-12] AgentPrune: multi-agent 통신 중복 제거 → 28–72% token 감소, $5.6 vs $43.7 (2024)
[FACT-13] One-shot spatial-temporal pruning으로 최적 topology 도출
[FACT-16] 단순 token-budget baseline이 naive multi-agent보다 성능 우수할 수 있음

## Multi-Lens Analysis

### Domain Expert (Lens 1) — 5가지 전략

**Strategy 1: S1+S2 Merge, S3+S4 Merge**
Adjacent stages 간 높은 context 공유 → 2+1 → 3 calls/step.
AgentPrune의 28–72% token 감소 근거. 반론: S1/S2 분리가 hallucination recovery의 load-bearing 구조일 수 있음.

**Strategy 2: Confidence-Based Adaptive Early Exit**
S2 confidence ≥75% AND no mirage flag → S3–S5 skip.
Expected: 2.5–3 calls/step 평균. 반론: 미로 특성상 "확신 있는 환각" 문제 — 높은 confidence가 환각과 공존 가능.

**Strategy 3: Speculative CoT (소형 draft)**
S1+S2 = 소형 모델 draft, S3 = 대형 모델 verify.
48–66% 지연 감소 가능. 반론: 미로 상태 추적에 소형 모델 실패율 높음 (Haiku MEI=0.398).

**Strategy 4: Token Budgeting (S2+S5)**
단계 복잡도 기반 max_tokens 동적 할당.
61% 압축 가능. 반론: backtrack reasoning 중단 위험.

**Strategy 5: AgentPrune 토폴로지 최적화**
20회 calibration → stage agreement rate 측정 → empirical pruning.
반론: seed overfitting 위험.

### Self-Critique (Lens 2)

- [OVERCONFIDENT] S2 confidence gate: 자기보고 confidence는 순환 논리 — 개선 필요
- [MISSING] step-level stage agreement rate 데이터 없음 — 가장 중요한 미지수
- [CONFLICT] SCoT 48–66% gains: 수학 추론 benchmark 기반, 미로 탐색으로 domain transfer 미검증
- [MISSING] Stage merge calibration overhead의 break-even 계산 없음

### Synthesis (Lens 3) — 구현 계획

**Phase 1 (Quick Win, 0–2주)**: Token Budgeting on S2+S5
- S1 mirage flag 기반 step complexity → max_tokens 동적 설정
- 기대 효과: 40–55% token 감소, MEI 영향 최소
- 필요: 20–30 calibration trials

**Phase 2 (중기, 2–6주)**: Objective-Gated Early Exit
- S2 confidence가 아닌 S1의 객관적 maze state features로 gate
  - (a) 해당 셀 방문 이력? (b) 인접 셀 mirage 관찰? (c) loop signature?
  - 세 조건 모두 음성 → 2 calls (S1+S2 only)
  - 1개 이상 양성 → 5 calls (full pipeline)
- 기대: 2.8–3.2 calls/step 평균 (36–44% calls 감소)
- 핵심 개선: confidence gate → objective state gate

**Phase 3 (장기, 6–12주)**: Stage Merging + SCoT 탐색
- S3+S4 agreement rate 측정 후 merger 결정
- SCoT 드래프트 수용률 50%+ 확인 시 채택
- S1+S2 merge는 S3+S4 검증 완료 후 검토

## Final Conclusion

### 결론

MARL 5-stage의 효율화는 3단계로 접근:
1. **즉시 (0주)**: S2+S5 token budgeting → 40–55% token 감소, MEI 유지
2. **단기 (2–6주)**: S1 objective state gate → 평균 2.8–3.2 calls/step
3. **중기 (6–12주)**: S3+S4 merge + SCoT 실험 → 2.2–2.8 calls/step

핵심 설계 원칙:
- S2 self-confidence는 gate로 쓰지 말 것 (확신 있는 환각 문제)
- S1의 객관적 maze state (mirage flag, visit history, loop signature)를 gate signal로 사용
- Stage merge는 calibration 데이터 없이 시작하지 말 것

예상 최종 효율:
| Phase | Calls/Step | Token 비율 | MEI 리스크 |
|-------|-----------|-----------|-----------|
| 현재 MARL v2 | 5.0 | 1.0× | — |
| Phase 1 | 5.0 | 0.55–0.65× | 최소 |
| Phase 2 | 2.8–3.2 | 0.45–0.55× | 낮음-중간 |
| Phase 3 | 2.2–2.8 | 0.35–0.45× | 중간 |

## Sources
- HELIOS (arxiv 2504.10724)
- Speculative CoT (arxiv 2504.19095)
- SelfBudgeter (arxiv 2505.11274)
- AgentPrune (arxiv 2410.02506)
- TALE (ACL 2025, aclanthology 2025.findings-acl.1274)
