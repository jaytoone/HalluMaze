# HF Community Post v3 — HalluMaze (Claude 4.x Update)
_작성일: 2026-03-26 | 포스팅 가능 시각: 즉시_

---

## 포스트 내용

---

We expanded HalluMaze to 13 models — and Claude's new 4.x line tells a surprising story.

**Quick recap**: HalluMaze tests whether LLMs recognize their own mistakes. Mazes contain *mirage walls* that look passable but block movement. When the model hits one and gets `BLOCKED`, does it update its belief — or keep pushing?

The original 10-model leaderboard (n=600 trials) showed every frontier LLM falls below a random walk on our metacognitive recovery metric (MEI).

We just ran the Claude 4.x family under the same protocol (n=60 each):

🥇 **Claude-Sonnet-4.5** — MEI 0.783 (new #1, HRR 89.2%)
2️⃣ Claude-3.7-Sonnet — MEI 0.774 (HRR 87.5%)
8️⃣ **Claude-Sonnet-4.6** — MEI 0.545 (HRR 58.3%)
1️⃣2️⃣ **Claude-Haiku-4.5** — MEI 0.376 (HRR 38.3%)

★ Random Walk baseline: MEI 0.900

**Three things that shouldn't surprise you, but will:**

**Newer ≠ better metacognition.** Claude-Sonnet-4.6 (latest) ranks 8th with MEI 0.545 — well below 4.5 (0.783) and even 3.7 (0.774). It solves more mazes (SR 60% vs 36.7%) but recovers from errors less reliably.

**SR and MEI are orthogonal.** 4.6 has the highest solve rate in the entire 13-model leaderboard (60%), yet ranks 8th on metacognitive quality. A model that "wins" more often isn't necessarily better at knowing when it's wrong.

**The gap persists.** Even the new #1 (Sonnet-4.5, MEI 0.783) is 0.117 below a random walk that has no memory, no reasoning, and no model weights.

Full 13-model leaderboard + 780 trial records: Be2Jay/hallumaze-benchmark
Live race viewer: https://huggingface.co/spaces/Be2Jay/hallumaze

---

## 포스팅 메모

- **태그**: hallucination, benchmark, llm-evaluation, metacognition, claude
- **이미지**: hallumaze_race_screenshot.png 또는 새 리더보드 스크린샷
- **글자 수**: ~1,050자 (한도 내)
- **키 메시지**: Claude-Sonnet-4.5 신규 #1, 4.6은 SR↑ but MEI↓ (반직관적)

## 변경 내역 (v2 → v3)

- 13모델 확장 리더보드로 업데이트
- Claude 4.x 실험 결과 추가 (n=60 each)
- SR vs MEI 분리 현상 강조 (4.6이 SR 1위지만 MEI 8위)
- "Newer ≠ better metacognition" 메시지 추가
