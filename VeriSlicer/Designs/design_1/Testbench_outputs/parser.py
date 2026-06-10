#this parser is used to compare Verilog TB(only_tb.txt) and Python TB(tb_with_cocotb.txt) outputs
import re

def parse_cordic_log(file_path):
    # Regex pattern to find the Angle, sin, and cos values
    # It looks for the word "Angle:", grabs the digits, then does the same for sin and cos
    pattern = re.compile(r"Angle:\s+(\d+)\s+sin\s*=\s*([-0-9.]+)\s+cos\s*=\s*([-0-9.]+)")
    
    try:
        with open(file_path, 'r') as file:
            for line in file:
                match = pattern.search(line)
                if match:
                    angle = match.group(1)
                    sin_val = match.group(2)
                    cos_val = match.group(3)
                    
                    # Formats the output to match your requested spacing
                    print(f"Angle: {int(angle):11}  sin = {sin_val}  cos = {cos_val}")
                    
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")

if __name__ == "__main__":
    # Make sure 'tb_with_cocotb.txt' is in the same directory as this script
    parse_cordic_log("tb_with_cocotb.txt")
