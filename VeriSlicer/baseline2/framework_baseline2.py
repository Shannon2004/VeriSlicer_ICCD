import os
import re
from llm_request_baseline2 import build_and_save_prompt_baseline2
from evaluate_llm_baseline2 import evaluate_design_baseline2

import json
import os
from collections import defaultdict

def print_final_accuracy(results_file="local_results/master_results.jsonl"):
    """Parses the JSONL results file and prints a formatted academic accuracy report."""
    if not os.path.exists(results_file):
        print(f"Error: Could not find {results_file}. Have you run the evaluation yet?")
        return

    total_evaluated = 0
    total_correct = 0
    
    # Dictionary to track stats per design (e.g., design_1, design_2)
    design_stats = defaultdict(lambda: {"total": 0, "correct": 0})

    with open(results_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
                
            data = json.loads(line)
            design = data.get("design_name", "Unknown")
            is_correct = data.get("is_correct", False)
            
            # Update global counts
            total_evaluated += 1
            if is_correct:
                total_correct += 1
                
            # Update per-design counts
            design_stats[design]["total"] += 1
            if is_correct:
                design_stats[design]["correct"] += 1

    if total_evaluated == 0:
        print("No evaluation data found in the file.")
        return

    # Calculate percentages
    overall_accuracy = (total_correct / total_evaluated) * 100

    # Print the beautifully formatted academic report
    print("\n" + "═"*50)
    print(" 📊 FINAL VERISLICER ACCURACY REPORT")
    print("═"*50)
    print(f" Total Errors Evaluated : {total_evaluated}")
    print(f" Total Exact Matches    : {total_correct}")
    print(f" OVERALL TOP-1 ACCURACY : {overall_accuracy:.2f}%")
    print("-" * 50)
    print(" Breakdown by Design:")
    
    # Sort alphabetically by design name for a clean output
    for design in sorted(design_stats.keys()):
        stats = design_stats[design]
        acc = (stats["correct"] / stats["total"]) * 100
        print(f"  * {design: <10} : {acc: >6.2f}%  ({stats['correct']}/{stats['total']})")
        
    print("═"*50 + "\n")

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

def main():
    error_designs_dir = "../Error_designs"
    
    # 1. Sanity check the directory
    if not os.path.exists(error_designs_dir):
        print(f"❌ ERROR: Could not find directory: {error_designs_dir}")
        print("Please ensure you are running this script from the Pyverilog_general folder.")
        return

    # 2. Gather all error directories (e.g., error_design_1_1, error_design_5_3)
    error_dirs = [d for d in os.listdir(error_designs_dir) 
                  if os.path.isdir(os.path.join(error_designs_dir, d))]
    
    # Sort them alphanumerically for clean logging
    error_dirs.sort()

    error_dirs=['error_design_1_1','error_design_1_2','error_design_1_3','error_design_1_4',
                   'error_design_2_1','error_design_2_2','error_design_2_3','error_design_2_4',
                   'error_design_3_1','error_design_3_2','error_design_3_3','error_design_3_4',
                   'error_design_4_1','error_design_4_2','error_design_4_3','error_design_4_4',
                   'error_design_5_1','error_design_5_2','error_design_5_3','error_design_5_4',
                   'error_design_6_1','error_design_6_2','error_design_6_3','error_design_6_4',
                   'error_design_8_1','error_design_8_2','error_design_8_3','error_design_8_4',
                   'error_design_9_1','error_design_9_2','error_design_9_3','error_design_9_4',
                   'error_design_10_1','error_design_10_2','error_design_10_3','error_design_10_4',
                   'error_design_11_1', 'error_design_11_2', 'error_design_11_3', 'error_design_11_4',
                    'error_design_17_1','error_design_17_2'
                   ]

    print(f"{'='*60}")
    print(f"🚀 STARTING BASELINE 1 (VANILLA) EVALUATION PIPELINE")
    print(f"Found {len(error_dirs)} error directories to process.")
    print(f"{'='*60}\n")

    # After: print(f"Found {len(error_dirs)} error directories to process.")
    # Add this block:
    
    results_file = "gemmini_results_baseline2/master_results.jsonl"
    if os.path.exists(results_file):
        os.remove(results_file)
        print(f"[*] Cleared previous results file: {results_file}")
    
    # 3. Master Loop
    for error_dir in error_dirs:
        # Dynamically extract the base design name (e.g., "error_design_5_3" -> "design_5")
        match = re.search(r'(design_\d+)', error_dir)
        if not match:
            print(f"⚠️ Warning: Skipping '{error_dir}'. Could not infer base design name.")
            continue
            
        design_name = match.group(1)
        
        print(f"--- Processing {error_dir} ({design_name}) ---")
        
        # Step A: Build the raw prompt
        print(f"[*] Building Baseline 1 Prompt (Raw Code + Error Symptom)...")
        build_and_save_prompt_baseline2(design_name, error_dir)
        
        # Step B: Send to Gemini and Grade
        print(f"[*] Sending to Gemini for Evaluation...")
        evaluate_design_baseline2(design_name, error_dir, output_dir="gemmini_results_baseline2")
        
        print(f"--- {error_dir} COMPLETE ---\n")

    print(f"{'='*60}")
    print(f"✅ BASELINE 1 PIPELINE FULLY COMPLETE.")
    print(f"Your ablation data is safely logged in: gemmini_results_baseline2/master_results.jsonl")
    print(f"{'='*60}")

    # 10. Print the Final Scoreboard
    print("\nAll designs processed! Calculating final metrics...")
    print_final_accuracy(results_file="gemmini_results_baseline2/master_results.jsonl") # CHANGED
    # at the end of main(), after all designs are processed:
    print_top5_accuracy(results_file="gemmini_results_baseline2/master_results.jsonl")

if __name__ == "__main__":
    main()
