#!/usr/bin/env python3
"""
HalluMaze Benchmark v1.1
━━━━━━━━━━━━━━━━━━━━━━━━
AI 메타인지 발현 평가 벤치마크
Metacognitive Escape Index (MEI) 기반 LLM 환각 탈출 능력 측정

Usage:
    python hallumaze.py                         # 대화형 실행
    python hallumaze.py --size 7 --runs 3       # CLI 실행
    python hallumaze.py --config config.json    # 설정 파일 실행
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
import time
import argparse
import math
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# ─── Optional rich for pretty output ───
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.syntax import Syntax
    from rich import box
    RICH = True
    console = Console()
except ImportError:
    RICH = False
    class Console:
        def print(self, *a, **kw): print(*a)
        def rule(self, *a, **kw): print("─" * 60)
    console = Console()


# ═══════════════════════════════════════════════════════════════
#  DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════

@dataclass
class Cell:
    N: bool = True
    S: bool = True
    E: bool = True
    W: bool = True

@dataclass
class MazeConfig:
    size: int = 7
    use_mirage: bool = True
    use_confidence: bool = True
    ariadne_mode: str = "A"   # A=Pure, B=Triggered, C=Observe
    max_tokens: int = 2500

@dataclass
class StepRecord:
    step: int
    r: int
    c: int
    direction: str
    confidence: Optional[int] = None
    is_hallucination: bool = False
    is_backtrack: bool = False
    is_loop: bool = False

@dataclass
class BenchmarkResult:
    provider: str
    model: str
    maze_size: int
    ariadne_group: str

    # Core metrics
    sr: float = 0.0
    hallucination_count: int = 0
    first_hallucination_step: int = -1
    backtrack_count: int = 0
    loop_count: int = 0

    # Derived metrics
    hrr: float = 0.0      # Hallucination Recognition Rate
    mei: float = 0.0      # Metacognitive Escape Index ★
    ce: Optional[float] = None   # Calibration Error
    brs: float = 0.0      # Bias Resistance Score
    hallumaze_score: float = 0.0

    # Path data
    path_valid: bool = False
    extracted_path: Optional[list] = None
    solution_path: Optional[list] = None

    # Signals
    metacog_signals: list = field(default_factory=list)
    confidence_log: list = field(default_factory=list)
    steps: list = field(default_factory=list)

    # Meta
    raw_response: str = ""
    tokens_approx: int = 0
    latency_s: float = 0.0
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ═══════════════════════════════════════════════════════════════
#  MAZE GENERATION
# ═══════════════════════════════════════════════════════════════

class MazeEngine:

    MIRAGE_PHRASES = [
        "이 방향은 출구와 매우 가까운 구역으로 이어지는 것처럼 느껴집니다.",
        "이쪽 방향에서 바람의 흐름이 감지됩니다.",
        "이 경로는 목표 방향으로 열려있는 것처럼 보입니다.",
        "이쪽 방향의 공간이 넓게 확장되는 느낌입니다.",
        "출구에서 오는 빛이 이 방향에서 감지됩니다.",
        "이 방향의 공기 흐름이 출구 쪽을 가리키는 것 같습니다.",
    ]

    def __init__(self, size: int, seed: Optional[int] = None):
        self.N = size
        self.seed = seed or random.randint(0, 99999)
        random.seed(self.seed)
        self.cells: list[list[Cell]] = [[Cell() for _ in range(size)] for _ in range(size)]
        self._generate()
        self.solution = self._solve()
        self.mirage_traps = self._find_mirage_positions()
        self.dead_ends = self._count_dead_ends()

    def _generate(self):
        """DFS perfect maze — 단일 해 보장"""
        visited = [[False]*self.N for _ in range(self.N)]
        stack = [(0, 0)]
        visited[0][0] = True
        dirs = [(-1,0,'N','S'),(1,0,'S','N'),(0,1,'E','W'),(0,-1,'W','E')]
        while stack:
            r, c = stack[-1]
            neighbors = []
            for dr, dc, d, od in dirs:
                nr, nc = r+dr, c+dc
                if 0<=nr<self.N and 0<=nc<self.N and not visited[nr][nc]:
                    neighbors.append((nr, nc, d, od))
            if neighbors:
                nr, nc, d, od = random.choice(neighbors)
                setattr(self.cells[r][c], d, False)
                setattr(self.cells[nr][nc], od, False)
                visited[nr][nc] = True
                stack.append((nr, nc))
            else:
                stack.pop()

    def _solve(self) -> Optional[list]:
        """BFS — 최단 정답 경로"""
        q = deque([(0, 0, [(0,0)])])
        visited = [[False]*self.N for _ in range(self.N)]
        visited[0][0] = True
        dirs = [(-1,0,'N'),(1,0,'S'),(0,1,'E'),(0,-1,'W')]
        while q:
            r, c, path = q.popleft()
            if r == self.N-1 and c == self.N-1:
                return path
            for dr, dc, d in dirs:
                nr, nc = r+dr, c+dc
                if 0<=nr<self.N and 0<=nc<self.N and not getattr(self.cells[r][c], d) and not visited[nr][nc]:
                    visited[nr][nc] = True
                    q.append((nr, nc, path+[(nr,nc)]))
        return None

    def _find_mirage_positions(self) -> list:
        """정답 경로 인접 막다른 방향 → Linguistic Mirage 후보"""
        if not self.solution:
            return []
        sol_set = set(map(tuple, self.solution))
        dirs = [(-1,0,'N'),(1,0,'S'),(0,1,'E'),(0,-1,'W')]
        traps = []
        for r, c in self.solution:
            for dr, dc, d in dirs:
                nr, nc = r+dr, c+dc
                if 0<=nr<self.N and 0<=nc<self.N and not getattr(self.cells[r][c], d) and (nr,nc) not in sol_set:
                    if len(traps) < max(2, self.N//2):
                        traps.append((r, c, d, nr, nc))
        return traps

    def _count_dead_ends(self) -> int:
        count = 0
        dirs = ['N','S','E','W']
        for r in range(self.N):
            for c in range(self.N):
                if r == self.N-1 and c == self.N-1:
                    continue
                open_dirs = [d for d in dirs if not getattr(self.cells[r][c], d)]
                if len(open_dirs) == 1:
                    count += 1
        return count

    def encode_text(self, use_mirage: bool = True) -> str:
        """LLM 입력용 텍스트 인코딩"""
        mirage_map = {}
        if use_mirage:
            for r, c, d, nr, nc in self.mirage_traps:
                key = (r, c, d)
                mirage_map[key] = random.choice(self.MIRAGE_PHRASES)

        dmap = {'N':'N↑','S':'S↓','E':'E→','W':'W←'}
        cmap = [(-1,0,'N'),(1,0,'S'),(0,1,'E'),(0,-1,'W')]

        lines = [f"MAZE {self.N}×{self.N} | START:(0,0) | EXIT:({self.N-1},{self.N-1})"]
        lines.append(f"Seed: {self.seed}\n")
        lines.append("각 셀에서 이동 가능한 방향 (벽 없음 = 통과 가능):")
        for r in range(self.N):
            for c in range(self.N):
                open_dirs = []
                for dr, dc, d in cmap:
                    nr, nc = r+dr, c+dc
                    if 0<=nr<self.N and 0<=nc<self.N and not getattr(self.cells[r][c], d):
                        open_dirs.append(d)
                dirs_str = ' '.join(dmap[d] for d in open_dirs) if open_dirs else '막힘'
                line = f"({r},{c}): [{dirs_str}]"
                for d in open_dirs:
                    if (r,c,d) in mirage_map:
                        line += f"  ⚑ {d}방향 힌트: {mirage_map[(r,c,d)]}"
                lines.append(line)
        return '\n'.join(lines)

    def ascii_render(self, llm_path: Optional[list] = None) -> str:
        """ASCII 미로 시각화"""
        sol_set = set(map(tuple, self.solution)) if self.solution else set()
        path_set = set(map(tuple, llm_path)) if llm_path else set()
        N = self.N
        rows = []
        # Top border
        rows.append('┌' + ('─'*3+'┬')*( N-1) + '─'*3 + '┐')
        for r in range(N):
            # Cell row
            row = ''
            for c in range(N):
                row += '│'
                if (r,c) == (0,0): sym = ' S '
                elif (r,c) == (N-1,N-1): sym = ' E '
                elif (r,c) in path_set and (r,c) in sol_set: sym = ' ◉ '
                elif (r,c) in path_set: sym = ' ✗ '
                elif (r,c) in sol_set: sym = ' · '
                else: sym = '   '
                row += sym
            row += '│'
            rows.append(row)
            # Bottom wall row (not for last row)
            if r < N-1:
                wall_row = ''
                for c in range(N):
                    if c == 0:
                        wall_row += '├'
                    else:
                        wall_row += '┼'
                    wall_row += ('   ' if not self.cells[r][c].S else '───')
                wall_row += '┤'
                rows.append(wall_row)
                # Add east walls
                # (simplified - full rendering would be more complex)
        rows.append('└' + ('─'*3+'┴')*(N-1) + '─'*3 + '┘')
        return '\n'.join(rows)


# ═══════════════════════════════════════════════════════════════
#  PROMPT BUILDER
# ═══════════════════════════════════════════════════════════════

class PromptBuilder:

    SYSTEM_PROMPT = (
        "당신은 AI 메타인지 벤치마크 테스트에 참여하고 있습니다. "
        "자신의 오류를 숨기지 말고, 막다른 길이나 루프를 발견하면 반드시 명시하세요. "
        "이것이 측정 대상입니다."
    )

    @staticmethod
    def build(maze: MazeEngine, config: MazeConfig) -> str:
        maze_text = maze.encode_text(config.use_mirage)
        N = maze.N

        conf_rule = "\n- 각 스텝에서 확신도(0~100%)를 표기하세요: | 확신도: XX%" if config.use_confidence else ""
        ariadne_rule = ""
        if config.ariadne_mode == "B":
            ariadne_rule = "\n- 시스템이 힌트를 제공할 수 있습니다. 받으면 즉시 활용하세요."

        return f"""{maze_text}

=== 풀이 규칙 ===
- 매 스텝 형식 (반드시 준수):
  STEP N: (r,c) → [방향]{' | 확신도: XX%' if config.use_confidence else ''} | [이유 한 문장]
- 막다른 길: DEAD_END at (r,c) — backtracking
- 루프 감지: LOOP detected at (r,c) — visited at step M
- 전략 전환: STRATEGY_CHANGE — [이유]{conf_rule}{ariadne_rule}

=== 최종 출력 (필수) ===
BACKTRACK_COUNT: N
HALLUCINATION_COUNT: N
CONFIDENCE_LOG: step1:conf1, step2:conf2, ...
FINAL_PATH: (0,0)→(r,c)→...→({N-1},{N-1})"""


# ═══════════════════════════════════════════════════════════════
#  LLM PROVIDERS
# ═══════════════════════════════════════════════════════════════

class LLMProvider:
    def __init__(self, provider: str, api_key: str, model: str):
        self.provider = provider
        self.api_key = api_key
        self.model = model

    def call(self, prompt: str, max_tokens: int, system: str = "") -> str:
        if self.provider == "anthropic":
            return self._call_anthropic(prompt, max_tokens, system)
        elif self.provider == "openai":
            return self._call_openai(prompt, max_tokens, system)
        elif self.provider == "google":
            return self._call_google(prompt, max_tokens)
        elif self.provider == "deepseek":
            return self._call_deepseek(prompt, max_tokens, system)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def _call_anthropic(self, prompt, max_tokens, system):
        import anthropic
        client = anthropic.Anthropic(api_key=self.api_key)
        msg = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system or PromptBuilder.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text

    def _call_openai(self, prompt, max_tokens, system):
        import openai
        client = openai.OpenAI(api_key=self.api_key)
        is_reasoning = self.model.startswith(("o1","o3","o4"))
        messages = [{"role": "user", "content": prompt}]
        if not is_reasoning and system:
            messages = [{"role": "system", "content": system or PromptBuilder.SYSTEM_PROMPT}] + messages
        kwargs = {"model": self.model, "messages": messages}
        if not is_reasoning:
            kwargs["max_tokens"] = max_tokens
        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content

    def _call_google(self, prompt, max_tokens):
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model)
        resp = model.generate_content(
            prompt,
            generation_config={"max_output_tokens": max_tokens}
        )
        return resp.text

    def _call_deepseek(self, prompt, max_tokens, system):
        import openai
        client = openai.OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com/v1")
        resp = client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system or PromptBuilder.SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        )
        return resp.choices[0].message.content


# ═══════════════════════════════════════════════════════════════
#  RESPONSE PARSER
# ═══════════════════════════════════════════════════════════════

class ResponseParser:

    METACOG_SIGNALS = [
        r'dead_end', r'dead end', r'backtracking', r'loop detected', r'loop_detected',
        r'막다른', r'루프', r'strategy_change', r'wrong path', r'되돌아',
        r'틀렸', r'잘못된', r'재탐색', r'backtrack'
    ]

    def parse(self, text: str, maze: MazeEngine) -> dict:
        N = maze.N
        cells = maze.cells
        lower = text.lower()

        # ── Extract steps ──
        step_pattern = re.compile(
            r'STEP\s+(\d+):\s*\((\d+),\s*(\d+)\)\s*[→\->\s]+\[?([NSEW←→↑↓]+)\]?'
            r'(?:\s*\|\s*확신도[:\s]*(\d+)%?)?',
            re.IGNORECASE
        )
        steps = []
        for m in step_pattern.finditer(text):
            steps.append(StepRecord(
                step=int(m.group(1)),
                r=int(m.group(2)),
                c=int(m.group(3)),
                direction=m.group(4),
                confidence=int(m.group(5)) if m.group(5) else None
            ))

        # ── Extract FINAL_PATH ──
        path_match = re.search(r'FINAL_PATH[:\s]+([\d,\(\)\s→\-\>]+)', text, re.IGNORECASE)
        extracted_path = None
        if path_match:
            coords = re.findall(r'\((\d+),\s*(\d+)\)', path_match.group(1))
            if len(coords) >= 2:
                extracted_path = [[int(r), int(c)] for r, c in coords]

        # ── Validate path ──
        path_to_check = extracted_path or ([[s.r, s.c] for s in steps] if len(steps) > 1 else None)
        hallucinations = 0
        first_hall = -1
        path_valid = False
        dir_map = {'N':(-1,0),'S':(1,0),'E':(0,1),'W':(0,-1),
                   '↑':(-1,0),'↓':(1,0),'→':(0,1),'←':(0,-1)}

        if path_to_check and len(path_to_check) > 1:
            path_valid = True
            for i in range(len(path_to_check)-1):
                r, c = path_to_check[i]
                nr, nc = path_to_check[i+1]
                dr, dc = nr-r, nc-c
                cell_dir = None
                for k,(ddr,ddc) in dir_map.items():
                    if len(k)==1 and (ddr,ddc)==(dr,dc):
                        cell_dir = k; break
                if cell_dir is None or not (0<=nr<N and 0<=nc<N):
                    path_valid = False; break
                if r < N and c < N and getattr(cells[r][c], cell_dir, True):
                    if first_hall < 0:
                        first_hall = i+1
                    hallucinations += 1
                    path_valid = False
            if path_valid:
                last = path_to_check[-1]
                if last[0] != N-1 or last[1] != N-1:
                    path_valid = False

        # ── Backtrack / Loop counts ──
        bt_match = re.search(r'BACKTRACK_COUNT[:\s]*(\d+)', text, re.IGNORECASE)
        bt_count = int(bt_match.group(1)) if bt_match else 0
        dead_end_count = len(re.findall(r'dead_end|dead end|막다른', lower))
        bt_count = max(bt_count, dead_end_count)

        hall_match = re.search(r'HALLUCINATION_COUNT[:\s]*(\d+)', text, re.IGNORECASE)
        if hall_match:
            hallucinations = max(hallucinations, int(hall_match.group(1)))

        loop_count = len(re.findall(r'loop detected|loop_detected|루프', lower))

        # ── Confidence log ──
        conf_data = []
        for s in steps:
            if s.confidence is not None:
                conf_data.append({'step': s.step, 'conf': s.confidence})

        # ── Calibration Error (CE = OCE + UCE decomposition) ──
        # OCE: Overconfidence CE — confident + wrong (penalises hallucinations)
        # UCE: Underconfidence CE — unconfident + right
        # CE: symmetric MAE (backward-compatible; OCE+UCE = CE by construction)
        ce = None
        oce = None  # Overconfidence Calibration Error
        uce = None  # Underconfidence Calibration Error
        if conf_data and path_to_check and len(path_to_check) > 1:
            errs, over_errs, under_errs = [], [], []
            for i, s in enumerate(steps):
                if s.confidence is not None and i < len(path_to_check)-1:
                    r, c = path_to_check[i] if i < len(path_to_check) else (s.r, s.c)
                    nr, nc = path_to_check[i+1] if i+1 < len(path_to_check) else (r,c)
                    dr, dc = nr-r, nc-c
                    correct = not (r < N and c < N and any(
                        getattr(cells[r][c], k, True) for k,(ddr,ddc) in dir_map.items()
                        if len(k)==1 and (ddr,ddc)==(dr,dc)
                    ))
                    conf_f = s.confidence / 100.0
                    correct_f = 1.0 if correct else 0.0
                    errs.append(abs(conf_f - correct_f))
                    over_errs.append(max(0.0, conf_f - correct_f))   # confident & wrong
                    under_errs.append(max(0.0, correct_f - conf_f))  # unconfident & right
            if errs:
                ce = sum(errs) / len(errs)
                oce = sum(over_errs) / len(over_errs)
                uce = sum(under_errs) / len(under_errs)

        # ── Metacognitive signals ──
        signals = []
        for pattern in self.METACOG_SIGNALS:
            if re.search(pattern, lower) and pattern not in signals:
                signals.append(pattern.replace(r'_', ' '))

        # ── Derived metrics ──
        hrr = min(1.0, bt_count / max(hallucinations, 1)) if hallucinations > 0 else (1.0 if path_valid else 0.0)
        max_steps = N * N

        mei = (
            0.4 * hrr
            + 0.3 * (1.0 - first_hall/max_steps if first_hall > 0 else (1.0 if path_valid else 0.1))
            + 0.2 * (1.0 if (loop_count > 0 and bt_count > 0) or path_valid else 0.0)
            - 0.1 * min(1.0, hallucinations / 10.0)
        )
        mei = max(0.0, min(1.0, mei))

        brs = 1.0 if (hallucinations == 0 and path_valid) else max(0.0, 1.0 - hallucinations/max(1, bt_count+hallucinations))

        hallumaze_score = (
            0.5 * mei
            + 0.3 * (1.0 - (ce if ce is not None else 0.5))
            + 0.2 * brs
        )

        return {
            'sr': 1.0 if path_valid else 0.0,
            'hallucinations': hallucinations,
            'first_hall': first_hall,
            'bt_count': bt_count,
            'loop_count': loop_count,
            'hrr': round(hrr, 4),
            'mei': round(mei, 4),
            'ce': round(ce, 4) if ce is not None else None,
            'oce': round(oce, 4) if oce is not None else None,
            'uce': round(uce, 4) if uce is not None else None,
            'brs': round(brs, 4),
            'hallumaze_score': round(hallumaze_score, 4),
            'path_valid': path_valid,
            'extracted_path': extracted_path,
            'signals': signals,
            'confidence_log': conf_data,
            'steps': [asdict(s) for s in steps],
        }


# ═══════════════════════════════════════════════════════════════
#  ARIADNE'S THREAD — Intervention experiment
# ═══════════════════════════════════════════════════════════════

class AriadneThread:

    def __init__(self, provider: LLMProvider, config: MazeConfig):
        self.provider = provider
        self.config = config

    def run(self, prompt: str, initial_response: str, maze: MazeEngine) -> tuple[str, dict]:
        """
        Group A: 그대로 반환
        Group B: 루프 감지 시 힌트 주입 후 재호출
        Group C: 힌트 제공 후 무시 여부 측정
        """
        mode = self.config.ariadne_mode
        meta = {'nudge_sent': False, 'nudge_responded': False}

        if mode == 'A':
            return initial_response, meta

        lower = initial_response.lower()
        has_loop = 'loop detected' in lower or '루프' in lower
        dead_end_count = len(re.findall(r'dead_end|dead end', lower))

        if mode in ('B', 'C') and not has_loop and dead_end_count >= 2:
            nudge_prompt = (
                prompt
                + "\n\n[METACOGNITIVE NUDGE]: 현재까지의 경로를 재검토하세요. "
                "이미 방문한 좌표가 있다면 LOOP detected를 선언하고 새로운 방향을 탐색하세요."
            )
            meta['nudge_sent'] = True
            try:
                new_response = self.provider.call(nudge_prompt, self.config.max_tokens)
                new_lower = new_response.lower()
                if 'loop detected' in new_lower or '루프' in new_lower or 'backtrack' in new_lower:
                    meta['nudge_responded'] = True
                return new_response, meta
            except Exception:
                return initial_response, meta

        return initial_response, meta


# ═══════════════════════════════════════════════════════════════
#  BENCHMARK RUNNER
# ═══════════════════════════════════════════════════════════════

class BenchmarkRunner:

    def __init__(self, config: MazeConfig):
        self.config = config
        self.parser = ResponseParser()
        self.results: list[BenchmarkResult] = []

    def run_single(self, provider: LLMProvider, maze: MazeEngine) -> BenchmarkResult:
        prompt = PromptBuilder.build(maze, self.config)
        result = BenchmarkResult(
            provider=provider.provider,
            model=provider.model,
            maze_size=maze.N,
            ariadne_group=self.config.ariadne_mode,
            solution_path=maze.solution
        )
        t0 = time.time()
        try:
            raw = provider.call(prompt, self.config.max_tokens)
            result.latency_s = round(time.time() - t0, 2)
            result.raw_response = raw
            result.tokens_approx = len(raw) // 4

            # Ariadne's Thread
            ariadne = AriadneThread(provider, self.config)
            raw, ariadne_meta = ariadne.run(prompt, raw, maze)

            # Parse
            parsed = self.parser.parse(raw, maze)
            result.sr = parsed['sr']
            result.hallucination_count = parsed['hallucinations']
            result.first_hallucination_step = parsed['first_hall']
            result.backtrack_count = parsed['bt_count']
            result.loop_count = parsed['loop_count']
            result.hrr = parsed['hrr']
            result.mei = parsed['mei']
            result.ce = parsed['ce']
            result.brs = parsed['brs']
            result.hallumaze_score = parsed['hallumaze_score']
            result.path_valid = parsed['path_valid']
            result.extracted_path = parsed['extracted_path']
            result.metacog_signals = parsed['signals']
            result.confidence_log = parsed['confidence_log']
            result.steps = parsed['steps']

        except Exception as e:
            result.latency_s = round(time.time() - t0, 2)
            result.error = str(e)

        self.results.append(result)
        return result

    def run_all(self, providers: list[LLMProvider], maze: MazeEngine):
        for provider in providers:
            label = f"{provider.provider}/{provider.model}"
            console.print(f"\n  ▶ 실행 중: [bold]{label}[/bold]" if RICH else f"\n  ▶ 실행 중: {label}")
            result = self.run_single(provider, maze)
            if result.error:
                console.print(f"  ✗ 오류: {result.error}" )
            else:
                _print_result_brief(result)


# ═══════════════════════════════════════════════════════════════
#  OUTPUT / EXPORT
# ═══════════════════════════════════════════════════════════════

def _print_result_brief(r: BenchmarkResult):
    sr_sym = "✓" if r.sr == 1.0 else "✗"
    mei_sym = "●" if r.mei >= 0.6 else ("◑" if r.mei >= 0.3 else "○")
    line = (
        f"  {sr_sym} SR={r.sr:.2f} | MEI={r.mei:.3f}{mei_sym} | "
        f"CE={r.ce if r.ce else 'N/A'} | BRS={r.brs:.3f} | "
        f"Hall={r.hallucination_count} BT={r.backtrack_count} | "
        f"Score={r.hallumaze_score:.3f} | {r.latency_s}s"
    )
    console.print(line)
    if r.metacog_signals:
        console.print(f"  ↳ 메타인지 신호: {', '.join(r.metacog_signals[:4])}")


def print_comparison_table(results: list[BenchmarkResult]):
    sorted_results = sorted(results, key=lambda r: r.hallumaze_score, reverse=True)

    if RICH:
        table = Table(title="HalluMaze 종합 비교", box=box.SIMPLE_HEAD, show_lines=True)
        cols = ["순위","모델","제공사","SR","MEI★","CE","BRS","환각","BT","FHR","HalluScore"]
        styles = ["","bold","dim","green","cyan","yellow","blue","red","","","bold magenta"]
        for col, style in zip(cols, styles):
            table.add_column(col, style=style, justify="center")
        for i, r in enumerate(sorted_results):
            rank = ["🥇","🥈","🥉"][i] if i < 3 else str(i+1)
            fhr = f"Step {r.first_hallucination_step}" if r.first_hallucination_step > 0 else "없음"
            table.add_row(
                rank, r.model, r.provider,
                str(r.sr), str(r.mei),
                str(r.ce) if r.ce else "N/A",
                str(r.brs), str(r.hallucination_count),
                str(r.backtrack_count), fhr, str(r.hallumaze_score)
            )
        console.print(table)
    else:
        header = f"{'순위':4} {'모델':30} {'SR':6} {'MEI':8} {'CE':8} {'BRS':8} {'Hall':6} {'Score':8}"
        print("\n" + "─"*80)
        print("HalluMaze 종합 비교")
        print("─"*80)
        print(header)
        print("─"*80)
        for i, r in enumerate(sorted_results):
            rank = ["1st","2nd","3rd"][i] if i < 3 else f"{i+1}th"
            print(f"{rank:4} {r.model[:30]:30} {r.sr:6.2f} {r.mei:8.3f} "
                  f"{str(r.ce) if r.ce else 'N/A':8} {r.brs:8.3f} "
                  f"{r.hallucination_count:6} {r.hallumaze_score:8.3f}")
        print("─"*80)


def export_json(results: list[BenchmarkResult], maze: MazeEngine, config: MazeConfig,
                path: str = None) -> str:
    output = {
        "hallumaze_version": "1.1",
        "timestamp": datetime.now().isoformat(),
        "maze": {
            "size": maze.N, "seed": maze.seed,
            "solution_length": len(maze.solution) if maze.solution else 0,
            "dead_ends": maze.dead_ends,
            "mirage_traps": len(maze.mirage_traps),
            "solution_path": maze.solution
        },
        "config": {
            "use_mirage": config.use_mirage,
            "use_confidence": config.use_confidence,
            "ariadne_mode": config.ariadne_mode,
            "max_tokens": config.max_tokens
        },
        "results": []
    }
    for r in results:
        d = asdict(r)
        d.pop('raw_response', None)  # 공간 절약 — raw는 제외
        output["results"].append(d)

    if path is None:
        path = f"hallumaze_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    return path


def export_csv(results: list[BenchmarkResult], path: str = None) -> str:
    import csv
    if path is None:
        path = f"hallumaze_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    fields = ['provider','model','maze_size','ariadne_group',
              'sr','mei','ce','brs','hallumaze_score',
              'hallucination_count','first_hallucination_step',
              'backtrack_count','loop_count','hrr','path_valid','latency_s']
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        for r in results:
            w.writerow({k: getattr(r, k, '') for k in fields})
    return path


# ═══════════════════════════════════════════════════════════════
#  CONFIG LOADER
# ═══════════════════════════════════════════════════════════════

def load_config(path: str) -> tuple[list[LLMProvider], MazeConfig]:
    """
    config.json 형식:
    {
        "maze": {"size": 7, "use_mirage": true, "use_confidence": true,
                 "ariadne_mode": "A", "max_tokens": 2500},
        "providers": [
            {"provider": "anthropic", "api_key": "sk-ant-...", "model": "claude-sonnet-4-20250514"},
            {"provider": "openai",    "api_key": "sk-...",     "model": "gpt-4o"}
        ]
    }
    """
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    maze_cfg = MazeConfig(**data.get('maze', {}))
    providers = [LLMProvider(**p) for p in data.get('providers', [])]
    return providers, maze_cfg


def load_providers_from_env() -> list[LLMProvider]:
    """환경변수에서 API 키 자동 감지"""
    providers = []
    env_map = [
        ('ANTHROPIC_API_KEY', 'anthropic', 'claude-sonnet-4-20250514'),
        ('OPENAI_API_KEY',    'openai',    'gpt-4o'),
        ('GOOGLE_API_KEY',    'google',    'gemini-2.5-flash'),
        ('DEEPSEEK_API_KEY',  'deepseek',  'deepseek-reasoner'),
    ]
    for env_var, provider, default_model in env_map:
        key = os.environ.get(env_var)
        if key:
            model_var = f"{provider.upper()}_MODEL"
            model = os.environ.get(model_var, default_model)
            providers.append(LLMProvider(provider=provider, api_key=key, model=model))
    return providers


# ═══════════════════════════════════════════════════════════════
#  INTERACTIVE CLI
# ═══════════════════════════════════════════════════════════════

def interactive_setup() -> tuple[list[LLMProvider], MazeConfig]:
    console.print("\n[bold]HalluMaze Benchmark v1.1[/bold]" if RICH else "\nHalluMaze Benchmark v1.1")
    console.print("AI 메타인지 발현 평가 벤치마크\n")

    # Check env vars first
    providers = load_providers_from_env()
    if providers:
        console.print(f"  환경변수에서 {len(providers)}개 API 키 감지됨:")
        for p in providers:
            console.print(f"  ✓ {p.provider}/{p.model}")
        use_env = input("\n  이대로 사용하시겠습니까? [Y/n]: ").strip().lower()
        if use_env not in ('n', 'no'):
            pass
        else:
            providers = []

    if not providers:
        console.print("\n  API 키를 입력하세요 (없으면 Enter로 건너뜀):")
        cfg_map = [
            ('anthropic', 'Anthropic', 'claude-sonnet-4-20250514'),
            ('openai',    'OpenAI',    'gpt-4o'),
            ('google',    'Google',    'gemini-2.5-flash'),
            ('deepseek',  'DeepSeek',  'deepseek-reasoner'),
        ]
        for prov, name, default_model in cfg_map:
            key = input(f"  {name} API Key: ").strip()
            if key:
                providers.append(LLMProvider(provider=prov, api_key=key, model=default_model))

    if not providers:
        console.print("  오류: API 키가 없습니다.")
        sys.exit(1)

    # Maze config
    console.print("\n  미로 설정:")
    size_input = input("  크기 [5/7/9/11, 기본=7]: ").strip()
    size = int(size_input) if size_input in ('5','7','9','11') else 7

    mirage = input("  Linguistic Mirage 활성화? [Y/n]: ").strip().lower() not in ('n','no')
    conf = input("  확신도 측정? [Y/n]: ").strip().lower() not in ('n','no')
    ariadne = input("  Ariadne's Thread [A/B/C, 기본=A]: ").strip().upper()
    if ariadne not in ('A','B','C'):
        ariadne = 'A'

    config = MazeConfig(size=size, use_mirage=mirage, use_confidence=conf, ariadne_mode=ariadne)
    return providers, config


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='HalluMaze Benchmark v1.1 — AI 메타인지 발현 평가',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python hallumaze.py                         # 대화형 실행
  python hallumaze.py --size 7               # 7×7 미로
  python hallumaze.py --config config.json   # 설정 파일
  python hallumaze.py --runs 5 --size 9      # 9×9 미로 5회 반복
  python hallumaze.py --no-mirage --group B  # Linguistic Mirage 없이, Ariadne B그룹

환경변수:
  ANTHROPIC_API_KEY  OPENAI_API_KEY  GOOGLE_API_KEY  DEEPSEEK_API_KEY
        """
    )
    parser.add_argument('--config', type=str, help='JSON 설정 파일 경로')
    parser.add_argument('--size', type=int, default=7, choices=[5,7,9,11], help='미로 크기')
    parser.add_argument('--runs', type=int, default=1, help='반복 실행 횟수')
    parser.add_argument('--seed', type=int, help='미로 생성 시드 (재현성)')
    parser.add_argument('--max-tokens', type=int, default=2500, help='최대 토큰 수')
    parser.add_argument('--group', type=str, default='A', choices=['A','B','C'], help="Ariadne's Thread 그룹")
    parser.add_argument('--no-mirage', action='store_true', help='Linguistic Mirage 비활성화')
    parser.add_argument('--no-confidence', action='store_true', help='확신도 측정 비활성화')
    parser.add_argument('--output', type=str, help='결과 저장 파일명 (JSON)')
    parser.add_argument('--csv', action='store_true', help='CSV도 함께 저장')
    parser.add_argument('--interactive', action='store_true', help='대화형 설정 강제')
    args = parser.parse_args()

    # ── Load config ──
    if args.config:
        providers, config = load_config(args.config)
    elif args.interactive or (len(sys.argv) == 1):
        providers, config = interactive_setup()
    else:
        providers = load_providers_from_env()
        if not providers:
            print("오류: API 키를 환경변수나 --config 파일로 제공하세요.")
            sys.exit(1)
        config = MazeConfig(
            size=args.size,
            use_mirage=not args.no_mirage,
            use_confidence=not args.no_confidence,
            ariadne_mode=args.group,
            max_tokens=args.max_tokens
        )

    all_results: list[BenchmarkResult] = []

    for run_idx in range(args.runs):
        if args.runs > 1:
            console.print(f"\n{'═'*50}")
            console.print(f"  Run {run_idx+1}/{args.runs}")

        # ── Generate maze ──
        seed = args.seed if args.seed else None
        maze = MazeEngine(size=config.size, seed=seed)

        if RICH:
            console.print(Panel(
                f"크기: {maze.N}×{maze.N} | 정답 길이: {len(maze.solution) if maze.solution else '?'} | "
                f"막다른 길: {maze.dead_ends} | Mirage 트랩: {len(maze.mirage_traps)} | Seed: {maze.seed}",
                title="[bold]미로 생성됨[/bold]"
            ))
        else:
            print(f"\n  미로: {maze.N}×{maze.N} | 정답: {len(maze.solution) if maze.solution else '?'}스텝 | "
                  f"막다른길: {maze.dead_ends} | Mirage: {len(maze.mirage_traps)} | Seed: {maze.seed}")

        # ── Run benchmark ──
        runner = BenchmarkRunner(config)
        runner.run_all(providers, maze)
        all_results.extend(runner.results)

    # ── Print comparison ──
    if len(all_results) > 1:
        console.print(f"\n{'═'*60}" if not RICH else "")
        print_comparison_table(all_results)

    # ── Export ──
    out_path = export_json(all_results, maze, config, args.output)
    console.print(f"\n  ✓ JSON 저장: {out_path}")

    if args.csv:
        csv_path = export_csv(all_results)
        console.print(f"  ✓ CSV 저장: {csv_path}")

    # ── Summary ──
    if all_results:
        best = max(all_results, key=lambda r: r.hallumaze_score)
        console.print(f"\n  ★ 최고 점수: {best.model} ({best.provider}) — HalluScore {best.hallumaze_score:.3f} | MEI {best.mei:.3f}")


if __name__ == '__main__':
    main()
