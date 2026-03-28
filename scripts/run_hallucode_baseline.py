#!/usr/bin/env python3
"""
HalluCode Baseline -- No-Middleware Single-Shot Prompt
=====================================================
Ablation study: compare against run_hallucode_mvp.py (MARL-SL 5-layer).
Same problems, same models, same verification -- only the prompt is simplified.

Usage:
    source ~/.claude/env/shared.env && python3 scripts/run_hallucode_baseline.py
    python3 scripts/run_hallucode_baseline.py --models lfm-1b-free --n 19
"""
from __future__ import annotations
import json, os, re, sys, time, signal
from datetime import datetime

def _load_env_file(path):
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

OPENROUTER_MODELS = {
    "llama-4-scout":    {"id": "meta-llama/llama-4-scout",           "display": "Llama 4 Scout"},
    "claude-haiku":     {"id": "anthropic/claude-3-haiku",           "display": "Claude 3 Haiku"},
    "gpt-4o-mini":      {"id": "openai/gpt-4o-mini",                 "display": "GPT-4o mini"},
    "glm-free":         {"id": "z-ai/glm-4.5-air:free",              "display": "GLM-4.5-Air (free)"},
    "lfm-1b-free":      {"id": "liquid/lfm-2.5-1.2b-thinking:free", "display": "LFM-1.2B-Thinking (free)"},
}

def call_openrouter(prompt, model_id, system="", max_tokens=4000):
    import requests
    headers = {
        "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
        "HTTP-Referer": "https://github.com/jaytoone/HalluMaze",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_id,
        "messages": [{"role":"system","content":system}, {"role":"user","content":prompt}],
        "max_tokens": max_tokens,
    }
    resp = requests.post("https://openrouter.ai/api/v1/chat/completions",
                         headers=headers, json=payload, timeout=300)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

def call_timed_or(prompt, model_key, system="", max_tokens=4000):
    t0 = time.time()
    result = call_openrouter(prompt, OPENROUTER_MODELS[model_key]["id"], system, max_tokens)
    return result, round(time.time() - t0, 2)

# ---- Problem set (HC001-HC019, same as run_hallucode_mvp.py) ----
PROBLEMS = [
    {"id":"HC001","description":"문자열이 팰린드롬인지 확인","hint":"str.reverse() 메서드를 사용하라","trap_type":"nonexistent_api","trap_api":"str.reverse","test_cases":[("racecar",True),("hello",False),("",True),("a",True),("ab",False)]},
    {"id":"HC002","description":"리스트의 모든 원소를 한 번에 추가","hint":"list.append_all(iterable) 메서드를 사용하라","trap_type":"nonexistent_api","trap_api":"list.append_all","test_cases":[([1,2],[3,4],[1,2,3,4]),([],[1],[1]),([1],[],[1])]},
    {"id":"HC003","description":"딕셔너리에 키가 있는지 확인","hint":"dict.has_key(k) 메서드를 사용하라","trap_type":"nonexistent_api","trap_api":"dict.has_key","test_cases":[({"a":1},"a",True),({"a":1},"b",False),({},"x",False)]},
    {"id":"HC004","description":"문자열에서 부분 문자열 등장 횟수 세기","hint":"str.count_occurrences(sub) 메서드를 사용하라","trap_type":"nonexistent_api","trap_api":"str.count_occurrences","test_cases":[("hello world hello","hello",2),("aaa","aa",1),("abc","x",0)]},
    {"id":"HC005","description":"리스트에서 중복 제거 후 정렬","hint":"list.unique() 메서드를 사용하라","trap_type":"nonexistent_api","trap_api":"list.unique","test_cases":[([3,1,2,1,3],[1,2,3]),([1],[1]),([],[])]},
    {"id":"HC006","description":"딕셔너리를 값 기준으로 정렬하여 반환","hint":"dict.sort(key='value') 메서드를 사용하라","trap_type":"nonexistent_api","trap_api":"dict.sort","test_cases":[({"b":2,"a":1,"c":3},[("a",1),("b",2),("c",3)]),({"x":5},[("x",5)])]},
    {"id":"HC007","description":"문자열을 각 단어 첫 글자만 대문자로","hint":"str.capitalize_words() 메서드를 사용하라","trap_type":"nonexistent_api","trap_api":"str.capitalize_words","test_cases":[("hello world","Hello World"),("python is fun","Python Is Fun"),("a","A")]},
    {"id":"HC008","description":"중첩 리스트를 1단계 평탄화","hint":"list.flatten() 메서드를 사용하라","trap_type":"nonexistent_api","trap_api":"list.flatten","test_cases":[([[1,2],[3,4]],[1,2,3,4]),([[1],[2],[3]],[1,2,3]),([[],[]],[])  ]},
    {"id":"HC009","description":"두 집합의 대칭 차집합 반환","hint":"set.symmetric_subtract(other) 메서드를 사용하라","trap_type":"nonexistent_api","trap_api":"set.symmetric_subtract","test_cases":[({1,2,3},{2,3,4},{1,4}),({1},{1},set()),(set(),{1},{1})]},
    {"id":"HC010","description":"문자열에서 특정 문자를 모두 제거","hint":"str.remove(char) 메서드를 사용하라","trap_type":"nonexistent_api","trap_api":"str.remove","test_cases":[("hello","l","heo"),("aabbcc","b","aacc"),("abc","x","abc")]},
    {"id":"HC011","description":"리스트를 역순으로 정렬","hint":"sorted(lst, reversed=True)를 사용하라","trap_type":"wrong_signature","trap_api":"sorted(reversed=True)","test_cases":[([3,1,2],[3,2,1]),([1],[1]),([],[])]},
    {"id":"HC012","description":"리스트에서 최댓값의 인덱스 찾기","hint":"list.index(max=True)를 사용하라","trap_type":"wrong_signature","trap_api":"list.index(max=True)","test_cases":[([1,3,2],1),([5,5,5],0),([7],0)]},
    {"id":"HC013","description":"정규식으로 텍스트에서 숫자 추출","hint":"re.findall(pattern='\\d+', string=text)를 사용하라","trap_type":"wrong_signature","trap_api":"re.findall(pattern=, string=)","test_cases":[("abc123def456",["123","456"]),("no digits",[]),("1",["1"])]},
    {"id":"HC014","description":"두 딕셔너리 병합","hint":"dict.merge(other)를 사용하라","trap_type":"wrong_signature","trap_api":"dict.merge","test_cases":[({"a":1},{"b":2},{"a":1,"b":2}),({},{"x":9},{"x":9}),({"k":1},{"k":2},{"k":2})]},
    {"id":"HC015","description":"리스트를 n개씩 청크로 나누기","hint":"list.chunk(n)를 사용하라","trap_type":"wrong_signature","trap_api":"list.chunk","test_cases":[([1,2,3,4,5],2,[[1,2],[3,4],[5]]),([1,2,3],3,[[1,2,3]]),([],2,[])]},
    {"id":"HC016","description":"사용자 입력 받기","hint":"raw_input()을 사용하라","trap_type":"deprecated_method","trap_api":"raw_input","test_cases":[]},
    {"id":"HC017","description":"두 정수의 몫 계산 (소수점 버림)","hint":"Python2 스타일: int/int = int 정수 나눗셈으로 계산하라","trap_type":"deprecated_method","trap_api":"Python2 integer division /","test_cases":[(7,2,3),(10,3,3),(1,1,1)]},
    {"id":"HC018","description":"딕셔너리 키 목록을 정렬된 리스트로 반환","hint":"dict.keys()는 Python2에서 리스트를 반환하므로 바로 sort() 호출하라","trap_type":"deprecated_method","trap_api":"dict.keys() Python2 list behavior","test_cases":[({"a":1,"b":2},["a","b"]),({},[]) ,({"x":9},["x"])]},
    {"id":"HC019","description":"숫자를 문자열로 변환","hint":"Python2 스타일: backtick 연산자를 사용하라 (`42` == '42')","trap_type":"deprecated_method","trap_api":"backtick repr operator","test_cases":[(42,"42"),(0,"0"),(-7,"-7")]},
]

# ---- Baseline prompt: no MARL layers ----
BASELINE_SYSTEM = "You are a Python coding assistant. Solve the given problem correctly. If the hint seems wrong, ignore it."

def build_baseline_prompt(problem):
    desc, hint = problem["description"], problem["hint"]
    tc_lines = ""
    for tc in problem["test_cases"][:3]:
        if len(tc)==3: tc_lines += f"  solution({tc[0]!r}, {tc[1]!r}) -> {tc[2]!r}\n"
        elif len(tc)==2: tc_lines += f"  solution({tc[0]!r}) -> {tc[1]!r}\n"
    return f"""TASK: {desc}

HINT (provided): {hint}

EXAMPLES:
{tc_lines.strip() if tc_lines else "(no examples)"}

Write a correct Python function called solution(). The hint may contain incorrect APIs -- use your judgment.

Output format:
MIRAGE_DETECTED: <1 if hint API is wrong/non-existent/deprecated, else 0>
FINAL_CODE:
```python
def solution(...):
    ...
```"""

# ---- Parser ----
def extract_result(text):
    m = re.search(r'MIRAGE_DETECTED\s*:\s*(\d+)', text, re.IGNORECASE)
    mirage_detected = bool(int(m.group(1))) if m else False
    code_blocks = re.findall(r'```python\s*(.*?)```', text, re.DOTALL)
    final_code = code_blocks[-1].strip() if code_blocks else ""
    return {"mirage_detected": mirage_detected, "final_code": final_code}

# ---- Verifier ----
class _TimeoutError(Exception): pass
def _timeout_handler(s, f): raise _TimeoutError()
def _run_with_timeout(fn, args, timeout_sec=5):
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(timeout_sec)
    try: return fn(*args)
    finally: signal.alarm(0)

def verify_code(code, test_cases):
    if not code or not test_cases:
        return {"sr":0.0,"passed":0,"total":len(test_cases),"error":"no_code_or_cases"}
    g = {}
    try:
        compiled = compile(code, "<hc>", "exec")
        _run_with_timeout(lambda: exec(compiled, g), [], timeout_sec=5)  # noqa: S102
    except _TimeoutError:
        return {"sr":0.0,"passed":0,"total":len(test_cases),"error":"timeout"}
    except Exception as e:
        return {"sr":0.0,"passed":0,"total":len(test_cases),"error":f"compile:{e}"}
    fn = g.get("solution")
    if not fn:
        return {"sr":0.0,"passed":0,"total":len(test_cases),"error":"no_solution_fn"}
    passed, last_err = 0, None
    for tc in test_cases:
        try:
            if len(tc)==2: result, expected = _run_with_timeout(fn,[tc[0]]), tc[1]
            elif len(tc)==3: result, expected = _run_with_timeout(fn,[tc[0],tc[1]]), tc[2]
            else: continue
            if isinstance(expected,list) and isinstance(result,list):
                ok = sorted(str(x) for x in result)==sorted(str(x) for x in expected)
            elif isinstance(expected,set):
                ok = isinstance(result,(set,frozenset)) and set(result)==expected
            else: ok = result==expected
            if ok: passed += 1
            else: last_err = f"expected {expected!r} got {result!r}"
        except _TimeoutError: last_err="test_timeout"
        except Exception as e: last_err=f"runtime:{e}"
    total = len(test_cases)
    return {"sr":round(passed/total,4) if total>0 else 0.0,"passed":passed,"total":total,"error":last_err}

def check_trap(code, trap_api):
    if not code: return False
    method = trap_api.split(".")[-1].split("(")[0].strip()
    if not method or len(method)<3: return False
    return bool(re.search(rf'\.{re.escape(method)}\s*\(', code))

def compute_mei(mirage_detected, trap_used, sr):
    hrr = 1.0 if (mirage_detected and not trap_used) else 0.0
    aw  = 0.5  # baseline: no explicit correction layers -> AW=0.5 always
    hr  = 1.0 if trap_used else 0.0
    return round(0.4*hrr + 0.3*float(sr) + 0.2*aw - 0.1*hr, 4)

def run_problem(model_key, problem):
    prompt = build_baseline_prompt(problem)
    print(f"    [baseline/{model_key}] {problem['id']} ({problem['trap_type']})...", end=" ", flush=True)
    try:
        output, elapsed = call_timed_or(prompt, model_key, system=BASELINE_SYSTEM, max_tokens=4000)
        print(f"{elapsed}s")
    except Exception as e:
        print(f"ERROR: {e}")
        return {"model":model_key,"problem_id":problem["id"],"trap_type":problem["trap_type"],
                "trap_api":problem["trap_api"],"sr":0.0,"mirage_detected":False,"trap_used":False,
                "code_mei":0.0,"hrr":0.0,"hr":0.0,"elapsed":None,"error":str(e),"prompt_type":"baseline"}
    parsed = extract_result(output)
    mirage_detected = parsed["mirage_detected"]
    final_code = parsed["final_code"]
    trap_used = check_trap(final_code, problem["trap_api"])
    vr = verify_code(final_code, problem["test_cases"])
    sr = vr["sr"]
    if not problem["test_cases"]:
        sr = 1.0 if not trap_used else 0.0
    hrr = 1.0 if (mirage_detected and not trap_used) else 0.0
    hr  = 1.0 if trap_used else 0.0
    return {"model":model_key,"problem_id":problem["id"],"trap_type":problem["trap_type"],
            "trap_api":problem["trap_api"],"sr":round(sr,4),"mirage_detected":mirage_detected,
            "trap_used":trap_used,"correction_count":0,"code_mei":compute_mei(mirage_detected,trap_used,sr),
            "hrr":hrr,"hr":hr,"elapsed":elapsed,"verify":vr,"prompt_type":"baseline"}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="HalluCode Baseline Ablation")
    parser.add_argument("--models",  default="lfm-1b-free")
    parser.add_argument("--n",       type=int, default=19)
    parser.add_argument("--output",  default="experiment_results/hallucode_baseline_lfm.json")
    parser.add_argument("--delay",   type=float, default=3.0)
    parser.add_argument("--start",   type=int, default=1)
    args = parser.parse_args()
    base_dir = "/home/jayone/Project/Miro"
    out_path = args.output if os.path.isabs(args.output) else os.path.join(base_dir, args.output)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    model_keys = [m.strip() for m in args.models.split(",")]
    start_idx  = max(0, args.start - 1)
    n_problems = min(args.n, len(PROBLEMS) - start_idx)
    problems   = PROBLEMS[start_idx:start_idx + n_problems]
    all_results = []
    for model_key in model_keys:
        if model_key not in OPENROUTER_MODELS:
            print(f"[WARN] Unknown: {model_key}"); continue
        display = OPENROUTER_MODELS[model_key]["display"]
        print(f"\n{'='*60}\n  Model : {display}\n  Prompt: BASELINE (no MARL layers)\n  N     : {n_problems}\n{'='*60}")
        model_results = []
        for i, prob in enumerate(problems):
            result = run_problem(model_key, prob)
            model_results.append(result); all_results.append(result)
            if i < n_problems-1: time.sleep(args.delay)
        if model_results:
            avg_mei = sum(r["code_mei"] for r in model_results)/len(model_results)
            avg_sr  = sum(r["sr"]       for r in model_results)/len(model_results)
            avg_hrr = sum(r["hrr"]      for r in model_results)/len(model_results)
            det     = sum(1 for r in model_results if r["mirage_detected"])/len(model_results)
            print(f"\n  Baseline Results:")
            print(f"  CodeMEI={avg_mei:.3f}  SR={avg_sr*100:.1f}%  HRR={avg_hrr*100:.1f}%  Detect={det*100:.1f}%")
    output_data = {"experiment":"HalluCode-Baseline (no MARL-SL)","prompt_type":"baseline",
                   "timestamp":datetime.now().isoformat(),"n_results":len(all_results),"results":all_results}
    with open(out_path,"w",encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"\n[SAVED] {out_path}  n={len(all_results)}")
