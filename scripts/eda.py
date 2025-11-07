"""
EDA Script - Analyze match rates between parquet files and MHTML files
"""

import os
import pandas as pd


# Load parquet files grouped by type
parquet_dir = "mm_mind2web/data"
parquet_files = [f for f in os.listdir(parquet_dir) if f.endswith('.parquet')]

print(f"Found {len(parquet_files)} parquet files")

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

print(f"\nParquet file groups:")
for group_name, files in parquet_groups.items():
    print(f"  {group_name}: {len(files)} files")

# Load each group into a dataframe
dataframes = {}
for group_name, files in parquet_groups.items():
    if not files:
        print(f"\n⚠️  No files for {group_name}, skipping...")
        continue
    
    print(f"\n📦 Loading {group_name} parquet files...")
    df_list = []
    for parquet_file in files:
        print(f"   Loading {parquet_file}...")
        df_temp = pd.read_parquet(os.path.join(parquet_dir, parquet_file))
        df_list.append(df_temp)
    
    df_combined = pd.concat(df_list, ignore_index=True)
    dataframes[group_name] = df_combined
    print(f"✅ {group_name}: {len(df_combined)} rows, {df_combined['action_uid'].nunique()} unique action_uids")

# Get all task folders
task_dir = "mm_mind2web/task"
task_folders = [f for f in os.listdir(task_dir) if os.path.isdir(os.path.join(task_dir, f))]

print(f"\n{'='*80}")
print(f"Found {len(task_folders)} task folders")
print(f"{'='*80}\n")

# Analyze match rates for each task folder
results = []

for task_uid in sorted(task_folders):
    snapshots_dir = os.path.join(task_dir, task_uid, "processed", "snapshots")
    
    if not os.path.exists(snapshots_dir):
        print(f"⚠️  {task_uid}: snapshots directory not found, skipping...")
        continue
    
    # Extract action_uids from MHTML filenames
    mhtml_files = [f for f in os.listdir(snapshots_dir) if f.endswith('_before.mhtml')]
    mhtml_action_uids = set()
    for filename in mhtml_files:
        action_uid = filename.replace('_before.mhtml', '')
        mhtml_action_uids.add(action_uid)
    
    if not mhtml_action_uids:
        print(f"⚠️  {task_uid}: No MHTML files found, skipping...")
        continue
    
    print(f"\n📁 Task: {task_uid}")
    print(f"   MHTML files: {len(mhtml_action_uids)} action_uids")
    
    # Check match rate for each dataframe
    task_results = {'task_uid': task_uid, 'mhtml_count': len(mhtml_action_uids)}
    
    for df_name, df in dataframes.items():
        # Get action_uids in this dataframe for this task_uid
        df_task = df[df['annotation_id'] == task_uid]
        df_action_uids = set(df_task['action_uid'].unique())
        
        # Calculate matches
        matches = mhtml_action_uids & df_action_uids
        match_count = len(matches)
        match_rate = (match_count / len(mhtml_action_uids) * 100) if mhtml_action_uids else 0
        
        # Also check how many df action_uids are in mhtml
        df_in_mhtml = df_action_uids & mhtml_action_uids
        df_match_rate = (len(df_in_mhtml) / len(df_action_uids) * 100) if df_action_uids else 0
        
        task_results[f'{df_name}_matches'] = match_count
        task_results[f'{df_name}_match_rate'] = match_rate
        task_results[f'{df_name}_df_count'] = len(df_action_uids)
        task_results[f'{df_name}_df_match_rate'] = df_match_rate
        
        print(f"   {df_name:15} | MHTML matches: {match_count:3}/{len(mhtml_action_uids):3} ({match_rate:5.1f}%) | "
              f"DF has: {len(df_action_uids):3} action_uids, {len(df_in_mhtml):3} in MHTML ({df_match_rate:5.1f}%)")
    
    results.append(task_results)

# Summary statistics
print(f"\n{'='*80}")
print(f"SUMMARY STATISTICS")
print(f"{'='*80}\n")

for df_name in dataframes.keys():
    print(f"\n{df_name.upper()}:")
    print(f"{'-'*80}")
    
    total_mhtml = sum(r['mhtml_count'] for r in results)
    total_matches = sum(r.get(f'{df_name}_matches', 0) for r in results)
    total_df_count = sum(r.get(f'{df_name}_df_count', 0) for r in results)
    total_df_matches = sum(r.get(f'{df_name}_df_count', 0) - (r.get(f'{df_name}_df_count', 0) - r.get(f'{df_name}_matches', 0)) for r in results)
    
    overall_match_rate = (total_matches / total_mhtml * 100) if total_mhtml > 0 else 0
    overall_df_match_rate = (total_matches / total_df_count * 100) if total_df_count > 0 else 0
    
    print(f"  Total MHTML action_uids across all tasks: {total_mhtml}")
    print(f"  Total matches: {total_matches}")
    print(f"  Overall match rate (matches/MHTML): {overall_match_rate:.1f}%")
    print(f"  Total action_uids in DF for these tasks: {total_df_count}")
    print(f"  Overall DF match rate (matches/DF): {overall_df_match_rate:.1f}%")
    
    # Tasks with best/worst match rates
    tasks_with_data = [r for r in results if r.get(f'{df_name}_df_count', 0) > 0]
    if tasks_with_data:
        best_task = max(tasks_with_data, key=lambda x: x.get(f'{df_name}_match_rate', 0))
        worst_task = min(tasks_with_data, key=lambda x: x.get(f'{df_name}_match_rate', 0))
        print(f"  Best match rate: {best_task['task_uid']} ({best_task.get(f'{df_name}_match_rate', 0):.1f}%)")
        print(f"  Worst match rate: {worst_task['task_uid']} ({worst_task.get(f'{df_name}_match_rate', 0):.1f}%)")

# Create a summary dataframe
summary_df = pd.DataFrame(results)
print(f"\n{'='*80}")
print(f"DETAILED RESULTS (first 10 tasks)")
print(f"{'='*80}\n")
print(summary_df.head(10).to_string(index=False))

# Save results
output_file = "parquet_mhtml_match_analysis.csv"
summary_df.to_csv(output_file, index=False)
print(f"\n✅ Results saved to {output_file}")



# print(df.info())
# print(df.head(1)['action_uid'])
# print(df.head(1)['confirmed_task'])
# print(df.head(1)['annotation_id'])
# print(df['screenshot'].isnull().sum())

# print(df[df['action_uid']=='8121d266-e16a-4265-ac02-a2e6fd7fca16'].head())

# print(df[df['annotation_id']=='277e3468-f8cb-45c6-9e4b-0328066c42d3']['action_uid'].tolist())

# image_size_set = set()
# for i in range(len(df)):
#     try:
#         image = PIL.Image.open(io.BytesIO(df['screenshot'][i]['bytes']))
#         # image.show()
#         image_size_set.add(image.size)
#         # print(df['target_action_reprs'][i])
#     except Exception as e:
#         print(f"Error opening image {i}: {e}")
#         continue

# print(image_size_set)
# min_width = float('inf')
# min_height = float('inf')
# max_width = 0
# max_height = 0
# height_set = set()
# width_set = set()
# for size in image_size_set:
#     min_width = min(min_width, size[0])
#     min_height = min(min_height, size[1])
#     max_width = max(max_width, size[0])
#     max_height = max(max_height, size[1])
#     height_set.add(size[1])
#     width_set.add(size[0])

# print(f"Min width: {min_width}, Min height: {min_height}, Max width: {max_width}, Max height: {max_height}")
# print(f"Height set: {height_set}, Width set: {width_set}")

# # round height set to the nearest 1000
# height_set = set(round(height, -3) for height in height_set)
# print(f"Height set: {height_set}")
# # round width set to the nearest 10
# width_set = set(round(width, -1) for width in width_set)
# print(f"Width set: {width_set}")
