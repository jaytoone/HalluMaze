# [expert-research] MARL-SL Multi-Model 검증 필요성 분석
**Date**: 2026-03-26  **Skill**: expert-research

## Original Question
MARL-SL을 다른 모델로도 검증해야 하는가? 현재 GLM-4.7 only (n=10) 결과로 논문 제출 시 reviewer가 어떤 비판을 할 수 있고, 어떤 추가 실험이 필요한가? Multi-model 검증의 학술적 필요성과 현실적 제약 조건 분석.

## Web Facts

[FACT-1] NeurIPS 2025 checklist에서 robustness to violations of assumptions을 명시적으로 요구. 단일 모델 결과만으로는方法的 가정의 강건성 입증 어려움.
- Source: https://neurips.cc/public/guides/PaperChecklist

[FACT-2] Benchmark Agreement Testing (BAT) 연구에 따르면, 새 벤치마크는 최소 2개 이상 기존 벤치마크와의 상관관계로 검증되어야 하며, 단일 벤치마크/모델 결과는 권위不足.
- Source: https://research.ibm.com/publications/benchmark-agreement-testing-done-right-a-guide-for-llm-benchmark-evaluation

[FACT-3] LLM-eval@NeurIPS 워크숍에서 multi-model lifecycle 전체에 걸친 robust methodology 강조.
- Source: https://sites.google.com/view/llm-eval-workshop

[FACT-4] Measuring what Matters (arXiv 2025) 연구: 445개 논문 체계적 검토 결과, 강력한 LLM 벤치마크는至少 3개 모델 이상での 검증이 표준.
- Source: https://arxiv.org/pdf/2511.04703

## Multi-Lens Analysis

### LENS 1: Domain Expert
1. **단일 모델 한계**: MARL-SL이 GLM-4.7에서만 동작한다는 가정은 방법론的一般화 가능성問題. Reviewer는 "이 효과가 모델 특정한 것 아닌가?" 질문必定.
2. **n=10 통계적 약점**: n=10은 preliminary result로 분류되며, 특히 MARL-SL의 SR=80% Wilson CI가 [44%, 97%]로 넓어 Eff v2 SR=50% CI와 overlap → 통계적 비유의 가능성.
3. ** novelty 기여도**: Single-Layer 아이디어는 기존 SPP (Solo Performance Prompting, Wang et al. 2023)와 유사성이 있으며, multi-model 재현 없이는 novel contribution으로 인정받기 어려움.

### LENS 2: Devil's Advocate
- **Overconfident**: "MARL-SL이 항상 우수"라는 주장 → GLM-4.7 خاص推理能力에 기인할 가능성 무시.
- **Missing**: Claude 3.7 Sonnet (최고 MEI=0.774 모델)에서 MARL-SL 적용 시 결과 차이 未検証.
- **Counterargument**: MARL-SL이 1 call으로 동작하는 것은 GLM-4.7의 긴 context window + 내부 CoT () 특성에依存할 수 있음.

### LENS 3: Practical Synthesizer
- **Confirmed**: 추가 모델 검증 필요 (至少 1개 이상,最好是 Claude or Llama)
- **Challenged**: n=10→n=30 확대 + multi-model 2개 이상 = 최소 40 trial 추가 소요
- **Missing**: ablation study (각 layer 제거 실험)도 reviewer 요청 예상

## Final Conclusion

### 권장 추가 실험
1. **Multi-model 검증**: GLM-4.7 외 1개 모델 (권장: Claude 3.7 Sonnet 또는 Llama-4-Maverick)
2. **Sample size 확대**: n=10→n=30 (MARL-SL)
3. **Ablation**: 5개 layer 각 제거 시 MEI 변화 측정
4. **SPP 비교**: Solo Performance Prompting과의 성능 비교 (선행연구 대비)

### 현실적 제약
- API 비용: 40 trial × $0.5-1.0 ≈ $20-40 추가 소요
- 시간: 약 2-4시간 (모델별 1-2시간)

###論文投稿 전략
- 현재 결과 → "preliminary result"로 명시하고 "planned extensions"에 multi-model 검증 포함
- Alternative: Abstract에서 "demonstrated on GLM-4.7"으로 범위 한정

## Sources
- https://neurips.cc/public/guides/PaperChecklist
- https://research.ibm.com/publications/benchmark-agreement-testing-done-right-a-guide-for-llm-benchmark-evaluation
- https://sites.google.com/view/llm-eval-workshop
- https://arxiv.org/pdf/2511.04703