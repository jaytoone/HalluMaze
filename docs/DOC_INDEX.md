# HalluMaze Documentation Index

| 파일 | 설명 | 날짜 |
|------|------|------|
| docs/research/20260328-hallucode-cubic-evaluation.md | HalluCode MRC Cubic 자격 평론: 원자성/직교성/조합성/견고성 판정, 기존 벤치마크 갭, 3-Cubic 스택 설계, NeurIPS 로드맵 | 2026-03-28 |
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
- [[projects/Miro/research/20260323-hallumaze-paper-draft|20260323-hallumaze-paper-draft]]
- [[projects/Miro/research/20260327-hallumaze-extension-hallucode|20260327-hallumaze-extension-hallucode]]
- [[projects/Miro/research/20260323-hallumaze-extension-todos|20260323-hallumaze-extension-todos]]
- [[projects/Miro/research/20260326-marl-sl-multi-model-validation|20260326-marl-sl-multi-model-validation]]
- [[projects/Miro/research/20260325-marl-efficiency-research|20260325-marl-efficiency-research]]
- [[projects/Miro/misc/ontolo-biz-unconscious-purchase-20260327|ontolo-biz-unconscious-purchase-20260327]]
- [[projects/Miro/research/20260328-hallucode-cubic-evaluation|20260328-hallucode-cubic-evaluation]]
- [[projects/Miro/research/20260324-marl5stage-fix-solutions|20260324-marl5stage-fix-solutions]]
