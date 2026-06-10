import os
import json
import re
import time
from google import genai
from google.genai import types

# The modern SDK automatically picks up the GEMINI_API_KEY from the environment
client = genai.Client()

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

def query_llm(prompt_file_path, max_retries=5):
    """Sends prompt to Gemini with smart Retry-After parsing and Token limits."""
    with open(prompt_file_path, 'r') as f:
        prompt_data = json.load(f)
        
    full_prompt = f"{prompt_data['system_prompt']}\n\n{prompt_data['user_prompt']}"
    
    # 🛑 SAFETY VALVE: Forcefully cap the prompt to ~3 million chars
    MAX_CHARS = 3000000 
    if len(full_prompt) > MAX_CHARS:
        print(f"\n[LLM Eval] ⚠️ WARNING: Prompt is {len(full_prompt)} chars! Truncating to fit Free Tier TPM limits.")
        top_chunk = full_prompt[:1000000]
        bottom_chunk = full_prompt[-(MAX_CHARS - 1000000):]
        full_prompt = top_chunk + "\n\n... [MASSIVE VCD TRACE TRUNCATED FOR API LIMITS] ...\n\n" + bottom_chunk

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2, 
                ),
            )
            
            # Clean up potential Markdown formatting from the LLM
            raw_text = response.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
                
            return json.loads(raw_text.strip())
            
        except Exception as e:
            error_msg = str(e)
            
            # Catch 429 Rate Limits and Quota Exhaustions
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                # Dynamically read how long Google wants us to wait!
                match = re.search(r'retry in (\d+\.?\d*)s', error_msg)
                if match:
                    wait_time = float(match.group(1)) + 2.0 # Add 2 seconds of buffer
                else:
                    wait_time = 15.0 * (attempt + 1) # Fallback backoff
                    
                print(f"[LLM Eval] ⏳ Google requested a pause. Waiting {wait_time:.1f}s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(wait_time)
            else:
                print(f"[LLM Eval] ❌ Unrecoverable API Error: {e}")
                return None
                
    print("[LLM Eval] ❌ Max retries reached. Skipping design.")
    return None

def evaluate_design(design_name, error_dir, output_dir="gemmini_results"):
    """Runs the full evaluation for a single error design."""
    prompt_path = os.path.join("llm_prompts", design_name, f"{error_dir}_prompt.json")
    
    if not os.path.exists(prompt_path):
        print(f"Prompt not found for {error_dir}. Skipping.")
        return
        
    print(f"\n[LLM Eval] Analyzing {error_dir}...")
    
    actual_line = get_ground_truth_line(design_name, error_dir)
    if actual_line is None:
        print("[LLM Eval] Failed to find ground truth in error_info.txt.")
        return
        
    # 🛑 THE SPEED BUMP: Force 5 seconds of wait time BEFORE the request
    # 60 seconds / 5 seconds = 12 Requests Per Minute. This mathematically guarantees 
    # we stay under Google's 15 RPM Free Tier limit!
    print("[LLM Eval] Pacing request (5s wait) to respect API limits...")
    time.sleep(5)
    
    llm_answer = query_llm(prompt_path)
    
    if not llm_answer or "buggy_line" not in llm_answer:
        print(f"[LLM Eval] ❌ LLM failed to return a valid object.")
        save_evaluation_log(design_name, error_dir, actual_line, -1, {"root_cause": "API Failure"}, False, output_dir)
        return
        
    predicted_line = llm_answer["buggy_line"]
    is_correct = (predicted_line == actual_line)
    
    print(f"[LLM Eval] Ground Truth : Line {actual_line}")
    print(f"[LLM Eval] LLM Predicted: Line {predicted_line}")
    
    if is_correct:
        print("[LLM Eval] ✅ SUCCESS: The LLM found the exact bug!")
    else:
        print("[LLM Eval] ❌ FAILED: The LLM missed the bug.")
        
    save_evaluation_log(design_name, error_dir, actual_line, predicted_line, llm_answer, is_correct, output_dir)

def save_evaluation_log(design_name, error_dir, actual, predicted, llm_answer, is_correct, output_dir):
    """Saves the results to a JSONL log."""
    os.makedirs(output_dir, exist_ok=True)
    
    log_data = {
        "error_id": error_dir,
        "design_name": design_name,
        "actual_line": actual,
        "predicted_line": predicted,
        "is_correct": is_correct,
        "llm_root_cause": llm_answer.get("root_cause", ""),
        "llm_fixed_code": llm_answer.get("fixed_code", "")
    }
    
    log_file = os.path.join(output_dir, "master_results.jsonl")
    with open(log_file, 'a') as f:
        f.write(json.dumps(log_data) + "\n")

if __name__ == "__main__":
    evaluate_design("design_5", "error_design_5_3")