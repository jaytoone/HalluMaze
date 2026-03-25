# HF Community Post v2 — HalluMaze
_저장일: 2026-03-25 | 24시간 후 포스팅 예정_

---

## 포스트 내용 (1177자 이하, 이미지 첨부 예정)

---

A random walk — no memory, no reasoning — beats every frontier LLM at recognizing its own mistakes.

We ran 600 trials across 10 models on **HalluMaze**: mazes with *mirage walls* that look open but block movement. When the model hits one and gets `BLOCKED`, the question is simple — does it update its belief, or keep pushing?

Results (MEI = metacognitive escape index, higher = better):

🥇 Claude-3.7-Sonnet — 0.774 (HRR 87.5%)
🥈 GLM-4.7 — 0.615 (HRR 71.8%)
🥉 Llama-4-Maverick — 0.600 (HRR 81.1%)
4️⃣ MiniMax-M2.5 — 0.593 (HRR 60.0%)
5️⃣ Llama-4-Scout — 0.589 (HRR 81.0%)
6️⃣ Qwen-2.5-72B — 0.559 (HRR 60.7%)
7️⃣ Gemini-Flash-Lite — 0.432 (HRR 40.3%)
8️⃣ Claude-3-Haiku — 0.398 (HRR 36.3%)
9️⃣ GPT-4o-mini — 0.391 (HRR 38.2%)
🔟 GPT-4o — 0.315 (HRR 35.3%)

★ Random Walk baseline: 0.900

Three things that surprised us:

**Cost inversion.** GPT-4o ($10/M tokens) ranks dead last — below GPT-4o-mini ($0.60/M). A 17× price gap in the wrong direction.

**Solving ≠ recovering.** MiniMax has the 2nd best solve rate (53%) but ranks 4th on MEI. GLM ranks 2nd despite barely solving any maze (SR 8%). These are different skills.

**The gap is large.** Best model is still 0.126 below a random walk. Effect sizes d=0.6–2.1 across all 10 models. p<0.001.

Live leaderboard + race viewer: https://huggingface.co/spaces/Be2Jay/hallumaze
All 600 trial records: Be2Jay/hallumaze-benchmark

---

## 포스팅 메모

- **이미지**: `hallumaze_race_screenshot.png` 첨부 (레이스 중간 상태, 5모델 SOLVED)
- **태그**: hallucination, benchmark, llm-evaluation, metacognition
- **포스팅 가능 시각**: 2026-03-26 10:30 이후 (24시간 쿼터 리셋)
- **글자 수**: ~1,050자 (여유 있음)

## 개선 포인트 (트렌딩 분석 결과)

| 기존 문제 | 개선 방향 |
|-----------|-----------|
| 마크다운 테이블 (렌더링 안 됨) | 이모지 번호 + 인라인 숫자 리스트 |
| 지나치게 학술적 문체 | 구체적 발견 + 비용 비교 강조 |
| 링크가 텍스트로만 | HF 카드 링크 임베드 활용 |
| 너무 긴 단락 | 2문장 이하 짧은 단락 분리 |
