# [expert-research] AP Booster 코드 벤치마크 다양화 전략
**Date**: 2026-03-30  **Skill**: expert-research-v2

## Original Question
AP Booster (Adversarial Priming)의 코드 벤치마크 다양화 전략 — HumanEval, MBPP 외 어떤 공개 코딩 벤치마크를 추가해야 NeurIPS 2026 reviewer를 설득할 수 있는가?

현재 상황: GLM-4.5-Air로 HumanEval-Trap(pass@1=0.875), MBPP-Trap(detection=85.7%), MBPP-Easy AP v2 with Qwen3.5-122B(pass@1=0.538). 목표: AP Booster가 모델-독립적, 벤치마크-독립적임을 입증.

## Agent Response Summary

### Deep Analyst
**Domain**: NeurIPS 2026 벤치마크 외적 타당성 (External Validity in LLM Coding Benchmarks)

**Key Points**:
1. **NeurIPS 2026 E&D Track 요구사항** [ESTABLISHED] — "Evaluations & Datasets" (renamed from D&B)
   - 구성 타당성(construct validity), 판별 타당성(discriminant validity), Croissant 포맷 필수
   - 3개 이상 모델 × 3개 이상 벤치마크에서의 효과 입증 권장
2. **AP injection 가능성 순위** [REASONING]
   - DS-1000: numpy/pandas fake methods → VERY HIGH
   - BigCodeBench: `Requirements:` section → VERY HIGH
   - EvalPlus: HumanEval+ robustness check → HIGH (but overlap)
   - LiveCodeBench: algorithm-only → LOW
   - SWE-bench: attribution problem → MODERATE
3. **Benchmark-independence 주장의 허점** [UNCERTAIN → CRITICAL]
   - 현재 16개 generic trap을 모든 벤치마크에 재활용 → genuine independence 아님
   - Domain-specific trap library 설계 필요

**Risks**:
- Generic trap recycling이 reviewer에게 발각될 경우 claim 전체 붕괴
- Croissant 포맷 미준수로 NeurIPS 제출 자체 거부 가능

### Fact Finder
**Collected Facts (web-sourced)**:

- [FACT-1] NeurIPS 2026 E&D Track은 "Evaluations & Datasets"로 명칭 변경 확정 (source: neurips.cc)
- [FACT-2] Croissant metadata format이 HuggingFace 표준으로 채택됨 (source: mlcommons.org/croissant)
- [FACT-3] BigCodeBench: 1,140 tasks, 7 domains (math, string processing, ML, etc.), `Requirements:` section에 API hint 주입 가능 (source: bigcode-project.org)
- [FACT-4] DS-1000: 1,000 problems, numpy/pandas/sklearn 도메인, library-specific operations 중심 (source: ds1000-code-generation.github.io)
- [FACT-5] EvalPlus: HumanEval 기반 추가 테스트케이스, robustness 강화 목적 (source: evalplus.github.io)
- [FACT-6] Fake library hallucination 수용률 99% (arXiv 2509.22202) — LLM이 존재하지 않는 패키지명도 사용
- [FACT-7] HumanEval score와 package hallucination 역상관 (FACT-17 in analysis)
- [FACT-8] LiveCodeBench: 실제 competitive programming 문제, 알고리즘 중심 — fake API injection 부자연스러움

### Devil's Advocate
**CRITICAL Critiques**:

1. **[CRITICAL] Generic trap = fake benchmark-independence**
   - 동일 16개 trap(fake_dict_method, fake_str_method 등)을 HalluCode, HumanEval-Trap, MBPP-Trap 전부에 재사용
   - "벤치마크-독립"이 아닌 "동일 trap을 다른 포맷에 붙인 것" — reviewer가 trap list를 보면 즉시 발각
   - Resolution: **VALID** → domain-specific trap library 설계 필수

2. **[CRITICAL] 낮은 sample size로 통계적 독립성 주장 불가**
   - HumanEval-Trap n=8, MBPP-Easy n=13 — NeurIPS 기준 underpowered
   - "모델-독립"도 GLM + Qwen 2개뿐 → 충분하지 않음
   - Resolution: **VALID** → n≥30 per condition 필요

3. **[MAJOR] AP 효과가 trap detection에서만 발생하는지 code quality 전반에서 발생하는지 미분리**
   - "system prompt only, no traps" ablation 조건 없음
   - 현재 setup으로는 AP가 trap 회피에만 효과적인지 일반 coding quality 향상인지 구분 불가
   - Resolution: **VALID** → ablation study 필요

4. **[MINOR] DS-1000은 실행 환경 복잡도 높음**
   - numpy/pandas 실행 + 검증 로직 복잡 — 구현 공수 과다

## Cross-Validation Matrix

| Topic | Deep Analyst | Devil's Advocate | Fact Finder | Consensus |
|-------|-------------|-----------------|-------------|-----------|
| NeurIPS E&D Track 요건 | Construct+Discriminant validity | [OVERCONFIDENT] Croissant 미준수 시 거부 | FACT-1,2 확인 | CONFIRMED-STRONG |
| DS-1000 injection feasibility | VERY HIGH | [MINOR] 구현 공수 높음 | FACT-4 확인 | STRONG |
| BigCodeBench injection feasibility | VERY HIGH | 동의 | FACT-3 확인 | CONFIRMED-STRONG |
| Generic trap recycling = 문제 | [UNCERTAIN] | [CRITICAL] 심각한 문제 | FACT-6,7 관련 | STRONG — benchmark-independence 주장 재설계 필요 |
| EvalPlus 추가 가치 | HIGH but overlap | [MAJOR] HumanEval subset — new dimension 아님 | FACT-5 확인 | CONTESTED |
| LiveCodeBench | LOW | 동의 | FACT-8 확인 | CONFIRMED (PASS) |
| Statistical power | 현재 underpowered | [CRITICAL] n≥30 필수 | 업계 기준 확인 | CONFIRMED-STRONG |

## Final Conclusion

### 추천 벤치마크 추가 순위

| 순위 | 벤치마크 | AP Injection | 추천 이유 |
|------|---------|-------------|---------|
| **1** | **DS-1000** | VERY HIGH | numpy/pandas domain — genuine domain shift, library-specific |
| **2** | **BigCodeBench** | VERY HIGH | `Requirements:` section injection, 7 domains × 1140 tasks |
| **3** | EvalPlus | HIGH | HumanEval robustness만 — new dimension 아님, 선택적 |
| PASS | LiveCodeBench | LOW | algorithm-only, injection 부자연스러움 |
| PASS | SWE-bench | MODERATE | attribution problem, scope mismatch |

### 필수 선행 조건 (CRITICAL)

**현재 generic trap 재활용 문제 해결 없이는 벤치마크 추가가 무의미.**

1. **Domain-specific trap library 설계** (per benchmark):
   - DS-1000용: fake pandas methods (`df.groupby_agg()`, `pd.read_csv_fast()` 등)
   - BigCodeBench용: domain별 fake stdlib calls (math, string, ML)
   - 각 10-15개 trap, 실제로는 존재하지 않는 API여야 함

2. **통계 power 확보**: n≥30 per condition (현재 n=8~15 → underpowered)

3. **Ablation study**: "AP system prompt + no traps" 조건 추가 → 효과 소스 분리

4. **NeurIPS E&D Track 준비**: Croissant 포맷 HuggingFace Dataset 카드 → `hf_dataset_readme.md` 업데이트

### 실행 우선순위

1. MBPP-Easy n≥30 재실행 (빠름, NIPA 이미 준비됨)
2. DS-1000 domain-specific trap library 설계 + 파일럿 (n=20)
3. BigCodeBench injection script (구조 파악 후)
4. HumanEval-Trap n=30 재실행 (Qwen3.5-122B)

## Reference Sources
- NeurIPS 2026 E&D Track: https://neurips.cc/Conferences/2026/CallForDatasetsBenchmarks
- BigCodeBench: https://bigcode-project.org/docs/projects/bigcodebench/
- DS-1000: https://ds1000-code-generation.github.io/
- EvalPlus: https://evalplus.github.io/leaderboard.html
- Fake library hallucination: arXiv 2509.22202
- Croissant format: https://mlcommons.org/croissant

## Further Investigation Needed
- DS-1000 문제 구조 세부 파악 (injection point 확정)
- BigCodeBench `Requirements:` section 포맷 확인
- Croissant 포맷 준수 공수 파악
