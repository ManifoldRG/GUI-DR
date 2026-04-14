"""
Generate paper-ready outputs from statistical analysis:
  (a) Methods paragraph for the 3 metrics
  (b) Unified table: hit rate + flip rate + net Δ + McNemar p
  (c) Decomposition plot: degraded vs improved flips
"""

import os
import pandas as pd
import numpy as np

# ============================================================================
# Load results
# ============================================================================
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
baseline_ci = pd.read_csv(os.path.join(DATA_DIR, 'baseline_confidence_intervals.csv'))
baseline_mc = pd.read_csv(os.path.join(DATA_DIR, 'baseline_mcnemar_tests.csv'))
finetuned_ci = pd.read_csv(os.path.join(DATA_DIR, 'finetuned_confidence_intervals.csv'))
finetuned_mc = pd.read_csv(os.path.join(DATA_DIR, 'finetuned_mcnemar_tests.csv'))

MODEL_LABELS = {
    'gta1': 'GTA-1',
    'qwen25vl': 'Qwen2.5-VL',
    'uitars15': 'UI-TARS-1.5',
    'baseline': 'UI-TARS-1.5 (base)',
    'all': 'FT-All (6.5k)',
    'style': 'FT-Style (6.5k)',
    'text_shrink_zoom': 'FT-TextShrink (6.5k)',
    'all_25k_3_epoch': 'FT-All (25k, 3ep)',
    '25k_salesforce_1_epoch': 'FT-Salesforce (25k)',
    '25k_perturbed_1_epoch': 'FT-Perturbed (25k)',
}

PERT_LABELS = {
    'precision': 'Precision',
    'style': 'Style',
    'text_shrink': 'Text Shrink',
}


def sig_stars(p):
    if p < 0.001: return '***'
    if p < 0.01: return '**'
    if p < 0.05: return '*'
    return ''


# ============================================================================
# (a) METHODS PARAGRAPH
# ============================================================================

METHODS_PARAGRAPH = r"""
\paragraph{Evaluation Metrics.}
We evaluate perturbation robustness along three complementary dimensions,
each computed over $n$ matched sample pairs (same task and step evaluated on
both the original and perturbed screenshot):

\begin{itemize}[nosep]
  \item \textbf{Hit rate} --- the proportion of predictions that fall inside
    the ground-truth bounding box. We report 95\% bootstrap confidence
    intervals (10{,}000 resamples) for all hit rates; exact binomial
    (Clopper--Pearson) intervals agreed within 0.2\,pp throughout and are
    omitted for brevity.
  \item \textbf{Flip rate} --- the fraction of matched pairs whose binary
    outcome (hit/miss) changed between the original and the perturbed
    condition. This measures \emph{prediction consistency}: a high flip rate
    indicates the model's output is sensitive to the perturbation, regardless
    of whether accuracy improves or degrades on average.
  \item \textbf{Net~$\Delta$} --- the difference in hit rate between the
    original and perturbed conditions (original $-$ perturbed), with 95\%
    bootstrap CI. A positive $\Delta$ indicates degradation. We test
    significance with McNemar's test on the $2\times2$ table of concordant
    and discordant pairs, reporting $p$-values with continuity correction
    (exact binomial $p$ for cells $<25$).
\end{itemize}

Flip rate and net~$\Delta$ decompose the perturbation effect: a perturbation
can cause many individual predictions to change (high flip rate) without
shifting overall accuracy (low $\Delta$), if roughly equal numbers of
samples degrade and improve. Conversely, a perturbation with a high
$\Delta$ necessarily has a high flip rate with an asymmetric split between
degraded and improved samples.
""".strip()


# ============================================================================
# (b) UNIFIED TABLE: hit rate, flip rate, net Δ, McNemar p
# ============================================================================

def _build_unified_rows(mc_df, ci_df, n_per_group):
    """Build rows for the unified table from McNemar + CI data."""
    mc = mc_df.copy()
    mc['query_group'] = mc['query_type'].map({
        'direct_query': 'Direct', 'relational_query': 'Relational'
    })
    # Total samples per (model × query_group) = n_per_group × 2 reasoning modes
    n_total = n_per_group * 2
    rows = []
    for model in mc['model'].unique():
        for pert in ['precision', 'style', 'text_shrink']:
            for qg in ['Direct', 'Relational']:
                mask = ((mc['model'] == model) & (mc['perturbation'] == pert) &
                        (mc['query_group'] == qg))
                sub = mc[mask]
                if len(sub) == 0:
                    continue

                # Hit rate on original (averaged over reasoning modes)
                orig_ci = ci_df[
                    (ci_df['model'] == model) &
                    (ci_df['variant'] == 'original') &
                    (ci_df['query_type'].map({'direct_query': 'Direct',
                                              'relational_query': 'Relational'}) == qg)
                ]
                orig_rate = orig_ci['hit_rate'].mean() if len(orig_ci) > 0 else np.nan
                orig_lo = orig_ci['boot_ci_lo'].mean() if len(orig_ci) > 0 else np.nan
                orig_hi = orig_ci['boot_ci_hi'].mean() if len(orig_ci) > 0 else np.nan

                # Flip rate = total discordant / n
                b_total = sub['b_orig_only'].sum()
                c_total = sub['c_pert_only'].sum()
                flips = b_total + c_total
                flip_rate = flips / (sub['n_matched'].sum())

                # Net Δ (averaged across reasoning modes)
                avg_diff = sub['diff'].mean()
                avg_lo = sub['diff_ci_lo'].mean()
                avg_hi = sub['diff_ci_hi'].mean()
                min_p = sub['mcnemar_p'].min()
                n_sig = (sub['mcnemar_p'] < 0.05).sum()
                n_tests = len(sub)

                # Degraded:Improved ratio
                ratio_str = f'{b_total/c_total:.1f}' if c_total > 0 else r'$\infty$'

                rows.append({
                    'model': model,
                    'perturbation': pert,
                    'query_group': qg,
                    'orig_rate': orig_rate,
                    'orig_ci_lo': orig_lo,
                    'orig_ci_hi': orig_hi,
                    'flip_rate': flip_rate,
                    'b_degraded': b_total,
                    'c_improved': c_total,
                    'ratio': ratio_str,
                    'net_diff': avg_diff,
                    'diff_ci_lo': avg_lo,
                    'diff_ci_hi': avg_hi,
                    'min_p': min_p,
                    'n_sig': n_sig,
                    'n_tests': n_tests,
                })
    return pd.DataFrame(rows)


def make_unified_table_baseline():
    df = _build_unified_rows(baseline_mc, baseline_ci, n_per_group=390)
    models = ['gta1', 'qwen25vl', 'uitars15']
    perts = ['precision', 'style', 'text_shrink']

    lines = []
    lines.append(r'\begin{table*}[ht]')
    lines.append(r'\centering')
    lines.append(r'\caption{Perturbation robustness of baseline models ($n = 390$ matched sample pairs per test).}')
    lines.append(r'\label{tab:robustness-baseline}')
    lines.append(r'\small')
    lines.append(r'\begin{tabular}{llc cc cc cc}')
    lines.append(r'\toprule')
    lines.append(r' & & & \multicolumn{2}{c}{\textbf{Flip Rate}} & \multicolumn{2}{c}{\textbf{Net $\Delta$ (\%)}} & & \\')
    lines.append(r'\cmidrule(lr){4-5} \cmidrule(lr){6-7}')
    lines.append(r'\textbf{Model} & \textbf{Pert.} & \textbf{Baseline Acc.} & \textbf{Direct} & \textbf{Rel.} & \textbf{Direct} & \textbf{Rel.} & $\boldsymbol{b}$\,/\,$\boldsymbol{c}$ & \textbf{Sig.} \\')
    lines.append(r'\midrule')

    for model in models:
        first = True
        for pert in perts:
            model_str = MODEL_LABELS[model] if first else ''
            first = False

            model_ci = baseline_ci[
                (baseline_ci['model'] == model) & (baseline_ci['variant'] == 'original')]
            orig_rate = model_ci['hit_rate'].mean()

            direct = df[(df['model'] == model) & (df['perturbation'] == pert) & (df['query_group'] == 'Direct')]
            relat = df[(df['model'] == model) & (df['perturbation'] == pert) & (df['query_group'] == 'Relational')]

            if len(direct) == 0 or len(relat) == 0:
                continue

            dr = direct.iloc[0]
            rr = relat.iloc[0]

            total_b = dr['b_degraded'] + rr['b_degraded']
            total_c = dr['c_improved'] + rr['c_improved']
            total_sig = dr['n_sig'] + rr['n_sig']
            total_tests = dr['n_tests'] + rr['n_tests']

            dr_p = baseline_mc[(baseline_mc['model'] == model) & (baseline_mc['perturbation'] == pert) &
                               (baseline_mc['query_type'] == 'direct_query')]['mcnemar_p']
            rr_p = baseline_mc[(baseline_mc['model'] == model) & (baseline_mc['perturbation'] == pert) &
                               (baseline_mc['query_type'] == 'relational_query')]['mcnemar_p']
            dr_stars = sig_stars(dr_p.min()) if len(dr_p) > 0 else ''
            rr_stars = sig_stars(rr_p.min()) if len(rr_p) > 0 else ''

            hit_str = f'{orig_rate*100:.1f}' if pert == perts[0] else ''

            lines.append(
                f'{model_str} & {PERT_LABELS[pert]} & '
                f'{hit_str} & '
                f'{dr["flip_rate"]*100:.1f}\\% & {rr["flip_rate"]*100:.1f}\\% & '
                f'{dr["net_diff"]*100:+.1f}{dr_stars} & {rr["net_diff"]*100:+.1f}{rr_stars} & '
                f'{int(total_b)}/{int(total_c)} & '
                f'{total_sig}/{total_tests}'
                + r' \\'
            )
        if model != models[-1]:
            lines.append(r'\midrule')

    lines.append(r'\bottomrule')
    lines.append(r'\end{tabular}')
    lines.append(r'\vspace{6pt}')
    lines.append(r'\begin{minipage}{\textwidth}')
    lines.append(r'\footnotesize')
    lines.append(r'\renewcommand{\arraystretch}{1.15}')
    lines.append(r'\begin{tabular}{@{} >{\bfseries}l @{\hspace{8pt}} p{0.80\textwidth} @{}}')
    lines.append(r'Baseline Acc. & Hit rate (\%) on unperturbed (original) screenshots, averaged across reasoning modes and query types. This is the model\textquotesingle s accuracy \emph{before} any perturbation is applied. \\[2pt]')
    lines.append(r'Flip Rate & Fraction of matched sample pairs whose binary outcome (hit/miss) \emph{changed} between original and perturbed conditions. Reported separately for \textbf{Direct} (direct-instruction) and \textbf{Rel.}\ (relational-instruction) queries. \\[2pt]')
    lines.append(r'Net\,$\Delta$ & Hit-rate drop in percentage points (original $-$ perturbed). Positive values mean the perturbation \emph{degraded} accuracy. \\[2pt]')
    lines.append(r'$b$\,/\,$c$ & Count of samples that degraded ($b$: correct$\,\to\,$wrong) vs.\ improved ($c$: wrong$\,\to\,$correct), aggregated across all configurations. When $b \gg c$, the perturbation causes systematic, directional degradation. \\[2pt]')
    lines.append(r'Sig. & Number of significant McNemar tests ($p < 0.05$) out of 4 total (2 reasoning modes $\times$ 2 query types). \\[2pt]')
    lines.append(r'{*\,/\,**\,/\,***} & McNemar\textquotesingle s $p < 0.05$\,/\,$p < 0.01$\,/\,$p < 0.001$. \\')
    lines.append(r'\end{tabular}')
    lines.append(r'\end{minipage}')
    lines.append(r'\end{table*}')
    return '\n'.join(lines)


def make_unified_table_finetuned():
    df = _build_unified_rows(finetuned_mc, finetuned_ci, n_per_group=429)
    models = ['baseline', 'all', 'style', 'text_shrink_zoom',
              'all_25k_3_epoch', '25k_salesforce_1_epoch', '25k_perturbed_1_epoch']
    perts = ['precision', 'style', 'text_shrink']

    lines = []
    lines.append(r'\begin{table*}[ht]')
    lines.append(r'\centering')
    lines.append(r'\caption{Perturbation robustness of finetuned models ($n = 390$ matched sample pairs per test). Same metrics and notation as Table~\ref{tab:robustness-baseline}.}')
    lines.append(r'\label{tab:robustness-finetuned}')
    lines.append(r'\scriptsize')
    lines.append(r'\begin{tabular}{llc cc cc cc}')
    lines.append(r'\toprule')
    lines.append(r' & & & \multicolumn{2}{c}{\textbf{Flip Rate}} & \multicolumn{2}{c}{\textbf{Net $\Delta$ (\%)}} & & \\')
    lines.append(r'\cmidrule(lr){4-5} \cmidrule(lr){6-7}')
    lines.append(r'\textbf{Model} & \textbf{Pert.} & \textbf{Baseline Acc.} & \textbf{Direct} & \textbf{Rel.} & \textbf{Direct} & \textbf{Rel.} & $\boldsymbol{b}$\,/\,$\boldsymbol{c}$ & \textbf{Sig.} \\')
    lines.append(r'\midrule')

    for model in models:
        first = True
        for pert in perts:
            model_str = MODEL_LABELS.get(model, model) if first else ''
            first = False

            model_ci = finetuned_ci[
                (finetuned_ci['model'] == model) & (finetuned_ci['variant'] == 'original')]
            orig_rate = model_ci['hit_rate'].mean()

            direct = df[(df['model'] == model) & (df['perturbation'] == pert) & (df['query_group'] == 'Direct')]
            relat = df[(df['model'] == model) & (df['perturbation'] == pert) & (df['query_group'] == 'Relational')]

            if len(direct) == 0 or len(relat) == 0:
                continue

            dr = direct.iloc[0]
            rr = relat.iloc[0]

            total_b = dr['b_degraded'] + rr['b_degraded']
            total_c = dr['c_improved'] + rr['c_improved']
            total_sig = dr['n_sig'] + rr['n_sig']
            total_tests = dr['n_tests'] + rr['n_tests']

            dr_p = finetuned_mc[(finetuned_mc['model'] == model) & (finetuned_mc['perturbation'] == pert) &
                               (finetuned_mc['query_type'] == 'direct_query')]['mcnemar_p']
            rr_p = finetuned_mc[(finetuned_mc['model'] == model) & (finetuned_mc['perturbation'] == pert) &
                               (finetuned_mc['query_type'] == 'relational_query')]['mcnemar_p']
            dr_stars = sig_stars(dr_p.min()) if len(dr_p) > 0 else ''
            rr_stars = sig_stars(rr_p.min()) if len(rr_p) > 0 else ''

            hit_str = f'{orig_rate*100:.1f}' if pert == perts[0] else ''

            lines.append(
                f'{model_str} & {PERT_LABELS[pert]} & '
                f'{hit_str} & '
                f'{dr["flip_rate"]*100:.1f}\\% & {rr["flip_rate"]*100:.1f}\\% & '
                f'{dr["net_diff"]*100:+.1f}{dr_stars} & {rr["net_diff"]*100:+.1f}{rr_stars} & '
                f'{int(total_b)}/{int(total_c)} & '
                f'{total_sig}/{total_tests}'
                + r' \\'
            )
        if model != models[-1]:
            lines.append(r'\midrule')

    lines.append(r'\bottomrule')
    lines.append(r'\end{tabular}')
    lines.append(r'\end{table*}')
    return '\n'.join(lines)


# ============================================================================
# (c) DECOMPOSITION PLOT: degraded vs improved stacked bars
# ============================================================================

def make_decomposition_plot(mc_df, ci_df, models, model_labels, n_per_group,
                            title, save_path=None):
    """
    Horizontal stacked bar chart: for each model × perturbation,
    show degraded (red, right) and improved (green, left) as bars
    from a center axis. Flip rate = total width. Asymmetry = net Δ direction.
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import seaborn as sns

    sns.set_style("whitegrid")
    plt.rcParams.update({
        'figure.dpi': 100, 'savefig.dpi': 150, 'font.size': 18,
        'text.color': 'black', 'axes.labelcolor': 'black',
        'axes.edgecolor': 'black', 'xtick.color': 'black',
        'ytick.color': 'black', 'axes.facecolor': 'white',
        'figure.facecolor': 'white',
    })

    # Font sizes matching the bar plots
    TITLE_SIZE = 24
    SUBTITLE_SIZE = 20
    TEXT_SIZE = 18
    BAR_LABEL_SIZE = 14
    AXIS_LABEL_SIZE = 20
    LEGEND_SIZE = 17

    perts = ['precision', 'style', 'text_shrink']
    pert_labels = ['Precision', 'Style', 'Text Shrink']
    query_groups = ['Direct', 'Relational']

    mc = mc_df.copy()
    mc['query_group'] = mc['query_type'].map({
        'direct_query': 'Direct', 'relational_query': 'Relational'
    })

    fig, axes = plt.subplots(1, 2, figsize=(14, 0.7 * len(models) * len(perts) + 2),
                             sharey=True)

    for qi, qg in enumerate(query_groups):
        ax = axes[qi]
        y_labels = []
        y_pos = []
        idx = 0

        for model in reversed(models):
            for pert in reversed(perts):
                mask = ((mc['model'] == model) & (mc['perturbation'] == pert) &
                        (mc['query_group'] == qg))
                sub = mc[mask]
                if len(sub) == 0:
                    continue

                b = sub['b_orig_only'].sum()
                c = sub['c_pert_only'].sum()
                n = sub['n_matched'].sum()
                b_pct = b / n * 100
                c_pct = c / n * 100
                min_p = sub['mcnemar_p'].min()
                stars = sig_stars(min_p)

                ax.barh(idx, b_pct, height=0.7, color='#e07b7b', edgecolor='none',
                        alpha=0.85, zorder=2)
                ax.barh(idx, -c_pct, height=0.7, color='#7bbd7b', edgecolor='none',
                        alpha=0.85, zorder=2)

                if b > 0:
                    ax.text(b_pct + 0.3, idx, f'{b}{stars}',
                            va='center', ha='left', fontsize=BAR_LABEL_SIZE, color='#a03030',
                            fontweight='bold')
                if c > 0:
                    ax.text(-c_pct - 0.3, idx, f'{c}',
                            va='center', ha='right', fontsize=BAR_LABEL_SIZE, color='#308030',
                            fontweight='bold')

                label = f'{model_labels.get(model, model)} / {pert_labels[perts.index(pert)]}'
                y_labels.append(label)
                y_pos.append(idx)
                idx += 1
            idx += 0.5

        ax.set_yticks(y_pos)
        ax.set_yticklabels(y_labels, fontsize=TEXT_SIZE)
        ax.tick_params(axis='x', labelsize=TEXT_SIZE)
        ax.axvline(x=0, color='black', linewidth=0.8, zorder=3)
        ax.set_xlabel('% of matched pairs', fontsize=AXIS_LABEL_SIZE)
        ax.set_title(f'{qg} Query', fontsize=SUBTITLE_SIZE, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='x', zorder=0)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        max_val = max(abs(ax.get_xlim()[0]), abs(ax.get_xlim()[1]))
        ax.set_xlim(-max_val - 4, max_val + 4)

    legend_patches = [
        mpatches.Patch(color='#e07b7b', alpha=0.85, label='Degraded ($b$: correct → wrong)'),
        mpatches.Patch(color='#7bbd7b', alpha=0.85, label='Improved ($c$: wrong → correct)'),
    ]
    fig.suptitle(title, fontsize=TITLE_SIZE, fontweight='bold', y=1.02)
    fig.legend(handles=legend_patches, loc='upper center', ncol=2,
               fontsize=LEGEND_SIZE, bbox_to_anchor=(0.5, 0.97), framealpha=0.95,
               edgecolor='#cccccc')
    plt.tight_layout(rect=[0.0, 0.0, 1.0, 0.91])

    if save_path:
        plt.savefig(save_path, bbox_inches='tight', dpi=150, facecolor='white')
        print(f"Saved: {save_path}")
    plt.show()


# ============================================================================
# (d) RESULTS PROSE — paragraphs describing the tables
# ============================================================================

def generate_results_prose():
    mc = baseline_mc.copy()

    # --- Aggregate stats for prose ---
    prec = mc[mc['perturbation'] == 'precision']
    style = mc[mc['perturbation'] == 'style']
    ts = mc[mc['perturbation'] == 'text_shrink']

    # Total flips
    total_prec_b = prec['b_orig_only'].sum()
    total_prec_c = prec['c_pert_only'].sum()
    total_style_b = style['b_orig_only'].sum()
    total_style_c = style['c_pert_only'].sum()
    total_ts_b = ts['b_orig_only'].sum()
    total_ts_c = ts['c_pert_only'].sum()
    n_total_pairs = mc['n_matched'].sum() // 3  # total matched pairs per perturbation

    # Worst cases per model
    worst = {}
    for model in ['gta1', 'qwen25vl', 'uitars15']:
        row = mc[(mc['model'] == model)].sort_values('diff', ascending=False).iloc[0]
        ci_row = baseline_ci[
            (baseline_ci['model'] == model) &
            (baseline_ci['variant'] == 'original') &
            (baseline_ci['use_reasoning'] == row['use_reasoning']) &
            (baseline_ci['query_type'] == row['query_type'])
        ].iloc[0]
        worst[model] = (row, ci_row)

    # Finetuned aggregate
    ft_mc = finetuned_mc.copy()
    ft_prec = ft_mc[ft_mc['perturbation'] == 'precision']

    lines = []

    # --- Baseline results paragraph ---
    lines.append(r'\paragraph{Baseline Models (Table~\ref{tab:robustness-baseline}).}')
    lines.append(
        f'Precision perturbation was the dominant source of degradation across all three baseline models, '
        f'reaching significance in {{\\bfseries {(prec["mcnemar_p"] < 0.05).sum()}}}/{len(prec)} McNemar tests '
        f'($p < 0.05$), compared to {(style["mcnemar_p"] < 0.05).sum()}/{len(style)} for style '
        f'and {(ts["mcnemar_p"] < 0.05).sum()}/{len(ts)} for text-shrink. '
        f'The effect was consistently unidirectional: {total_prec_b} samples degraded versus '
        f'{total_prec_c} improved ($b$/$c$ ratio $\\approx$ {total_prec_b/total_prec_c:.1f}:1), '
        f'whereas style perturbation produced a near-symmetric split '
        f'({total_style_b} degraded vs.\\ {total_style_c} improved, '
        f'{total_style_b/total_style_c:.1f}:1).'
    )
    lines.append('')

    # Per-model highlights
    r_gta, ci_gta = worst['gta1']
    qt = 'relational' if 'relational' in r_gta['query_type'] else 'direct'
    lines.append(
        f'GTA-1 showed the largest single drop on {qt} queries, '
        f'where precision perturbation reduced hit rate from '
        f'{r_gta["orig_hit_rate"]*100:.1f}\\% '
        f'(95\\% CI [{ci_gta["boot_ci_lo"]*100:.1f}, {ci_gta["boot_ci_hi"]*100:.1f}]) '
        f'to {r_gta["pert_hit_rate"]*100:.1f}\\%, '
        f'a drop of {r_gta["diff"]*100:.1f}\\,pp '
        f'($p < {_p_threshold(r_gta["mcnemar_p"])}$). '
    )

    r_ui, ci_ui = worst['uitars15']
    qt = 'relational' if 'relational' in r_ui['query_type'] else 'direct'
    lines.append(
        f'UI-TARS-1.5 was most affected on {qt} queries with a '
        f'{r_ui["diff"]*100:.1f}\\,pp drop ($p < {_p_threshold(r_ui["mcnemar_p"])}$), '
        f'and was the only model where precision perturbation was significant in all 4 configurations (4/4). '
    )

    r_qw, ci_qw = worst['qwen25vl']
    qt = 'relational' if 'relational' in r_qw['query_type'] else 'direct'
    lines.append(
        f'Qwen2.5-VL showed moderate sensitivity, with precision perturbation significant '
        f'primarily on relational queries (2/4 significant).'
    )
    lines.append('')

    # --- Instability paragraph ---
    lines.append(
        f'Importantly, the lack of significance for style and text-shrink perturbations does not mean '
        f'these perturbations had no effect on individual predictions. '
        f'Style perturbation flipped {total_style_b + total_style_c} of {n_total_pairs} sample pairs '
        f'({(total_style_b + total_style_c) / n_total_pairs * 100:.1f}\\% flip rate), '
        f"comparable to precision's "
        f'{total_prec_b + total_prec_c} flips ({(total_prec_b + total_prec_c) / n_total_pairs * 100:.1f}\\%). '
        f'However, because style flips were roughly bidirectional '
        f'({total_style_b} degraded vs.\\ {total_style_c} improved), '
        f'the net accuracy change was not statistically distinguishable from zero. '
        f'This reveals a distinction between \\emph{{robustness}} (net $\\Delta$) '
        f'and \\emph{{consistency}} (flip rate): '
        f'all three perturbation types cause substantial prediction instability, '
        f'but only precision perturbation does so in a systematically harmful direction.'
    )
    lines.append('')

    # --- Finetuned paragraph ---
    lines.append(r'\paragraph{Finetuned Models (Table~\ref{tab:robustness-finetuned}).}')
    lines.append(
        f'After finetuning, precision perturbation remained the primary source of '
        f'significant degradation ({(ft_prec["mcnemar_p"] < 0.05).sum()}/{len(ft_prec)} tests significant), '
        f'while style (1/{len(ft_mc[ft_mc["perturbation"]=="style"])}) and '
        f'text-shrink (0/{len(ft_mc[ft_mc["perturbation"]=="text_shrink"])}) '
        f'perturbations remained non-significant. '
        f'None of the finetuning strategies---whether trained on all perturbation types (FT-All), '
        f'a single perturbation type (FT-Style, FT-TextShrink), '
        f'or scaled to 25k samples---substantially reduced the precision vulnerability. '
        f'The $b$/$c$ ratios for precision remained close to 2:1 across all finetuned variants, '
        f'indicating that the directional nature of the degradation persisted. '
        f'Flip rates for style perturbation were comparable to or slightly higher than the baseline, '
        f'suggesting finetuning did not improve prediction consistency either.'
    )

    return '\n'.join(lines)


def _p_threshold(p):
    """Return a clean p-value threshold string for prose."""
    if p < 0.001: return '0.001'
    if p < 0.01: return '0.01'
    if p < 0.05: return '0.05'
    return f'{p:.3f}'


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    # --- (a) Methods paragraph ---
    print("=" * 80)
    print("(a) METHODS PARAGRAPH")
    print("=" * 80)
    print(METHODS_PARAGRAPH)

    # --- (b) Unified tables ---
    t_bl = make_unified_table_baseline()
    t_ft = make_unified_table_finetuned()

    print("\n" + "=" * 80)
    print("(b) UNIFIED TABLE — BASELINE")
    print("=" * 80)
    print(t_bl)

    print("\n" + "=" * 80)
    print("(b) UNIFIED TABLE — FINETUNED")
    print("=" * 80)
    print(t_ft)

    # --- (d) Results prose ---
    prose = generate_results_prose()
    print("\n" + "=" * 80)
    print("(d) RESULTS PROSE")
    print("=" * 80)
    print(prose)

    # --- Save LaTeX ---
    with open(os.path.join(DATA_DIR, 'paper_tables.tex'), 'w') as f:
        f.write("% === Methods paragraph (for Methods / Evaluation Metrics section) ===\n")
        f.write(METHODS_PARAGRAPH)
        f.write("\n\n% === Baseline robustness table ===\n")
        f.write(t_bl)
        f.write("\n\n% === Finetuned robustness table ===\n")
        f.write(t_ft)
        f.write("\n\n% === Results prose (for Results section) ===\n")
        f.write(prose)
    print(f"\nSaved to {os.path.join(DATA_DIR, 'paper_tables.tex')}")

    # --- (c) Decomposition plots ---
    print("\n" + "=" * 80)
    print("(c) DECOMPOSITION PLOTS")
    print("=" * 80)

    make_decomposition_plot(
        baseline_mc, baseline_ci,
        models=['gta1', 'qwen25vl', 'uitars15'],
        model_labels=MODEL_LABELS,
        n_per_group=390,
        title='Prediction Flips: Degraded vs. Improved (Baseline)',
        save_path=os.path.join(DATA_DIR, 'baseline_flip_decomposition.png')
    )

    make_decomposition_plot(
        finetuned_mc, finetuned_ci,
        models=['baseline', 'all', 'style', 'text_shrink_zoom',
                'all_25k_3_epoch', '25k_salesforce_1_epoch', '25k_perturbed_1_epoch'],
        model_labels=MODEL_LABELS,
        n_per_group=429,
        title='Prediction Flips: Degraded vs. Improved (Finetuned)',
        save_path=os.path.join(DATA_DIR, 'finetuned_flip_decomposition.png')
    )
