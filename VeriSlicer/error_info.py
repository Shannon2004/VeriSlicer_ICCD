import os
import re

BASE_DIR = "Error_designs"
ERROR_FILE = "/home/chirag/VeriSlicer/VeriSlicer_v5/error_lines.txt"

# Map design → list of errors
design_errors = {}

current_design = None

with open(ERROR_FILE, "r") as f:
    for line in f:
        line = line.strip()

        # Detect design
        match = re.match(r"design_(\d+):", line)
        if match:
            current_design = int(match.group(1))
            design_errors[current_design] = []
            continue

        # Detect error line
        match = re.match(r"\d+\.\s*Line\s*(\d+):\s*\((.*?)\)\s*TO\s*\((.*?)\)", line)
        if match and current_design is not None:
            line_no = match.group(1)
            original = match.group(2)
            modified = match.group(3)

            design_errors[current_design].append({
                "line": line_no,
                "original": original,
                "modified": modified
            })

# -------- Generate error_info.txt --------
for design, errors in design_errors.items():
    for idx, err in enumerate(errors, start=1):
        folder_name = f"error_design_{design}_{idx}"
        folder_path = os.path.join(BASE_DIR, folder_name)

        os.makedirs(folder_path, exist_ok=True)

        file_path = os.path.join(folder_path, "error_info.txt")

        with open(file_path, "w") as f:
            f.write(f"Design: Design {design}\n")
            f.write(f"Error line: {err['line']}\n\n")

            f.write("Original code:\n")
            f.write(f"{err['original']}\n\n")

            f.write("Erroneous code:\n")
            f.write(f"{err['modified']}\n\n")

            f.write("Error description:\n")

            # Basic heuristic for description
            if "&" in err['modified'] and "|" in err['original']:
                f.write("Logical operator replaced with Logical AND\n")
            elif "+" in err['modified'] and "-" in err['original']:
                f.write("Arithmetic operator changed from subtraction to addition\n")
            elif "^" in err['modified']:
                f.write("Logical XOR introduced\n")
            else:
                f.write("Logic modified\n")

print("All error_info.txt files generated successfully!")
