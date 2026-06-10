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


# ─────────────────────────────────────────────────────────────────────────────
# Helper: top-K system prompt injection
# Ported from evaluate_llm_local.py
# ─────────────────────────────────────────────────────────────────────────────

def _inject_topk_instruction(system_prompt: str) -> str:
    """
    Rewrite the output-format section of the system prompt so the model
    returns a RANKED LIST of TOP_K candidate buggy lines instead of a single
    integer.  The rest of the system prompt is preserved verbatim.

    Replaces the "buggy_line" key spec with "buggy_lines" (a ranked list).
    If the original format instruction cannot be located, the new instruction
    is appended at the end as a fallback.
    """
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
        # Fallback: append instruction if pattern not found
        new_prompt = (
            system_prompt.rstrip()
            + f"\n\nIMPORTANT OUTPUT FORMAT OVERRIDE:\n"
            + f'Replace the "buggy_line" key with "buggy_lines": a JSON array of '
            + f"exactly {TOP_K} line-number integers ranked most-likely to least-likely. "
            + f"Example: [23, 17, 45, 61, 80]"
        )

    return new_prompt


# ─────────────────────────────────────────────────────────────────────────────
# Helper: parse LLM JSON output
# Ported from evaluate_llm_local.py
# ─────────────────────────────────────────────────────────────────────────────

def _strip_markdown_fences(text: str) -> str:
    """Remove ```json … ``` or ``` … ``` wrappers the model may add."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_llm_response(raw: str) -> dict:
    """
    Extract the JSON object from the model's raw text.
    Tries strict parse first, then falls back to regex extraction.
    Returns a dict; on failure returns an empty dict.
    """
    cleaned = _strip_markdown_fences(raw)
    try:
        return json.loads(cleaned, strict=False)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(), strict=False)
        except json.JSONDecodeError:
            pass

    print(f"[Baseline 1] Could not parse JSON from LLM response:\n{raw[:500]}")
    return {}


def extract_predicted_lines(llm_answer: dict) -> list:
    """
    Extract a ranked list of predicted buggy line numbers from the parsed LLM
    response, handling three possible response shapes:

      Shape A (top-K):  {"buggy_lines": [23, 17, 45, 61, 80]}   ← target
      Shape B (legacy): {"buggy_line": 23}                       ← fallback
      Shape C (mixed):  both keys present – buggy_lines wins

    Always returns a plain list of ints. Invalid entries are skipped.
    """
    raw_list   = llm_answer.get("buggy_lines")
    raw_single = llm_answer.get("buggy_line")

    candidates = []

    if raw_list is not None:
        if isinstance(raw_list, list):
            candidates = raw_list
        else:
            print(f"[Baseline 1] 'buggy_lines' is not a list ({raw_list!r}); treating as single.")
            candidates = [raw_list]
    elif raw_single is not None:
        print(
            f"[Baseline 1] Model returned legacy 'buggy_line' key instead of 'buggy_lines'. "
            f"Top-{TOP_K} accuracy will be computed on a list of length 1."
        )
        candidates = [raw_single]

    result = []
    for val in candidates:
        try:
            result.append(int(val))
        except (ValueError, TypeError):
            print(f"[Baseline 1] Skipping non-integer buggy line candidate: {val!r}")

    if not result:
        print("[Baseline 1] No valid line numbers extracted from LLM answer.")

    return result


# ─────────────────────────────────────────────────────────────────────────────
# LLM query – unchanged ollama backend, top-K prompt injection added
# ─────────────────────────────────────────────────────────────────────────────

def query_local_llm(prompt_file_path):
    """Sends the prompt to a locally running Ollama model."""
    with open(prompt_file_path, 'r') as f:
        prompt_data = json.load(f)

    system_prompt = prompt_data.get('system_prompt', '')
    user_prompt   = prompt_data.get('user_prompt', '')

    # Inject top-K instruction into system prompt
    system_prompt_topk = _inject_topk_instruction(system_prompt)

    messages = [
        {"role": "system", "content": system_prompt_topk},
        {"role": "user",   "content": user_prompt}
    ]
        
    try:
        # The 'format="json"' flag forces the local model to output valid JSON
        response = ollama.chat(
            # Swapped to Qwen 2.5 Coder 14B 
            # (If this exact string fails, try 'qwen2.5-coder:14b')
            model='llama3.3', 
            messages=messages,
            format='json', 
            options={
                'temperature': 0.2,
                'num_predict': 1024,
                'num_ctx': 32768 # Increased context window to read whole Verilog files!
            }
        )
        
        raw_response = response['message']['content']
        return parse_llm_response(raw_response)
        
    except Exception as e:
        print(f"Local Model Error: {e}")
        return None


def evaluate_design_baseline2(design_name, error_dir, output_dir="local_results_baseline2"):
    """Runs the Baseline 1 evaluation using a local LLM with Top-K line prediction."""
    # Look for the prompt in the Baseline 1 folder
    prompt_path = os.path.join("llm_prompts_baseline2", design_name, f"{error_dir}_prompt.json")
    
    if not os.path.exists(prompt_path):
        print(f"Prompt not found at {prompt_path}. Skipping.")
        return
        
    print(f"\n[Baseline 1] Analyzing {error_dir}...")
    
    actual_line = get_ground_truth_line(design_name, error_dir)
    if actual_line is None:
        print("[Baseline 1] Failed to find ground truth in error_info.txt.")
        return
        
    llm_answer = query_local_llm(prompt_path)
    if not llm_answer:
        print("[Baseline 1] LLM failed to return a valid JSON object.")
        return

    # ── Extract ranked predictions ────────────────────────────────────────────
    predicted_lines = extract_predicted_lines(llm_answer)
    top1_prediction = predicted_lines[0] if predicted_lines else None

    # ── Compute top-1 and top-K correctness ──────────────────────────────────
    top1_correct = (
        top1_prediction is not None
        and top1_prediction == actual_line
    )
    topk_correct = actual_line in predicted_lines

    # Rank at which the correct line first appears (1-indexed; None = miss)
    hit_rank = None
    if actual_line in predicted_lines:
        hit_rank = predicted_lines.index(actual_line) + 1

    print(f"[Baseline 1] Ground Truth    : Line {actual_line}")
    print(f"[Baseline 1] Top-1 Predicted : Line {top1_prediction}")
    print(f"[Baseline 1] Top-{TOP_K} List     : {predicted_lines}")

    if top1_correct:
        print("[Baseline 1] ✅ TOP-1 SUCCESS")
    elif topk_correct:
        print(f"[Baseline 1] ✅ TOP-{TOP_K} SUCCESS (hit at rank {hit_rank})")
    else:
        print(f"[Baseline 1] ❌ FAILED (not in top-{TOP_K})")
        print(f"[Baseline 1] Reason given: {llm_answer.get('root_cause', 'None')}")
        
    save_evaluation_log(
        design_name, error_dir,
        actual_line, top1_prediction, predicted_lines,
        llm_answer, top1_correct, topk_correct, hit_rank,
        output_dir
    )


def save_evaluation_log(
    design_name, error_dir,
    actual, predicted, predicted_lines,
    llm_answer, is_correct, topk_correct, hit_rank,
    output_dir
):
    """Saves the Baseline 1 results including top-1 and top-K accuracy fields."""
    os.makedirs(output_dir, exist_ok=True)
    
    log_data = {
        "error_id":        error_dir,
        "design_name":     design_name,
        "actual_line":     actual,
        "predicted_line":  predicted,           # top-1 (backward compat)
        "predicted_lines": predicted_lines,     # full ranked top-K list
        "is_correct":      is_correct,          # top-1 correctness
        "topk_correct":    topk_correct,        # top-K correctness
        "hit_rank":        hit_rank,            # rank of correct line (1-indexed, None=miss)
        "top_k":           TOP_K,               # record what K was used
        "llm_root_cause":  llm_answer.get("root_cause", ""),
        "llm_fixed_code":  llm_answer.get("fixed_code", "")
    }
    
    log_file = os.path.join(output_dir, "master_results.jsonl")
    with open(log_file, 'a') as f:
        f.write(json.dumps(log_data) + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# Accuracy summary
# Ported from evaluate_llm_local.py
# ─────────────────────────────────────────────────────────────────────────────

def print_top5_accuracy(results_file: str = "local_results_baseline2/master_results.jsonl") -> None:
    """
    Read master_results.jsonl and print overall Top-1 and Top-K accuracy.
    Call this after all designs have been evaluated.
    """
    if not os.path.exists(results_file):
        print(f"[ERROR] Results file not found: {results_file}")
        return

    total = top1_hits = topk_hits = 0

    with open(results_file, "r") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            total     += 1
            top1_hits += int(bool(record.get("is_correct",   False)))
            topk_hits += int(bool(record.get("topk_correct", False)))

    if total == 0:
        print("No results found in file.")
        return

    top1_acc = 100.0 * top1_hits / total
    topk_acc = 100.0 * topk_hits / total
    k_val    = TOP_K  # use module-level TOP_K as display label

    print("\n" + "=" * 45)
    print("        FAULT LOCALISATION ACCURACY")
    print("=" * 45)
    print(f"  Total designs evaluated : {total}")
    print(f"  Top-1 correct           : {top1_hits:3d}  ({top1_acc:.1f}%)")
    print(f"  Top-{k_val} correct           : {topk_hits:3d}  ({topk_acc:.1f}%)")
    print("=" * 45 + "\n")


if __name__ == "__main__":
    # Make sure your prompt JSON files exist before running
    evaluate_design_baseline2("design_5", "error_design_5_3")
    print_top5_accuracy()