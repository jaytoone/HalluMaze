# HalluMaze Documentation Index

| 파일 | 설명 | 날짜 |
|------|------|------|
| scripts/run_aibooster_standard.py | AI Booster v3 (General Metacognitive Middleware) 실험 스크립트: 표준 HumanEval (no trap) + 3-step ANALYZE/VERIFY/CODE 미들웨어 vs Baseline. H_AB: 일반 코딩 벤치마크 raw pass@1 향상 검증 | 2026-03-30 |
| docs/research/20260330-ap-benchmark-selection.md | expert-research-v2 3-agent 파이프라인: BigCodeBench-Hard(148 tasks, instruct_prompt) 최종 추천 + 3개 선행조건 (AP ablation, trap library 확장 15개, Qwen3.5 seed 재실험). DA CRITICAL: AP effect = instruction-following? 분리 ablation 필수 | 2026-03-30 |
| experiment_results/humaneval_trap_qwen35_ap.json | HumanEval-Trap AP Booster (Qwen3.5-122B NIPA H200, n=17 valid, seed=100): pass@1=1.000, detection=100%. 모델-독립성 확증: GLM Δ=+0.575 vs Qwen ability-moderated (ceiling effect) | 2026-03-30 |
| experiment_results/humaneval_trap_qwen35_baseline.json | HumanEval-Trap Baseline (Qwen3.5-122B, n=17 valid, seed=200): pass@1=1.000†. †강력한 모델은 trap 언급해도 코드는 정확하게 작성 (ceiling at baseline) | 2026-03-30 |
| experiment_results/mbpp_easy_trap_qwen35_ap_v2_n30.json | MBPP-Easy-Trap AP v2 (Qwen3.5-122B, n=29 valid, seed=100): pass@1=0.517, detection=0.931. Definitive n=30 run confirming pilot trend | 2026-03-30 |
| experiment_results/mbpp_easy_trap_qwen35_baseline_n30.json | MBPP-Easy-Trap Baseline (Qwen3.5-122B, n=30 valid, seed=200): pass@1=0.267. Definitive n=30 baseline | 2026-03-30 |
| experiment_results/mbpp_easy_n30_stats.json | MBPP-Easy-Trap n=30 통계: Fisher p=0.064, Cohen h=0.519, Bootstrap CI=[+0.013,+0.489] | 2026-03-30 |
| experiment_results/mbpp_easy_pooled_stats.json | MBPP-Easy-Trap POOLED 통계 (n=42 AP / n=45 baseline): Δ=+0.235, h=0.484, OR=2.71, p=0.031 (significant). Bootstrap CI=[+0.030,+0.422] | 2026-03-30 |
| docs/research/20260330-ap-benchmark-diversification.md | AP Booster 코드 벤치마크 다양화 전략 (expert-research-v2): DS-1000(1위)>BigCodeBench(2위)>EvalPlus>PASS. CRITICAL: generic trap recycling → domain-specific trap library 설계 필요. NeurIPS E&D Track 요건 분석 | 2026-03-30 |
| experiment_results/hallucode_full.json | HalluCode Full Experiment: 2모델(GLM n=19, LFM n=20)×3 trap type. GLM CodeMEI=0.737/SR=100%, LFM CodeMEI=0.215/SR=5%. SR⊥CodeMEI 코딩 도메인 확증 | 2026-03-28 |
| experiment_results/hallucode_baseline_glm.json | HalluCode Baseline GLM-4.5-Air (n=19 merged). SR=78.9%/HRR=68.4%/MEI=0.579 vs MARL-SL SR=100%/HRR=84.2%/MEI=0.737. H6 교차검증: 대형모델 MARL-SL +ΔCodeMEI=+0.158 | 2026-03-29 |
| experiment_results/hallucode_baseline_lfm.json | HalluCode Baseline Ablation: LFM-1.2B no-MARL (n=19). SR=68.4%/HRR=0% vs MARL-SL SR=5%/HRR=25%. H6 소형모델 MARL-SL −ΔCodeMEI=−0.059 | 2026-03-29 |
| scripts/run_hallucode_baseline.py | HalluCode Baseline 단순 프롬프트 스크립트 (no MARL-SL, ablation용) | 2026-03-29 |
| scripts/run_hallucode_booster.py | HalluCode AP Booster 스크립트: Adversarial Priming (booster/marl_sl/baseline 3가지 prompt-type 지원) | 2026-03-29 |
| scripts/analyze_hallucode_stats.py | HalluCode NeurIPS 통계분석: Bootstrap CI (n=2000) + Wilcoxon + Cohen's d + power analysis | 2026-03-29 |
| experiment_results/hallucode_booster_glm.json | GLM-4.5-Air AP Booster n=19 완전: CodeMEI=0.821, SR=100%, HRR=84.2%. H7 CONFIRMED (vs MARL-SL Δ=+0.084, d=+2.25, p<0.001) | 2026-03-29 |
| experiment_results/hallucode_booster_lfm.json | LFM-1.2B AP Booster n=17 valid: CodeMEI=0.371, SR=56.9%, HRR=23.5%. H7 CONFIRMED (vs MARL-SL Δ=+0.182, d=+0.57, p=0.038) | 2026-03-29 |
| experiment_results/hallucode_stats.json | HalluCode 통계 결과 JSON: Bootstrap CI, Wilcoxon p-values, Cohen's d, power analysis (all 6 comparisons) | 2026-03-29 |
| scripts/build_hallucode_full.py | HalluCode Full Experiment 결과 병합+통계 산출 스크립트 | 2026-03-28 |
| docs/research/20260328-hallucode-cubic-evaluation.md | HalluCode MRC Cubic 자격 평론: C6 생태 타당성, C7 H6 교차검증, C8 H7 AI Booster CONFIRMED — AP > MARL-SL for ALL models (GLM n=19 완전, CodeMEI 0.821) | 2026-03-29 |
| scripts/run_hallucode_mvp.py | HalluCode MVP 파일럿: False API Hint 20문제 + MARL-SL 코딩 프롬프트 + CodeMEI 검증 파이프라인 | 2026-03-27 |
| docs/research/20260327-hallumaze-extension-hallucode.md | HalluCode/HalluTool 확장 연구: 선행 연구 갭 분석, MARL-SL 코딩 매핑, CodeMEI 설계, MVP 실험 설계안 | 2026-03-27 |
| docs/misc/ontolo-biz-unconscious-purchase-20260327.md | ontolo-agent biz-unconscious-purchase — HF 포스트 CTA 최적화 분석 | 2026-03-27 |
| docs/research/20260323-hallumaze-paper-draft.md | HalluMaze 논문 초안 (NeurIPS 2026 target) | 2026-03-23 |
| docs/research/20260323-hallumaze-extension-todos.md | 확장 연구 방향 분석 (expert-research-v2) | 2026-03-23 |
| docs/research/20260324-marl5stage-fix-solutions.md | MARL 5-stage 성능 저하 해결책 연구 (expert-research-v2) | 2026-03-24 |
| docs/research/20260324-hallumaze-ecological-validity.md | HalluMaze 생태학적 타당성 확장 방향 | 2026-03-24 |
| docs/hf_post.md | HuggingFace community blog post about HalluMaze benchmark | 2026-03-24 |
| docs/hallumaze_arxiv.tex | arXiv LaTeX paper draft (NeurIPS 2026 format) | 2026-03-24 |
| docs/hallumaze.bib | BibTeX references for arXiv paper | 2026-03-24 |
| docs/hf_post_v2.md | HF 커뮤니티 포스트 v2 (트렌딩 스타일, 24시간 후 포스팅 예정) | 2026-03-25 |
| experiment_results/humaneval_trap_glm_ap.json | HumanEval-Trap AP Booster (GLM, n=8 valid): pass@1=0.875, trap_detection=87.5%. 동일 AP 프롬프트 공인 벤치마크 전이 입증 | 2026-03-29 |
| experiment_results/humaneval_trap_glm_baseline.json | HumanEval-Trap Baseline (GLM, n=10 valid): pass@1=0.300. Δ=+0.575 vs AP Booster | 2026-03-29 |
| experiment_results/humaneval_correlation_analysis.json | HalluCode ↔ HumanEval 외적 타당성 분석: HumanEval-Trap Δ=+0.575, d=+1.16, 크기-능력 일관성 정성 분석 | 2026-03-29 |
| scripts/run_humaneval_trap.py | HumanEval-Trap 실험 스크립트: false API hint 주입 + AP Booster/baseline 비교 (pass@1 측정) | 2026-03-29 |
| scripts/analyze_humaneval_correlation.py | HalluCode ↔ HumanEval 상관 분석: HumanEval-Trap 결과 + Spearman 상관 (n≥5 시 활성화) | 2026-03-29 |
| experiment_results/mbpp_trap_glm_ap.json | MBPP-Trap AP Booster (GLM, n=14 valid): pass@1=0.000, trap_detection=85.7%. MBPP 난이도 과제: AP 탐지 전이 확인, base coding quality가 bottleneck | 2026-03-29 |
| experiment_results/mbpp_trap_glm_baseline.json | MBPP-Trap Baseline (GLM, n=11 valid): pass@1=0.000, trap_used=45.5%. 난이도 moderator 확인 | 2026-03-29 |
| experiment_results/hallumaze_spearman_analysis.json | HalluMaze MEI × HumanEval Spearman ρ=+0.30 (p=0.32, n=13) — MEI는 코딩 능력(HumanEval)과 독립적. GPT-4o(HE=90.2%) → MEI rank 13. HalluMaze 고유성 입증 | 2026-03-29 |
| scripts/analyze_hallumaze_coding_spearman.py | HalluMaze 13-model MEI × 공개 HumanEval pass@1 Spearman 분석 스크립트 | 2026-03-29 |
| scripts/run_mbpp_trap.py | MBPP-Trap 실험 스크립트: MBPP datasets 로드 + 3-trap 주입 + AP/baseline pass@1 측정 | 2026-03-29 |
| scripts/run_mbpp_easy_trap.py | AP Booster v2 + MBPP-Easy 필터: 3-step prompt(DETECT→ALTERNATIVE→CODE) + ref solution ≤7줄 필터. 난이도 교란 제거 후 AP 효과 분리 측정 | 2026-03-29 |
| experiment_results/mbpp_easy_trap_qwen35_ap_v2.json | MBPP-Easy-Trap AP v2 (Qwen3.5-122B NIPA H200, n=13 valid): pass@1=0.538, detection=92.3%. 난이도 unblock 확인. | 2026-03-30 |
| experiment_results/mbpp_easy_trap_qwen35_baseline.json | MBPP-Easy-Trap Baseline (Qwen3.5-122B, n=15): pass@1=0.333. Δ=+0.205 vs AP v2 | 2026-03-30 |
| experiment_results/mbpp_easy_stats.json | MBPP-Easy-Trap 통계: Bootstrap CI, Fisher exact p=0.24 (underpowered), Cohen h=0.417 | 2026-03-30 |
| docs/hf_post_v4.md | HF 커뮤니티 포스트 v4 (HalluCode AP Booster 전용: 80-token prompt beats MARL-SL, GLM d=+2.25 p<0.001) | 2026-03-29 |
| docs/hf_dataset_readme.md | HuggingFace Dataset 카드 — 13-model 리더보드, 파일 목록, 인용 정보 (HF 업로드 ready) | 2026-03-29 |
| docs/hf_post_v3.md | HF 커뮤니티 포스트 v3 (Claude 4.x 확장 결과 포함, 13모델 리더보드) | 2026-03-26 |
| experiment_results/claude4x_pilot.json | Claude 4.x Pilot (n=5, Phase A): Haiku-4.5/Sonnet-4.5/Sonnet-4.6 초기 결과 | 2026-03-26 |
| experiment_results/claude4x_full.json | Claude 4.x Full (n=60 each): Haiku-4.5 SR=5%, Sonnet-4.5 SR=36.7% MEI=0.783 #1, Sonnet-4.6 SR=60% MEI=0.545 | 2026-03-26 |
| docs/research/20260325-marl-efficiency-research.md | MARL 5-Stage 효율성 혁신 방법론 (expert-research-v2, token/time optimization) | 2026-03-25 |
| experiment_results/marl_efficient_glm.json | MARL Efficient v1: adaptive token budget (n=10, MEI=0.697, 64% token savings) | 2026-03-25 |
| experiment_results/marl_efficient_v2_glm.json | MARL Efficient v2: early exit + adaptive budget (n=10, MEI=0.802, SR=0.50, 64% token savings) | 2026-03-25 |
| experiment_results/marl_single_layer_glm.json | MARL-SL: 5-roles in 1 call via role-tagged output (n=10, MEI=0.829, SR=0.80, 1.60 calls, 117s, -74% calls vs Eff v2) | 2026-03-26 |
| scripts/run_marl_single_layer_glm.py | MARL Single-Layer runner: GLM-4.7, role-tagged prompt, PathValidator gate | 2026-03-26 |
| experiment_results/baseline_timing_glm.json | GLM-4.7 baseline single-call timing (n=6, mean=36.5s, min=8.3s, max=111.9s) | 2026-03-26 |
| docs/research/20260326-marl-sl-multi-model-validation.md | MARL-SL Multi-Model 검증 필요성 분석 (reviewer 비판 대비) | 2026-03-26 |
| scripts/run_marl_sl_openrouter.py | MARL-SL OpenRouter runner (multi-model validation) | 2026-03-26 |
| experiment_results/marl_sl_openrouter.json | MARL-SL multi-model validation results (Llama/GPT: 0% valid) | 2026-03-26 |
| docs/figures/fig1_mei_leaderboard.png | Figure 1: MEI leaderboard bar chart (600dpi) | 2026-03-24 |
| docs/figures/fig2_hrr_sr_scatter.png | Figure 2: HRR vs SR dissociation scatter (600dpi) | 2026-03-24 |
| docs/figures/fig3_cost_mei.png | Figure 3: MEI vs API cost scatter (600dpi) | 2026-03-24 |

## Related
- [[projects/Miro/research/20260328-hallucode-cubic-evaluation|20260328-hallucode-cubic-evaluation]]
- [[projects/Miro/research/20260327-hallumaze-extension-hallucode|20260327-hallumaze-extension-hallucode]]
- [[projects/Miro/research/20260323-hallumaze-paper-draft|20260323-hallumaze-paper-draft]]
- [[projects/Miro/research/20260330-ap-benchmark-selection|20260330-ap-benchmark-selection]]
- [[projects/Miro/research/20260330-ap-benchmark-diversification|20260330-ap-benchmark-diversification]]
- [[projects/Miro/research/20260326-marl-sl-multi-model-validation|20260326-marl-sl-multi-model-validation]]
- [[projects/Miro/research/20260323-hallumaze-extension-todos|20260323-hallumaze-extension-todos]]
- [[projects/Miro/research/20260325-marl-efficiency-research|20260325-marl-efficiency-research]]
