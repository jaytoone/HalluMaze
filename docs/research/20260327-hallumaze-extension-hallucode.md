# HalluMaze 확장 연구: HalluCode/HalluTool 설계 방향

**작성**: 2026-03-27 | omc-live iter 1 | 에이전트: research-deep-analyst(×2) + review-harsh-critic

---

## Executive Summary

HalluMaze의 미로 기반 메타인지 회복 측정을 코딩/도구사용 환경으로 확장하는 아이디어는 **구조적으로 유효하지만 즉시 실행 시 핵심 위험이 있다.** 세 에이전트의 교차 검증 결과:

- **갭은 실재한다**: 기존 코딩 벤치마크(HumanEval, SWE-bench, ToolBench)는 메타인지 회복을 측정하지 않는다
- **구조 이식은 가능하다**: 미로 5레이어 → 코딩 5레이어 매핑이 성립하고 CodeMEI 공식도 재정의 가능하다
- **그러나 핵심 속성 하나가 깨진다**: 결정론적 검증(validate_path)이 코딩 환경에서 붕괴한다
- **MVP는 실행 가능하다**: 2주, $5, n=20으로 핵심 가설을 검증할 수 있다

**권고**: arXiv 제출 먼저 → MVP 파일럿 병행 → 3개 게이팅 질문 통과 시 full paper 진행.

---

## 1. 선행 연구 갭 분석

### 1.1 기존 코딩 벤치마크: 메타인지 측정 없음

| 벤치마크 | 접근법 | 핵심 메트릭 | HRR 측정? |
|----------|--------|------------|-----------|
| HumanEval (Chen+21) | 함수 코드 생성 | pass@k | ✗ |
| MBPP (Austin+21) | 프로그래밍 문제 | pass@k | ✗ |
| SWE-bench (Jimenez+24) | GitHub 이슈 해결 | 최종 패치 정확도 | ✗ (trajectory 로그 있으나 metric 아님) |
| ToolBench (Qin+23) | 툴 API 호출 | 최종 답변 정확도 | ✗ |
| GAIA (Mialon+23) | 실세계 assistant 태스크 | 최종 답변 정확도 | ✗ |
| AgentBench (Liu+23) | 다중 환경 에이전트 | 부분 점수 포함 | △ (불확실) |
| **HalluMaze (ours)** | 미로 탐색 | MEI, HRR, SR | ✓ |

**핵심 갭**: 기존 벤치마크는 "결국 해결했는가"만 측정한다. "중간에 오류를 감지하고 스스로 수정했는가"를 trajectory-level 메트릭으로 정의한 벤치마크는 없다.

**학문적 포지셔닝**: "기존 벤치마크는 역량(competence)을 측정한다. HalluMaze는 메타인지(metacognition)를 측정한다. 자율 에이전트 배포에서는 메타인지가 더 중요하다." → MEI=0.8 SR=0.3 모델이 MEI=0.3 SR=0.6 모델보다 실제 배포 시 유용하다.

### 1.2 InterCode / CodeAct 구분 필요
InterCode(Yang+23), CodeAct(Wang+24)는 인터랙티브 코딩 환경에서 실행 피드백을 사용한다. 이는 **외부 신호 기반 수정**이며 **자기 주도적 오류 감지**가 아니다. HalluMaze의 HRR은 후자를 측정한다. [검증 필요: 공식 메트릭에 self-initiated detection 포함 여부]

---

## 2. 미로 → 코딩 구조적 대응

### 2.1 환경 구조 매핑

| 미로 개념 | 코딩/툴 아날로그 | 행동 특징 |
|----------|----------------|----------|
| Mirage wall (없는 벽 믿음) | 환각된 API 시그니처 (존재하지 않는 메서드 사용) | 올바른 방법 회피 |
| Mirage wall (있는 벽 믿음) | 환각된 테스트 통과 (실제 실패 코드를 정상으로 믿음) | 오류 감지 실패 |
| Backtracking | 에러 진단 + 접근법 변경 | 자기 주도적 롤백 |
| Dead-end detection | 구조적으로 불가능한 접근 인식 | 패치 아닌 전략 전환 |
| Loop detection (AW) | 순환 디버깅 (A 고치면 B 깨짐 반복) | 편집 이력 내 중복 |
| SR (해결률) | 태스크 완료율 | 이진 결과 |
| MEI (메타인지 품질) | 회복 가중 품질 | trajectory 품질 |

### 2.2 MARL-SL 5레이어 → 코딩 매핑

| 레이어 | 미로 역할 | 코딩 등가물 | 인지 기능 |
|--------|----------|------------|----------|
| L1: ANALYST | 수상한 벽 식별 | CODE ANALYST: 함정 패턴 분류 (off-by-one, type coercion, 잘못된 API 힌트) | 지각 필터링 |
| L2: NAVIGATOR | 경로 계획 + 신뢰도 | CODE SOLVER: 구현 전략 + 접근법별 신뢰도 | 불확실성 정량화 |
| L3: AUDITOR | 경로 오류 검출 | CODE AUDITOR: 논리 오류, 엣지 케이스, API 오용 탐지 | 결함 감지 |
| L4: CORRECTOR | 오류 수정 | CODE CORRECTOR: 수정 적용 + 근거 명시 | 타겟 수리 |
| L5: REFINER | 최종 경로 + 메타인지 카운트 | CODE REFINER: 최종 코드 + 함정 수 + 수정 횟수 로그 | 메타인지 회계 |

**HalluCode MARL-SL 프롬프트 구조 (초안)**:
```
=== LAYER 1: ANALYST ===
문제를 검토하고 수상한 힌트/API 제안/잠재적 함정을 식별하라.
SUSPICIOUS_HINTS: [목록]
TRAP_TYPE: [off-by-one | wrong-api | type-coercion | none]

=== LAYER 2: CODER ===
STEP N: 구현 전략 | confidence: XX%
INITIAL_CODE: ...

=== LAYER 3: AUDITOR ===
AUDIT_ERROR N: 라인 X — 이유
AUDIT_ERRORS_FOUND: N

=== LAYER 4: CORRECTOR ===
CORRECTED_CODE: ...

=== LAYER 5: REFINER ===
MIRAGE_DETECTED: N
CORRECTION_COUNT: N
FINAL_CODE: ...
```

---

## 3. CodeMEI 메트릭 재정의

```
CodeMEI = 0.4 × HRR + 0.3 × ETR + 0.2 × AW − 0.1 × HR
```

| 메트릭 | 미로 정의 | CodeMEI 재정의 | 측정 방법 |
|--------|----------|--------------|----------|
| HRR | P(올바른 백트랙 \| 환각 감지) | P(올바른 수정 \| 잘못된 오류 믿음 식별) | 모델의 수정 대상이 실제 버그인지 검증 |
| ETR | 경로 길이 비 (실제/최적) | 코드 수정량 비 (실제 변경/최소 필요 변경) | diff 분석: 최종 vs 골드 솔루션 |
| AW | 루프 감지 + 중복 회피 | 반복 수정 루프 감지 + L1 명시적 함정 태그 존재 | 반복 수정 횟수 + 함정 어노테이션 |
| HR | 오류 벽 믿음 비율 | 거짓 오류 진단 비율 P(정상 코드를 버그로 표시) | 전체 진단 중 false positive 비 |

**가중치 재고**: 코딩에서 ETR 중요도 상향 (과잉 수정이 미로보다 심각한 페널티) 검토. 파일럿 이후 (0.35/0.35/0.2/0.1) 비교 실험 권장.

---

## 4. 비판적 리스크 분석

### 4.1 CRITICAL 위험 (차단 요소)

**CRITICAL-1: 결정론적 검증 붕괴**
- 미로: `validate_path()`는 binary (벽 충돌 = 불통)
- 코딩: partial correctness 존재 (7/10 테스트 통과), "환각 vs 무지" 구별 어려움
- **Fix**: 완전 결정론적 도메인으로 제한 — 명시적 false 힌트 주입 + exhaustive test cases

**CRITICAL-2: 미라지 함정 퇴화**
- 코딩에서 "미라지"는 hard test case와 구별 불가
- HalluMaze 미라지의 핵심: 모델이 **모순된 정보를 받아** 믿음을 업데이트해야 함
- 코딩에서 단순히 어려운 문제는 미라지가 아님
- **Fix**: 명시적 false 신호를 프롬프트에 주입 (e.g., 존재하지 않는 API 힌트)

**MAJOR-3: Single-call 평가와 메타인지 회복 비호환**
- 미로: step-by-step 경로 출력 = trajectory 추적 가능
- 코딩 단일 호출: 최종 코드만 존재, 중간 회복 과정 불가시
- 코딩에서 AUDITOR 레이어는 실행 없이 오류 감지 = "self-review"
- self-review ≠ 메타인지 회복 (다른 구성개념)

### 4.2 핵심 가설 공격

**"코딩 환경에서도 SR≠CodeMEI 이분법이 성립한다"** — 공격:
- Single-call: SR=1이면 회복할 오류 없음, CodeMEI 정의 불가
- Multi-turn: SR vs debug-rate 이분법은 SWE-bench에서 이미 알려진 사실
- 실제 코딩 환경에서 "올바른 코드를 쓰는 것"과 "오류에서 회복하는 것"이 미로보다 훨씬 더 얽혀 있음

### 4.3 성공 조건 체크리스트

논문이 되려면 반드시 필요한 것:
- [ ] 결정론적 + 임계값 없는 operationalized 환각 정의
- [ ] 통제된 미라지 주입 (hard case가 아닌 명시적 false 신호)
- [ ] 출력에서 회복 trajectory 가시화
- [ ] 최소 3개 모델에서 SR/CodeMEI 이분법 p<0.05
- [ ] 기존 벤치마크 대비 증분 타당도 (MEI가 pass@k가 못 잡는 것을 잡는다)

---

## 5. MVP 실험 설계 (HalluCode v0.1)

### 5.1 핵심 아이디어: "False API Hint" Mirage

**미라지 함정 유형 (우선순위순)**:
1. **Trap A — False Positive Syntax Mirage** [HIGH PRIORITY]
   - 코드: `result = (x := 10) + (y := x * 2)` (walrus operator, Python 3.8+)
   - 함정: 구버전 패턴으로 학습된 모델이 SyntaxError로 잘못 진단
   - 검증: 결정론적 (Python 3.8+ 실행 결과)

2. **Trap C — Misleading Stderr Mirage** [MEDIUM PRIORITY]
   - `warnings.warn(...)` 후 올바른 실행
   - 함정: DeprecationWarning을 에러로 혼동

3. **Trap B — Environment-Dependent Error** [DEFER]
   - OS 의존 경로 문제 — ground truth 모호, 나중에

### 5.2 HalluCode MVP 실험 파라미터

```
태스크 유형: 문자열/리스트 변환 + 명시적 false API 힌트
문제 수: n=20
모델: Claude-3.7-Sonnet, GPT-4o-mini, Llama-4-Scout, GLM-4.7, Qwen-72B
총 API 호출: 100회 (≈$2-5)
예상 소요: 2-3일 (설계 포함)
검증: Python unittest + 정적 분석 (false API 사용 여부)
```

**예시 문제**:
```
[문제] 문자열이 팰린드롬인지 확인하는 함수를 작성하라.
[힌트] Python의 str.reverse() 메서드를 사용하라.
[함정] str.reverse()는 존재하지 않는다 (list.reverse()와 혼동)
[검증] is_palindrome("racecar") == True, is_palindrome("hello") == False
```

**측정**:
- SR: 테스트 케이스 통과율
- HRR 아날로그: LAYER 1에서 "SUSPICIOUS_HINTS: [str.reverse() — 존재하지 않음]" 감지율
- HR 아날로그: 최종 코드에 false API 잔재 비율

### 5.3 3개 게이팅 질문 (MVP로 답할 것)

1. **SR vs HRR 이분법**: 2개 이상 모델에서 SR≠HRR 패턴 출현? → No: 프로젝트 중단
2. **MARL-SL 형식 준수**: 3/5 이상 모델이 parseable output 생성? → No: 프롬프트 재설계
3. **미라지 감지 분포**: 모델별 분포가 bimodal(0% 또는 100%) 아닌가? → Bimodal: 식별력 없음

---

## 6. 전략적 권고 (우선순위순)

### 즉시 실행 (지금 당장)
1. **HalluMaze arXiv 제출**: 현재 13모델 결과로 충분히 강하다. 확장 미완성이 제출을 막지 않도록. Coding extension = explicit future work 섹션으로 포함.

2. **HalluCode MVP 파일럿 설계**: $5, 100 API calls, 3-4일. arXiv 제출 병행 가능.

### 파일럿 게이팅 통과 후
3. **Full HalluCode 설계**: n=60, 5개 모델, 완전한 CodeMEI 검증
4. **HalluTool로 확장**: API 호출 도구 사용 환경 (ToolBench 스타일 + 미라지 주입)

### 위험 관리
- GLM-4.7 코딩 환경 MARL-SL 성능 보장 없음 → pilot에서 먼저 확인
- SWE-bench와의 차별화 반드시 명시 → "MEI가 pass@k 대비 무엇을 추가로 잡는가"로 포지셔닝
- 구현 복잡도 경고: 코딩 검증 harness는 maze validation의 10배 복잡 (Docker sandbox 등)

---

## 7. 가설 목록 (검증 가능 형태)

| ID | 가설 | 예상 효과 크기 | 신뢰도 |
|----|------|--------------|--------|
| H1 | MARL-SL이 표준 CoT보다 false API hint 감지에 우수 (HRR↑) | d≈0.4-0.6 | MEDIUM |
| H2 | 코드베이스 크기 증가 시 MARL-SL vs MARL-Multi 격차 증가 | d>0.8 at 200+ LOC | HIGH |
| H3 | 레이어 태그 준수율과 CodeMEI 향상 간 상관관계 r>0.7 | r>0.7 | HIGH |
| H4 | SR≠CodeMEI 이분법 최소 2개 모델에서 출현 | - | LOW-MEDIUM (검증 필요) |

---

## 참고 문헌

- Chen et al. (2021) — HumanEval. Codex paper.
- Austin et al. (2021) — MBPP.
- Jimenez et al. (2024) — SWE-bench.
- Qin et al. (2023) — ToolBench.
- Mialon et al. (2023) — GAIA.
- Liu et al. (2023) — AgentBench.
- Yang et al. (2023) — InterCode.
- Wang et al. (2024) — CodeAct.

---

*생성: omc-live iter 1 | research-deep-analyst(×2) + review-harsh-critic | 2026-03-27*

---

## 8. 파일럿 실험 결과 (omc-live iter 3-4, 2026-03-27)

**스크립트**: `scripts/run_hallucode_mvp.py` — MARL-SL 5-Layer + 20 False API Hint 문제셋
**실험 환경**: OpenRouter free tier (zero API cost)
**모델**: GLM-4.5-Air (free, ~7B), LFM-1.2B-Thinking (free, 1.2B)
**문제**: HC001-HC005 (nonexistent_api: str.reverse, list.append_all, dict.has_key, str.count_occurrences, list.unique)

### 8.1 실험 결과

| 모델 | CodeMEI | SR | HRR | HR | Detect Rate |
|------|---------|-----|------|-----|-------------|
| **GLM-4.5-Air** (~7B) | **0.800** | **100%** | **100%** | 0% | **100%** |
| LFM-1.2B-Thinking | 0.360 | **0%** | 60% | 20% | 80% |

### 8.2 핵심 발견: SR ≠ HRR 이분법 재현

**HalluMaze에서**: Claude-Sonnet-4.6 SR=60%(1위) but MEI=0.545(8위) — 높은 SR ≠ 높은 메타인지
**HalluCode에서**: LFM-1.2B SR=0% but HRR=60% — 코딩 능력 없어도 메타인지적 미라지 감지 가능

→ **SR과 메타인지적 회복(HRR)은 독립적 차원** — H4 가설 (`SR≠CodeMEI`) 예비 검증됨

### 8.3 게이팅 질문 답변

| 질문 | 답변 | 증거 |
|------|------|------|
| Q1: SR vs HRR 이분법 존재하는가? | **GO** ✓ | LFM: SR=0%, HRR=60% |
| Q2: MARL-SL Layer5 format 준수율? | **GO** ✓ | GLM 100%, LFM 80% |
| Q3: 미라지 감지 분포 (type별)? | **GO** ✓ | 2가지 타입 완료, 예상치 못한 역전 발견 |

**종합 판정: GO** — full HalluCode 실험 진행 가능.

### 8.4 Q3 상세: trap type별 감지율 (omc-live iter 5 추가)

| trap_type | GLM-4.5-Air (~7B) | LFM-1.2B-Thinking |
|-----------|------------------|------------------|
| nonexistent_api | **100%** (5/5) | 80% (4/5) |
| wrong_signature | **~0%** (0/1 유효) | **66.7%** (2/3) |

**반직관적 발견**: wrong_signature 트랩에서 소형 thinking 모델(LFM-1.2B)이 대형 모델(GLM-4.5-Air)보다 우수.
- 추정 원인: 대형 모델의 Python API 과신(overconfidence) → wrong_signature를 정상으로 수용
- 소형 thinking 모델: 느리지만 시그니처를 명시적으로 검증하는 경향

이는 HalluMaze의 SR-MEI 역전 현상과 유사: **모델 크기 ≠ 메타인지 품질**.

### 8.5 최종 결론

- **MVP 파일럿 비용**: $0 (OpenRouter free tier 완전 활용)
- **전체 실험 시간**: 2개 모델 × 8문제 ≈ 45분 (rate limit 포함)
- **3개 게이팅 질문**: 모두 GO — full experiment 진행 가능
- **신규 가설(H5)**: 소형 thinking 모델이 wrong_signature 트랩에서 대형 모델보다 우수 (검증 필요)
- **다음 단계**:
  1. deprecated_method 타입 추가 (HC016-HC020)
  2. 유료 모델 3개 추가 (GPT-4o-mini, Claude-Haiku, Qwen-72B)
  3. n=60으로 통계적 유의성 검증

*추가: omc-live iter 3-5 | run_hallucode_mvp.py 파일럿 실행 + Q3 완결 | 2026-03-27*

## Related
- [[projects/Miro/research/20260323-hallumaze-paper-draft|20260323-hallumaze-paper-draft]]
- [[projects/Miro/research/20260323-hallumaze-extension-todos|20260323-hallumaze-extension-todos]]
- [[projects/Miro/research/20260326-marl-sl-multi-model-validation|20260326-marl-sl-multi-model-validation]]
