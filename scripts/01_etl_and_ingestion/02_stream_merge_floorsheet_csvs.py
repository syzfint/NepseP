import os
import glob

base_dir = r"c:\Users\achar\Downloads\neps\archive (3)\NEPSE_data"
output_file = r"c:\Users\achar\Downloads\neps\archive (3)\NEPSE_all_data.csv"

all_files = glob.glob(os.path.join(base_dir, "**", "*.csv"), recursive=True)

header_written = False

with open(output_file, 'w', encoding='utf-8') as outfile:
    for file in all_files:
        try:
            with open(file, 'r', encoding='utf-8') as infile:
                header = infile.readline()
                if not header:
                    continue
                
                if not header_written:
                    outfile.write(header)
                    header_written = True
                
                for line in infile:
                    outfile.write(line)
        except Exception as e:
            print(f"Error reading {file}: {e}")

print(f"Successfully combined {len(all_files)} files into {output_file}")
