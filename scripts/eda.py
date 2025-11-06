import pandas as pd
import io
import PIL.Image 


# df = pd.read_parquet("test_domain-00000-of-00011-26c55c12cbbcdc8e.parquet")
df = pd.read_parquet("mm_mind2web/data/test_domain-00002-of-00011-f4d93275c87bbd81.parquet")

print(df.info())
print(df.head(1)['action_uid'])
print(df.head(1)['confirmed_task'])
print(df.head(1)['annotation_id'])
print(df['screenshot'].isnull().sum())

# print(df[df['action_uid']=='8121d266-e16a-4265-ac02-a2e6fd7fca16'].head())

# print(df[df['annotation_id']=='277e3468-f8cb-45c6-9e4b-0328066c42d3']['action_uid'].tolist())

image_size_set = set()
for i in range(len(df)):
    try:
        image = PIL.Image.open(io.BytesIO(df['screenshot'][i]['bytes']))
        # image.show()
        image_size_set.add(image.size)
        # print(df['target_action_reprs'][i])
    except Exception as e:
        print(f"Error opening image {i}: {e}")
        continue

print(image_size_set)
min_width = float('inf')
min_height = float('inf')
max_width = 0
max_height = 0
height_set = set()
width_set = set()
for size in image_size_set:
    min_width = min(min_width, size[0])
    min_height = min(min_height, size[1])
    max_width = max(max_width, size[0])
    max_height = max(max_height, size[1])
    height_set.add(size[1])
    width_set.add(size[0])

print(f"Min width: {min_width}, Min height: {min_height}, Max width: {max_width}, Max height: {max_height}")
print(f"Height set: {height_set}, Width set: {width_set}")

# round height set to the nearest 1000
height_set = set(round(height, -3) for height in height_set)
print(f"Height set: {height_set}")
# round width set to the nearest 10
width_set = set(round(width, -1) for width in width_set)
print(f"Width set: {width_set}")
