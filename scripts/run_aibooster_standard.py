#!/usr/bin/env python3
"""
AI Booster v3 -- Standard Coding Benchmark (No Trap Injection)
=============================================================
목표: HalluCode에서 검증된 metacognitive middleware (AI Booster)를
     표준 공인 코딩 벤치마크 (HumanEval, MBPP)에 적용했을 때
     raw pass@1 향상 효과를 검증.

연구 가설:
  H_AB: AI Booster 미들웨어는 trap injection 없이도
        공인 코딩 벤치마크에서 pass@1을 향상시킨다.

설계 원칙:
  - 표준 HumanEval 원본 사용 (trap 주입 없음)
  - AI Booster v3: 3-step metacognitive verification middleware
    (ANALYZE -> VERIFY -> CODE) -- trap-free general version
  - Baseline: 동일 문제에 시스템 프롬프트 없이 직접 풀기
  - pass@1 측정: HumanEval 내장 test cases 실행

Primary models (HF popular — 어그로용):
    # OpenRouter 파일럿 (지금 바로 실행 가능):
    python3 scripts/run_aibooster_standard.py --model llama-70b-free --mode booster --n 30 --seed 42
    python3 scripts/run_aibooster_standard.py --model llama-70b-free --mode baseline --n 30 --seed 42
    python3 scripts/run_aibooster_standard.py --model qwen3-coder-free --mode booster --n 30 --seed 42
    python3 scripts/run_aibooster_standard.py --model qwen3-coder-free --mode baseline --n 30 --seed 42
    python3 scripts/run_aibooster_standard.py --model qwen3-next-free --mode booster --n 30 --seed 42
    python3 scripts/run_aibooster_standard.py --model qwen3-next-free --mode baseline --n 30 --seed 42
    # NIPA H200 (local-qwen25coder, local-llama33, local-qwen3-32b)

Legacy / prior experiment reference:
    python3 scripts/run_aibooster_standard.py --model glm-free --mode booster --n 30 --seed 42
    python3 scripts/run_aibooster_standard.py --model local-qwen35 --mode booster --n 30 --seed 42

NIPA vLLM launch commands (H200 80GB):
    # [1] Qwen2.5-Coder-32B BF16 — HF #1 coding model (926k dl, 92.7% HumanEval)
    python -m vllm.entrypoints.openai.api_server \
        --model Qwen/Qwen2.5-Coder-32B-Instruct --dtype bfloat16 \
        --gpu-memory-utilization 0.85 --port 18001
    # [2] Llama-3.3-70B INT4 — Meta flagship (88.4% HumanEval, ~17.5GB VRAM)
    python -m vllm.entrypoints.openai.api_server \
        --model meta-llama/Llama-3.3-70B-Instruct --load-in-4bit \
        --dtype bfloat16 --gpu-memory-utilization 0.85 --port 18002
    # [3] Qwen3-32B — 2025년 5월 출시, HF 최트렌딩 (300만+ dl, hybrid thinking)
    python -m vllm.entrypoints.openai.api_server \
        --model Qwen/Qwen3-32B --dtype bfloat16 \
        --gpu-memory-utilization 0.85 --port 18003
"""
from __future__ import annotations
import json, os, re, sys, time, random, socket, subprocess, tempfile
from datetime import datetime

# ===== WSL2 DNS MONKEY-PATCH =====
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

# ===== ENV LOADING =====
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

# ===== MODELS =====
OPENROUTER_MODELS = {
    "glm-free":         {"id": "z-ai/glm-4.5-air:free",                  "display": "GLM-4.5-Air (free)"},
    "lfm-1b-free":      {"id": "liquid/lfm-2.5-1.2b-thinking:free",      "display": "LFM-1.2B-Thinking (free)"},
    "llama-70b-free":   {"id": "meta-llama/llama-3.3-70b-instruct:free", "display": "Llama 3.3 70B (free)"},
    "qwen3-next-free":  {"id": "qwen/qwen3-next-80b-a3b-instruct:free",  "display": "Qwen3-Next-80B-A3B (free)"},
    "qwen3-coder-free": {"id": "qwen/qwen3-coder:free",                   "display": "Qwen3-Coder (free)"},
    "gpt-4o-mini":      {"id": "openai/gpt-4o-mini",                     "display": "GPT-4o mini"},
}
MODELS_LOCAL = {
    # ── [LEGACY] Qwen3.5-122B-A10B: HalluCode 실험 연속성용 (일반 인기 모델 아님) ──
    #     NIPA 커스텀 서빙명 (HF 공개 모델 아님) — 논문 연속성 위해 보존
    "local-qwen35": {
        "id": "qwen3.5-122b-a10b",
        "display": "Qwen3.5-122B-A10B (NIPA local, legacy)",
        "base_url": "http://localhost:18000/v1",
    },
    # ── [PRIMARY] HuggingFace 실제 인기 모델 — 논문 임팩트 극대화 ────────────
    # [1] Qwen2.5-Coder-32B: 코딩 특화 최인기 모델 (HF #1 coding, 92.7% HumanEval)
    #     vllm serve Qwen/Qwen2.5-Coder-32B-Instruct --port 18001 --dtype bfloat16 --max-model-len 8192
    "local-qwen25coder": {
        "id": "Qwen/Qwen2.5-Coder-32B-Instruct",
        "display": "Qwen2.5-Coder-32B (NIPA local)",
        "base_url": "http://localhost:18001/v1",
    },
    # [2] Llama-3.3-70B INT4: Meta 최인기 범용 모델 (88.4% HumanEval, ~17.5GB VRAM)
    #     python -m vllm.entrypoints.openai.api_server --model meta-llama/Llama-3.3-70B-Instruct --load-in-4bit --dtype bfloat16 --gpu-memory-utilization 0.85 --port 18002
    "local-llama33": {
        "id": "meta-llama/Llama-3.3-70B-Instruct",
        "display": "Llama-3.3-70B-INT4 (NIPA local)",
        "base_url": "http://localhost:18002/v1",
    },
    # [3] Qwen3-32B: 2025년 5월 출시, HF 최트렌딩 (300만+ 다운로드), hybrid thinking
    #     python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen3-32B --dtype bfloat16 --gpu-memory-utilization 0.85 --port 18003
    "local-qwen3-32b": {
        "id": "Qwen/Qwen3-32B",
        "display": "Qwen3-32B (NIPA local)",
        "base_url": "http://localhost:18003/v1",
    },
}
MODELS_ALL = {**OPENROUTER_MODELS, **MODELS_LOCAL}

# ===== AI BOOSTER v3 -- General Metacognitive Middleware =====
# HalluCode 검증된 3-step verification, trap-free general version
AIBOOSTER_SYSTEM = """You are an expert Python programmer with enhanced metacognitive verification.

When solving any coding problem, follow these 3 steps before writing code:

STEP 1 - ANALYZE: Identify potential pitfalls
  * Incorrect assumptions about API behavior or function signatures
  * Edge cases: empty input, None values, overflow, type mismatches
  * Common algorithmic mistakes: off-by-one, wrong loop bounds, mutating input

STEP 2 - VERIFY: For each function/API you plan to use
  * Confirm it exists in standard Python or the target library
  * Confirm argument types and order are correct
  * Confirm the return type matches how you use it

STEP 3 - CODE: Write the solution after the above checks

This metacognitive verification process improves code correctness. Do not skip steps."""


def build_booster_prompt(problem: dict) -> str:
    return f"""{problem["prompt"]}

Follow the AI Booster protocol:

=== STEP 1: ANALYZE -- Potential Pitfalls ===
(Edge cases, API assumptions, algorithmic risks)

=== STEP 2: VERIFY -- API/Logic Check ===
(Confirm all functions/methods you plan to use exist and are correct)

=== STEP 3: FINAL CODE ===
```python
# Complete the function below:
```"""


def build_baseline_prompt(problem: dict) -> str:
    return f"""{problem["prompt"]}

Complete the function implementation in Python.

```python
# Complete the function below:
```"""


# ===== API CALLS =====
import requests

def call_openrouter(prompt: str, model_id: str, system: str = "", max_tokens: int = 2048) -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": model_id,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.0,
    }
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=180,
    )
    if resp.status_code == 429:
        raise RuntimeError("rate_limit_429")
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"].get("content") or ""


def call_local(prompt: str, model: dict, system: str = "", max_tokens: int = 2048) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": model["id"],
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.0,
    }
    resp = requests.post(
        f"{model['base_url']}/chat/completions",
        json=payload,
        timeout=180,
    )
    if resp.status_code == 429:
        raise RuntimeError("rate_limit_429")
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"].get("content") or ""


def call_model(prompt: str, model_key: str, system: str = "", max_tokens: int = 2048) -> str:
    if model_key.startswith("local-"):
        return call_local(prompt, MODELS_LOCAL[model_key], system=system, max_tokens=max_tokens)
    return call_openrouter(prompt, OPENROUTER_MODELS[model_key]["id"], system=system, max_tokens=max_tokens)


# ===== HUMANEVAL LOADER =====
def load_humaneval(n: int = 30, seed: int = 42) -> list[dict]:
    try:
        from datasets import load_dataset
        ds = load_dataset("openai/openai_humaneval", split="test")
    except Exception as e:
        print(f"[ERROR] Failed to load HumanEval: {e}")
        print("  Install: pip install datasets")
        sys.exit(1)

    problems = list(ds)
    rng = random.Random(seed)
    rng.shuffle(problems)
    selected = problems[:n]

    return [
        {
            "task_id": p["task_id"],
            "entry_point": p["entry_point"],
            "prompt": p["prompt"],
            "canonical_solution": p["canonical_solution"],
            "test": p["test"],
        }
        for p in selected
    ]


# ===== CODE EXTRACTION =====
def extract_code(response: str, entry_point: str) -> str:
    # Try ```python ... ``` blocks
    m = re.search(r'```python\s*(.*?)```', response, re.DOTALL)
    if m:
        code = m.group(1).strip()
        if f'def {entry_point}' in code:
            return code

    # Try ``` ... ``` blocks
    m = re.search(r'```\s*(.*?)```', response, re.DOTALL)
    if m:
        code = m.group(1).strip()
        if f'def {entry_point}' in code:
            return code

    # Try STEP 3 / FINAL CODE section
    for marker in ['STEP 3: FINAL CODE', 'STEP 3 --', 'FINAL CODE', 'FINAL_CODE']:
        idx = response.find(marker)
        if idx >= 0:
            tail = response[idx:]
            m2 = re.search(r'```(?:python)?\s*(.*?)```', tail, re.DOTALL)
            if m2 and f'def {entry_point}' in m2.group(1):
                return m2.group(1).strip()

    # Fallback: extract def block from full response
    if f'def {entry_point}' in response:
        lines = response.split('\n')
        func_lines = []
        in_func = False
        for line in lines:
            if f'def {entry_point}' in line:
                in_func = True
            if in_func:
                func_lines.append(line)
                # Stop at next top-level def/class that isn't the target
                if func_lines and len(func_lines) > 1:
                    stripped = line.lstrip()
                    if (stripped.startswith('def ') or stripped.startswith('class ')) and f'def {entry_point}' not in line:
                        func_lines = func_lines[:-1]
                        break
        return '\n'.join(func_lines)

    return response.strip()


# ===== EVALUATION =====
def execute_humaneval(solution_code: str, test_code: str, entry_point: str, timeout: int = 10) -> tuple[bool, str]:
    if not solution_code or f'def {entry_point}' not in solution_code:
        return False, f"No valid function definition for {entry_point}"

    full_code = f"{solution_code}\n\n{test_code}\n\ncheck({entry_point})\n"

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(full_code)
        fname = f.name

    try:
        result = subprocess.run(
            [sys.executable, fname],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode == 0:
            return True, ""
        else:
            return False, (result.stderr or result.stdout)[:300]
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, str(e)
    finally:
        try:
            os.unlink(fname)
        except OSError:
            pass


# ===== MAIN EXPERIMENT =====
def run_experiment(model_key: str, mode: str, n: int, seed: int, output_path: str):
    model_info = MODELS_ALL[model_key]
    print(f"\n[AI Booster v3 -- Standard HumanEval]")
    print(f"  Model: {model_info['display']}")
    print(f"  Mode: {mode.upper()}")
    print(f"  n={n}, seed={seed}")
    print(f"  Output: {output_path}")
    print("=" * 60)

    problems = load_humaneval(n=n, seed=seed)
    print(f"  Loaded {len(problems)} standard HumanEval problems (no traps)")

    results = []
    passed = 0
    errors = 0

    for i, prob in enumerate(problems):
        task_id = prob["task_id"]
        entry_point = prob["entry_point"]
        print(f"\n[{i+1}/{len(problems)}] {task_id} ({entry_point})", end=" ", flush=True)

        if mode == "booster":
            prompt = build_booster_prompt(prob)
            system = AIBOOSTER_SYSTEM
        else:
            prompt = build_baseline_prompt(prob)
            system = ""

        response = None
        error_msg = None
        for attempt in range(3):
            try:
                response = call_model(prompt, model_key, system=system)
                break
            except RuntimeError as e:
                if "rate_limit_429" in str(e):
                    wait = 15 * (attempt + 1)
                    print(f"\n    Rate limit -- waiting {wait}s", flush=True)
                    time.sleep(wait)
                else:
                    error_msg = str(e)
                    break
            except Exception as e:
                error_msg = str(e)
                if attempt < 2:
                    time.sleep(5)

        if response is None:
            print(f"[ERROR] {error_msg}", flush=True)
            errors += 1
            results.append({
                "task_id": task_id,
                "entry_point": entry_point,
                "mode": mode,
                "passed": False,
                "error": error_msg or "no response",
                "response_len": 0,
            })
            continue

        code = extract_code(response, entry_point)
        ok, exec_err = execute_humaneval(code, prob["test"], entry_point)

        status = "PASS" if ok else f"FAIL({exec_err[:40]})"
        print(status, flush=True)

        if ok:
            passed += 1

        results.append({
            "task_id": task_id,
            "entry_point": entry_point,
            "mode": mode,
            "passed": ok,
            "exec_error": exec_err if not ok else "",
            "response_len": len(response),
        })

        if (i + 1) % 5 == 0:
            _save(output_path, results, passed, errors, model_key, mode, n, seed, partial=True)
            valid_so_far = i + 1 - errors
            print(f"  [CKPT] {i+1}/{len(problems)} | pass@1={passed/valid_so_far:.3f}", flush=True)

        time.sleep(1)

    _save(output_path, results, passed, errors, model_key, mode, n, seed, partial=False)

    valid = len(results) - errors
    pass_at_1 = passed / valid if valid > 0 else 0.0
    print(f"\n{'='*60}")
    print(f"  FINAL: pass@1 = {pass_at_1:.3f} ({passed}/{valid})")
    print(f"  Errors: {errors}")
    print(f"  Saved: {output_path}")
    return pass_at_1


def _save(path, results, passed, errors, model_key, mode, n, seed, partial=False):
    valid = len(results) - errors
    pass_at_1 = passed / valid if valid > 0 else 0.0
    data = {
        "experiment": "AI Booster v3 -- Standard HumanEval (no trap injection)",
        "hypothesis": "H_AB: AI Booster middleware improves raw pass@1 on standard coding benchmarks",
        "model": MODELS_ALL[model_key]["display"],
        "model_key": model_key,
        "mode": mode,
        "n_requested": n,
        "n_valid": valid,
        "n_errors": errors,
        "seed": seed,
        "partial": partial,
        "pass_at_1": round(pass_at_1, 4),
        "passed": passed,
        "timestamp": datetime.now().isoformat(),
        "results": results,
    }
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AI Booster v3 -- Standard HumanEval Experiment")
    parser.add_argument("--model", default="glm-free", choices=list(MODELS_ALL.keys()))
    parser.add_argument("--mode", default="booster", choices=["booster", "baseline"],
                        help="booster=AI Booster v3 middleware, baseline=no middleware")
    parser.add_argument("--n", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.output is None:
        model_tag = args.model.replace("-", "_")
        args.output = f"experiment_results/aibooster_humaneval_{model_tag}_{args.mode}.json"

    run_experiment(
        model_key=args.model,
        mode=args.mode,
        n=args.n,
        seed=args.seed,
        output_path=args.output,
    )
