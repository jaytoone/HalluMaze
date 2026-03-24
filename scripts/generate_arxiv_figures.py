#!/usr/bin/env python3
"""Generate arXiv figures from analysis_final2.json."""

import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# Load data
with open('/home/jayone/Project/Miro/experiment_results/analysis_final2.json') as f:
    af = json.load(f)

summary = af['summary']
models_by_mei = af['metadata']['models_by_mei']

# Style constants
BG = '#0d1117'
BG2 = '#161b22'
TEXT = '#c9d1d9'
TEXT2 = '#8b949e'
GRID = '#21262d'
BLUE = '#4f8ff7'
RED = '#f85149'
GRAY_LIGHT = '#6e7681'
GRAY = '#484f58'
GOLD = '#fbbf24'
GREEN = '#3fb950'
PURPLE = '#a371f7'
CYAN = '#58a6ff'

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['DejaVu Sans', 'Helvetica', 'Arial'],
    'font.size': 11,
    'axes.facecolor': BG2,
    'figure.facecolor': BG,
    'text.color': TEXT,
    'axes.labelcolor': TEXT,
    'axes.edgecolor': GRID,
    'xtick.color': TEXT2,
    'ytick.color': TEXT2,
    'grid.color': GRID,
    'grid.alpha': 0.5,
})

# ============================================================
# Figure 1: MEI Leaderboard Bar Chart (horizontal)
# ============================================================
fig1, ax1 = plt.subplots(figsize=(10, 6))

# Include Random Walk + all models
all_models = ['random_walk'] + models_by_mei
display_names = {
    'random_walk': 'Random Walk',
    'Claude-3.7-Sonnet': 'Claude-3.7-Sonnet',
    'GLM-4.7': 'GLM-4.7',
    'Llama-4-Maverick': 'Llama-4-Maverick',
    'MiniMax-M2.5': 'MiniMax-M2.5',
    'Llama-4-Scout': 'Llama-4-Scout',
    'Qwen-2.5-72B': 'Qwen-2.5-72B',
    'Gemini-2.0-Flash-Lite': 'Gemini-2.0-Flash-Lite',
    'Claude-3-Haiku': 'Claude-3-Haiku',
    'GPT-4o-mini': 'GPT-4o-mini',
    'GPT-4o': 'GPT-4o',
}

meis = [summary[m]['mei']['mean'] for m in all_models]
ci_los = [summary[m]['mei']['ci_lo'] for m in all_models]
ci_his = [summary[m]['mei']['ci_hi'] for m in all_models]
errs_lo = [m - l for m, l in zip(meis, ci_los)]
errs_hi = [h - m for m, h in zip(meis, ci_his)]

# Colors
colors = []
for m in all_models:
    if m == 'random_walk':
        colors.append(GOLD)
    elif m == 'Claude-3.7-Sonnet':
        colors.append(BLUE)
    elif m == 'GPT-4o':
        colors.append(RED)
    elif m == 'GPT-4o-mini':
        colors.append('#d94a3f')
    else:
        colors.append(GRAY_LIGHT)

y_pos = np.arange(len(all_models))[::-1]
bars = ax1.barh(y_pos, meis, height=0.6, color=colors, alpha=0.9,
                xerr=[errs_lo, errs_hi], error_kw={'ecolor': TEXT2, 'capsize': 3, 'linewidth': 1})

# Random Walk baseline dashed line
rw_mei = summary['random_walk']['mei']['mean']
ax1.axvline(x=rw_mei, color=GOLD, linestyle='--', linewidth=1.2, alpha=0.7, label=f'Random Walk = {rw_mei:.3f}')

ax1.set_yticks(y_pos)
ax1.set_yticklabels([display_names[m] for m in all_models], fontsize=10)
ax1.set_xlabel('MEI (Metacognitive Escape Index)', fontsize=12)
ax1.set_xlim(0, 1.0)
ax1.set_title('HalluMaze Leaderboard: MEI Scores (n=60 per model, 95% CI)',
              fontsize=13, fontweight='bold', pad=15)
ax1.legend(loc='lower right', fontsize=9, framealpha=0.3)
ax1.grid(axis='x', alpha=0.3)

# Add value labels
for i, (mei, m) in enumerate(zip(meis, all_models)):
    ax1.text(mei + 0.015, y_pos[i], f'{mei:.3f}', va='center', fontsize=9, color=TEXT)

fig1.tight_layout()
fig1.savefig('/home/jayone/Project/Miro/docs/figures/fig1_mei_leaderboard.png', dpi=600,
             bbox_inches='tight', facecolor=BG)
plt.close(fig1)
print("Figure 1 saved.")

# ============================================================
# Figure 2: HRR-SR Dissociation Scatter
# ============================================================
fig2, ax2 = plt.subplots(figsize=(8, 7))

for m in models_by_mei:
    sr = summary[m]['sr']['mean']
    hrr = summary[m]['hrr']['mean']

    if m == 'Claude-3.7-Sonnet':
        c, s, zorder = BLUE, 120, 10
    elif m == 'GPT-4o':
        c, s, zorder = RED, 120, 10
    elif m == 'GPT-4o-mini':
        c, s, zorder = '#d94a3f', 90, 8
    else:
        c, s, zorder = GRAY_LIGHT, 80, 5

    ax2.scatter(sr, hrr, c=c, s=s, zorder=zorder, alpha=0.9, edgecolors='white', linewidth=0.5)

    # Label positioning to avoid overlap
    offset_x, offset_y = 0.012, 0.015
    ha = 'left'
    if m == 'GPT-4o-mini':
        offset_y = -0.03
    elif m == 'Claude-3-Haiku':
        offset_y = -0.03
    elif m == 'Llama-4-Scout':
        offset_x = -0.01
        ha = 'right'
    elif m == 'MiniMax-M2.5':
        offset_x = 0.015
        offset_y = -0.02

    short_name = m.replace('Gemini-2.0-Flash-Lite', 'Gemini-Flash').replace('Qwen-2.5-72B', 'Qwen-72B')
    ax2.annotate(short_name, (sr, hrr),
                 xytext=(sr + offset_x, hrr + offset_y),
                 fontsize=8, color=TEXT2, ha=ha)

# Random Walk star
ax2.scatter(1.0, 1.0, marker='*', c=GOLD, s=250, zorder=15, edgecolors='white', linewidth=0.5)
ax2.annotate('Random Walk', (1.0, 1.0), xytext=(0.88, 0.96), fontsize=9, color=GOLD, fontweight='bold')

# Quadrant lines
ax2.axvline(x=0.3, color=GRID, linestyle=':', linewidth=1, alpha=0.6)
ax2.axhline(y=0.5, color=GRID, linestyle=':', linewidth=1, alpha=0.6)

# Quadrant labels
ax2.text(0.02, 0.95, 'High HRR\nLow SR', fontsize=8, color=TEXT2, alpha=0.5,
         transform=ax2.transAxes, va='top')
ax2.text(0.65, 0.95, 'High HRR\nHigh SR', fontsize=8, color=TEXT2, alpha=0.5,
         transform=ax2.transAxes, va='top')
ax2.text(0.02, 0.08, 'Low HRR\nLow SR', fontsize=8, color=TEXT2, alpha=0.5,
         transform=ax2.transAxes)
ax2.text(0.65, 0.08, 'Low HRR\nHigh SR', fontsize=8, color=TEXT2, alpha=0.5,
         transform=ax2.transAxes)

ax2.set_xlabel('Solve Rate (SR)', fontsize=12)
ax2.set_ylabel('Hallucination Recovery Rate (HRR)', fontsize=12)
ax2.set_xlim(-0.03, 1.1)
ax2.set_ylim(0.15, 1.1)
ax2.set_title('HRR vs SR Dissociation: Recovery and Task Completion Are Separable',
              fontsize=12, fontweight='bold', pad=15)
ax2.grid(alpha=0.2)

fig2.tight_layout()
fig2.savefig('/home/jayone/Project/Miro/docs/figures/fig2_hrr_sr_scatter.png', dpi=600,
             bbox_inches='tight', facecolor=BG)
plt.close(fig2)
print("Figure 2 saved.")

# ============================================================
# Figure 3: MEI vs Cost Scatter (log scale X)
# ============================================================
fig3, ax3 = plt.subplots(figsize=(9, 7))

# API costs ($/M output tokens)
costs = {
    'Claude-3.7-Sonnet': 15.0,
    'GPT-4o': 10.0,
    'Claude-3-Haiku': 1.25,
    'GPT-4o-mini': 0.60,
    'Llama-4-Maverick': 0.60,
    'Qwen-2.5-72B': 0.39,
    'Gemini-2.0-Flash-Lite': 0.30,
    'Llama-4-Scout': 0.30,
    'MiniMax-M2.5': 0.01,  # near-free, use small value for log scale
    'GLM-4.7': 0.01,       # local/free
}

for m in models_by_mei:
    cost = costs[m]
    mei = summary[m]['mei']['mean']

    if m == 'Claude-3.7-Sonnet':
        c, s, zorder = BLUE, 150, 10
    elif m == 'GPT-4o':
        c, s, zorder = RED, 150, 10
    elif m == 'GPT-4o-mini':
        c, s, zorder = '#d94a3f', 100, 8
    else:
        c, s, zorder = GRAY_LIGHT, 90, 5

    ax3.scatter(cost, mei, c=c, s=s, zorder=zorder, alpha=0.9, edgecolors='white', linewidth=0.5)

    # Labels
    short = m.replace('Gemini-2.0-Flash-Lite', 'Gemini-Flash').replace('Qwen-2.5-72B', 'Qwen-72B')
    offset_x_frac = 1.15  # multiplicative for log scale
    offset_y = 0.015
    ha = 'left'
    if m == 'GLM-4.7':
        offset_y = 0.02
    elif m == 'MiniMax-M2.5':
        offset_y = -0.025
    elif m == 'Llama-4-Scout':
        offset_y = -0.025
    elif m == 'GPT-4o-mini':
        offset_y = 0.02
    elif m == 'Llama-4-Maverick':
        offset_y = -0.02

    ax3.annotate(short, (cost, mei),
                 xytext=(cost * offset_x_frac, mei + offset_y),
                 fontsize=8, color=TEXT2, ha=ha)

# Arrows for frontier inversion
# GPT-4o: red arrow pointing down with label
ax3.annotate('Most expensive\n= worst MEI',
             xy=(costs['GPT-4o'], summary['GPT-4o']['mei']['mean']),
             xytext=(costs['GPT-4o'] * 0.4, summary['GPT-4o']['mei']['mean'] - 0.06),
             fontsize=9, color=RED, fontweight='bold',
             arrowprops=dict(arrowstyle='->', color=RED, lw=1.5),
             ha='center')

# Claude-3.7-Sonnet: blue arrow pointing up
ax3.annotate('Best MEI',
             xy=(costs['Claude-3.7-Sonnet'], summary['Claude-3.7-Sonnet']['mei']['mean']),
             xytext=(costs['Claude-3.7-Sonnet'] * 0.4, summary['Claude-3.7-Sonnet']['mei']['mean'] + 0.05),
             fontsize=9, color=BLUE, fontweight='bold',
             arrowprops=dict(arrowstyle='->', color=BLUE, lw=1.5),
             ha='center')

ax3.set_xscale('log')
ax3.set_xlabel('API Cost ($/M output tokens, log scale)', fontsize=12)
ax3.set_ylabel('MEI (Metacognitive Escape Index)', fontsize=12)
ax3.set_xlim(0.005, 30)
ax3.set_ylim(0.2, 0.9)
ax3.set_title('Frontier Cost Inversion: API Cost Does Not Predict Metacognition',
              fontsize=12, fontweight='bold', pad=15)
ax3.grid(alpha=0.2)

# Custom x tick labels
ax3.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, p: f'${x:.2f}' if x < 1 else f'${x:.0f}'))

# Add shaded region for "free/local" models
ax3.axvspan(0.005, 0.02, alpha=0.1, color=GREEN, zorder=0)
ax3.text(0.012, 0.88, 'Free/Local', fontsize=8, color=GREEN, alpha=0.7, ha='center', rotation=90)

fig3.tight_layout()
fig3.savefig('/home/jayone/Project/Miro/docs/figures/fig3_cost_mei.png', dpi=600,
             bbox_inches='tight', facecolor=BG)
plt.close(fig3)
print("Figure 3 saved.")

print("\nAll figures generated successfully.")
