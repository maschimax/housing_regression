import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import seaborn as sns

dataset = 'sensor'
# Use: ['t outperform default [s]', 'time'] or: ['Max Cut AUC', 'AUC']
ap_analysis_type = ['t outperform default [s]', 'time']
setup_variants = [(1, False), (8, False), (1, True)]

setup_labels = ['Single worker, no warm-start',
                'Eight workers, no warm-start', 'Single worker, warm-start']

ipt_colors = ['#005a94', '#D4E6F4', '#ffcc99']
bar_width = 0.3

hpo_map_dict = {
    'Bohamiann': 'BOHAMIANN',
    'BOHB': 'BOHB',
    'CMA-ES': 'CMA-ES',
    'Fabolas': 'FABOLAS',
    'GPBO': 'GPBO',
    'Hyperband': 'HB',
    'RandomSearch': 'Random Search',
    'SMAC': 'SMAC',
    'TPE': 'TPE',
    'Default HPs': 'Default HPs'
}

file_path = './hpo_framework/results/%s/RankingAnalysis/%s_ranked_metrics.csv' % (
    dataset, dataset)

ranked_df = pd.read_csv(file_path, index_col=0)
hpo_techs = ['RandomSearch', 'GPBO', 'SMAC', 'TPE', 'CMA-ES',
             'Hyperband', 'BOHB', 'Fabolas', 'Bohamiann']

dv_per_setup_df = pd.DataFrame([])

idx = 0

for i in range(len(setup_variants)):

    this_setup = setup_variants[i]

    setup_df = ranked_df.loc[(ranked_df['Workers'] == this_setup[0]) &
                             (ranked_df['Warm start'] == this_setup[1]) &
                             (ranked_df['1st metric'] == ap_analysis_type[0]), :].copy(deep=True)

    for this_tech in hpo_techs:

        dv_arr = setup_df.loc[(setup_df['1st metric HPO-technique'] == this_tech),
                              '1st metric scaled deviation']

        dv_arr[dv_arr == np.inf] = 1.0

        dv_arr = dv_arr.to_numpy()

        this_distance_value = np.nanmean(dv_arr)

        dv_per_setup_df.loc[idx, 'HPO technique'] = hpo_map_dict[this_tech]
        dv_per_setup_df.loc[idx,
                            'Average Distance Value'] = this_distance_value
        dv_per_setup_df.loc[idx, 'Benchmarking Setup'] = setup_labels[i]

        idx += 1

sns.set_theme(font='Arial', style='ticks')

cat = sns.catplot(data=dv_per_setup_df, x='HPO technique', y='Average Distance Value',
                  hue='Benchmarking Setup', kind='bar', legend=False,
                  palette=sns.color_palette(['#176290', '#79B4CF', '#dddddd']))

cat.fig.set_size_inches(6.5, 4)
cat.set(xlabel=None)

plt.tick_params(axis='both', labelsize=11)
plt.tick_params(axis='x', rotation=90)
plt.legend(loc='upper right')

fig_name = './hpo_framework/results/%s/RankingAnalysis/AP_dv_per_setup_%s_%s.svg' % (
    dataset, ap_analysis_type[1], dataset)
cat.fig.savefig(fig_name, bbox_inches='tight')
