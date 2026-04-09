"""
Plot: Performance by Relational Query Direction — Hit Accuracy
Converted from HTML canvas to matplotlib, matching the font config from plot_with_ci.py.

Usage:
    python data/plot_directional_bias.py
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# Data from the HTML source
DIRS = ['Above', 'Below', 'Left', 'Right']
ROWS = [
    {'label': 'Qwen2.5-VL',  'noR': [0.301, 0.451, 0.517, 0.713], 'wR': [0.400, 0.462, 0.469, 0.660]},
    {'label': 'UI-TARS-1.5', 'noR': [0.195, 0.256, 0.368, 0.571], 'wR': [0.303, 0.385, 0.450, 0.680]},
    {'label': 'GTA-1',       'noR': [0.567, 0.718, 0.689, 0.781], 'wR': [0.534, 0.681, 0.632, 0.794]},
]

SALMON = '#AD8868'
SAGE = '#78AF96'

# Font sizes matching plot_with_ci.py
TITLE_SIZE = 24
SUBTITLE_SIZE = 20
TEXT_SIZE = 18
BAR_LABEL_SIZE = 14
AXIS_LABEL_SIZE = 20
LEGEND_SIZE = 17


def main():
    plt.rcParams.update({
        'figure.dpi': 100, 'savefig.dpi': 150, 'font.size': 18,
        'text.color': 'black', 'axes.labelcolor': 'black',
        'axes.edgecolor': 'black', 'xtick.color': 'black',
        'ytick.color': 'black', 'axes.facecolor': 'white',
        'figure.facecolor': 'white',
    })

    n_rows = len(ROWS)
    fig, axes = plt.subplots(n_rows, 2, figsize=(14, 4 * n_rows + 1), sharey=False)

    fig.suptitle('Performance by Relational Query Direction \u2013 Hit Accuracy',
                 fontsize=TITLE_SIZE, fontweight='bold', y=1.01)

    col_titles = ['Without Reasoning', 'With Reasoning']
    bar_width = 0.5
    x = np.arange(len(DIRS))

    for ri, row in enumerate(ROWS):
        datasets = [row['noR'], row['wR']]
        colors = [SALMON, SAGE]

        for ci in range(2):
            ax = axes[ri, ci]
            vals = datasets[ci]

            bars = ax.bar(x, vals, bar_width, color=colors[ci], alpha=0.85,
                          edgecolor='none', zorder=2)

            # Bar value labels — staggered
            for bi, (bar, val) in enumerate(zip(bars, vals)):
                if bi % 2 == 0:
                    y_pos = bar.get_height() + 0.008
                    va = 'bottom'
                else:
                    y_pos = bar.get_height() + 0.008
                    va = 'bottom'
                ax.text(bar.get_x() + bar.get_width() / 2., y_pos,
                        f'{val:.3f}', ha='center', va=va,
                        fontsize=BAR_LABEL_SIZE, fontweight='bold', zorder=3)

            ax.set_xticks(x)
            ax.set_xticklabels(DIRS, fontsize=TEXT_SIZE)
            ax.tick_params(axis='y', labelsize=TEXT_SIZE)
            ax.set_ylim(0, max(max(row['noR']), max(row['wR'])) + 0.08)
            ax.grid(True, alpha=0.3, linestyle='--', axis='y', zorder=0)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)

            # Column title on top row only
            if ri == 0:
                ax.set_title(col_titles[ci], fontsize=SUBTITLE_SIZE, fontweight='bold', pad=10)

            # Row label on left column only
            if ci == 0:
                ax.set_ylabel(row['label'], fontsize=AXIS_LABEL_SIZE, fontweight='bold')

            # X-axis label on bottom row only
            if ri == n_rows - 1:
                ax.set_xlabel('Direction', fontsize=AXIS_LABEL_SIZE)

    # Legend
    import matplotlib.patches as mpatches
    legend_patches = [
        mpatches.Patch(color=SALMON, alpha=0.85, label='Without Reasoning'),
        mpatches.Patch(color=SAGE, alpha=0.85, label='With Reasoning'),
    ]
    fig.legend(handles=legend_patches, loc='upper center', ncol=2,
               fontsize=LEGEND_SIZE, bbox_to_anchor=(0.5, 0.96),
               framealpha=0.95, edgecolor='#cccccc')

    plt.tight_layout(rect=[0.0, 0.0, 1.0, 0.90])
    plt.subplots_adjust(hspace=0.35, wspace=0.20)

    save_path = 'data/directional_bias_hit_accuracy.png'
    plt.savefig(save_path, bbox_inches='tight', dpi=150, facecolor='white')
    print(f"Saved: {save_path}")
    plt.close(fig)


if __name__ == '__main__':
    main()
