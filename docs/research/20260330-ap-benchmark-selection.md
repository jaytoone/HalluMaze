# [expert-research-v2] AP Booster 다음 코드 벤치마크 선정
**Date**: 2026-03-30  **Skill**: expert-research-v2

## Original Question
AP Booster (Adversarial Priming) 다음 실험 대상 공인 코드 벤치마크 선정. 현재 상황: HumanEval-Trap (GLM Δ=+0.575 p<0.001, Qwen3.5 detection=100%/ability-moderated), MBPP-Easy-Trap (pooled p=0.031, n=42/45, Cohen h=0.484). 목표: NeurIPS 2026 E&D Track reviewer를 위한 추가 external validity. 후보: DS-1000, BigCodeBench, EvalPlus.

---

## Agent Response Summary

### Deep Analyst
- **BigCodeBench #1**: Requirements: 섹션 injection 자연스러움 (FACT-7 confirmed), 139 libs × 7 domains = domain shift 증거, ICLR 2025 Oral = reviewer 인지도, instruct/complete ablation 가능
- **EvalPlus REJECTED**: HumanEval 상위 버전 → AP 관점에서 novelty 없음
- **DS-1000 conditional**: data science API injection 가능하나 GitHub 404, citation impact 낮음

### Fact Finder
- **[FACT-6]** BigCodeBench 필드: task_id, complete_prompt (docstring), instruct_prompt (NL), canonical_solution, test (unittest.TestCase)
- **[FACT-7]** complete_prompt 내 "Requirements: numpy, pandas" 섹션 명시 존재 → injection 지점 확인
- **[FACT-8]** 1,140 tasks, 139 libs, 7 domains, human 97% vs best model 60%
- **[FACT-9]** Docker "strongly recommended"; 대안: HF Space bigcodebench-evaluator API (remote, docker 불필요)
- **[FACT-11/12]** EvalPlus HumanEval 80x 확장 → pass@k 19-28% 하락. 코드 robustness 차원 추가
- **[FACT-5]** DS-1000 GitHub repo 404; HuggingFace 접근 가능
- BigCodeBench flakiness ~0.2% per run 공식 인정
- BigCodeBench-Hard subset: 148 tasks (전체 13%)

### Devil's Advocate (CRITICAL/MAJOR 발견)
- **CRITICAL-1**: Qwen3.5 HumanEval-Trap에서 AP(seed=100)와 Baseline(seed=200) 다른 seed 사용 → 다른 문제 비교 → 직접 비교 무효
- **CRITICAL-2**: AP system prompt가 "이 벤치마크에 FAKE API 있음"을 명시적으로 고지 → detection rate가 metacognitive ability가 아닌 instruction-following 측정일 가능성
- **MAJOR-1**: trap library 16개뿐 (7 nonexistent_api + 5 wrong_signature + 4 deprecated_method), 3개 벤치마크에 동일 trap 재사용 = generic trap recycling
- **MAJOR-2**: 풀링 방법론 불명확 (n=42/45 어떻게 도출?) → p-hacking 의심 가능
- **[FACT-CONFLICT]**: EvalPlus REJECTED 근거 약함 — FACT-11/12로 robustness 차원 측정 가능

---

## Cross-Validation Matrix

### 2-1. Fact Comparison (Analyst claims vs Fact Finder)

| Analyst Claim | Evidence Tag | Fact Finder Verification | Verdict |
|---------------|-------------|-------------------------|---------|
| BigCodeBench Requirements: injection 가능 | [ESTABLISHED] | FACT-7: docstring Requirements 섹션 확인 | **CONFIRMED** |
| 139 libs × 7 domains = domain shift | [ESTABLISHED] | FACT-8: 1,140 tasks, 139 libs, 7 domains | **CONFIRMED** |
| ICLR 2025 Oral = reviewer 인지도 | [REASONING] | Fact Finder 언급 있으나 명시 없음 | **UNVERIFIED** |
| instruct/complete ablation 가능 | [ESTABLISHED] | FACT-6: 두 필드 모두 존재 | **CONFIRMED** |
| EvalPlus = novelty 없음 | [REASONING] | FACT-11/12: robustness 차원 존재 | **CONTRADICTED** |
| DS-1000 citation impact 낮음 | [REASONING] | FACT-5: GitHub 404, community momentum 낮음 | **CONFIRMED** |

### 2-2. Critique Comparison (Analyst vs Devil's Advocate)

| DA Critique | Severity | Analyst Response | Resolution |
|------------|----------|-----------------|------------|
| Seed mismatch Qwen3.5 | CRITICAL | 언급 없음 | **VALID → 재실험 필요** |
| AP = instruction-following? | CRITICAL | 언급 없음 | **VALID → ablation 필요** |
| 16 trap 재사용 | MAJOR | 언급 있으나 blocking 조건 아님 | **VALID → 선행 조건** |
| Pooled p methodology | MAJOR | 언급 없음 | **PARTIAL → 명시 필요** |
| BigCodeBench flakiness | MAJOR | 언급 없음 | **MINOR → 문서화로 해결** |
| EvalPlus robustness 차원 | MAJOR | 기각 | **PARTIAL → 보조 실험으로 가능** |

### 2-3. Three-Party Consensus Matrix

| Topic | Deep Analyst | Devil's Advocate | Fact Finder | Consensus |
|-------|-------------|-----------------|-------------|-----------|
| BigCodeBench을 다음 벤치마크로 | #1 추천 | 조건부 동의 (선행조건 필요) | 강력 지지 (ICLR Oral, injection 확인) | **STRONG** |
| domain-specific trap 우선 개발 | 언급 없음 | MAJOR (blocking condition) | 확인 없음 | **CONTESTED → trap 개발 선행** |
| EvalPlus 기각 | 기각 | 조건부 반대 (robustness 차원) | FACT-11/12 반박 근거 제공 | **CONTESTED** |
| Qwen3.5 seed 재실험 | 언급 없음 | CRITICAL | seed 정보 확인 | **CONFIRMED REJECT → 재실험** |
| AP ablation (instruction-following) | 언급 없음 | CRITICAL | 확인 없음 | **UNRESOLVED → 선행 필요** |

---

## Final Conclusion

### Core Answer: BigCodeBench, 단 3개 선행 조건 완료 후

**BigCodeBench-Hard (148 tasks, instruct_prompt split)** 가 다음 실험 대상으로 최적이다. 단, 아래 3개 선행 조건을 완료하지 않으면 실험을 확장해도 scientific value가 없다.

### 선행 조건 (우선순위 순)

**[P0] AP ablation 실험 — CRITICAL (NeurIPS reviewer blocking risk)**
- AP system prompt를 3단계로 분리 실험:
  1. `Baseline`: 시스템 프롬프트 없음
  2. `AP-Light`: "API 사용 시 주의하라" (trap 존재 미언급)
  3. `AP-Full`: 현재 방식 "이 벤치마크에 FAKE API 의도적으로 포함됨"
- GLM-4.5-Air, HumanEval-Trap, n=20 per condition
- 목적: AP effect = metacognition vs instruction-following 구분
- 예상 결과: AP-Light < AP-Full이면 metacognition 증거; AP-Light ≈ AP-Full이면 instruction-following

**[P1] Trap library 확장 — MAJOR (generic recycling 차단)**
- 현재: 16 generic Python traps (3 벤치마크 재사용)
- 목표: BigCodeBench용 domain-specific traps 15개 추가
  - pandas fake method: `df.pivot_smart()`, `df.rolling_trim()`
  - numpy fake: `np.lstsq_regularized()`, `np.conv2d_fast()`
  - requests fake: `requests.get_async()`, `requests.Session.retry_on_429()`
  - sklearn fake: `model.fit_partial_cv()`, `cross_validate_bootstrap()`
- 구현: `scripts/bigcodebench_traps.py` 신규 생성

**[P2] Qwen3.5 HumanEval-Trap 재실험 — CRITICAL (data integrity)**
- 문제: AP(seed=100) vs Baseline(seed=200) — 다른 문제 비교
- 수정: 동일 seed=42 사용, 또는 seed를 인수로 받되 AP/Baseline 동일하게
- n=20 per condition, 같은 20개 문제에서 AP vs Baseline 비교

### 이후 BigCodeBench-Trap 구현

선행 조건 완료 후:
1. `bigcode/bigcodebench` HuggingFace에서 Hard split (148 tasks) 로드
2. `instruct_prompt`에 domain-specific fake library hint injection
3. AP/Baseline 비교 (n≥30 per condition, same problems)
4. HF Space evaluator 또는 Docker로 pass@1 측정
5. 통계: Fisher exact + Bootstrap CI + Cohen's h

### EvalPlus 재고

EvalPlus(HumanEval+)는 "domain shift"가 아닌 "robustness" 차원을 추가한다. BigCodeBench 이후 **Appendix 실험**으로 적합:
- HumanEval-Trap (현재 ~20 tasks) → HumanEval+-Trap (80x test suite)
- AP Booster가 더 robust한 코드를 생성하는지 측정
- 메인 결과가 아닌 보조 증거로 활용

### Actionable Recommendations

```
Week 1: P0 ablation (GLM-4.5-Air, HumanEval-Trap, 3조건 × n=20)
Week 2: P1 trap library 확장 (BigCodeBench domain-specific 15 traps)
         P2 Qwen3.5 seed 재실험
Week 3: BigCodeBench-Hard-Trap 파일럿 (n=15, 검증)
Week 4: BigCodeBench-Hard-Trap 전체 (n≥30, 논문 수준)
```

---

## Reference Sources
- [BigCodeBench paper (ICLR 2025)](https://arxiv.org/abs/2406.15877) — 1,140 tasks, 139 libs, 7 domains
- [DS-1000 paper (arXiv 2022)](https://arxiv.org/abs/2211.11501) — 1,000 data science tasks
- [EvalPlus paper (NeurIPS 2023)](https://arxiv.org/abs/2305.01210) — HumanEval 80x test augmentation
- [BigCodeBench GitHub](https://github.com/bigcode-project/bigcodebench) — problem schema, docker eval
- [BigCodeBench Evaluator HF Space](https://huggingface.co/spaces/bigcode/bigcodebench-evaluator)
- [DS-1000 HuggingFace Dataset](https://huggingface.co/datasets/xlangai/DS-1000)
- [BigCodeBench Leaderboard](https://huggingface.co/spaces/bigcode/bigcodebench-leaderboard)

---

## Further Investigation Needed
- AP ablation 실험 결과 (instruction-following vs metacognition 분리)
- BigCodeBench-Hard domain-specific trap이 GLM/Qwen에서 실제로 감지되는지 파일럿
- Docker vs HF Space evaluator 결과 일치도 확인
