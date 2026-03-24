# [expert-research-v2] HalluMaze 확장 연구 방향 분석
**Date**: 2026-03-23  **Skill**: expert-research-v2

## Original Question
HalluMaze 실험 확장 가능한 TODO를 영향력/의미 높은 순으로 리서치.
NeurIPS 2026 Datasets & Benchmarks Track 투고 목표.

## Web Facts
- [FACT-1] HalluLens (ACL 2025): 동적 test set 생성으로 data leakage 방지, 외재적/내재적 hallucination 구분. https://aclanthology.org/2025.acl-long.1176/
- [FACT-2] CorrectBench (NeurIPS 2025): 자기수정 벤치마크. 미래 방향: adaptive pipeline, 언제 수정할지 결정. https://arxiv.org/abs/2510.16062
- [FACT-3] Self-Correction Bench: 64.5% blind spot rate. "Wait" 토큰으로 89.3% 감소. https://openreview.net/forum?id=7K1kXowjK1
- [FACT-4] NeurIPS 2025 Multi-Turn Workshop: multi-turn RL, long-horizon, agentic 평가 장려. https://workshop-multi-turn-interaction.github.io/
- [FACT-5] AgentBoard (NeurIPS 2024): 세분화된 progress rate 메트릭이 이진 성공보다 정보 밀도 높음.
- [FACT-6] NeurIPS 2025 D&B Track: 84% 신규 데이터셋 공개, Croissant 메타데이터 required.
- [FACT-7] "Know When You're Wrong" (arXiv 2026): LLM confidence-correctness alignment. https://arxiv.org/html/2603.06604

## Final Ranked TODO List

### RANK 1: 실패 모드 분류학 (Failure Mode Taxonomy)
- **학술적 의미**: aggregate MEI를 diagnostic tool로 격상. mirage 미인식 / 오수정 / 루프 고착 분류
- **구현 난이도**: Low-Medium (기존 480 trials 로그 후처리)
- **NeurIPS 채택 가능성**: HIGH

### RANK 2: Frontier + Reasoning Model Coverage
- **학술적 의미**: GPT-4o, Claude-3.5, DeepSeek-R1 추가. Reasoning 모델 그룹 비교
- **구현 난이도**: Low ($100-300 API 비용)
- **NeurIPS 채택 가능성**: HIGH (prerequisite — 없으면 리뷰어 reject)

### RANK 3: HuggingFace + Croissant 메타데이터
- **학술적 의미**: NeurIPS D&B 필수 요건
- **구현 난이도**: Low (행정 작업)
- **NeurIPS 채택 가능성**: MANDATORY

### RANK 4: Multi-Turn Interactive Protocol
- **학술적 의미**: single-call 설계의 "path generation vs navigation" 모호성 해소
- **구현 난이도**: Medium (maze loop 래핑 + 재실험)
- **NeurIPS 채택 가능성**: HIGH (deadline risk)

### RANK 5: Prompt Sensitivity / Robustness 테스트
- **학술적 의미**: "점수가 prompting artifact인가" 방어. 3 variants × top-4 models × 60 = 720 trials
- **구현 난이도**: Medium
- **NeurIPS 채택 가능성**: HIGH

### RANK 6: Confidence Calibration (ECE/Brier)
- **학술적 의미**: 기존 confidence 데이터에서 ECE 계산. 추가 실험 불필요
- **구현 난이도**: Low
- **NeurIPS 채택 가능성**: MEDIUM-HIGH (Rank 1과 결합 시 강력)

### RANK 7: Adaptive Correction 프로토콜
- **학술적 의미**: CorrectBench와 연결, "Wait" token HalluMaze 재현
- **구현 난이도**: Medium
- **NeurIPS 채택 가능성**: MEDIUM (부록 수준)

### RANK 8: 미로 다양성 확장 (Topology Generalization)
- **학술적 의미**: DFS 편향 방어
- **구현 난이도**: Low
- **NeurIPS 채택 가능성**: MEDIUM (defensive only)

### RANK 9: 인간 베이스라인
- **학술적 의미**: 맥락화 효과, 단 생태학적 타당성 문제
- **구현 난이도**: Medium (IRB + crowdsourcing)
- **NeurIPS 채택 가능성**: LOW-MEDIUM

## 실행 일정 제안
| 시기 | TODO |
|------|------|
| 즉시 (1-2주) | RANK 3: HuggingFace |
| 즉시 (2-4주) | RANK 2: Frontier models |
| 단기 (1달) | RANK 1: Failure taxonomy + RANK 6: Calibration |
| 중기 (2달) | RANK 5: Prompt robustness |
| 중기 (2-3달) | RANK 4: Multi-turn |
| 여유 시 | RANK 7, 8 |

## Sources
- https://aclanthology.org/2025.acl-long.1176/
- https://arxiv.org/abs/2510.16062
- https://openreview.net/forum?id=7K1kXowjK1
- https://workshop-multi-turn-interaction.github.io/
- https://proceedings.neurips.cc/paper_files/paper/2024/file/877b40688e330a0e2a3fc24084208dfa-Paper-Datasets_and_Benchmarks_Track.pdf
- https://blog.neurips.cc/2025/09/30/reflecting-on-the-2025-review-process-from-the-datasets-and-benchmarks-chairs/
- https://arxiv.org/html/2603.06604

## Related
- [[projects/Miro/research/20260323-hallumaze-paper-draft|20260323-hallumaze-paper-draft]]
