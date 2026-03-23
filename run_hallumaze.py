#!/usr/bin/env python3
"""
HalluMaze Benchmark — MiniMax + GLM-4.7 전용 런처
환경변수: ~/.claude/env/shared.env (MiniMax) + .envrc (GLM/NIPA)

Usage:
    source ~/.claude/env/shared.env && python run_hallumaze.py
    python run_hallumaze.py --size 5 --runs 2
"""
from __future__ import annotations

import sys
import os
import argparse
import re


def _load_env_file(path: str):
    """source 없이 env 파일 파싱 → os.environ 주입 (export 여부 무관)"""
    try:
        with open(os.path.expanduser(path)) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                # export VAR=value 또는 VAR=value 형식
                m = re.match(r'^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$', line)
                if m:
                    key, val = m.group(1), m.group(2).strip('"\'')
                    if key not in os.environ:   # 이미 설정된 값 우선
                        os.environ[key] = val
    except FileNotFoundError:
        pass


# 전역 env 파일 선로드
_load_env_file("~/.claude/env/shared.env")
_load_env_file(".envrc")

# files/ 폴더의 hallumaze 모듈 로드
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'files'))

from hallumaze import (
    LLMProvider, MazeConfig, MazeEngine, BenchmarkRunner,
    print_comparison_table, export_json, export_csv,
    PromptBuilder, console, RICH, BenchmarkResult
)


# ═══════════════════════════════════════════════════════════════
#  PROVIDER EXTENSIONS — MiniMax & GLM
# ═══════════════════════════════════════════════════════════════

def _strip_think(text: str) -> str:
    """MiniMax/추론 모델의 <think>...</think> 블록 제거 후 실제 답변 반환."""
    import re
    stripped = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    return stripped if stripped else text  # think-only 응답이면 원문 유지


def _call_minimax(self: LLMProvider, prompt: str, max_tokens: int, system: str = "") -> str:
    """MiniMax — OpenAI 호환 API (reasoning model: max_tokens 강제 8000+)"""
    import openai
    base_url = os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.io/v1")
    # MiniMax-M2.5는 추론 모델: <think> 블록이 ~3000+ 토큰 소모 → 최소 8000 필요
    effective_tokens = max(max_tokens, 8000)
    client = openai.OpenAI(api_key=self.api_key, base_url=base_url)
    resp = client.chat.completions.create(
        model=self.model,
        max_tokens=effective_tokens,
        messages=[
            {"role": "system", "content": system or PromptBuilder.SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
    )
    raw = resp.choices[0].message.content
    return _strip_think(raw)


def _call_glm(self: LLMProvider, prompt: str, max_tokens: int, system: str = "") -> str:
    """GLM-4.7 — ZAI API (Anthropic SDK 호환, api.z.ai/api/anthropic)"""
    import anthropic

    base_url = os.environ.get("GLM_BASE_URL", "https://api.z.ai/api/anthropic")
    client = anthropic.Anthropic(api_key=self.api_key, base_url=base_url)
    msg = client.messages.create(
        model=self.model,
        max_tokens=max_tokens,
        system=system or PromptBuilder.SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


# LLMProvider 패치
_original_call = LLMProvider.call

def _patched_call(self: LLMProvider, prompt: str, max_tokens: int, system: str = "") -> str:
    if self.provider == "minimax":
        return _call_minimax(self, prompt, max_tokens, system)
    if self.provider == "glm":
        return _call_glm(self, prompt, max_tokens, system)
    return _original_call(self, prompt, max_tokens, system)

LLMProvider.call = _patched_call


# ═══════════════════════════════════════════════════════════════
#  PROVIDER SETUP
# ═══════════════════════════════════════════════════════════════

def build_providers() -> list[LLMProvider]:
    providers = []

    # MiniMax
    mm_key = os.environ.get("MINIMAX_API_KEY")
    if mm_key:
        model = os.environ.get("MINIMAX_MODEL", "MiniMax-M2.5")
        providers.append(LLMProvider(provider="minimax", api_key=mm_key, model=model))
        console.print(f"  ✓ MiniMax / {model}")
    else:
        console.print("  ✗ MINIMAX_API_KEY 없음 — 건너뜀")

    # GLM-4.7 (ZhipuAI 공식 API)
    glm_key = os.environ.get("GLM_API_KEY")
    if glm_key:
        model = os.environ.get("GLM_MODEL", "glm-4-air")
        providers.append(LLMProvider(provider="glm", api_key=glm_key, model=model))
        console.print(f"  ✓ GLM / {model} (ZhipuAI open.bigmodel.cn)")
    else:
        console.print("  ✗ GLM_API_KEY 없음 — GLM 건너뜀")

    return providers


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(description="HalluMaze — MiniMax + GLM 런처")
    ap.add_argument("--size",  type=int, default=7, choices=[5, 7, 9, 11], help="미로 크기 (기본 7)")
    ap.add_argument("--runs",  type=int, default=1, help="반복 횟수 (기본 1)")
    ap.add_argument("--seed",  type=int, default=None, help="시드 (재현성)")
    ap.add_argument("--group", type=str, default="A", choices=["A","B","C"], help="Ariadne 그룹")
    ap.add_argument("--no-mirage",     action="store_true", help="Linguistic Mirage 비활성화")
    ap.add_argument("--no-confidence", action="store_true", help="확신도 비활성화")
    ap.add_argument("--max-tokens",    type=int, default=2500)
    ap.add_argument("--output", type=str, default=None, help="JSON 결과 파일 경로")
    ap.add_argument("--csv",    action="store_true", help="CSV 함께 저장")
    args = ap.parse_args()

    console.print("\n" + ("═"*60))
    console.print("  HalluMaze Benchmark v1.1 — MiniMax × GLM-4.7")
    console.print("  AI 메타인지 발현 측정 (MEI 기반)")
    console.print(("═"*60) + "\n")

    # 프로바이더
    console.print("  [프로바이더]")
    providers = build_providers()
    if not providers:
        console.print("\n  오류: 사용 가능한 프로바이더가 없습니다.")
        console.print("  source ~/.claude/env/shared.env 후 재시도하세요.")
        sys.exit(1)

    config = MazeConfig(
        size=args.size,
        use_mirage=not args.no_mirage,
        use_confidence=not args.no_confidence,
        ariadne_mode=args.group,
        max_tokens=args.max_tokens,
    )
    console.print(f"\n  [미로 설정] {config.size}×{config.size} | "
                  f"Mirage={'ON' if config.use_mirage else 'OFF'} | "
                  f"Confidence={'ON' if config.use_confidence else 'OFF'} | "
                  f"Ariadne={config.ariadne_mode}")

    all_results: list[BenchmarkResult] = []

    for run_idx in range(args.runs):
        if args.runs > 1:
            console.print(f"\n{'─'*50}  Run {run_idx+1}/{args.runs}  {'─'*50}")

        maze = MazeEngine(size=config.size, seed=args.seed)
        console.print(f"\n  [미로] Seed={maze.seed} | 정답 길이={len(maze.solution or [])} | "
                      f"막다른길={maze.dead_ends} | 미라지트랩={len(maze.mirage_traps)}")

        runner = BenchmarkRunner(config)
        runner.run_all(providers, maze)
        all_results.extend(runner.results)

        # 정답 경로 시각화
        console.print("\n  [정답 경로 시각화]")
        console.print(maze.ascii_render())

    # 종합 비교표
    console.print("\n")
    print_comparison_table(all_results)

    # 결과 저장
    maze_last = maze  # 마지막 미로 기준
    json_path = export_json(all_results, maze_last, config, path=args.output)
    console.print(f"\n  JSON 저장: {json_path}")

    if args.csv:
        csv_path = export_csv(all_results)
        console.print(f"  CSV  저장: {csv_path}")

    # MEI 최고점 모델 출력
    if all_results:
        best = max(all_results, key=lambda r: r.hallumaze_score)
        console.print(f"\n  ★ 최고 HalluScore: {best.model} ({best.provider}) = {best.hallumaze_score:.3f}")
        console.print(f"    MEI={best.mei:.3f} | SR={best.sr:.2f} | 환각={best.hallucination_count} | BT={best.backtrack_count}")


if __name__ == "__main__":
    main()
