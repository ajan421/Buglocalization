"""
Check Parquet File Structure
Shows what columns are available for ground truth validation
"""

import pandas as pd

# Load the parquet file
print("Loading parquet file...")
df = pd.read_parquet('0000.parquet')

print("\n" + "="*80)
print("PARQUET FILE STRUCTURE")
print("="*80)

# Show all columns
print(f"\nTotal Rows: {len(df)}")
print(f"\nColumns ({len(df.columns)}):")
for i, col in enumerate(df.columns, 1):
    print(f"  {i}. {col}")

# Check for ground truth columns
print("\n" + "-"*80)
print("GROUND TRUTH COLUMNS:")
print("-"*80)

ground_truth_keywords = ['updated', 'changed', 'modified', 'fix', 'commit', 'sha', 'files']
ground_truth_cols = [col for col in df.columns if any(keyword in col.lower() for keyword in ground_truth_keywords)]

if ground_truth_cols:
    print("[OK] Found potential ground truth columns:")
    for col in ground_truth_cols:
        print(f"  - {col}")
        # Show sample
        sample = df[df[col].notna()].head(1)
        if not sample.empty:
            print(f"    Sample: {sample[col].iloc[0]}")
else:
    print("[WARNING] No obvious ground truth columns found")

# Check for bug report columns
print("\n" + "-"*80)
print("BUG REPORT COLUMNS:")
print("-"*80)

bug_keywords = ['title', 'body', 'description', 'summary', 'issue', 'bug']
bug_cols = [col for col in df.columns if any(keyword in col.lower() for keyword in bug_keywords)]

if bug_cols:
    print("[OK] Found bug report columns:")
    for col in bug_cols:
        print(f"  - {col}")
else:
    print("[WARNING] No obvious bug report columns found")

# Show first complete row as sample
print("\n" + "-"*80)
print("SAMPLE ROW (First Bug):")
print("-"*80)
if len(df) > 0:
    sample_row = df.iloc[0]
    for key, value in sample_row.items():
        if pd.notna(value):
            value_str = str(value)
            if len(value_str) > 100:
                value_str = value_str[:100] + "..."
            print(f"{key}: {value_str}")

print("\n" + "="*80)
print("[COMPLETE] Parquet file structure analysis complete!")
print("="*80)

