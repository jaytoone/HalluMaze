#!/usr/bin/env python3
"""
HalluMaze Paper-Quality Experiment Runner
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
논문급 통계 설계:
  - 2 models (MiniMax-M2.5, GLM-4.7)
  - 2 maze sizes (5×5, 7×7)
  - Ariadne Group A (통제 조건)
  - n=30 독립 seed per size (reproducible seed pool)
  - Bootstrap 1000× → 95% CI
  - Wilcoxon rank-sum + Bonferroni (α=0.017)
  - Cohen's d effect size

Usage:
    python3 run_experiment.py                   # full run (n=30 per size)
    python3 run_experiment.py --pilot           # pilot (n=5, quick sanity check)
    python3 run_experiment.py --resume          # resume from saved checkpoint
    python3 run_experiment.py --stats-only      # stats from existing results file
"""
from __future__ import annotations

import sys, os, json, re, math, time, argparse, random
from datetime import datetime
from pathlib import Path

# ── env loading ──────────────────────────────────────────────────────────────
def _load_env(path):
    try:
        with open(os.path.expanduser(path)) as f:
            for line in f:
                m = re.match(r'^(?:export\s+)?([A-Za-z_]\w*)=(.+)$', line.strip())
                if m:
                    os.environ.setdefault(m.group(1), m.group(2).strip('"\''))
    except FileNotFoundError:
        pass

_load_env("~/.claude/env/shared.env")
_load_env(".envrc")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'files'))
from hallumaze import (
    LLMProvider, MazeConfig, MazeEngine, BenchmarkRunner,
    PromptBuilder, console, RICH
)

# ── Provider patches (same as run_hallumaze.py) ───────────────────────────────
def _strip_think(text: str) -> str:
    stripped = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    return stripped if stripped else text

def _call_minimax(self, prompt, max_tokens, system=""):
    import openai
    client = openai.OpenAI(
        api_key=self.api_key,
        base_url=os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.io/v1")
    )
    # MiniMax-M2.5 추론 모델: <think> 블록이 ~3000+ 토큰 소모 → 최소 8000 필요
    effective_tokens = max(max_tokens, 8000)
    resp = client.chat.completions.create(
        model=self.model, max_tokens=effective_tokens,
        messages=[{"role":"system","content":system or PromptBuilder.SYSTEM_PROMPT},
                  {"role":"user","content":prompt}])
    return _strip_think(resp.choices[0].message.content)

def _call_glm(self, prompt, max_tokens, system=""):
    import anthropic
    client = anthropic.Anthropic(
        api_key=self.api_key,
        base_url=os.environ.get("GLM_BASE_URL", "https://api.z.ai/api/anthropic")
    )
    msg = client.messages.create(
        model=self.model, max_tokens=max_tokens,
        system=system or PromptBuilder.SYSTEM_PROMPT,
        messages=[{"role":"user","content":prompt}])
    return msg.content[0].text

_orig_call = LLMProvider.call
def _patched_call(self, prompt, max_tokens, system=""):
    if self.provider == "minimax": return _call_minimax(self, prompt, max_tokens, system)
    if self.provider == "glm":     return _call_glm(self, prompt, max_tokens, system)
    return _orig_call(self, prompt, max_tokens, system)
LLMProvider.call = _patched_call


# ═══════════════════════════════════════════════════════════════
#  SEED POOL — 재현 가능한 30개 독립 seed
# ═══════════════════════════════════════════════════════════════

# 사전 고정 seed pool (논문 재현성 보장)
SEED_POOL = [
    1001, 2002, 3003, 4004, 5005, 6006, 7007, 8008, 9009, 1010,
    1111, 2222, 3333, 4444, 5555, 6666, 7777, 8888, 9999, 1234,
    2345, 3456, 4567, 5678, 6789, 7890, 8901, 9012, 1357, 2468,
]
assert len(SEED_POOL) == 30, "seed pool must be exactly 30"


# ═══════════════════════════════════════════════════════════════
#  STATISTICS
# ═══════════════════════════════════════════════════════════════

def bootstrap_ci(data: list[float], n_boot: int = 1000, ci: float = 0.95) -> tuple[float, float, float]:
    """Bootstrap 신뢰구간. Returns (mean, lower, upper)."""
    arr = data[:]
    n = len(arr)
    if n == 0:
        return 0.0, 0.0, 0.0
    means = []
    for _ in range(n_boot):
        sample = [random.choice(arr) for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    alpha = 1 - ci
    lo = means[int(alpha/2 * n_boot)]
    hi = means[int((1 - alpha/2) * n_boot)]
    return sum(arr)/n, lo, hi


def cohens_d(a: list[float], b: list[float]) -> float:
    """Cohen's d effect size."""
    if len(a) < 2 or len(b) < 2:
        return 0.0
    mean_a, mean_b = sum(a)/len(a), sum(b)/len(b)
    var_a = sum((x - mean_a)**2 for x in a) / (len(a)-1)
    var_b = sum((x - mean_b)**2 for x in b) / (len(b)-1)
    pooled_sd = math.sqrt((var_a + var_b) / 2)
    return (mean_a - mean_b) / pooled_sd if pooled_sd > 0 else 0.0


def wilcoxon_rank_sum(a: list[float], b: list[float]) -> float:
    """Approximate Wilcoxon rank-sum p-value (normal approximation)."""
    n1, n2 = len(a), len(b)
    if n1 == 0 or n2 == 0:
        return 1.0
    combined = [(v, 0) for v in a] + [(v, 1) for v in b]
    combined.sort(key=lambda x: x[0])
    # Assign ranks (average for ties)
    ranks = [0.0] * (n1 + n2)
    i = 0
    while i < len(combined):
        j = i
        while j < len(combined) and combined[j][0] == combined[i][0]:
            j += 1
        avg_rank = (i + j + 1) / 2.0
        for k in range(i, j):
            ranks[k] = avg_rank
        i = j
    W = sum(ranks[i] for i in range(len(combined)) if combined[i][1] == 0)
    mu_W = n1 * (n1 + n2 + 1) / 2
    sigma_W = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)
    if sigma_W == 0:
        return 1.0
    z = (W - mu_W) / sigma_W
    # Two-tailed p-value via normal CDF approximation
    p = 2 * (1 - _norm_cdf(abs(z)))
    return p


def _norm_cdf(z: float) -> float:
    """Standard normal CDF (Abramowitz & Stegun approximation)."""
    t = 1 / (1 + 0.2316419 * abs(z))
    d = 0.3989423 * math.exp(-z*z/2)
    p = d*t*(0.3193815 + t*(-0.3565638 + t*(1.7814779 + t*(-1.8212560 + t*1.3302744))))
    return 1 - p if z > 0 else p


# ═══════════════════════════════════════════════════════════════
#  EXPERIMENT RUNNER
# ═══════════════════════════════════════════════════════════════

RESULTS_DIR = Path("experiment_results")
RESULTS_DIR.mkdir(exist_ok=True)


def build_providers() -> list[LLMProvider]:
    providers = []
    mm_key = os.environ.get("MINIMAX_API_KEY")
    if mm_key:
        providers.append(LLMProvider(
            provider="minimax", api_key=mm_key,
            model=os.environ.get("MINIMAX_MODEL", "MiniMax-M2.5")))
    glm_key = os.environ.get("GLM_API_KEY")
    if glm_key:
        providers.append(LLMProvider(
            provider="glm", api_key=glm_key,
            model=os.environ.get("GLM_MODEL", "glm-4.7")))
    return providers


def run_single_trial(provider: LLMProvider, size: int, seed: int,
                     config: MazeConfig) -> dict:
    """단일 trial 실행 → 결과 dict 반환."""
    maze = MazeEngine(size=size, seed=seed)
    runner = BenchmarkRunner(config)
    result = runner.run_single(provider, maze)
    return {
        "provider": result.provider,
        "model": result.model,
        "size": size,
        "seed": seed,
        "sr": result.sr,
        "mei": result.mei,
        "ce": result.ce,
        "brs": result.brs,
        "hallumaze_score": result.hallumaze_score,
        "hallucination_count": result.hallucination_count,
        "backtrack_count": result.backtrack_count,
        "loop_count": result.loop_count,
        "hrr": result.hrr,
        "path_valid": result.path_valid,
        "latency_s": result.latency_s,
        "error": result.error,
        "metacog_signals": result.metacog_signals,
        "solution_length": len(maze.solution or []),
        "dead_ends": maze.dead_ends,
    }


def run_experiment(providers: list[LLMProvider], sizes: list[int],
                   seeds: list[int], config: MazeConfig,
                   checkpoint_file: str) -> list[dict]:
    """전체 실험 실행. 체크포인트로 resume 지원."""
    # Load existing results
    completed = []
    if os.path.exists(checkpoint_file):
        with open(checkpoint_file) as f:
            completed = json.load(f)
        console.print(f"  [재개] 기존 {len(completed)}개 결과 로드")

    completed_keys = {(r["model"], r["size"], r["seed"]) for r in completed}
    total = len(providers) * len(sizes) * len(seeds)
    done = len(completed)

    for provider in providers:
        for size in sizes:
            for seed in seeds:
                key = (provider.model, size, seed)
                if key in completed_keys:
                    continue
                done += 1
                label = f"[{done}/{total}] {provider.model} | {size}×{size} | seed={seed}"
                console.print(f"\n  ▶ {label}")
                t0 = time.time()
                try:
                    trial = run_single_trial(provider, size, seed, config)
                    elapsed = time.time() - t0
                    status = "✓" if trial["path_valid"] else "✗"
                    console.print(
                        f"  {status} SR={trial['sr']:.1f} MEI={trial['mei']:.3f} "
                        f"Hall={trial['hallucination_count']} BT={trial['backtrack_count']} "
                        f"Score={trial['hallumaze_score']:.3f} | {elapsed:.1f}s"
                    )
                except Exception as e:
                    trial = {"provider": provider.provider, "model": provider.model,
                             "size": size, "seed": seed, "error": str(e),
                             "sr": 0, "mei": 0, "ce": None, "brs": 0,
                             "hallumaze_score": 0, "hallucination_count": 0,
                             "backtrack_count": 0, "loop_count": 0, "hrr": 0,
                             "path_valid": False, "latency_s": 0,
                             "metacog_signals": [], "solution_length": 0, "dead_ends": 0}
                    console.print(f"  ✗ 오류: {e}")

                completed.append(trial)
                # Save checkpoint after every trial
                with open(checkpoint_file, 'w') as f:
                    json.dump(completed, f, ensure_ascii=False, indent=2)

    return completed


# ═══════════════════════════════════════════════════════════════
#  STATISTICS REPORT
# ═══════════════════════════════════════════════════════════════

def compute_stats(trials: list[dict]) -> dict:
    """모델 × 크기별 통계 계산."""
    # Group data
    groups: dict[tuple, list[dict]] = {}
    for t in trials:
        if t.get("error"):
            continue
        key = (t["model"], t["size"])
        groups.setdefault(key, []).append(t)

    stats = {}
    for key, ts in groups.items():
        model, size = key
        mei_vals    = [t["mei"] for t in ts]
        sr_vals     = [t["sr"] for t in ts]
        score_vals  = [t["hallumaze_score"] for t in ts]
        hall_vals   = [float(t["hallucination_count"]) for t in ts]
        brs_vals    = [t["brs"] for t in ts]

        stats[key] = {
            "n": len(ts),
            "model": model, "size": size,
            "sr":     bootstrap_ci(sr_vals),
            "mei":    bootstrap_ci(mei_vals),
            "score":  bootstrap_ci(score_vals),
            "hall":   bootstrap_ci(hall_vals),
            "brs":    bootstrap_ci(brs_vals),
        }
    return stats


def pairwise_tests(trials: list[dict], metric: str = "mei") -> dict:
    """모델 쌍별 Wilcoxon rank-sum + Bonferroni 보정."""
    models = list({t["model"] for t in trials if not t.get("error")})
    sizes  = list({t["size"]  for t in trials if not t.get("error")})
    results = {}
    n_comparisons = len(sizes)  # per size, one comparison

    for size in sizes:
        vals = {m: [t[metric] for t in trials
                    if t["model"] == m and t["size"] == size and not t.get("error")]
                for m in models}
        if len(models) < 2:
            continue
        for i in range(len(models)):
            for j in range(i+1, len(models)):
                m1, m2 = models[i], models[j]
                a, b = vals[m1], vals[m2]
                if not a or not b:
                    continue
                p = wilcoxon_rank_sum(a, b)
                p_bonf = min(1.0, p * n_comparisons)
                d = cohens_d(a, b)
                results[(m1, m2, size)] = {
                    "p_raw": round(p, 4),
                    "p_bonferroni": round(p_bonf, 4),
                    "cohens_d": round(d, 4),
                    "n1": len(a), "n2": len(b),
                    "sig": p_bonf < 0.05,
                }
    return results


def print_paper_table(stats: dict, tests: dict):
    """논문 Table 1 + Table 2 출력."""
    console.print("\n" + "═"*80)
    console.print("  TABLE 1 — Main Results (mean ± 95% CI, Bootstrap n=1000)")
    console.print("═"*80)
    header = f"{'Model':<22} {'Size':>5} {'n':>4}  {'SR':>12}  {'MEI':>12}  {'HalluScore':>12}  {'BRS':>12}"
    console.print(header)
    console.print("─"*80)

    for (model, size), s in sorted(stats.items(), key=lambda x: (x[0][1], x[0][0])):
        def fmt(ci): return f"{ci[0]:.3f} [{ci[1]:.3f},{ci[2]:.3f}]"
        console.print(
            f"  {model:<20} {size:>5}×{size}  {s['n']:>3}  "
            f"{fmt(s['sr']):>17}  {fmt(s['mei']):>17}  "
            f"{fmt(s['score']):>17}  {fmt(s['brs']):>17}"
        )

    console.print("\n" + "═"*80)
    console.print("  TABLE 2 — Pairwise Statistical Tests (Wilcoxon rank-sum, Bonferroni α=0.017)")
    console.print("═"*80)
    header2 = f"{'Comparison':<45} {'Size':>5} {'p (raw)':>10} {'p (Bonf)':>10} {'d':>8} {'Sig':>5}"
    console.print(header2)
    console.print("─"*80)
    for (m1, m2, size), t in sorted(tests.items(), key=lambda x: x[0][2]):
        comp = f"{m1[:20]} vs {m2[:18]}"
        sig = "★" if t["sig"] else "ns"
        console.print(
            f"  {comp:<43} {size:>5}×{size}  "
            f"{t['p_raw']:>10.4f}  {t['p_bonferroni']:>10.4f}  "
            f"{t['cohens_d']:>8.3f}  {sig:>5}"
        )


def save_paper_report(trials, stats, tests, output_path: str):
    """논문 보조 데이터 JSON 저장."""
    report = {
        "experiment": {
            "date": datetime.now().isoformat(),
            "design": {
                "models": list({t["model"] for t in trials}),
                "sizes": sorted(list({t["size"] for t in trials})),
                "seeds": SEED_POOL,
                "ariadne_group": "A",
                "n_per_condition": len(SEED_POOL),
                "bootstrap_iterations": 1000,
                "alpha": 0.05,
                "bonferroni_alpha": 0.05 / 2,
            }
        },
        "table1_main_results": {
            f"{model}/{size}": {
                "n": s["n"],
                "sr_mean": s["sr"][0], "sr_ci_lo": s["sr"][1], "sr_ci_hi": s["sr"][2],
                "mei_mean": s["mei"][0], "mei_ci_lo": s["mei"][1], "mei_ci_hi": s["mei"][2],
                "score_mean": s["score"][0], "score_ci_lo": s["score"][1], "score_ci_hi": s["score"][2],
                "brs_mean": s["brs"][0], "brs_ci_lo": s["brs"][1], "brs_ci_hi": s["brs"][2],
            }
            for (model, size), s in stats.items()
        },
        "table2_pairwise_tests": {
            f"{m1}_vs_{m2}_size{size}": v
            for (m1, m2, size), v in tests.items()
        },
        "raw_trials": trials,
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return output_path


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(description="HalluMaze Paper-Quality Experiment")
    ap.add_argument("--pilot",      action="store_true", help="파일럿 (n=5, 빠른 검증)")
    ap.add_argument("--resume",     action="store_true", help="체크포인트에서 재개")
    ap.add_argument("--stats-only", action="store_true", help="기존 결과에서 통계만 재계산")
    ap.add_argument("--checkpoint", type=str, default="experiment_results/checkpoint.json")
    ap.add_argument("--output",     type=str, default=None)
    ap.add_argument("--sizes",      type=str, default="5,7", help="미로 크기 (쉼표 구분)")
    ap.add_argument("--n",          type=int, default=30, help="seed 수 (기본 30)")
    args = ap.parse_args()

    console.print("\n" + "═"*70)
    console.print("  HalluMaze Paper-Quality Experiment")
    console.print("  MiniMax-M2.5 × GLM-4.7 | Ariadne A | Bootstrap CI")
    console.print("═"*70)

    sizes = [int(s) for s in args.sizes.split(",")]
    n = min(args.n, 30)
    seeds = SEED_POOL[:5] if args.pilot else SEED_POOL[:n]

    config = MazeConfig(size=7, use_mirage=True, use_confidence=True,
                        ariadne_mode="A", max_tokens=2500)

    if args.stats_only:
        cp = args.checkpoint
        if not os.path.exists(cp):
            console.print(f"  오류: {cp} 없음")
            sys.exit(1)
        with open(cp) as f:
            trials = json.load(f)
        console.print(f"  기존 {len(trials)}개 결과로 통계 계산")
    else:
        providers = build_providers()
        if not providers:
            console.print("  오류: 프로바이더 없음 (API 키 확인)")
            sys.exit(1)
        console.print(f"\n  [설계] 모델: {[p.model for p in providers]}")
        console.print(f"  [설계] 크기: {sizes} | seeds: {len(seeds)}개 | 총 trials: {len(providers)*len(sizes)*len(seeds)}")
        console.print(f"  [설계] 예상 시간: ~{len(providers)*len(sizes)*len(seeds)*40//60}분")

        if not args.resume and os.path.exists(args.checkpoint):
            console.print(f"\n  기존 체크포인트 발견: {args.checkpoint}")
            resp = input("  삭제 후 새로 시작? [y/N]: ").strip().lower()
            if resp == 'y':
                os.remove(args.checkpoint)

        trials = run_experiment(providers, sizes, seeds, config, args.checkpoint)

    # ── Statistics ──────────────────────────────────────────────
    valid = [t for t in trials if not t.get("error")]
    error_count = len(trials) - len(valid)
    console.print(f"\n  완료: {len(valid)}/{len(trials)} 성공 ({error_count} 오류)")

    stats = compute_stats(valid)
    tests_mei   = pairwise_tests(valid, "mei")
    tests_score = pairwise_tests(valid, "hallumaze_score")

    print_paper_table(stats, tests_mei)

    # ── Save report ──────────────────────────────────────────────
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = args.output or f"experiment_results/paper_results_{ts}.json"
    save_paper_report(valid, stats, tests_mei, out)
    console.print(f"\n  JSON 저장: {out}")

    # ── Summary ─────────────────────────────────────────────────
    console.print("\n" + "═"*70)
    console.print("  EXPERIMENT SUMMARY")
    console.print("═"*70)
    for (model, size), s in sorted(stats.items()):
        mei_m, mei_lo, mei_hi = s["mei"]
        sc_m, sc_lo, sc_hi   = s["score"]
        console.print(
            f"  {model[:22]:<22} {size}×{size} | "
            f"MEI={mei_m:.3f} [95%CI {mei_lo:.3f}-{mei_hi:.3f}] | "
            f"Score={sc_m:.3f} [95%CI {sc_lo:.3f}-{sc_hi:.3f}]"
        )

    if tests_mei:
        console.print("\n  [Wilcoxon MEI 기준]")
        for (m1, m2, size), t in sorted(tests_mei.items()):
            sig_str = "★ SIGNIFICANT" if t["sig"] else "ns"
            console.print(
                f"  {m1[:18]} vs {m2[:18]} @ {size}×{size}: "
                f"p={t['p_bonferroni']:.4f} d={t['cohens_d']:.3f} [{sig_str}]"
            )

    console.print(f"\n  결과 파일: {out}")
    console.print("  논문 Table 1/2 데이터 포함 — 재현 가능한 seed pool 공개됨")


if __name__ == "__main__":
    main()
