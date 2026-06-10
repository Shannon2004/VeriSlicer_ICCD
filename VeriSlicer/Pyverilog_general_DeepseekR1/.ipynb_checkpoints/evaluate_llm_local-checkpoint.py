"""
evaluate_llm_local.py
─────────────────────
Sends a pre-built LLM prompt to a locally-hosted model (Ollama by default,
or any OpenAI-compatible server such as vLLM / LM-Studio), parses the JSON
response containing a RANKED TOP-K list of candidate buggy lines, compares
against the ground-truth stored in error_info.txt, and appends one record
per design to a master JSONL results file.

Top-K behaviour
───────────────
The system prompt is patched at runtime to ask the model for "buggy_lines":
a ranked list of TOP_K integers instead of the original single "buggy_line".
Both top-1 and top-K correctness are recorded.  TOP_K is configurable at the
top of this file (default: 5).

Called by framework_local.py as:
    evaluate_design_local(design_name, error_dir, output_dir="local_results")
"""

import os
import re
import json
import time
import logging
import requests

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION  – edit these to match your local setup
# ─────────────────────────────────────────────────────────────────────────────

# ── Ollama settings ──────────────────────────────────────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"          # default Ollama port

# Locally pulled models – select the one to use by changing OLLAMA_MODEL
OLLAMA_MODELS = [
    "codestral",
    "qwen2.5-coder:32b",
    "deepseek-r1:32b",
    "deepseek-coder-v2",
    "deepseek-r1:14b",
    "qwen2.5-coder:14b",
    "llama3.3"
]
# OLLAMA_MODEL   = OLLAMA_MODELS[6]                  # change index to switch model
OLLAMA_TIMEOUT = 900                               # seconds

# ── Sampling parameters (shared) ─────────────────────────────────────────────
MAX_TOKENS  = 32768
TEMPERATURE = 0.0          # deterministic for reproducible structured output

# ── Retry settings ───────────────────────────────────────────────────────────
MAX_RETRIES = 3
RETRY_DELAY = 5            # seconds between retries

# ── Top-K prediction settings ────────────────────────────────────────────────
TOP_K = 5                  # ask the LLM to rank its top-K candidate bug lines

# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helper: top-K system prompt injection
# ─────────────────────────────────────────────────────────────────────────────

def _inject_topk_instruction(system_prompt: str) -> str:
    # 🛑 FIX 2: Stern psychological prompting for reasoning models
    top_k_format = (
        f'2. "buggy_lines": A JSON array of exactly {TOP_K} integers representing line numbers from the Sliced Verilog. '
        f'CRITICAL RULE: You MUST provide exactly {TOP_K} numbers. Even if you are 100% confident in a single line, '
        f'you MUST include alternative highly-suspicious lines to reach exactly {TOP_K}. Never return a single integer. '
        f'Example: [23, 17, 45, 61, 80]'
    )

    # 🛑 FIX 3: Bulletproof regex to catch any numbering format (1., 2., -, *)
    new_prompt, n_subs = re.subn(
        r'(?:\d+\.|\-|\*)?\s*"buggy_line"\s*:[^\n]+',
        top_k_format,
        system_prompt,
        flags=re.IGNORECASE
    )

    if n_subs == 0:
        log.warning("Could not locate 'buggy_line' format spec in system prompt; appending fallback.")
        new_prompt = (
            system_prompt.rstrip()
            + f"\n\nIMPORTANT OUTPUT FORMAT OVERRIDE:\n"
            + f'Replace the "buggy_line" key with "buggy_lines": a JSON array of exactly {TOP_K} integers. '
            + f'You MUST provide exactly {TOP_K} alternative lines. Example: [23, 17, 45, 61, 80]'
        )

    return new_prompt


# ─────────────────────────────────────────────────────────────────────────────
# Helper: call local LLM
# ─────────────────────────────────────────────────────────────────────────────

def _ollama_flush_memory(OLLAMA_MODEL):
    """
    Force Ollama to evict the model's KV-cache / context state from GPU/CPU
    memory by sending a keep_alive=0 request.  This guarantees the next call
    starts with a completely blank context and is not influenced by any
    previous prompt's residual state.

    Ollama keeps a loaded model resident for 5 minutes by default; setting
    keep_alive to "0m" unloads it immediately after the (empty) request.
    A small timeout is used because no heavy inference is performed.
    """
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": "",       # empty prompt – only here to trigger the unload
        "keep_alive": "0m", # unload model from memory immediately
    }
    try:
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        log.info("Ollama memory flushed (model KV-cache evicted).")
    except Exception as exc:            # non-fatal – log and continue
        log.warning("Ollama memory flush failed (non-fatal): %s", exc)


def _call_ollama(system_prompt, user_prompt, OLLAMA_MODEL):
    """
    Send a single-turn chat request to a running Ollama instance.

    Memory is explicitly flushed BEFORE the request so that no residual
    KV-cache state from a previous prompt can bleed into this inference,
    and flushed AFTER so the next call also starts completely clean.
    """
    # Pre-call: evict any leftover KV-cache from prior prompts
    _ollama_flush_memory(OLLAMA_MODEL)

    url = f"{OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "options": {
            "temperature": TEMPERATURE,
            "num_predict": MAX_TOKENS,
            # "num_predict": 4096, 
            "num_ctx": MAX_TOKENS
        },
        # Only system + user message – never pass conversation history.
        # A fresh two-message list guarantees a stateless single-turn call.
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
    }
    resp = requests.post(url, json=payload, timeout=OLLAMA_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    result = data["message"]["content"]

    # Post-call: evict this call's KV-cache so the next prompt starts clean
    _ollama_flush_memory(OLLAMA_MODEL)

    return result


def query_local_llm(system_prompt, user_prompt,OLLAMA_MODEL):
    """
    Call the local Ollama backend with retry logic.
    Returns the raw text response from the model.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log.info("LLM request (attempt %d/%d) …", attempt, MAX_RETRIES)
            return _call_ollama(system_prompt, user_prompt,OLLAMA_MODEL)
        except requests.exceptions.Timeout:
            log.warning("Timeout on attempt %d.", attempt)
        except requests.exceptions.ConnectionError as exc:
            log.warning("Connection error on attempt %d: %s", attempt, exc)
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            if status == 404:
                log.error(
                    "Ollama returned 404 – model '%s' is not pulled.\n"
                    "  Fix:  ollama pull %s\n"
                    "  Check available models:  curl http://localhost:11434/api/tags\n"
                    "  Then update OLLAMA_MODEL at the top of this file.",
                    OLLAMA_MODEL, OLLAMA_MODEL,
                )
            else:
                log.error("HTTP %s error: %s", status, exc)
            break                          # no point retrying 4xx errors
        if attempt < MAX_RETRIES:
            log.info("Retrying in %d s …", RETRY_DELAY)
            time.sleep(RETRY_DELAY)

    raise RuntimeError(
        f"LLM query failed after {MAX_RETRIES} attempt(s). "
        "Check that your local server is running."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helper: parse LLM JSON output
# ─────────────────────────────────────────────────────────────────────────────

def _strip_markdown_fences(text: str) -> str:
    """Remove ```json … ``` or ``` … ``` wrappers the model may add."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_llm_response(raw: str) -> dict:
    """Extract the JSON object from the model's raw text."""
    
    # 🛑 FIX 1: Completely delete the <think> block so internal brackets don't break parsing
    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL | re.IGNORECASE).strip()
    
    # 1. Strip fences and try direct parse
    cleaned = _strip_markdown_fences(cleaned)
    try:
        return json.loads(cleaned, strict=False)
    except json.JSONDecodeError:
        pass

    # 2. Greedy search is now SAFE because the think block is gone
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(), strict=False)
        except json.JSONDecodeError:
            pass

    log.error("Could not parse JSON from LLM response. Saving raw output to raw_failed_response.txt")
    with open("raw_failed_response.txt", "a") as f:
        f.write("=== FAILED PARSE ===\n" + raw + "\n====================\n")
    return {}


def extract_predicted_lines(llm_answer: dict) -> list[int]:
    """
    Extract a ranked list of predicted buggy line numbers from the parsed LLM
    response, handling three possible response shapes:

      Shape A (top-K):  {"buggy_lines": [23, 17, 45, 61, 80]}   ← target
      Shape B (legacy): {"buggy_line": 23}                       ← fallback
      Shape C (mixed):  both keys present – buggy_lines wins

    Always returns a plain list[int].  Invalid entries are skipped with a
    warning.  The list may be shorter than TOP_K if the model under-predicted;
    it is never padded so callers must handle variable length.
    """
    raw_list  = llm_answer.get("buggy_lines")
    raw_single = llm_answer.get("buggy_line")

    candidates: list = []

    if raw_list is not None:
        # Model returned the top-K list as requested
        if isinstance(raw_list, list):
            candidates = raw_list
        else:
            # Model wrapped a single value in the wrong key type
            log.warning("'buggy_lines' is not a list (%r); treating as single.", raw_list)
            candidates = [raw_list]
    elif raw_single is not None:
        # Legacy single-line response – wrap so downstream code is uniform
        log.warning(
            "Model returned legacy 'buggy_line' key instead of 'buggy_lines'. "
            "Top-%d accuracy will be computed on a list of length 1.", TOP_K
        )
        candidates = [raw_single]

    # Coerce to int, drop anything that can't be converted
    result: list[int] = []
    for val in candidates:
        try:
            result.append(int(val))
        except (ValueError, TypeError):
            log.warning("Skipping non-integer buggy line candidate: %r", val)

    if not result:
        log.error("No valid line numbers extracted from LLM answer.")

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Helper: ground-truth extraction
# ─────────────────────────────────────────────────────────────────────────────

def get_ground_truth_line(error_dir: str) -> int | None:
    """
    Read the actual buggy line number from
    ../Error_designs/{error_dir}/error_info.txt

    Actual file format:
        Design: CORDIC
        Error line: 23
        ...
    """
    info_path = os.path.join("../Error_designs", error_dir, "error_info.txt")
    if not os.path.exists(info_path):
        log.warning("error_info.txt not found: %s", info_path)
        return None

    with open(info_path, "r") as fh:
        content = fh.read()

    # Primary format: "Error line: 23"
    # Also tolerates minor variations in spacing / capitalisation just in case
    pattern = r"Error\s+line\s*:\s*(\d+)"
    match = re.search(pattern, content, re.IGNORECASE)
    if match:
        return int(match.group(1))

    log.warning(
        "Could not find buggy line number in %s.\n"
        "Expected a line matching: Error line: <number>",
        info_path,
    )
    return None


def get_failing_signal_from_timestamp(error_dir: str) -> str | None:
    """
    Read the failing signal name from
    ../Error_designs/{error_dir}/error_timestamp.txt

    Actual file format:
        TEST FAILED AT 37.0 ns
        FAILING SIGNAL : x_o
        ERROR DETAILS  : Expected x_o to be 32768, got 19896

    NOTE: framework_local.py's get_failing_signal() incorrectly reads this
    from error_info.txt – this function reads from the correct file.
    """
    ts_path = os.path.join("../Error_designs", error_dir, "error_timestamp.txt")
    if not os.path.exists(ts_path):
        log.warning("error_timestamp.txt not found: %s", ts_path)
        return None

    with open(ts_path, "r") as fh:
        content = fh.read()

    match = re.search(r"FAILING SIGNAL\s*:\s*(\w+)", content, re.IGNORECASE)
    if match:
        return match.group(1)

    log.warning("Could not find FAILING SIGNAL in %s.", ts_path)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Helper: load pre-built prompt
# ─────────────────────────────────────────────────────────────────────────────

def load_prompt(design_name: str, error_dir: str) -> dict | None:
    """
    Load the JSON prompt file produced by build_and_save_prompt().
    Expected location: prompts/{design_name}/{error_dir}_prompt.json
    """
    prompt_path = os.path.join("llm_prompts", design_name, f"{error_dir}_prompt.json")
    if not os.path.exists(prompt_path):
        log.error("Prompt file not found: %s", prompt_path)
        return None
    with open(prompt_path, "r") as fh:
        return json.load(fh)


# ─────────────────────────────────────────────────────────────────────────────
# Main public function
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_design_local(
    design_name,
    error_dir,
    output_dir = "local_results",
    OLLAMA_INDEX = 100
):
    """
    Evaluate one error design with Top-K line prediction:
      1. Load the pre-built JSON prompt.
      2. Inject the top-K output format instruction into the system prompt.
      3. Query the local LLM.
      4. Parse the ranked list of predicted buggy lines.
      5. Load the ground-truth line from error_info.txt.
      6. Compute top-1 and top-K correctness.
      7. Append a structured result record to master_results.jsonl.

    Parameters
    ----------
    design_name : str   e.g. "design_1"
    error_dir   : str   e.g. "error_design_1_1"
    output_dir  : str   directory for JSONL results (created if absent)
    """
    OLLAMA_MODEL   = OLLAMA_MODELS[int(OLLAMA_INDEX)]                  # change index to switch model
    
    log.info("── Evaluating %s ──", error_dir)

    # ── 1. Load prompt ────────────────────────────────────────────────────────
    prompt_data = load_prompt(design_name, error_dir)
    if prompt_data is None:
        log.error("Skipping %s – prompt file missing.", error_dir)
        return

    system_prompt = prompt_data.get("system_prompt", "")
    user_prompt   = prompt_data.get("user_prompt",   "")

    print(f"MODEL USED: {OLLAMA_MODEL}")
    
    if not system_prompt or not user_prompt:
        log.error("Prompt file for %s is missing system_prompt or user_prompt.", error_dir)
        return

    # ── 2. Query local LLM ────────────────────────────────────────────────────
    # NOTE: Top-K format is now built directly into the system prompt by
    # llm_request.py, so no injection hack is needed here.
    log.info("Using system prompt as-is (Top-%d format already embedded).", TOP_K)
    try:
        raw_response = query_local_llm(system_prompt, user_prompt,OLLAMA_MODEL)
    except RuntimeError as exc:
        log.error("LLM query failed for %s: %s", error_dir, exc)
        raw_response = ""

    # ── 4. Parse LLM JSON and extract ranked line list ────────────────────────
    llm_answer: dict      = parse_llm_response(raw_response) if raw_response else {}
    predicted_lines: list[int] = extract_predicted_lines(llm_answer)

    # Convenience aliases
    top1_prediction: int | None = predicted_lines[0] if predicted_lines else None

    # ── 5. Load ground truth ─────────────────────────────────────────────────
    actual = get_ground_truth_line(error_dir)

    # ── 6. Compute correctness at each rank ──────────────────────────────────
    top1_correct: bool = (
        actual is not None
        and top1_prediction is not None
        and top1_prediction == actual
    )
    topk_correct: bool = (
        actual is not None
        and actual in predicted_lines
    )

    # Determine the rank at which the correct line first appears (1-indexed)
    # None means it was not found in any of the TOP_K predictions
    hit_rank: int | None = None
    if actual is not None and actual in predicted_lines:
        hit_rank = predicted_lines.index(actual) + 1

    log.info(
        "%s | actual=%-4s  top1=%-4s  top%d_list=%s  top1_correct=%-5s  top%d_correct=%-5s  hit_rank=%s",
        error_dir,
        actual,
        top1_prediction,
        TOP_K, predicted_lines,
        top1_correct,
        TOP_K, topk_correct,
        hit_rank,
    )

    # ── 7. Build log record ───────────────────────────────────────────────────
    log_data = {
        "error_id":        error_dir,
        "design_name":     design_name,
        "actual_line":     actual,
        "predicted_line":  top1_prediction,          # top-1 (backward compat)
        "predicted_lines": predicted_lines,          # full ranked top-K list
        "is_correct":      top1_correct,             # top-1 correctness
        "topk_correct":    topk_correct,             # top-K correctness
        "hit_rank":        hit_rank,                 # rank of correct line (1-indexed, None=miss)
        "top_k":           TOP_K,                    # record what K was used
        "llm_root_cause":  llm_answer.get("root_cause", ""),
        "llm_fixed_code":  llm_answer.get("fixed_code", ""),
    }

    # ── 8. Persist to JSONL ──────────────────────────────────────────────────
    os.makedirs(output_dir, exist_ok=True)
    results_path = os.path.join(output_dir, f"master_results_{OLLAMA_MODEL}.jsonl")

    with open(results_path, "a") as fh:
        fh.write(json.dumps(log_data) + "\n")

    log.info("Result appended to %s", results_path)

# ─────────────────────────────────────────────────────────────────────────────
# Accuracy summary
# ─────────────────────────────────────────────────────────────────────────────

def print_top5_accuracy(results_file: str = "local_results/master_results.jsonl") -> None:
    """
    Read master_results.jsonl and print overall Top-1 and Top-5 accuracy.
    Call this after all designs have been evaluated.
    """
    if not os.path.exists(results_file):
        print(f"[ERROR] Results file not found: {results_file}")
        return

    total = top1_hits = top5_hits = 0

    with open(results_file, "r") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            total      += 1
            top1_hits  += int(bool(record.get("is_correct",   False)))
            top5_hits  += int(bool(record.get("topk_correct", False)))

    if total == 0:
        print("No results found in file.")
        return

    top1_acc = 100.0 * top1_hits / total
    top5_acc = 100.0 * top5_hits / total

    print("\n" + "=" * 45)
    print("        FAULT LOCALISATION ACCURACY")
    print("=" * 45)
    print(f"  Total designs evaluated : {total}")
    print(f"  Top-1 correct           : {top1_hits:3d}  ({top1_acc:.1f}%)")
    print(f"  Top-5 correct           : {top5_hits:3d}  ({top5_acc:.1f}%)")
    print("=" * 45 + "\n")