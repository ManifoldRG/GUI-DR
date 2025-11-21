import pandas as pd
import ast

df = pd.read_csv('data/variant_data 2.csv')

# 1. check if any empties in image_path, step_instruction, multi_element_instruction, target_bounding_box columns
print('Number of empties in image_path, step_instruction, multi_element_instruction, target_bounding_box columns:')
print(df[['image_path', 'step_instruction', 'multi_element_instruction', 'target_bounding_box']].isna().sum())

# show all the rows with empty multi_element_instruction and target_bounding_box columns, no wrapping in terminal
print('Rows with empty multi_element_instruction and target_bounding_box:')
print(df[df['multi_element_instruction'].isna() | df['target_bounding_box'].isna()]['task_id'].unique().tolist())


# # 3. if target_coordinates is empty for the row, then calculate it from target_bounding_box
# # first check how many rows have empty target_coordinates
print(df[['target_coordinates']].isna().sum())
df['target_coordinates'] = df['target_bounding_box'].apply(lambda x: (lambda bbox: (round(bbox[0] + bbox[2] / 2), round(bbox[1] + bbox[3] / 2)))(ast.literal_eval(x) if isinstance(x, str) else x))

print('Number of empties in target_coordinates column:')
print(df[['target_coordinates']].isna().sum())

# 4. remove prefix before run_xxxxx_test_xxxx/ in the image filepath like /Users/lockewang/FIG/WebDomainRandomizer/final_data/ or with final_data_filtered/ from the 'image_path' column
import re

def clean_image_path(row):
    image_path = row['image_path']
    step_index = str(row['step_index'])
    step_instruction = str(row['step_instruction']) if pd.notna(row['step_instruction']) else "unknown"
    if pd.isna(image_path) or '/run_' not in image_path:
        return image_path
    # Extract the /run_...{runfolder}/ part, up to and including /visualizations/
    match = re.search(r'/run_([^/]+)/[^/]*visualizations/', image_path)
    if match:
        run_folder = match.group(1)  # e.g. 20251112_005125_test_website_original/7eefb724-4b06-4d7b-a7d3-7a78f3413b6d/
        # Strip any trailing slashes:
        run_folder = run_folder.rstrip("/")
        action_type = step_instruction.split(" ")[0].lower() if step_instruction else "unknown"
        new_path = f'run_{run_folder}step_{step_index}_{action_type}.png'
        return new_path
    # fallback, try more general split
    if '/run_' in image_path:
        # find everything after "/run_"
        after_run = image_path.split('/run_', 1)[1]
        # Remove any "visualizations/" or "screenshots/" part and after
        after_run_base = re.split(r'(visualizations/|screenshots/)', after_run)[0]
        run_folder = after_run_base.rstrip("/")
        action_type = step_instruction.split(" ")[0].lower() if step_instruction else "unknown"
        new_path = f'run_{run_folder}/screenshots/step_{step_index}_{action_type}.png'
        return new_path
    return image_path

df['image_path'] = df.apply(clean_image_path, axis=1)
print(df['image_path'])

df.to_csv('data/variant_data_cleaned.csv', index=False)

