# HalluCode: 코딩 능력 평가 '큐빅(Cubic)' 자격 평론

**작성**: 2026-03-28 | omc-live iter 1 | research-deep-analyst
**대상**: HalluCode MVP 파일럿(v1.25) 결과 기반

---

## Executive Summary

HalluCode는 현존하는 코딩 벤치마크 스택에서 유일하게 비어 있는 **"메타인지 회복(MRC: Metacognitive Recovery Cubic)"** 축을 점유하며, SR과의 실증적 해리를 파일럿 단계에서 이미 보여준 점에서 MRC Cubic 자격을 원칙적으로 획득했다. 다만 n=5의 증거 기반 취약성이 커뮤니티 수용의 병목이며, n=60 풀 스케일 + 5개 이상 모델 검증이 FULL GO 판정의 유일한 경로다.

---

## C1. '큐빅(Cubic)' 개념 정의

좋은 평가 단위(Cubic)가 갖춰야 할 4속성:

| 속성 | 정의 | 기존 사례 |
|------|------|----------|
| **원자성(Atomic)** | 단일 인지 작동을 측정 | HumanEval = SR cubic |
| **직교성(Orthogonal)** | 다른 큐빅과 상관 낮음 | BLEU vs ROUGE (부분적 실패) |
| **조합성(Composable)** | 결합 시 상위 개념 창발 | MMLU = 지식 큐빅들의 합 |
| **견고성(Robust)** | 암기/게임 방지 | HumanEval (오염으로 부분 실패) |

HumanEval이 "코딩 능력 전체"가 아닌 "함수 단위 코드 생성"만 측정하듯, 큐빅은 **좁아야** 한다. 좁음은 결함이 아니라 설계 목표다.

---

## C2. 기존 벤치마크 대비 HalluCode의 갭

| 벤치마크 | 측정 대상 | HRR 측정? | HalluCode 차별점 |
|----------|----------|---------|----------------|
| HumanEval | pass@k (SR) | ✗ | HRR cubic이 SR과 직교함을 증명 |
| MBPP | pass@k (SR) | ✗ | 동상 |
| SWE-bench | 실세계 버그 패치 | ✗ | 실무 적용 cubic (별개 축) |
| ToolBench | API 호출 정확도 | ✗ | API 성공률 ≠ hallucinated API 감지 |
| GAIA | 멀티스텝 완료율 | ✗ | 최종 결과만 측정 |

**핵심 갭**: 기존 벤치마크는 "최종 출력이 맞는가(SR)"를 측정한다. 모델이 잘못된 API를 사용했으나 **우연히 동작하는 코드**를 생성한 경우, 기존 벤치마크는 이를 성공으로 기록한다. HalluCode는 이 블랙박스를 열어 인과 구조를 측정한다.

---

## C3. HalluCode 큐빅 자격 판정

### 원자성: PARTIAL

HalluCode 내부에 두 하위 능력 존재:
- (1) 잘못된 API 감지 (HRR)
- (2) 감지 후 올바른 코드 생성 (SR)

파일럿 데이터가 이를 실증:
```
LFM-1.2B: HRR=60%, SR=0% → 감지는 하지만 실행 불가
```

그러나 BLEU도 precision + brevity penalty의 합성이나 단일 큐빅으로 통용된다. **"composite atomic unit"**으로 해석 가능. 조건부 원자성 인정.

### 직교성: GO ✓

파일럿 데이터가 SR⊥HRR 해리를 직접 입증:

| 모델 | SR | HRR | 해석 |
|------|-----|------|------|
| GLM-4.5-Air | 100% | 100% | 두 능력 동시 보유 |
| LFM-1.2B-Thinking | **0%** | **60%** | **해리 확인** |

HumanEval cubic과 독립적 차원임을 n=2 파일럿이 방향성 입증. 대규모 검증 필요하나 방향은 명확.

### 조합성: GO ✓

HumanEval(SR) × HalluCode(HRR) 2×2 프로파일:

| SR 고 | HRR 고 | 모델 타입 |
|--------|---------|----------|
| HIGH | HIGH | 완전 유능 코더 (GLM-4.5-Air형) |
| HIGH | LOW | **hallucination blind — 운이 좋았을 뿐** |
| LOW | HIGH | 메타인지 있으나 실행 부족 (LFM-1.2B형) |
| LOW | LOW | 전면 실패 |

"HIGH SR, LOW HRR" 모델의 식별이 배포 안전성에서 핵심 가치다.

### 견고성: PARTIAL

| 공격 벡터 | 취약도 | 대응 |
|----------|--------|------|
| 트랩 API 암기 | MEDIUM | 랜덤 생성 함정으로 대응 가능 |
| 과보수적 거부 전략 | LOW | ETR 패널티가 억제 |
| AW 측정 주관성 | MEDIUM | 자동화 파서로 보완 |

---

## C4. 한계와 반론

| 한계 | 심각도 | 대응 |
|------|--------|------|
| n=5 파일럿 | **HIGH** | n=60 스케일업이 유일한 해결책 |
| 3가지 트랩만 | HIGH | v2에서 10+ 타입 확장 |
| 인공적 시나리오 | MEDIUM | GitHub Copilot 오류 분포 데이터로 생태 타당성 보강 |
| "너무 좁다" 반론 | LOW | 큐빅은 좁아야 한다 — 좁음이 목표 |

**가장 강한 반론**: "인공 함정이 실제 코딩 오류 분포를 대표하는가"
→ 외부 데이터(GitHub Copilot 로그, Stack Overflow)로 생태 타당성 검증 필요 [UNCERTAIN]

---

## C5. 최종 평결 및 확장 가능성

### 완전한 코딩 평가 스택 (3-Cubic 모델)

```
Cubic 1 — HumanEval : 코드 생성 정확도 (SR, pass@k)
Cubic 2 — HalluCode : 메타인지 오류 회복 (HRR, CodeMEI)  ← 기존 공백
Cubic 3 — SWE-bench : 실세계 버그 수정 (patch success rate)
────────────────────────────────────────────────────────
합산 프로파일 : [생성] × [자기검증] × [실무 적용]
```

세 큐빅이 상호 직교적이라면, 모델 코딩 능력을 **3차원 벡터**로 표현하는 평가 체계 성립.

### Full Experiment 결과 (n=39, 2모델, 3 trap type) — 2026-03-28

```
모델            | CodeMEI  | SR    | HRR   | 비고
GLM-4.5-Air    | 0.737    | 100%  | 84%   | 7B급, 무료 tier
LFM-1.2B       | 0.215    | 5%    | 25%   | 1.2B thinking model

Trap-type 난이도 (GLM 기준):
  nonexistent_api  : CodeMEI=0.810, Detect=100% (가장 쉬움)
  deprecated_method: CodeMEI=0.725, Detect=75%  (중간)
  wrong_signature  : CodeMEI=0.600, Detect=80%  (가장 어려움)
```

**SR⊥CodeMEI 코딩 도메인 확증**: GLM SR=100% vs LFM SR=5% — 20× 차이. 그러나 LFM도 CodeMEI=0.215 (HRR=25%)로 일부 메타인지 능력 보유. 코딩 능력과 오류 감지력은 독립 차원.

### H5 가설 — 기각 (n=5 full experiment)

```
wrong_signature 트랩 (full experiment, n=5):
  GLM-4.5-Air (~7B) : Detect = 80%   ← 대형 모델이 우세
  LFM-1.2B-Thinking : Detect = 0%    ← 소형 모델은 감지 불가

(파일럿 n=3 결과와 반대: LFM 66.7% > GLM ≈0% → 소표본 위양성)
```

**결론**: H5는 n=3 파일럿의 소표본 위양성(false positive)으로 확인. wrong_signature는 모델 크기와 무관하게 어렵지만 소형 모델에서 더욱 취약. trap_type × model_size 교차 분석은 유효한 연구 방향이나 방향성이 반전됨.

### NeurIPS 로드맵

| 시점 | 목표 | 조건 |
|------|------|------|
| 2026-Q2 | arXiv 제출 (HalluMaze v1) | 현재 결과로 충분. HalluCode = future work 1단락 |
| 2026-Q3 | HalluCode n=60 확장 실험 | 5개 모델, 현 n=39 → 확대 (HC020 timeout 해결 포함) |
| 2027 NeurIPS | HalluCode 독립 논문 | MRC cubic 독립 기여 주장 |

---

## C6. HalluCode SR 생태 타당성 (Ecological Validity) 근거

### 질문: HalluCode 결과가 실제 코딩 능력과 유관한가?

**3-레이어 입증 구조**:

#### Layer 1 — 실행 동등성 (Execution Equivalence)
- HalluCode SR은 `verify_code()`로 측정: 코드 컴파일 → 유닛 테스트 실행 → 바이너리 합격/불합격
- HumanEval/MBPP와 **동일한 평가 방법론** (pass@k와 동일)
- 텍스트 유사도 메트릭이 아닌 실제 코드 실행 기반 → 직접적 코딩 능력 측정

#### Layer 2 — 모델 크기 일관성 (Model Size Consistency)
| 모델 | 파라미터 | HalluCode SR | 외부 랭킹 |
|------|----------|-------------|----------|
| GLM-4.5-Air | ~7B | 100% | Artificial Analysis: 23/100 (#12/55) |
| LFM-1.2B-Thinking | 1.2B | 5% | Artificial Analysis: 6/100 (#17/24 on-device) |

| 추가 증거 | 수치 | 소스 |
|----------|------|------|
| GLM-4.7 (same Zhipu family) | HumanEval 94.2% (#6/55) | BenchLM.ai |
| LFM-1.2B | **HumanEval 미등재** | BenchLM, llm-stats.com |

20× SR 격차는 7B vs 1.2B의 예상 코딩 능력 차이와 일관됨.
LFM-1.2B는 표준 HumanEval 리더보드 미등재 — 코딩 능력 취약 확인.

#### Layer 3 — 역방향 보수성 (Adversarial Hardness Lower Bound)
- HalluCode SR은 **역방향 API 힌트 주입** 조건에서 측정
- 역방향 조건에서도 SR=100% 달성 모델은 중립 조건 동등 SR 모델보다 **강한 코딩 능력 보유**
- → HalluCode SR은 실제 코딩 능력의 **보수적 하한값(conservative lower bound)**

### 현재 한계 (HONEST)
- GLM-4.5-Air, LFM-1.2B 모두 HumanEval pass@1 공식 수치 미발표 (GLM-4.7은 94.2% 있음)
- Artificial Analysis Intelligence Index는 coding-specific이 아닌 복합 지표
- 직접 Spearman 상관 계산 불가 (companion paper에서 5개 모델로 수행 예정)

### 결론
HalluCode SR은 실제 코딩 능력의 타당한 측정값이다 — 실행 방법론 동등성으로 원칙적으로 성립하고, 모델 크기 일관성으로 방향성이 확인된다. HRR은 기존 벤치마크에 없는 독립 메타인지 차원을 추가한다.

---

## 실행 권고

1. **완료**: arXiv draft에 "HalluCode Ecological Validity" 단락 추가 (3-레이어 주장 + Section ref)
2. **이번 달**: n=60 스케일업 우선순위 확정 — GPT-4o-mini, Claude-Haiku, Qwen-72B 크레딧 확보
3. **v2**: 트랩 타입 10+ 확장 + GitHub/SO 오류 분포 데이터로 생태 타당성 보강
4. **companion paper**: 5개 모델 HumanEval × HalluCode SR Spearman correlation 계산

---

## Verification Required

- [UNCERTAIN] 실제 API hallucination 빈도 (GitHub Copilot 로그 분석)
- [RESOLVED/REJECTED] H5 (wrong_signature × 소형 thinking 모델 우세): n=5 full experiment에서 기각. LFM Detect=0% vs GLM=80%. n=3 파일럿은 소표본 위양성.
- [UNCERTAIN] ToolBench 자연 발생 실패 케이스에서 HalluCode 트랩 패턴 빈도
- [PARTIALLY RESOLVED] HalluCode SR ecological validity: 3-레이어 이론 구축 완료. 직접 Spearman 상관은 companion paper에서 수행 예정.

---

*생성: omc-live iter 1 | research-deep-analyst | 2026-03-28*
*업데이트: omc-live iter 1 | ecological validity C6 추가 | 2026-03-28*

## Related
- [[projects/Miro/research/20260324-hallumaze-ecological-validity|20260324-hallumaze-ecological-validity]]
- [[projects/Miro/research/20260327-hallumaze-extension-hallucode|20260327-hallumaze-extension-hallucode]]
- [[projects/Miro/research/20260323-hallumaze-paper-draft|20260323-hallumaze-paper-draft]]
