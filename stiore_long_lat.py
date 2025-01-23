import pandas as pd

# Load the CSV files
main_csv_path = "address_mapped.csv"  # Path to the first CSV file
lat_long_csv_path = "address_mapped_with_lat_long.csv"  # Path to the second CSV file

# Read the files into dataframes
main_df = pd.read_csv(main_csv_path)
lat_long_df = pd.read_csv(lat_long_csv_path)

# Merge the two dataframes on the 'zip' column
merged_df = pd.merge(main_df, lat_long_df, on="zip", how="left")

# Save the updated dataframe back to a new CSV file
output_csv_path = "updated_main_file.csv"
merged_df.to_csv(output_csv_path, index=False)

print(f"Updated CSV file saved as {output_csv_path}")
