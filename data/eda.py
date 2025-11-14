import pandas as pd

df = pd.read_csv("data/run_20251112_004959_test_domain_original_reviews.csv")

# print number of rows with both target_correct and nearest_correct equal to True
print(len(df[(df['target_correct'] == True) & (df['nearest_correct'] == True)]))

# print number of rows with target_correct equal to True and nearest_correct equal to False
print(len(df[(df['target_correct'] == True) & (df['nearest_correct'] == False)]))
