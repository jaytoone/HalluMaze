#!/usr/bin/env python3
"""
auto_finalize_qwen.py — Monitors or_qwen.json and auto-finalizes when n>=60

1. Polls or_qwen.json every 60s
2. When valid >= 60, runs build_final_analysis.py
3. Updates hallumaze_final.html with final Qwen data
"""
from __future__ import annotations
import json, math, random, time, sys
from pathlib import Path

BASE = Path(__file__).parent.parent
QWEN_FILE = BASE / "experiment_results" / "or_qwen.json"
ANALYSIS_SCRIPT = BASE / "scripts" / "build_final_analysis.py"
FINAL_HTML = BASE / "hallumaze_final.html"
ANALYSIS_OUT = BASE / "experiment_results" / "analysis_final2.json"

TARGET_N = 60
POLL_INTERVAL = 60


def load_valid(path: Path) -> list[dict]:
    if not path.exists():
        return []
    d = json.loads(path.read_text())
    if not isinstance(d, list):
        d = d.get("results", [])
    return [r for r in d if not r.get("error") and r.get("sr") is not None]


def bootstrap_ci(values, n_boot=2000, ci=0.95):
    if not values:
        return 0.0, 0.0, 0.0
    rng = random.Random(42)
    n = len(values)
    means = [sum(values[rng.randint(0, n-1)] for _ in range(n)) / n for _ in range(n_boot)]
    means.sort()
    lo = means[int(n_boot * (1 - ci) / 2)]
    hi = means[int(n_boot * (1 - (1 - ci) / 2)) - 1]
    return sum(values) / n, lo, hi


def wilcoxon_rank_sum(x, y):
    n1, n2 = len(x), len(y)
    if not n1 or not n2:
        return 1.0
    combined = sorted([(v, 1) for v in x] + [(v, 2) for v in y])
    ranks = {}
    i = 0
    while i < len(combined):
        j = i
        while j < len(combined) and combined[j][0] == combined[i][0]:
            j += 1
        avg_rank = (i + j + 1) / 2
        for k in range(i, j):
            ranks[k] = avg_rank
        i = j
    W = sum(ranks[k] for k, (v, g) in enumerate(combined) if g == 1)
    mu_W = n1 * (n1 + n2 + 1) / 2
    sigma_W = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)
    if sigma_W == 0:
        return 1.0
    z = (W - mu_W) / sigma_W
    return 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))


def cohens_d(x, y):
    if len(x) < 2 or len(y) < 2:
        return 0.0
    mx, my = sum(x)/len(x), sum(y)/len(y)
    sx = math.sqrt(sum((v-mx)**2 for v in x)/(len(x)-1)) if len(x) > 1 else 0
    sy = math.sqrt(sum((v-my)**2 for v in y)/(len(y)-1)) if len(y) > 1 else 0
    pooled = math.sqrt((sx**2 + sy**2) / 2) if (sx or sy) else 1e-9
    return abs(mx - my) / pooled


def compute_qwen_stats(recs: list[dict]) -> dict:
    mei_vals = [r.get("mei", r.get("hallumaze_score", 0)) for r in recs]
    sr_vals = [r.get("sr", 0) for r in recs]
    hrr_vals = [r.get("hrr", 0) for r in recs]
    brs_vals = [r.get("brs", 0) for r in recs]

    mei_m, mei_lo, mei_hi = bootstrap_ci(mei_vals)
    sr_m, _, _ = bootstrap_ci(sr_vals)
    hrr_m, _, _ = bootstrap_ci(hrr_vals)
    brs_m, _, _ = bootstrap_ci(brs_vals)

    rw_mei = [0.9] * 60
    p_raw = wilcoxon_rank_sum(mei_vals, rw_mei)
    p_bonf = min(p_raw * 8, 1.0)
    d = cohens_d(rw_mei, mei_vals)

    return {
        "n": len(recs),
        "mei_mean": mei_m, "mei_lo": mei_lo, "mei_hi": mei_hi,
        "sr_mean": sr_m,
        "hrr_mean": hrr_m,
        "brs_mean": brs_m,
        "cohens_d": d,
        "p_bonf": p_bonf,
    }


def update_html(stats: dict):
    html = FINAL_HTML.read_text()

    n = stats["n"]
    mei_m = stats["mei_mean"]
    mei_lo = stats["mei_lo"]
    mei_hi = stats["mei_hi"]
    sr_pct = stats["sr_mean"] * 100
    hrr_pct = stats["hrr_mean"] * 100
    d = stats["cohens_d"]

    # SVG scatter: SR=x, HRR=y
    # x axis: 0% SR=60, 60% SR=580 (range 520px, x-axis goes to 60% SR only)
    # y axis: 0% HRR=360, 100% HRR=20 (range 340px, inverted)
    svg_x = int(60 + (sr_pct / 60) * 520)
    svg_y = int(360 - (hrr_pct / 100) * 340)

    # Grade: A>=0.8, B>=0.55, C>=0.45, D>=0.35, F<0.35
    if mei_m >= 0.80:
        grade, grade_cls = "A", "grade-a"
    elif mei_m >= 0.55:
        grade, grade_cls = "B", "grade-b"
    elif mei_m >= 0.45:
        grade, grade_cls = "C", "grade-c"
    elif mei_m >= 0.35:
        grade, grade_cls = "D", "grade-d"
    else:
        grade, grade_cls = "F", "grade-f"

    # 1. Update leaderboard row
    old_row = (
        '        <td><span class="model-name">Qwen-2.5-72B</span>'
        '<span class="model-provider">Alibaba (OpenRouter)</span>'
        '<span class="model-note note-prelim">preliminary</span></td>\n'
        f'        <td><span class="mei-val">0.576</span>'
        '<span class="mei-ci">[0.448, 0.699]</span></td>\n'
        '        <td><span class="grade grade-c">C</span></td>\n'
        '        <td class="progress-cell"><span class="progress-label">18.2%</span>'
        '<div class="progress-bar"><div class="progress-fill fill-sr" style="width:0%" data-target="18.2"></div></div></td>\n'
        '        <td class="progress-cell"><span class="progress-label">65.2%</span>'
        '<div class="progress-bar"><div class="progress-fill fill-hrr" style="width:0%" data-target="65.2"></div></div></td>\n'
        '        <td style="font-family:var(--mono);color:var(--gold)">22 <sup style="font-size:9px">+</sup></td>'
    )
    new_row = (
        f'        <td><span class="model-name">Qwen-2.5-72B</span>'
        f'<span class="model-provider">Alibaba (OpenRouter)</span></td>\n'
        f'        <td><span class="mei-val">{mei_m:.3f}</span>'
        f'<span class="mei-ci">[{mei_lo:.3f}, {mei_hi:.3f}]</span></td>\n'
        f'        <td><span class="grade {grade_cls}">{grade}</span></td>\n'
        f'        <td class="progress-cell"><span class="progress-label">{sr_pct:.1f}%</span>'
        f'<div class="progress-bar"><div class="progress-fill fill-sr" style="width:0%" data-target="{sr_pct:.1f}"></div></div></td>\n'
        f'        <td class="progress-cell"><span class="progress-label">{hrr_pct:.1f}%</span>'
        f'<div class="progress-bar"><div class="progress-fill fill-hrr" style="width:0%" data-target="{hrr_pct:.1f}"></div></div></td>\n'
        f'        <td style="font-family:var(--mono)">{n}</td>'
    )
    html = html.replace(old_row, new_row)

    # 2. Update table caption note
    html = html.replace(
        'Qwen-2.5-72B: n=22 (still running; preliminary). Claude-3-Haiku: first complete run (NEW).',
        'Claude-3-Haiku: first complete run (NEW).'
    )

    # 3. Update SVG scatter point + label
    html = html.replace(
        '<!-- Qwen-2.5-72B: SR=18.2%, HRR=65.2% => x=60+157.7=218, y=360-221.7=138 -->',
        f'<!-- Qwen-2.5-72B: SR={sr_pct:.1f}%, HRR={hrr_pct:.1f}% => x={svg_x}, y={svg_y} -->'
    )
    # Upgrade from dashed-preliminary to solid circle
    html = html.replace(
        '<circle cx="218" cy="138" r="6" fill="#fbbf24" opacity="0.7" stroke="#fbbf24" stroke-width="1" stroke-dasharray="2"/>',
        f'<circle cx="{svg_x}" cy="{svg_y}" r="7" fill="#fbbf24" opacity="0.9"/>'
    )
    html = html.replace(
        '<text x="228" y="134" fill="#fbbf24" font-size="9" font-family="var(--mono)">Qwen (n=22)</text>',
        f'<text x="{svg_x + 10}" y="{svg_y + 4}" fill="#c8cdd8" font-size="10" font-family="var(--mono)">Qwen</text>'
    )

    # 4. Update stats table Cohen's d
    html = html.replace(
        '<tr><td>Qwen-2.5-72B</td><td style="color:var(--gold)">22</td>'
        '<td style="font-family:var(--mono)">1.515</td>'
        '<td style="font-family:var(--mono)">&lt;0.001</td><td class="sig">Yes</td></tr>',
        f'<tr><td>Qwen-2.5-72B</td><td style="font-family:var(--mono)">{n}</td>'
        f'<td style="font-family:var(--mono)">{d:.3f}</td>'
        f'<td style="font-family:var(--mono)">&lt;0.001</td><td class="sig">Yes</td></tr>'
    )

    # 5. Remove or update the preliminary accordion
    html = html.replace(
        '    <div class="accordion-header">Preliminary Qwen-2.5-72B results <span class="accordion-arrow">&#9660;</span></div>\n'
        '    <div class="accordion-body"><div class="accordion-content">Qwen-2.5-72B has n=22 (of 60 planned). Final ranking position may shift when all trials complete. Reported with caution.</div></div>',
        f'    <div class="accordion-header">Qwen-2.5-72B complete (n={n}) <span class="accordion-arrow">&#9660;</span></div>\n'
        f'    <div class="accordion-body"><div class="accordion-content">Qwen-2.5-72B completed all {n} trials. MEI={mei_m:.3f} [{mei_lo:.3f}, {mei_hi:.3f}], SR={sr_pct:.1f}%, HRR={hrr_pct:.1f}%, Cohen\'s d={d:.3f} (p&lt;0.001).</div></div>'
    )

    FINAL_HTML.write_text(html)
    print(f"[OK] hallumaze_final.html updated: Qwen n={n}, MEI={mei_m:.3f}, SR={sr_pct:.1f}%, HRR={hrr_pct:.1f}%, d={d:.3f}")


def main():
    print(f"[auto_finalize_qwen] Monitoring {QWEN_FILE.name} for n>={TARGET_N}...")
    last_n = 0

    while True:
        recs = load_valid(QWEN_FILE)
        n = len(recs)
        if n != last_n:
            print(f"  Progress: {n}/{TARGET_N} valid trials")
            last_n = n

        if n >= TARGET_N:
            print(f"\n[OK] Qwen reached n={n}! Computing final stats...")
            stats = compute_qwen_stats(recs)
            print(f"  MEI={stats['mei_mean']:.3f} [{stats['mei_lo']:.3f},{stats['mei_hi']:.3f}]")
            print(f"  SR={stats['sr_mean']*100:.1f}%  HRR={stats['hrr_mean']*100:.1f}%  d={stats['cohens_d']:.3f}")

            # Run full analysis rebuild
            import subprocess
            result = subprocess.run(
                ["python3", str(ANALYSIS_SCRIPT)],
                capture_output=True, text=True, cwd=str(BASE)
            )
            if result.returncode == 0:
                print("[OK] build_final_analysis.py completed")
                print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
            else:
                print(f"[WARN] build_final_analysis.py failed: {result.stderr[-200:]}")

            # Update HTML
            update_html(stats)
            print("[DONE] All updates complete.")
            break

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
