"""
Analyze the relationship between parquet files and MHTML files
"""

import os
import pandas as pd
from collections import defaultdict

# Load parquet files grouped by type
parquet_dir = "mm_mind2web/data"
parquet_files = [f for f in os.listdir(parquet_dir) if f.endswith('.parquet')]

# Group parquet files by type
parquet_groups = {
    'test_domain': [],
    'test_task': [],
    'test_website': [],
    'train': []
}

for parquet_file in parquet_files:
    if parquet_file.startswith('test_domain'):
        parquet_groups['test_domain'].append(parquet_file)
    elif parquet_file.startswith('test_task'):
        parquet_groups['test_task'].append(parquet_file)
    elif parquet_file.startswith('test_website'):
        parquet_groups['test_website'].append(parquet_file)
    elif parquet_file.startswith('train'):
        parquet_groups['train'].append(parquet_file)

# Load each group into a dataframe (only load action_uid and annotation_id columns)
print("Loading parquet files (action_uid and annotation_id only)...")
dataframes = {}
for group_name, files in parquet_groups.items():
    if not files:
        continue
    
    print(f"  Loading {group_name} ({len(files)} files)...")
    df_list = []
    for parquet_file in files:
        df_temp = pd.read_parquet(os.path.join(parquet_dir, parquet_file), columns=['action_uid', 'annotation_id'])
        df_list.append(df_temp)
    
    df_combined = pd.concat(df_list, ignore_index=True)
    dataframes[group_name] = df_combined
    print(f"    {group_name}: {len(df_combined)} rows, {df_combined['action_uid'].nunique()} unique action_uids, {df_combined['annotation_id'].nunique()} unique tasks")

# Get all task folders
task_dir = "mm_mind2web/task"
task_folders = [f for f in os.listdir(task_dir) if os.path.isdir(os.path.join(task_dir, f))]

print(f"\nAnalyzing {len(task_folders)} task folders...\n")

# Analyze each task
task_analysis = []

for task_uid in sorted(task_folders):
    snapshots_dir = os.path.join(task_dir, task_uid, "processed", "snapshots")
    
    if not os.path.exists(snapshots_dir):
        continue
    
    # Extract action_uids from MHTML filenames
    mhtml_files = [f for f in os.listdir(snapshots_dir) if f.endswith('_before.mhtml')]
    mhtml_action_uids = set()
    for filename in mhtml_files:
        action_uid = filename.replace('_before.mhtml', '')
        mhtml_action_uids.add(action_uid)
    
    if not mhtml_action_uids:
        continue
    
    # Check which parquet groups have data for this task
    task_info = {
        'task_uid': task_uid,
        'mhtml_count': len(mhtml_action_uids),
        'parquet_groups': []
    }
    
    all_parquet_action_uids = set()
    parquet_groups_with_task = []
    
    for df_name, df in dataframes.items():
        df_task = df[df['annotation_id'] == task_uid]
        if len(df_task) > 0:
            df_action_uids = set(df_task['action_uid'].unique())
            all_parquet_action_uids.update(df_action_uids)
            parquet_groups_with_task.append(df_name)
            
            matches = mhtml_action_uids & df_action_uids
            task_info['parquet_groups'].append({
                'group': df_name,
                'count': len(df_action_uids),
                'matches': len(matches),
                'match_rate': len(matches) / len(mhtml_action_uids) * 100 if mhtml_action_uids else 0
            })
    
    # Check overlap between MHTML and all parquet data
    all_matches = mhtml_action_uids & all_parquet_action_uids
    task_info['total_parquet_count'] = len(all_parquet_action_uids)
    task_info['total_matches'] = len(all_matches)
    task_info['overall_match_rate'] = len(all_matches) / len(mhtml_action_uids) * 100 if mhtml_action_uids else 0
    task_info['parquet_groups_list'] = ', '.join(parquet_groups_with_task) if parquet_groups_with_task else 'none'
    
    task_analysis.append(task_info)

# Summary analysis
print("="*80)
print("KEY FINDINGS")
print("="*80)

# 1. Tasks with parquet data
tasks_with_parquet = [t for t in task_analysis if t['total_parquet_count'] > 0]
tasks_without_parquet = [t for t in task_analysis if t['total_parquet_count'] == 0]

print(f"\n1. Tasks with parquet data: {len(tasks_with_parquet)}/{len(task_analysis)}")
print(f"   Tasks without parquet data: {len(tasks_without_parquet)}/{len(task_analysis)}")

# 2. Overlap between parquet groups
print(f"\n2. Checking overlap between parquet groups...")
all_action_uids_by_group = {}
for df_name, df in dataframes.items():
    all_action_uids_by_group[df_name] = set(df['action_uid'].unique())

print(f"   Unique action_uids per group:")
for group, uids in all_action_uids_by_group.items():
    print(f"     {group:15}: {len(uids):,} unique action_uids")

# Check overlaps
print(f"\n   Overlaps between groups:")
groups_list = list(all_action_uids_by_group.keys())
for i, group1 in enumerate(groups_list):
    for group2 in groups_list[i+1:]:
        overlap = all_action_uids_by_group[group1] & all_action_uids_by_group[group2]
        if overlap:
            print(f"     {group1:15} & {group2:15}: {len(overlap):,} overlapping action_uids")

# 3. Tasks that appear in multiple parquet groups
print(f"\n3. Tasks appearing in multiple parquet groups:")
task_to_groups = defaultdict(set)
for df_name, df in dataframes.items():
    for task_id in df['annotation_id'].unique():
        task_to_groups[task_id].add(df_name)

multi_group_tasks = {task: groups for task, groups in task_to_groups.items() if len(groups) > 1}
print(f"   Tasks in multiple groups: {len(multi_group_tasks)}")
if multi_group_tasks:
    for task, groups in list(multi_group_tasks.items())[:10]:
        print(f"     {task}: {', '.join(sorted(groups))}")
    if len(multi_group_tasks) > 10:
        print(f"     ... and {len(multi_group_tasks) - 10} more")

# 4. Match rate distribution
print(f"\n4. Match rate distribution:")
match_rates = [t['overall_match_rate'] for t in tasks_with_parquet]
if match_rates:
    print(f"   Mean match rate: {sum(match_rates) / len(match_rates):.1f}%")
    print(f"   Min match rate: {min(match_rates):.1f}%")
    print(f"   Max match rate: {max(match_rates):.1f}%")
    
    perfect_matches = [t for t in tasks_with_parquet if t['overall_match_rate'] == 100.0]
    partial_matches = [t for t in tasks_with_parquet if 0 < t['overall_match_rate'] < 100.0]
    no_matches = [t for t in tasks_with_parquet if t['overall_match_rate'] == 0.0]
    
    print(f"   Perfect matches (100%): {len(perfect_matches)} tasks")
    print(f"   Partial matches (1-99%): {len(partial_matches)} tasks")
    print(f"   No matches (0%): {len(no_matches)} tasks")

# 5. Sample tasks with low match rates
print(f"\n5. Sample tasks with low match rates (<50%):")
low_match_tasks = [t for t in tasks_with_parquet if t['overall_match_rate'] < 50.0]
for task in sorted(low_match_tasks, key=lambda x: x['overall_match_rate'])[:5]:
    print(f"   {task['task_uid']}: {task['overall_match_rate']:.1f}% match ({task['total_matches']}/{task['mhtml_count']} MHTML files)")
    print(f"      Parquet groups: {task['parquet_groups_list']}")
    for pg in task['parquet_groups']:
        print(f"        {pg['group']:15}: {pg['matches']}/{task['mhtml_count']} matches ({pg['match_rate']:.1f}%)")

# 6. Check if MHTML action_uids are completely different from parquet
print(f"\n6. Are MHTML files from different trajectories?")
all_parquet_uids = set()
for uids in all_action_uids_by_group.values():
    all_parquet_uids.update(uids)

all_mhtml_uids = set()
for task in task_analysis:
    snapshots_dir = os.path.join(task_dir, task['task_uid'], "processed", "snapshots")
    if os.path.exists(snapshots_dir):
        mhtml_files = [f for f in os.listdir(snapshots_dir) if f.endswith('_before.mhtml')]
        for filename in mhtml_files:
            action_uid = filename.replace('_before.mhtml', '')
            all_mhtml_uids.add(action_uid)

overlap_all = all_mhtml_uids & all_parquet_uids
print(f"   Total unique MHTML action_uids: {len(all_mhtml_uids):,}")
print(f"   Total unique parquet action_uids: {len(all_parquet_uids):,}")
print(f"   Overlap: {len(overlap_all):,} ({len(overlap_all)/len(all_mhtml_uids)*100:.1f}% of MHTML)")
print(f"   MHTML-only: {len(all_mhtml_uids - all_parquet_uids):,}")
print(f"   Parquet-only: {len(all_parquet_uids - all_mhtml_uids):,}")

# Save detailed results
results_df = pd.DataFrame([
    {
        'task_uid': t['task_uid'],
        'mhtml_count': t['mhtml_count'],
        'total_parquet_count': t['total_parquet_count'],
        'total_matches': t['total_matches'],
        'overall_match_rate': t['overall_match_rate'],
        'parquet_groups': t['parquet_groups_list'],
        **{f"{pg['group']}_matches": pg['matches'] for pg in t['parquet_groups']},
        **{f"{pg['group']}_match_rate": pg['match_rate'] for pg in t['parquet_groups']}
    }
    for t in task_analysis
])

output_file = "parquet_mhtml_relationship_analysis.csv"
results_df.to_csv(output_file, index=False)
print(f"\n✅ Detailed results saved to {output_file}")

