import os
import json
import re
import ollama

# ── Top-K prediction settings ─────────────────────────────────────────────────
TOP_K = 5   # ask the LLM to rank its top-K candidate bug lines

def get_ground_truth_line(design_name, error_dir):
    """Extracts the actual buggy line number from error_info.txt"""
    error_info_path = os.path.join("../Error_designs", error_dir, "error_info.txt")
    if not os.path.exists(error_info_path):
        return None
    with open(error_info_path, 'r') as f:
        content = f.read()
        match = re.search(r'Error line:\s*(\d+)', content, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None

def _inject_topk_instruction(system_prompt: str) -> str:
    """Rewrite the output-format section of the system prompt to return a RANKED LIST."""
    top_k_format = (
        f'1. "buggy_lines": A JSON array of exactly {TOP_K} integers, each being '
        f"a line number from the Sliced Verilog, ranked from most likely to least "
        f"likely to be the defect origin. The true bug line should appear as early "
        f"in the list as possible. Example: [23, 17, 45, 61, 80]"
    )

    new_prompt, n_subs = re.subn(
        r'1\.\s+"buggy_line":[^\n]+',
        top_k_format,
        system_prompt,
    )

    if n_subs == 0:
        new_prompt = (
            system_prompt.rstrip()
            + f"\n\nIMPORTANT OUTPUT FORMAT OVERRIDE:\n"
            + f'Replace the "buggy_line" key with "buggy_lines": a JSON array of '
            + f"exactly {TOP_K} line-number integers ranked most-likely to least-likely. "
            + f"Example: [23, 17, 45, 61, 80]"
        )
    return new_prompt

def _strip_markdown_fences(text: str) -> str:
    """Remove markdown wrappers the model may add (syntax-safe regex)."""
    text = text.strip()
    # Fixed syntax: `{3}` matches exactly 3 backticks without causing string termination errors
    text = re.sub(r"^`{3}(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*`{3}$", "", text)
    return text.strip()

def parse_llm_response(raw: str) -> dict:
    cleaned = _strip_markdown_fences(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    print(f"[Baseline 2] Could not parse JSON from LLM response:\n{raw[:500]}")
    return {}

def extract_predicted_lines(llm_answer: dict) -> list:
    """Extract a ranked list of predicted buggy line numbers."""
    raw_list   = llm_answer.get("buggy_lines")
    raw_single = llm_answer.get("buggy_line")

    candidates = []
    if raw_list is not None:
        if isinstance(raw_list, list):
            candidates = raw_list
        else:
            candidates = [raw_list]
    elif raw_single is not None:
        candidates = [raw_single]

    result = []
    for val in candidates:
        try:
            result.append(int(val))
        except (ValueError, TypeError):
            pass

    return result

def query_local_llm(prompt_file_path):
    """Sends the prompt to a locally running Ollama model."""
    with open(prompt_file_path, 'r') as f:
        prompt_data = json.load(f)

    system_prompt = prompt_data.get('system_prompt', '')
    user_prompt   = prompt_data.get('user_prompt', '')

    system_prompt_topk = _inject_topk_instruction(system_prompt)

    messages = [
        {"role": "system", "content": system_prompt_topk},
        {"role": "user",   "content": user_prompt}
    ]
        
    try:
        response = ollama.chat(
            model="llama3.3", 
            messages=messages,
            format='json', 
            options={
                'temperature': 0.2,
                'num_predict': 1024,
                'num_ctx': 32768  # Or even 32768, if your machine has enough RAM/VRAM! # Crucial for handling massive VCD traces
            }
        )
        raw_response = response['message']['content']
        return parse_llm_response(raw_response)
        
    except Exception as e:
        print(f"Local Model Error: {e}")
        return None

def evaluate_design_baseline4(design_name, error_dir, output_dir="local_results_baseline4"):
    prompt_path = os.path.join("llm_prompts_baseline4", design_name, f"{error_dir}_prompt.json")
    
    if not os.path.exists(prompt_path):
        print(f"Prompt not found for {error_dir}. Skipping.")
        return
        
    print(f"\n[Baseline 2] Analyzing {error_dir}...")
    
    actual_line = get_ground_truth_line(design_name, error_dir)
    if actual_line is None:
        print("[Baseline 2] Failed to find ground truth in error_info.txt.")
        return
        
    llm_answer = query_local_llm(prompt_path)
    if not llm_answer:
        print("[Baseline 2] LLM failed to return a valid JSON object.")
        return
        
    predicted_lines = extract_predicted_lines(llm_answer)
    top1_prediction = predicted_lines[0] if predicted_lines else None

    top1_correct = (top1_prediction is not None and top1_prediction == actual_line)
    topk_correct = actual_line in predicted_lines

    hit_rank = None
    if actual_line in predicted_lines:
        hit_rank = predicted_lines.index(actual_line) + 1

    print(f"[Baseline 2] Ground Truth    : Line {actual_line}")
    print(f"[Baseline 2] Top-1 Predicted : Line {top1_prediction}")
    print(f"[Baseline 2] Top-{TOP_K} List     : {predicted_lines}")
    
    if top1_correct:
        print("[Baseline 2] ✅ TOP-1 SUCCESS")
    elif topk_correct:
        print(f"[Baseline 2] ✅ TOP-{TOP_K} SUCCESS (hit at rank {hit_rank})")
    else:
        print(f"[Baseline 2] ❌ FAILED (not in top-{TOP_K})")
        print(f"[Baseline 2] Reason given: {llm_answer.get('root_cause', 'None')}")
        
    save_evaluation_log(
        design_name, error_dir, actual_line, top1_prediction, predicted_lines, 
        llm_answer, top1_correct, topk_correct, hit_rank, output_dir
    )

def save_evaluation_log(design_name, error_dir, actual, predicted, predicted_lines, llm_answer, is_correct, topk_correct, hit_rank, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    log_data = {
        "error_id": error_dir,
        "design_name": design_name,
        "actual_line": actual,
        "predicted_line": predicted,
        "predicted_lines": predicted_lines,
        "is_correct": is_correct,
        "topk_correct": topk_correct,
        "hit_rank": hit_rank,
        "top_k": TOP_K,
        "llm_root_cause": llm_answer.get("root_cause", ""),
        "llm_fixed_code": llm_answer.get("fixed_code", "")
    }
    
    log_file = os.path.join(output_dir, "master_results.jsonl")
    with open(log_file, 'a') as f:
        f.write(json.dumps(log_data) + "\n")

if __name__ == "__main__":
    evaluate_design_baseline4("design_5", "error_design_5_3")