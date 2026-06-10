import os
import re
import json
from collections import defaultdict
from llm_request_baseline3 import build_and_save_prompt_baseline3
from evaluate_llm_baseline3 import evaluate_design_baseline3, TOP_K

def print_final_accuracy(results_file="local_results_baseline3/master_results.jsonl"):
    if not os.path.exists(results_file):
        print(f"Error: Could not find {results_file}. Have you run the evaluation yet?")
        return

    total_evaluated = 0
    total_correct = 0
    design_stats = defaultdict(lambda: {"total": 0, "correct": 0})

    with open(results_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            design = data.get("design_name", "Unknown")
            is_correct = data.get("is_correct", False)
            
            total_evaluated += 1
            if is_correct:
                total_correct += 1
                
            design_stats[design]["total"] += 1
            if is_correct:
                design_stats[design]["correct"] += 1

    if total_evaluated == 0:
        return

    overall_accuracy = (total_correct / total_evaluated) * 100

    print("\n" + "═"*50)
    print(" 📊 FINAL VERISLICER ACCURACY REPORT")
    print("═"*50)
    print(f" Total Errors Evaluated : {total_evaluated}")
    print(f" Total Exact Matches    : {total_correct}")
    print(f" OVERALL TOP-1 ACCURACY : {overall_accuracy:.2f}%")
    print("-" * 50)
    print(" Breakdown by Design:")
    
    for design in sorted(design_stats.keys()):
        stats = design_stats[design]
        acc = (stats["correct"] / stats["total"]) * 100
        print(f"  * {design: <10} : {acc: >6.2f}%  ({stats['correct']}/{stats['total']})")
        
    print("═"*50 + "\n")

def print_top5_accuracy(results_file="local_results_baseline3/master_results.jsonl"):
    if not os.path.exists(results_file):
        return

    total = top1_hits = topk_hits = 0

    with open(results_file, "r") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            total      += 1
            top1_hits  += int(bool(record.get("is_correct",   False)))
            topk_hits  += int(bool(record.get("topk_correct", False)))

    if total == 0:
        print("No results found in file.")
        return

    top1_acc = 100.0 * top1_hits / total
    topk_acc = 100.0 * topk_hits / total

    print("\n" + "=" * 45)
    print("        FAULT LOCALISATION ACCURACY")
    print("=" * 45)
    print(f"  Total designs evaluated : {total}")
    print(f"  Top-1 correct           : {top1_hits:3d}  ({top1_acc:.1f}%)")
    print(f"  Top-{TOP_K} correct           : {topk_hits:3d}  ({topk_acc:.1f}%)")
    print("=" * 45 + "\n")

def main():
    error_designs_dir = "../Error_designs"
    
    if not os.path.exists(error_designs_dir):
        print(f"❌ ERROR: Could not find directory: {error_designs_dir}")
        return

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

    
    # error_dirs.sort()

    print(f"{'='*60}")
    print(f"🚀 STARTING BASELINE 2 (TRACE ONLY) EVALUATION PIPELINE")
    print(f"Found {len(error_dirs)} error directories to process.")
    print(f"{'='*60}\n")
    
    results_file = "local_results_baseline3/master_results.jsonl"
    if os.path.exists(results_file):
        os.remove(results_file)
        print(f"[*] Cleared previous results file: {results_file}")

    for error_dir in error_dirs:
        match = re.search(r'(design_\d+)', error_dir)
        if not match:
            continue
            
        design_name = match.group(1)
        
        print(f"--- Processing {error_dir} ({design_name}) ---")
        
        # Step A: Build the raw prompt with Full VCD
        print(f"[*] Building Baseline 2 Prompt (Raw Code + Full VCD)...")
        build_and_save_prompt_baseline3(design_name, error_dir)
        
        # Step B: Send to Ollama and Grade
        print(f"[*] Sending to Local LLM for Evaluation...")
        evaluate_design_baseline3(design_name, error_dir, output_dir="local_results_baseline3")
        
        print(f"--- {error_dir} COMPLETE ---\n")

    print(f"{'='*60}")
    print(f"✅ BASELINE 2 PIPELINE FULLY COMPLETE.")
    print(f"Your ablation data is safely logged in: {results_file}")
    print(f"{'='*60}")
    
    print("\nAll designs processed! Calculating final metrics...")
    print_final_accuracy(results_file)
    print_top5_accuracy(results_file)

if __name__ == "__main__":
    main()