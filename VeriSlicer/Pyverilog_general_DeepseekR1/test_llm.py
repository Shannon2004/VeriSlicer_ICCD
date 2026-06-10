import json
import evaluate_llm_local
from llm_request import build_and_save_prompt

design = 'design_5'
error = 'error_design_5_2'

# Rebuild prompt (in case of changes)
prompt_data = build_and_save_prompt(design, error)

# Evaluate directly and print Raw
raw_out = evaluate_llm_local.query_local_llm(prompt_data['system_prompt'], prompt_data['user_prompt'])
print("--- RAW LLM OUTPUT ---")
print(raw_out)
print("----------------------")

# See if it parses
print("--- PARSED OUTPUT ---")
try:
    j = evaluate_llm_local.parse_llm_output(raw_out)
    print(json.dumps(j, indent=2))
except Exception as e:
    print(f"FAILED TO PARSE: {e}")
