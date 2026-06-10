import os
import json
from vcd_summarizer import summarize_vcd


def read_file_safely(filepath):
    """Utility to read a file and return a warning string if missing."""
    if filepath and os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read().strip()
    return ""

# added last 3 lines in critical rules and point 5 in methodology
def build_and_save_prompt(design_name, error_dir):
    """Constructs the LLM prompt from the extracted pipeline data.
    
    Combines four data sources into an optimized prompt:
      1. Sliced Verilog code (FIRST — lets decoder cache the code)
      2. Error symptom (failing signal + expected vs actual)
      3. Numerical failure analysis (pre-computed hints)
      4. Module description (behavioral spec)
    
    Uses Chain-of-Thought anchoring: the model must output
    'buggy_code_snippet' BEFORE 'buggy_lines' to force it to
    mentally locate the code before guessing line numbers.
    """
    
    # ---- Paths ----
    error_designs_dir = "../Error_designs"
    designs_dir = "../Designs"
    
    timestamp_path = os.path.join(error_designs_dir, error_dir, "error_timestamp.txt")
    sliced_code_path = os.path.join("sliced_code", design_name, error_dir, "sliced_code.txt")
    trimmed_vcd_path = os.path.join("trimmed_vcds", design_name, f"{error_dir}_trimmed_trace.txt")
    description_path = os.path.join(designs_dir, design_name, "description.txt")
    
    # ---- Read data ----
    error_timestamp = read_file_safely(timestamp_path)
    sliced_code = read_file_safely(sliced_code_path)
    description = read_file_safely(description_path)
    
    # Get compact failure analysis (NOT raw VCD — pre-computed hints)
    compact_vcd = summarize_vcd(
        trimmed_vcd_path, 
        error_timestamp_path=timestamp_path,
        max_cycles=3, 
        char_budget=3000
    )
    
    # ──────────────────────────────────────────────────────────────────────
    # SYSTEM PROMPT — optimized for Qwen 2.5 Coder 14B
    # ──────────────────────────────────────────────────────────────────────
    system_prompt = """You are an expert Verilog RTL debugger. A hardware design has a bug on EXACTLY ONE line. Your job is to find that line.

METHODOLOGY (follow these steps IN ORDER):
1. Read the ERROR SYMPTOM to learn WHICH signal failed, and the EXPECTED vs ACTUAL values.
2. Read the NUMERICAL ANALYSIS to understand the mathematical relationship between expected and actual.
3. Search the Sliced Verilog Code for the line that COMPUTES the failing signal.
4. Trace BACKWARD: find what assignments, always blocks, or sub-modules drive that signal.
5. Before declaring a bug, verify that the suspected line produces a DIFFERENT truth table or arithmetic result than expected.
CRITICAL RULES:
- Line numbers come from the LEFT EDGE of the Sliced Verilog Code (e.g. "  41: assign AND_Output = ..." means line 41).
- You MUST copy the exact buggy code snippet from the sliced code BEFORE reporting the line number.
- The "buggy_lines" array MUST contain exactly 5 integers from the sliced code, ranked most-likely first.
- DO NOT flag stylistic differences as bugs.
- If two implementations are logically equivalent (e.g., if/else vs ternary operator, different ordering of conditions, use of temporary wires), they are NOT bugs.
- Only report a bug if the LOGIC FUNCTION changes (i.e., output differs for some input).

OUTPUT FORMAT: Return ONLY this JSON:
{
  "step1_failing_signal": "Name of the signal that failed and the expected vs actual values",
  "step2_analysis": "What numerical relationship exists between expected and actual",
  "step3_trace": "Which code computes this signal? Trace backward through the modules.",
  "buggy_code_snippet": "Copy the EXACT suspicious line from the sliced code, including its line number prefix",
  "buggy_lines": [most_likely, 2nd, 3rd, 4th, 5th],
  "root_cause": "One sentence: what operator/signal/constant is wrong and what should it be",
  "fixed_code": "The corrected single line of Verilog"
}"""

    # ──────────────────────────────────────────────────────────────────────
    # USER PROMPT — code FIRST, then symptom (Qwen benefits from this order)
    # ──────────────────────────────────────────────────────────────────────
    sections = []

    # Section 1: Module Description (behavioral spec)
    if description:
        sections.append(f"## Module Description\n{description}")
    
    # Section 2: Sliced Verilog Code FIRST — let the decoder cache it
    sections.append(
        f"## Sliced Verilog Code\n"
        f"Each line starts with its ORIGINAL LINE NUMBER followed by a colon. "
        f"You MUST use these exact numbers in \"buggy_lines\".\n\n"
        f"{sliced_code}"
    )
    
    # Section 3: Error Symptom
    sections.append(f"## Error Symptom\n{error_timestamp}")
    
    # Section 4: Failure Analysis (pre-computed numerical hints)
    if compact_vcd:
        sections.append(f"## Failure Analysis\n{compact_vcd}")
    
    
    
    # Final instruction
    sections.append(
        "TASK: Find the ONE buggy line. Copy its exact code snippet, "
        "then return its line number from the Sliced Verilog Code. "
        "Return ONLY the JSON object."
    )
    
    user_prompt = "\n\n".join(sections)

    # ---- Package and save ----
    prompt_data = {
        "error_id": error_dir,
        "design_name": design_name,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt
    }
    
    out_dir = os.path.join("llm_prompts", design_name)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{error_dir}_prompt.json")
    
    with open(out_path, 'w') as f:
        json.dump(prompt_data, f, indent=4)
    
    total_chars = len(system_prompt) + len(user_prompt)
    print(f"Saved LLM prompt to: {out_path} ({total_chars} chars total)")
    return prompt_data


if __name__ == "__main__":
    build_and_save_prompt("design_1", "error_design_1_1")