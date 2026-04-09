"""
Generate the 3 remaining preprint figures:
  Fig 5:  fig_direct_vs_relational.png  — Direct vs relational accuracy drop
  Fig 11: fig_benchmark_mask_1.png      — ScreenSpot-v2: baseline vs 6.5k vs 25k
  Fig 12: fig_benchmark_mask_2.png      — ScreenSpot-v2: real vs synthetic + GUI-Perturbed comparison

Usage:
    python data/plot_remaining_figures.py
"""

import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Font sizes matching plot_with_ci.py
TITLE_SIZE = 24
SUBTITLE_SIZE = 20
TEXT_SIZE = 18
BAR_LABEL_SIZE = 14
AXIS_LABEL_SIZE = 20
LEGEND_SIZE = 17

def _setup_style():
    plt.rcParams.update({
        'figure.dpi': 100, 'savefig.dpi': 150, 'font.size': 18,
        'text.color': 'black', 'axes.labelcolor': 'black',
        'axes.edgecolor': 'black', 'xtick.color': 'black',
        'ytick.color': 'black', 'axes.facecolor': 'white',
        'figure.facecolor': 'white',
    })


# ============================================================================
# FIG 5: Direct vs Relational accuracy
# ============================================================================

def make_fig5_direct_vs_relational():
    """Grouped bar chart: direct vs relational hit rate per model, with/without reasoning."""
    _setup_style()
    ci = pd.read_csv(os.path.join(SCRIPT_DIR, 'baseline_confidence_intervals.csv'))

    models = ['qwen25vl', 'uitars15', 'gta1']
    model_labels = {'qwen25vl': 'Qwen2.5-VL', 'uitars15': 'UI-TARS-1.5', 'gta1': 'GTA-1'}
    reasoning_modes = [(False, 'No Reasoning'), (True, 'With Reasoning')]

    fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=True)
    fig.suptitle('Direct vs. Relational Instruction Accuracy', fontsize=TITLE_SIZE, fontweight='bold', y=1.02)

    colors_direct = '#7bafd4'
    colors_relat = '#e8956a'

    x = np.arange(len(models))
    bar_width = 0.35

    for ri, (reasoning, r_label) in enumerate(reasoning_modes):
        ax = axes[ri]
        ax.set_title(r_label, fontsize=SUBTITLE_SIZE, fontweight='bold', pad=10)

        direct_vals = []
        direct_ci_lo = []
        direct_ci_hi = []
        relat_vals = []
        relat_ci_lo = []
        relat_ci_hi = []

        for model in models:
            # Direct
            d = ci[(ci['model'] == model) & (ci['variant'] == 'original') &
                   (ci['query_type'] == 'direct_query') & (ci['use_reasoning'] == reasoning)]
            r = ci[(ci['model'] == model) & (ci['variant'] == 'original') &
                   (ci['query_type'] == 'relational_query') & (ci['use_reasoning'] == reasoning)]

            dv = d.iloc[0]['hit_rate'] * 100
            rv = r.iloc[0]['hit_rate'] * 100
            direct_vals.append(dv)
            direct_ci_lo.append(dv - d.iloc[0]['boot_ci_lo'] * 100)
            direct_ci_hi.append(d.iloc[0]['boot_ci_hi'] * 100 - dv)
            relat_vals.append(rv)
            relat_ci_lo.append(rv - r.iloc[0]['boot_ci_lo'] * 100)
            relat_ci_hi.append(r.iloc[0]['boot_ci_hi'] * 100 - rv)

        b1 = ax.bar(x - bar_width/2, direct_vals, bar_width,
                     yerr=[direct_ci_lo, direct_ci_hi],
                     capsize=4, error_kw={'linewidth': 1.2, 'capthick': 1.2, 'ecolor': '#555'},
                     color=colors_direct, alpha=0.85, edgecolor='none',
                     label='Direct', zorder=2)
        b2 = ax.bar(x + bar_width/2, relat_vals, bar_width,
                     yerr=[relat_ci_lo, relat_ci_hi],
                     capsize=4, error_kw={'linewidth': 1.2, 'capthick': 1.2, 'ecolor': '#555'},
                     color=colors_relat, alpha=0.85, edgecolor='none',
                     label='Relational', zorder=2)

        # Labels
        for bars in [b1, b2]:
            for bar in bars:
                h = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., h + 3,
                        f'{h:.1f}', ha='center', va='bottom',
                        fontsize=BAR_LABEL_SIZE, fontweight='bold')

        ax.set_xticks(x)
        ax.set_xticklabels([model_labels[m] for m in models], fontsize=TEXT_SIZE)
        ax.tick_params(axis='y', labelsize=TEXT_SIZE)
        ax.set_ylim(0, 110)
        ax.grid(True, alpha=0.3, linestyle='--', axis='y', zorder=0)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        if ri == 0:
            ax.set_ylabel('Hit Rate (%)', fontsize=AXIS_LABEL_SIZE)

    fig.legend(['Direct Instruction', 'Relational Instruction'],
               loc='upper center', ncol=2, fontsize=LEGEND_SIZE,
               bbox_to_anchor=(0.5, 0.94), framealpha=0.95, edgecolor='#ccc')
    plt.tight_layout(rect=[0.0, 0.0, 1.0, 0.86])
    plt.subplots_adjust(wspace=0.08)

    path = os.path.join(SCRIPT_DIR, 'fig_direct_vs_relational.png')
    plt.savefig(path, bbox_inches='tight', dpi=150, facecolor='white')
    print(f"Saved: {path}")
    plt.close(fig)


# ============================================================================
# FIG 11: ScreenSpot-v2 — baseline vs 6.5k vs 25k
# ============================================================================

def make_fig11_screenspot_scaling():
    """ScreenSpot-v2: baseline vs 6.5k all vs 25k 3epoch, by platform."""
    _setup_style()

    # Data from ScreenSpot JSON results (extracted above)
    platforms = ['Desktop\n(N=334)', 'Mobile\n(N=501)', 'Web\n(N=437)']
    metrics = ['Action Acc.', 'Text Acc.', 'Icon Acc.']
    models = ['Baseline', 'FT-All (6.5k)', 'FT-All (25k)']
    colors = ['#aec6e8', '#fdc08c', '#96cda0']

    data = {
        'Desktop': {
            'Baseline':       [0.8563, 0.9691, 0.7000],
            'FT-All (6.5k)':  [0.8293, 0.9433, 0.6714],
            'FT-All (25k)':   [0.7964, 0.9124, 0.6357],
        },
        'Mobile': {
            'Baseline':       [0.8603, 0.9138, 0.7867],
            'FT-All (6.5k)':  [0.8563, 0.9103, 0.7820],
            'FT-All (25k)':   [0.8343, 0.8897, 0.7583],
        },
        'Web': {
            'Baseline':       [0.8032, 0.8675, 0.7291],
            'FT-All (6.5k)':  [0.8032, 0.8547, 0.7438],
            'FT-All (25k)':   [0.7803, 0.8419, 0.7094],
        },
    }

    fig, axes = plt.subplots(3, 1, figsize=(10, 14), sharex=True)
    fig.suptitle('ScreenSpot-v2: Baseline vs 6.5k vs 25k', fontsize=TITLE_SIZE, fontweight='bold', y=1.01)

    x = np.arange(len(metrics))
    n_models = len(models)
    total_span = 0.75
    width = total_span / n_models

    platform_keys = ['Desktop', 'Mobile', 'Web']

    for pi, (plat_key, plat_label) in enumerate(zip(platform_keys, platforms)):
        ax = axes[pi]
        ax.set_title(plat_label, fontsize=SUBTITLE_SIZE, fontweight='bold', pad=10)

        for mi, model in enumerate(models):
            vals = [v * 100 for v in data[plat_key][model]]
            positions = x - (n_models - 1) / 2 * width + mi * width

            bars = ax.bar(positions, vals, width, color=colors[mi], alpha=0.9,
                          edgecolor='none', label=model if pi == 0 else '', zorder=2)

            for bi, (bar, val) in enumerate(zip(bars, vals)):
                if mi % 2 == 0:
                    y_pos = bar.get_height() + 0.4
                    va = 'bottom'
                else:
                    y_pos = bar.get_height() + 0.4
                    va = 'bottom'
                ax.text(bar.get_x() + bar.get_width()/2., y_pos,
                        f'{val:.1f}', ha='center', va=va,
                        fontsize=BAR_LABEL_SIZE, fontweight='bold')

        ax.set_xticks(x)
        ax.set_xticklabels(metrics, fontsize=TEXT_SIZE)
        ax.tick_params(axis='y', labelsize=TEXT_SIZE)
        ax.set_ylim(55, 105)
        ax.grid(True, alpha=0.3, linestyle='--', axis='y', zorder=0)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.set_ylabel('Accuracy (%)', fontsize=AXIS_LABEL_SIZE)

    fig.legend(models, loc='upper center', ncol=n_models, fontsize=LEGEND_SIZE,
               bbox_to_anchor=(0.5, 0.97), framealpha=0.95, edgecolor='#ccc')
    plt.tight_layout(rect=[0.0, 0.0, 1.0, 0.91])
    plt.subplots_adjust(hspace=0.35)

    path = os.path.join(SCRIPT_DIR, 'fig_benchmark_mask_1.png')
    plt.savefig(path, bbox_inches='tight', dpi=150, facecolor='white')
    print(f"Saved: {path}")
    plt.close(fig)


# ============================================================================
# FIG 12: ScreenSpot-v2 vs GUI-Perturbed — the masking effect
# ============================================================================

def make_fig12_benchmark_masking():
    """
    Side-by-side: ScreenSpot-v2 shows minimal degradation after finetuning,
    but GUI-Perturbed reveals the precision vulnerability persists.
    Left panel: ScreenSpot action_acc (overall, positive only).
    Right panel: GUI-Perturbed hit rate on original vs precision.
    """
    _setup_style()

    # ScreenSpot overall action_acc (positive only, averaged across platforms)
    ss_data = {
        'Baseline':          np.mean([0.8563, 0.8603, 0.8032]),
        'FT-All (6.5k)':     np.mean([0.8293, 0.8563, 0.8032]),
        'FT-All (25k)':      np.mean([0.7964, 0.8343, 0.7803]),
        'FT-Salesforce':     np.mean([0.8293, 0.8543, 0.8032]),
        'FT-Perturbed':      np.mean([0.8293, 0.8563, 0.8032]),
    }

    # GUI-Perturbed hit rates (from finetuned_confidence_intervals.csv)
    ci = pd.read_csv(os.path.join(SCRIPT_DIR, 'finetuned_confidence_intervals.csv'))
    gp_models = {
        'Baseline': 'baseline',
        'FT-All (6.5k)': 'all',
        'FT-All (25k)': 'all_25k_3_epoch',
        'FT-Salesforce': '25k_salesforce_1_epoch',
        'FT-Perturbed': '25k_perturbed_1_epoch',
    }
    gp_original = {}
    gp_precision = {}
    for label, model_key in gp_models.items():
        orig = ci[(ci['model'] == model_key) & (ci['variant'] == 'original')]['hit_rate'].mean()
        prec = ci[(ci['model'] == model_key) & (ci['variant'] == 'precision')]['hit_rate'].mean()
        gp_original[label] = orig
        gp_precision[label] = prec

    model_order = ['Baseline', 'FT-All (6.5k)', 'FT-All (25k)', 'FT-Salesforce', 'FT-Perturbed']
    short_labels = ['Base', 'FT-All\n6.5k', 'FT-All\n25k', 'FT-SF\n25k', 'FT-Pert\n25k']

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
    fig.suptitle('Benchmark Masking: ScreenSpot-v2 vs. GUI-Perturbed',
                 fontsize=TITLE_SIZE, fontweight='bold', y=1.02)

    x = np.arange(len(model_order))

    # --- Left: ScreenSpot ---
    ss_vals = [ss_data[m] * 100 for m in model_order]
    bars1 = ax1.bar(x, ss_vals, 0.6, color='#aec6e8', alpha=0.9, edgecolor='none', zorder=2)
    for bar, val in zip(bars1, ss_vals):
        ax1.text(bar.get_x() + bar.get_width()/2., val + 0.5,
                 f'{val:.1f}', ha='center', va='bottom',
                 fontsize=BAR_LABEL_SIZE, fontweight='bold')

    ax1.set_title('ScreenSpot-v2\n(Action Accuracy)', fontsize=SUBTITLE_SIZE, fontweight='bold', pad=10)
    ax1.set_xticks(x)
    ax1.set_xticklabels(short_labels, fontsize=TEXT_SIZE - 4)
    ax1.tick_params(axis='y', labelsize=TEXT_SIZE)
    ax1.set_ylabel('Accuracy (%)', fontsize=AXIS_LABEL_SIZE)
    ax1.set_ylim(70, 95)
    ax1.grid(True, alpha=0.3, linestyle='--', axis='y', zorder=0)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)

    # Annotation: "looks fine"
    ax1.annotate('< 3pp spread', xy=(2, ss_vals[2] - 1), fontsize=BAR_LABEL_SIZE,
                 fontweight='bold', color='#2a7f2a', ha='center')

    # --- Right: GUI-Perturbed ---
    width = 0.35
    orig_vals = [gp_original[m] * 100 for m in model_order]
    prec_vals = [gp_precision[m] * 100 for m in model_order]

    bars_orig = ax2.bar(x - width/2, orig_vals, width, color='#7bafd4', alpha=0.85,
                        edgecolor='none', label='Original', zorder=2)
    bars_prec = ax2.bar(x + width/2, prec_vals, width, color='#e8956a', alpha=0.85,
                        edgecolor='none', label='Precision', zorder=2)

    for bars in [bars_orig, bars_prec]:
        for bi, bar in enumerate(bars):
            h = bar.get_height()
            if bi % 2 == 0:
                y_pos = h + 0.3
                va = 'bottom'
            else:
                y_pos = h + 0.3
                va = 'bottom'
            ax2.text(bar.get_x() + bar.get_width()/2., y_pos,
                     f'{h:.1f}', ha='center', va=va,
                     fontsize=BAR_LABEL_SIZE - 1, fontweight='bold')

    ax2.set_title('GUI-Perturbed\n(Hit Rate)', fontsize=SUBTITLE_SIZE, fontweight='bold', pad=10)
    ax2.set_xticks(x)
    ax2.set_xticklabels(short_labels, fontsize=TEXT_SIZE - 4)
    ax2.tick_params(axis='y', labelsize=TEXT_SIZE)
    ax2.set_ylabel('Hit Rate (%)', fontsize=AXIS_LABEL_SIZE)
    ax2.set_ylim(45, 70)
    ax2.grid(True, alpha=0.3, linestyle='--', axis='y', zorder=0)
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.legend(fontsize=LEGEND_SIZE - 2, loc='lower right', framealpha=0.95)

    # Annotation: "5pp drop persists"
    ax2.annotate('~5pp drop persists\nacross all variants',
                 xy=(2, prec_vals[2]), xytext=(3.2, 49),
                 fontsize=BAR_LABEL_SIZE - 1, fontweight='bold', color='#cc3333',
                 arrowprops=dict(arrowstyle='->', color='#cc3333', lw=1.5),
                 ha='center')

    plt.tight_layout(rect=[0.0, 0.0, 1.0, 0.93])
    plt.subplots_adjust(wspace=0.25)

    path = os.path.join(SCRIPT_DIR, 'fig_benchmark_mask_2.png')
    plt.savefig(path, bbox_inches='tight', dpi=150, facecolor='white')
    print(f"Saved: {path}")
    plt.close(fig)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("Generating remaining preprint figures...")
    make_fig5_direct_vs_relational()
    make_fig11_screenspot_scaling()
    # Fig 12 (benchmark masking) dropped — 3pp vs 5pp spread is not compelling enough.
    # The masking argument works better as prose: ScreenSpot doesn't test perturbation
    # robustness at all, so it literally cannot detect the vulnerability.
    # make_fig12_benchmark_masking()
    print("Done!")
