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

if __name__ == "__main__":
    print_final_accuracy()