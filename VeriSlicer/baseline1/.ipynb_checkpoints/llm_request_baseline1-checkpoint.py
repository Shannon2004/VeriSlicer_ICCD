import os
import json

def read_file_safely(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return f.read().strip()
    return f"[Missing file: {filepath}]"

def read_verilog_with_lines(filepath):
    """Reads a file and injects line numbers so the LLM can cite them accurately."""
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            lines = f.readlines()
        # Prepend line numbers to exactly match how the ground truth is graded
        numbered_lines = [f"{i+1:4d}: {line.rstrip()}" for i, line in enumerate(lines)]
        return "\n".join(numbered_lines)
    return f"[Missing file: {filepath}]"

def build_and_save_prompt_baseline1(design_name, error_dir):
    error_designs_dir = "../Error_designs"
    
    timestamp_path = os.path.join(error_designs_dir, error_dir, "error_timestamp.txt")
    
    # NOTE: Double check this path! Is the buggy file actually named design_X.v?
    raw_code_path = os.path.join(error_designs_dir, error_dir, f"{design_name}.v")
    
    error_timestamp = read_file_safely(timestamp_path)
    
    # USE THE NEW FUNCTION HERE
    raw_code = read_verilog_with_lines(raw_code_path)
    
    system_prompt = """You are an expert VLSI Verification Engineer. Your task is to perform Fault Localization and RTL Repair. Analyze the provided Raw Verilog code and Error Symptom.
    METHODOLOGY (follow these steps IN ORDER):
1. Read the ERROR SYMPTOM to learn WHICH signal failed, and the EXPECTED vs ACTUAL values.
2. Guess the NUMERICAL ANALYSIS to understand the mathematical relationship between expected and actual.
3. Search the Sliced Verilog Code for the line that COMPUTES the failing signal.
4. Make sure to give a valid line number ALWAYS, and do not return None.
You must output a JSON object with exactly three keys:
1. "buggy_line": The exact integer line number from the Raw Verilog where the defect exists.
2. "root_cause": A sentence explanation of why the logic failed at the failing timestamp.
3. "fixed_code": The corrected single line of Verilog code."""

    user_prompt = f"""### [Raw Verilog Code]
{raw_code}
### [Error Symptom]
{error_timestamp}
"""

    prompt_data = {
        "error_id": error_dir,
        "design_name": design_name,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt
    }
    
    out_dir = os.path.join("llm_prompts_baseline1", design_name)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{error_dir}_prompt.json")
    
    with open(out_path, 'w') as f:
        json.dump(prompt_data, f, indent=4)
        
    return prompt_data

if __name__ == "__main__":
    build_and_save_prompt_baseline1("design_5", "error_design_5_3")
