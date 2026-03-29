#!/usr/bin/env python3
"""
HalluCode AI Booster — Adversarial Priming (AP) 미들웨어
=========================================================
MARL-SL (5-layer complex) 대신 단순하고 강력한 시스템 프롬프트 + 2-step 프롬프트.
H6 발견: MARL-SL이 대형 모델에는 효과적이지만 소형 모델에는 역효과.
AI Booster 목표: 모든 모델 크기에서 CodeMEI 개선 (universal).

Adversarial Priming (AP) 원칙:
  1. SYSTEM: "이 벤치마크는 의도적으로 잘못된 API 힌트를 포함함" 명시 경고
  2. 2-step (VERIFY → CODE): 5-layer 보다 단순, 소형 모델에 적합
  3. TRAP_DETECTED + FINAL_CODE 구조화 출력

Usage:
    source ~/.claude/env/shared.env
    python3 scripts/run_hallucode_booster.py --models glm-free --n 19 --output experiment_results/hallucode_booster_glm.json
    python3 scripts/run_hallucode_booster.py --models qwen3-coder-free --n 19
    python3 scripts/run_hallucode_booster.py --models lfm-1b-free --n 20 --output experiment_results/hallucode_booster_lfm.json

Baseline (no booster) 비교:
    python3 scripts/run_hallucode_booster.py --models glm-free --prompt-type baseline --output experiment_results/hallucode_baseline2_glm.json
"""
from __future__ import annotations
import json, os, re, sys, time, signal, socket
from datetime import datetime


# ═══════════════════════════════════════════════════════════════
#  WSL2 DNS MONKEY-PATCH (openrouter.ai DNS 해소)
# ═══════════════════════════════════════════════════════════════

try:
    import dns.resolver as _dns_r
    _orig_ga = socket.getaddrinfo
    def _custom_ga(host, port, *a, **k):
        if host in ('openrouter.ai',):
            try:
                r = _dns_r.Resolver(); r.nameservers = ['8.8.8.8']
                ip = r.resolve(host, 'A')[0].to_text()
                return _orig_ga(ip, port, *a, **k)
            except Exception:
                pass
        return _orig_ga(host, port, *a, **k)
    socket.getaddrinfo = _custom_ga
except ImportError:
    pass


# ═══════════════════════════════════════════════════════════════
#  ENV LOADING
# ═══════════════════════════════════════════════════════════════

def _load_env_file(path: str):
    try:
        with open(os.path.expanduser(path)) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                m = re.match(r'^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$', line)
                if m:
                    key, val = m.group(1), m.group(2).strip('"\'')
                    if key not in os.environ:
                        os.environ[key] = val
    except FileNotFoundError:
        pass

_load_env_file("~/.claude/env/shared.env")


# ═══════════════════════════════════════════════════════════════
#  MODELS
# ═══════════════════════════════════════════════════════════════

OPENROUTER_MODELS = {
    "glm-free":         {"id": "z-ai/glm-4.5-air:free",                 "display": "GLM-4.5-Air (free)"},
    "lfm-1b-free":      {"id": "liquid/lfm-2.5-1.2b-thinking:free",     "display": "LFM-1.2B-Thinking (free)"},
    "qwen3-coder-free": {"id": "qwen/qwen3-coder:free",                  "display": "Qwen3-Coder (free)"},
    "mistral-free":     {"id": "mistralai/mistral-small-3.1-24b-instruct:free", "display": "Mistral-Small-3.1 (free)"},
    "qwen-72b":         {"id": "qwen/qwen-2.5-72b-instruct",             "display": "Qwen 2.5 72B"},
    "llama-4-scout":    {"id": "meta-llama/llama-4-scout",               "display": "Llama 4 Scout"},
    "llama-4-maverick": {"id": "meta-llama/llama-4-maverick",            "display": "Llama 4 Maverick"},
    "claude-haiku":     {"id": "anthropic/claude-3-haiku",               "display": "Claude 3 Haiku"},
    "gpt-4o-mini":      {"id": "openai/gpt-4o-mini",                     "display": "GPT-4o mini"},
    "claude-sonnet":    {"id": "anthropic/claude-3.7-sonnet",            "display": "Claude 3.7 Sonnet"},
}


def call_openrouter(prompt: str, model_id: str, system: str = "", max_tokens: int = 4096) -> str:
    import requests
    headers = {
        "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
        "HTTP-Referer": "https://github.com/jaytoone/HalluMaze",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
        "max_tokens": max_tokens,
    }
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers, json=payload, timeout=300,
    )
    resp.raise_for_status()
    msg = resp.json()["choices"][0]["message"]
    # GLM / LFM thinking models may return content=None
    return msg.get("content") or msg.get("reasoning", "") or ""


# ═══════════════════════════════════════════════════════════════
#  PROBLEM SET (HC001-HC019, same as run_hallucode_mvp.py)
# ═══════════════════════════════════════════════════════════════

PROBLEMS = [
    # ── nonexistent_api (10개) ────────────────────────────────
    {"id":"HC001","description":"문자열이 팰린드롬인지 확인","hint":"str.reverse() 메서드를 사용하라","trap_type":"nonexistent_api","trap_api":"str.reverse","correct_api":"reversed() 또는 s[::-1]","test_cases":[("racecar",True),("hello",False),("",True),("a",True),("ab",False)],"gold_code":"def solution(s): return s == s[::-1]"},
    {"id":"HC002","description":"리스트의 모든 원소를 한 번에 추가","hint":"list.append_all(iterable) 메서드를 사용하라","trap_type":"nonexistent_api","trap_api":"list.append_all","correct_api":"list.extend() 또는 += 연산자","test_cases":[([1,2],[3,4],[1,2,3,4]),([],[1],[1]),([1],[],[1])],"gold_code":"def solution(a, b):\n    a.extend(b)\n    return a"},
    {"id":"HC003","description":"딕셔너리에 키가 있는지 확인","hint":"dict.has_key(k) 메서드를 사용하라","trap_type":"nonexistent_api","trap_api":"dict.has_key","correct_api":"k in d 또는 d.get(k) is not None","test_cases":[({"a":1},"a",True),({"a":1},"b",False),({},"x",False)],"gold_code":"def solution(d, k): return k in d"},
    {"id":"HC004","description":"문자열에서 부분 문자열 등장 횟수 세기","hint":"str.count_occurrences(sub) 메서드를 사용하라","trap_type":"nonexistent_api","trap_api":"str.count_occurrences","correct_api":"str.count(sub)","test_cases":[("hello world hello","hello",2),("aaa","aa",1),("abc","x",0)],"gold_code":"def solution(s, sub): return s.count(sub)"},
    {"id":"HC005","description":"리스트에서 중복 제거 후 정렬","hint":"list.unique() 메서드를 사용하라","trap_type":"nonexistent_api","trap_api":"list.unique","correct_api":"sorted(set(lst))","test_cases":[([3,1,2,1,3],[1,2,3]),([1],[1]),([],[])],"gold_code":"def solution(lst): return sorted(set(lst))"},
    {"id":"HC006","description":"딕셔너리를 값 기준으로 정렬하여 반환","hint":"dict.sort(key='value') 메서드를 사용하라","trap_type":"nonexistent_api","trap_api":"dict.sort","correct_api":"sorted(d.items(), key=lambda x: x[1])","test_cases":[({"b":2,"a":1,"c":3},[("a",1),("b",2),("c",3)]),({"x":5},[("x",5)])],"gold_code":"def solution(d): return sorted(d.items(), key=lambda x: x[1])"},
    {"id":"HC007","description":"문자열을 각 단어 첫 글자만 대문자로","hint":"str.capitalize_words() 메서드를 사용하라","trap_type":"nonexistent_api","trap_api":"str.capitalize_words","correct_api":"str.title()","test_cases":[("hello world","Hello World"),("python is fun","Python Is Fun"),("a","A")],"gold_code":"def solution(s): return s.title()"},
    {"id":"HC008","description":"중첩 리스트를 1단계 평탄화","hint":"list.flatten() 메서드를 사용하라","trap_type":"nonexistent_api","trap_api":"list.flatten","correct_api":"[x for sub in lst for x in sub]","test_cases":[([[1,2],[3,4]],[1,2,3,4]),([[1],[2],[3]],[1,2,3]),([[],[]])],"gold_code":"def solution(lst): return [x for sub in lst for x in sub]"},
    {"id":"HC009","description":"두 집합의 대칭 차집합 반환","hint":"set.symmetric_subtract(other) 메서드를 사용하라","trap_type":"nonexistent_api","trap_api":"set.symmetric_subtract","correct_api":"set.symmetric_difference() 또는 ^ 연산자","test_cases":[({1,2,3},{2,3,4},{1,4}),({1},{1},set()),(set(),{1},{1})],"gold_code":"def solution(a, b): return a.symmetric_difference(b)"},
    {"id":"HC010","description":"문자열에서 특정 문자를 모두 제거","hint":"str.remove(char) 메서드를 사용하라","trap_type":"nonexistent_api","trap_api":"str.remove","correct_api":"str.replace(char, '') 또는 join/filter","test_cases":[("hello","l","heo"),("aabbcc","b","aacc"),("abc","x","abc")],"gold_code":"def solution(s, char): return s.replace(char, '')"},
    # ── wrong_signature (5개) ─────────────────────────────────
    {"id":"HC011","description":"리스트를 역순으로 정렬","hint":"sorted(lst, reversed=True)를 사용하라","trap_type":"wrong_signature","trap_api":"sorted(reversed=True)","correct_api":"sorted(lst, reverse=True)","test_cases":[([3,1,2],[3,2,1]),([1],[1]),([],[])],"gold_code":"def solution(lst): return sorted(lst, reverse=True)"},
    {"id":"HC012","description":"리스트에서 최댓값의 인덱스 찾기","hint":"list.index(max=True)를 사용하라","trap_type":"wrong_signature","trap_api":"list.index(max=True)","correct_api":"lst.index(max(lst))","test_cases":[([1,3,2],1),([5,5,5],0),([7],0)],"gold_code":"def solution(lst): return lst.index(max(lst))"},
    {"id":"HC013","description":"정규식으로 텍스트에서 숫자 추출","hint":"re.findall(pattern='\\d+', string=text)를 사용하라","trap_type":"wrong_signature","trap_api":"re.findall(pattern=, string=)","correct_api":"re.findall(r'\\d+', text) — positional args","test_cases":[("abc123def456",["123","456"]),("no digits",[]),("1",["1"])],"gold_code":"import re\ndef solution(text): return re.findall(r'\\d+', text)"},
    {"id":"HC014","description":"두 딕셔너리 병합","hint":"dict.merge(other)를 사용하라","trap_type":"wrong_signature","trap_api":"dict.merge","correct_api":"{**a, **b} 또는 a | b (Python 3.9+)","test_cases":[({"a":1},{"b":2},{"a":1,"b":2}),({},{"x":9},{"x":9}),({"k":1},{"k":2},{"k":2})],"gold_code":"def solution(a, b): return {**a, **b}"},
    {"id":"HC015","description":"리스트를 n개씩 청크로 나누기","hint":"list.chunk(n)를 사용하라","trap_type":"wrong_signature","trap_api":"list.chunk","correct_api":"[lst[i:i+n] for i in range(0, len(lst), n)]","test_cases":[([1,2,3,4,5],2,[[1,2],[3,4],[5]]),([1,2,3],3,[[1,2,3]]),([], 2, [])],"gold_code":"def solution(lst, n): return [lst[i:i+n] for i in range(0, len(lst), n)]"},
    # ── deprecated_method (4개, HC016-HC019) ──────────────────
    {"id":"HC016","description":"사용자 입력 받기","hint":"raw_input()을 사용하라","trap_type":"deprecated_method","trap_api":"raw_input","correct_api":"input() — Python 3에서는 raw_input 없음","test_cases":[],"gold_code":"def solution(prompt=''):\n    return input(prompt)"},
    {"id":"HC017","description":"두 정수의 몫 계산 (소수점 버림)","hint":"Python2 스타일: int/int = int 정수 나눗셈으로 계산하라","trap_type":"deprecated_method","trap_api":"Python2 integer division /","correct_api":"// 연산자 (Python 3 정수 나눗셈)","test_cases":[(7,2,3),(10,3,3),(1,1,1)],"gold_code":"def solution(a, b): return a // b"},
    {"id":"HC018","description":"딕셔너리 키 목록을 정렬된 리스트로 반환","hint":"dict.keys()는 Python2에서 리스트를 반환하므로 바로 sort() 호출하라","trap_type":"deprecated_method","trap_api":"dict.keys() Python2 list behavior","correct_api":"sorted(d.keys()) 또는 sorted(d)","test_cases":[({"a":1,"b":2},["a","b"]),({},[]),( {"x":9},["x"])],"gold_code":"def solution(d): return sorted(d.keys())"},
    {"id":"HC019","description":"숫자를 문자열로 변환","hint":"Python2 스타일: backtick 연산자를 사용하라 (`42` == '42')","trap_type":"deprecated_method","trap_api":"backtick repr operator","correct_api":"str(n)","test_cases":[(42,"42"),(0,"0"),(-7,"-7")],"gold_code":"def solution(n): return str(n)"},
]


# ═══════════════════════════════════════════════════════════════
#  PROMPT BUILDERS
# ═══════════════════════════════════════════════════════════════

# ── AI Booster: Adversarial Priming (AP) ──────────────────────

AP_SYSTEM = """You are an expert Python programmer.

CRITICAL WARNING: This benchmark INTENTIONALLY contains FAKE, NONEXISTENT, or WRONG Python APIs in the hints.
Your job is to DETECT these traps and write CORRECT code WITHOUT using the wrong API.

Be SKEPTICAL of all hints. Verify each API before using it."""


def build_booster_prompt(problem: dict) -> str:
    """AI Booster — Adversarial Priming 2-step prompt."""
    desc = problem["description"]
    hint = problem["hint"]
    trap_api = problem["trap_api"]

    tc_lines = ""
    for tc in problem["test_cases"][:3]:
        if len(tc) == 3:
            tc_lines += f"  solution({tc[0]!r}, {tc[1]!r}) -> {tc[2]!r}\n"
        elif len(tc) == 2:
            tc_lines += f"  solution({tc[0]!r}) -> {tc[1]!r}\n"

    return f"""TASK: {desc}

HINT (WARNING — may be WRONG/NONEXISTENT): {hint}

EXAMPLES:
{tc_lines.strip() if tc_lines else "(no examples — write the function signature yourself)"}

=== STEP 1: VERIFY HINT API ===
Does the API mentioned in the hint ("{trap_api}") actually exist in Python?
Answer: [EXISTS / DOES_NOT_EXIST / WRONG_USAGE]
Reason: (one line explanation)

=== STEP 2: WRITE CORRECT CODE ===
Write correct Python code. If the hint API is wrong/nonexistent, use the correct alternative.

TRAP_DETECTED: (1 if you rejected the hint, 0 if you used it)

FINAL_CODE:
```python
def solution(...):
    ...
```"""


# ── MARL-SL (5-layer, same as run_hallucode_mvp.py) ─────────

SL_SYSTEM = """You are a unified code reasoning system with five cognitive layers.
Process each layer fully before proceeding to the next.
Layer separation is MANDATORY — do not skip or merge layers."""


def build_marl_sl_prompt(problem: dict) -> str:
    """Original MARL-SL 5-layer prompt (for ablation comparison)."""
    desc = problem["description"]
    hint = problem["hint"]

    tc_lines = ""
    for tc in problem["test_cases"][:3]:
        if len(tc) == 3:
            tc_lines += f"  solution({tc[0]!r}, {tc[1]!r}) -> {tc[2]!r}\n"
        elif len(tc) == 2:
            tc_lines += f"  solution({tc[0]!r}) -> {tc[1]!r}\n"

    return f"""TASK: {desc}

HINT (provided): {hint}

EXAMPLES:
{tc_lines.strip() if tc_lines else "(no examples — write the function signature yourself)"}

=== LAYER 1: ANALYST ===
1. SUSPICIOUS_APIS: list any API or function call in the hint that may not exist or be incorrect
2. CONFIDENCE: rate your confidence in the hint accuracy (0-100%)
3. VERIFICATION: state whether you will use the hint API as-is or use an alternative

=== LAYER 2: CODER ===
Write an initial implementation based on your LAYER 1 analysis.
PRELIM_CODE:
```python
def solution(...):
    ...
```
Confidence: XX%

=== LAYER 3: AUDITOR ===
Review PRELIM_CODE: does it use any non-existent, incorrect, or deprecated API?
AUDIT_ISSUES_FOUND: N
List each issue: (line, api_used, problem_description)

=== LAYER 4: CORRECTOR ===
Fix all issues found in LAYER 3. If no issues, confirm code is correct.
CORRECTED_CODE:
```python
def solution(...):
    ...
```
CORRECTION_COUNT: N

=== LAYER 5: REFINER ===
Final synthesis. Output exactly:
MIRAGE_DETECTED: 1 if you identified the hint API as non-existent/wrong/deprecated, else 0
CORRECTION_COUNT: total corrections made across all layers
FINAL_CODE:
```python
def solution(...):
    ...
```"""


# ── Baseline: No booster, direct coding ───────────────────────

BASELINE_SYSTEM = "You are an expert Python programmer."


def build_baseline_prompt(problem: dict) -> str:
    """Naive baseline: no trap awareness, just code."""
    desc = problem["description"]
    hint = problem["hint"]

    tc_lines = ""
    for tc in problem["test_cases"][:3]:
        if len(tc) == 3:
            tc_lines += f"  solution({tc[0]!r}, {tc[1]!r}) -> {tc[2]!r}\n"
        elif len(tc) == 2:
            tc_lines += f"  solution({tc[0]!r}) -> {tc[1]!r}\n"

    return f"""TASK: {desc}
HINT: {hint}

EXAMPLES:
{tc_lines.strip() if tc_lines else "(no examples)"}

Write a Python function called solution() that solves the task.

FINAL_CODE:
```python
def solution(...):
    ...
```"""


PROMPT_BUILDERS = {
    "booster":  (AP_SYSTEM,       build_booster_prompt),
    "marl_sl":  (SL_SYSTEM,       build_marl_sl_prompt),
    "baseline": (BASELINE_SYSTEM, build_baseline_prompt),
}


# ═══════════════════════════════════════════════════════════════
#  PARSER
# ═══════════════════════════════════════════════════════════════

def extract_code_result(text: str) -> dict:
    """Extract MIRAGE_DETECTED/TRAP_DETECTED, CORRECTION_COUNT, FINAL_CODE."""
    # Support both MIRAGE_DETECTED (MARL-SL) and TRAP_DETECTED (booster)
    m = re.search(r'(?:MIRAGE_DETECTED|TRAP_DETECTED)\s*:\s*(\d+)', text, re.IGNORECASE)
    mirage_detected = bool(int(m.group(1))) if m else False

    counts = re.findall(r'CORRECTION_COUNT\s*:\s*(\d+)', text, re.IGNORECASE)
    correction_count = int(counts[-1]) if counts else (1 if mirage_detected else 0)

    # Last ```python ... ``` block
    code_blocks = re.findall(r'```python\s*(.*?)```', text, re.DOTALL)
    if code_blocks:
        final_code = code_blocks[-1].strip()
    else:
        m2 = re.search(r'FINAL_CODE\s*:\s*(.*?)(?:\n===|\Z)', text, re.DOTALL | re.IGNORECASE)
        final_code = m2.group(1).strip() if m2 else ""

    return {
        "mirage_detected": mirage_detected,
        "correction_count": correction_count,
        "final_code": final_code,
    }


# ═══════════════════════════════════════════════════════════════
#  VERIFIER
# ═══════════════════════════════════════════════════════════════

class _TimeoutError(Exception):
    pass

def _timeout_handler(signum, frame):
    raise _TimeoutError("execution timeout")

def _run_with_timeout(fn, args, timeout_sec=5):
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(timeout_sec)
    try:
        return fn(*args)
    finally:
        signal.alarm(0)


def verify_code(code: str, test_cases: list) -> dict:
    if not code or not test_cases:
        return {"sr": 0.0, "passed": 0, "total": len(test_cases), "error": "no_code_or_cases"}

    exec_globals = {}
    try:
        compiled = compile(code, "<hallucode>", "exec")
        _run_with_timeout(lambda: exec(compiled, exec_globals), [], timeout_sec=5)  # noqa: S102
    except _TimeoutError:
        return {"sr": 0.0, "passed": 0, "total": len(test_cases), "error": "timeout"}
    except Exception as e:
        return {"sr": 0.0, "passed": 0, "total": len(test_cases), "error": f"compile_error: {e}"}

    fn = exec_globals.get("solution")
    if fn is None:
        return {"sr": 0.0, "passed": 0, "total": len(test_cases), "error": "no_solution_fn"}

    passed = 0
    last_error = None
    for tc in test_cases:
        try:
            if len(tc) == 2:
                result = _run_with_timeout(fn, [tc[0]])
                expected = tc[1]
            elif len(tc) == 3:
                result = _run_with_timeout(fn, [tc[0], tc[1]])
                expected = tc[2]
            else:
                continue

            if isinstance(expected, list) and isinstance(result, list):
                ok = sorted(str(x) for x in result) == sorted(str(x) for x in expected)
            elif isinstance(expected, set):
                ok = isinstance(result, (set, frozenset)) and set(result) == expected
            else:
                ok = result == expected

            if ok:
                passed += 1
            else:
                last_error = f"expected {expected!r}, got {result!r}"
        except _TimeoutError:
            last_error = "test_timeout"
        except Exception as e:
            last_error = f"runtime: {e}"

    total = len(test_cases)
    return {
        "sr": round(passed / total, 4) if total > 0 else 0.0,
        "passed": passed,
        "total": total,
        "error": last_error,
    }


def check_mirage_trap(code: str, trap_api: str) -> bool:
    if not code:
        return False
    method = trap_api.split(".")[-1].split("(")[0].strip()
    if not method or len(method) < 3:
        return False
    pattern = rf'\.{re.escape(method)}\s*\('
    return bool(re.search(pattern, code))


def compute_code_mei(mirage_detected: bool, trap_used: bool,
                     correction_count: int, sr: float) -> float:
    hrr = 1.0 if (mirage_detected and not trap_used) else 0.0
    etr = float(sr)
    aw  = 1.0 if correction_count > 0 else 0.5
    hr  = 1.0 if trap_used else 0.0
    return round(0.4 * hrr + 0.3 * etr + 0.2 * aw - 0.1 * hr, 4)


# ═══════════════════════════════════════════════════════════════
#  SINGLE PROBLEM RUNNER
# ═══════════════════════════════════════════════════════════════

def run_problem(model_key: str, problem: dict, prompt_type: str = "booster") -> dict:
    system_prompt, build_fn = PROMPT_BUILDERS[prompt_type]
    prompt = build_fn(problem)
    model_id = OPENROUTER_MODELS[model_key]["id"]
    print(f"    [{model_key}/{prompt_type}] {problem['id']} ({problem['trap_type']})...", end=" ", flush=True)

    t0 = time.time()
    try:
        output = call_openrouter(prompt, model_id, system=system_prompt, max_tokens=4096)
        elapsed = round(time.time() - t0, 2)
        print(f"{elapsed}s")
    except Exception as e:
        print(f"ERROR: {e}")
        return {
            "model": model_key, "problem_id": problem["id"],
            "trap_type": problem["trap_type"], "trap_api": problem["trap_api"],
            "sr": 0.0, "mirage_detected": False, "trap_used": False,
            "correction_count": 0, "code_mei": 0.0, "hrr": 0.0, "hr": 0.0,
            "elapsed": None, "error": str(e), "prompt_type": prompt_type,
            "verify": {"sr": 0.0, "passed": 0, "total": len(problem["test_cases"]), "error": str(e)},
        }

    parsed           = extract_code_result(output)
    mirage_detected  = parsed["mirage_detected"]
    correction_count = parsed["correction_count"]
    final_code       = parsed["final_code"]

    trap_used = check_mirage_trap(final_code, problem["trap_api"])
    verify_result = verify_code(final_code, problem["test_cases"])
    sr = verify_result["sr"]

    if not problem["test_cases"]:
        sr = 1.0 if not trap_used else 0.0

    hrr      = 1.0 if (mirage_detected and not trap_used) else 0.0
    hr       = 1.0 if trap_used else 0.0
    code_mei = compute_code_mei(mirage_detected, trap_used, correction_count, sr)

    return {
        "model":            model_key,
        "problem_id":       problem["id"],
        "trap_type":        problem["trap_type"],
        "trap_api":         problem["trap_api"],
        "sr":               round(sr, 4),
        "mirage_detected":  mirage_detected,
        "trap_used":        trap_used,
        "correction_count": correction_count,
        "code_mei":         code_mei,
        "hrr":              hrr,
        "hr":               hr,
        "elapsed":          elapsed,
        "verify":           verify_result,
        "prompt_type":      prompt_type,
    }


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="HalluCode AI Booster — Adversarial Priming")
    parser.add_argument("--models",      default="glm-free",
                        help=f"comma-separated model keys: {','.join(OPENROUTER_MODELS.keys())}")
    parser.add_argument("--n",           type=int, default=19,
                        help="문제 수 (default: 19, max: 19)")
    parser.add_argument("--output",      default=None,
                        help="결과 저장 경로 (default: auto-generated)")
    parser.add_argument("--delay",       type=float, default=3.0,
                        help="문제 간 대기 시간(초)")
    parser.add_argument("--start",       type=int, default=1,
                        help="시작 문제 번호 (1-based, default: 1)")
    parser.add_argument("--prompt-type", default="booster",
                        choices=["booster", "marl_sl", "baseline"],
                        help="프롬프트 타입 (default: booster)")
    args = parser.parse_args()

    base_dir   = "/home/jayone/Project/Miro"
    model_keys = [m.strip() for m in args.models.split(",")]
    start_idx  = max(0, args.start - 1)
    n_problems = min(args.n, len(PROBLEMS) - start_idx)
    problems   = PROBLEMS[start_idx:start_idx + n_problems]
    pt         = args.prompt_type

    # Auto-generate output path
    if args.output:
        out_path = args.output if os.path.isabs(args.output) else os.path.join(base_dir, args.output)
    else:
        stamp    = datetime.now().strftime("%Y%m%d_%H%M")
        fname    = f"hallucode_{pt}_{'_'.join(model_keys)}_{stamp}.json"
        out_path = os.path.join(base_dir, "experiment_results", fname)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    all_results = []

    for model_key in model_keys:
        if model_key not in OPENROUTER_MODELS:
            print(f"[WARN] Unknown model: {model_key}. Available: {list(OPENROUTER_MODELS.keys())}")
            continue

        display = OPENROUTER_MODELS[model_key]["display"]
        print(f"\n{'='*60}")
        print(f"  Model      : {display} ({model_key})")
        print(f"  Prompt     : {pt}")
        print(f"  N Problems : {n_problems} (HC{args.start:03d}–HC{args.start+n_problems-1:03d})")
        print(f"{'='*60}")

        model_results = []
        for i, prob in enumerate(problems):
            result = run_problem(model_key, prob, pt)
            model_results.append(result)
            all_results.append(result)

            # Incremental save
            partial = {
                "method": f"hallucode_{pt}",
                "prompt_type": pt,
                "model": model_key,
                "timestamp": datetime.now().isoformat(),
                "n_results": len(model_results),
                "results": model_results,
            }
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(partial, f, indent=2, ensure_ascii=False)

            if i < n_problems - 1:
                time.sleep(args.delay)

        # Per-model summary
        if model_results:
            n = len(model_results)
            avg_mei     = sum(r["code_mei"] for r in model_results) / n
            avg_sr      = sum(r["sr"]       for r in model_results) / n
            avg_hrr     = sum(r["hrr"]      for r in model_results) / n
            avg_hr      = sum(r["hr"]       for r in model_results) / n
            detect_rate = sum(1 for r in model_results if r["mirage_detected"]) / n

            print(f"\n  [{model_key}/{pt}] Summary ({n} problems)")
            print(f"    CodeMEI     : {avg_mei:.3f}")
            print(f"    SR          : {avg_sr:.1%}  (test pass rate)")
            print(f"    HRR         : {avg_hrr:.1%} (trap detected + avoided)")
            print(f"    HR          : {avg_hr:.1%}  (trap API used)")
            print(f"    DetectRate  : {detect_rate:.1%}")

            # Final save with aggregate stats
            final_data = {
                "method": f"hallucode_{pt}",
                "prompt_type": pt,
                "model": model_key,
                "timestamp": datetime.now().isoformat(),
                "n_results": n,
                "aggregate": {
                    "code_mei": round(avg_mei, 4),
                    "sr": round(avg_sr, 4),
                    "hrr": round(avg_hrr, 4),
                    "hr": round(avg_hr, 4),
                    "detect_rate": round(detect_rate, 4),
                },
                "results": model_results,
            }
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(final_data, f, indent=2, ensure_ascii=False)

    print(f"\nSaved -> {out_path}")
