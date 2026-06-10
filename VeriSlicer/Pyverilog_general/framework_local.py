import os
import subprocess
import re # Added for parsing error_info.txt
from trimmer import trim_vcd  # Import your trimmer function
from latency_est import estimate_worst_case_latency
from code_slicer import run_slicer
from llm_request import build_and_save_prompt
from evaluate_llm_local import evaluate_design_local
from calculate_accuracy import print_final_accuracy
from mapper import mapper
from evaluate_llm_local import print_top5_accuracy



def create_makefile(design_name, module_name, error_dir):
    """Generates the Makefile and forces pure ASCII text VCD output."""
    
    makefile_content = f"""# Auto-generated Makefile
SIM ?= icarus
TOPLEVEL_LANG ?= verilog
ENABLE_DUMP ?= 1

export PYTHONPATH := $(PWD)/../Testbenches/{design_name}:$(PYTHONPATH)

VERILOG_SOURCES += $(PWD)/../Error_designs/{error_dir}/{design_name}.v
TOPLEVEL = {design_name}
COCOTB_TEST_MODULES = {module_name}

ifeq ($(ENABLE_DUMP), 1)
    VERILOG_SOURCES += iverilog_dump.v
    COMPILE_ARGS += -s iverilog_dump
endif

include $(shell cocotb-config --makefiles)/Makefile.sim

iverilog_dump.v:
\techo '' > $@
\techo 'module iverilog_dump();' >> $@
\techo 'initial begin' >> $@
\techo '    $$dumpfile("$(PWD)/../Error_designs/{error_dir}/$(TOPLEVEL).vcd");' >> $@
\techo '    $$dumpvars(0, $(TOPLEVEL));' >> $@
\techo 'end' >> $@
\techo 'endmodule' >> $@

clean::
\trm -rf __pycache__ sim_build results.xml iverilog_dump.v
"""
    with open("Makefile", "w") as f:
        f.write(makefile_content)

def get_failing_signal(error_dir):
    """Dynamically extracts the failing pin from error_info.txt."""
    error_info_path = os.path.join("../Error_designs", error_dir, "error_timestamp.txt")
    if os.path.exists(error_info_path):
        with open(error_info_path, 'r') as f:
            content = f.read()
            # Looks for "FAILING SIGNAL : x_o" and extracts "x_o"
            match = re.search(r'FAILING SIGNAL\s*:\s*(\w+)', content, re.IGNORECASE)
            if match:
                return match.group(1)
    return None
def rename_graphs(design_name, error_dir):
    """Renames the output graphs AND the text file to prevent overwriting."""
    graph_dir = os.path.join("graphs", design_name)
    
    if os.path.exists(graph_dir):
        # Added pruned_data.txt to the list of files to be uniquely renamed
        for file_name in ["original_graph.png", "pruned_graph.png", "pruned_data.txt"]:
            old_path = os.path.join(graph_dir, file_name)
            if os.path.exists(old_path):
                new_name = f"{error_dir}_{file_name}"
                new_path = os.path.join(graph_dir, new_name)
                os.rename(old_path, new_path)
                print(f"Renamed {file_name} to: {new_path}")

def main():
    error_designs_dir = "../Error_designs"
    
    # Safely check if the directory exists
    if not os.path.exists(error_designs_dir):
        print(f"Error: Directory {error_designs_dir} not found!")
        return

    results_path = "local_results/master_results.jsonl"
    if os.path.exists(results_path):
        os.remove(results_path)
        print("Cleared previous results log.")

    failed_path = "raw_failed_response.txt"
    if os.path.exists(failed_path):
        os.remove(failed_path)
        print("Cleared previous failed path log.")

    # Automatically find all folders that start with "error_design_"
    # all_error_dirs = [d for d in os.listdir(error_designs_dir) 
                    #   if os.path.isdir(os.path.join(error_designs_dir, d)) and d.startswith("error_design_")]
    
    # Sort them alphabetically/numerically
    # all_error_dirs.sort()
    all_error_dirs = ["error_design_10_1"]
    for error_dir in all_error_dirs:
        # Parse "error_design_X_Y" to extract "design_X"
        parts = error_dir.split('_')
        if len(parts) >= 4:
            design_num = parts[2]
            design_name = f"design_{design_num}"
            module_name = f"test_design_{design_num}"
        else:
            print(f"Skipping malformed directory: {error_dir}")
            continue
            
        print(f"\n{'='*50}")
        print(f"Starting iteration for: {error_dir}")
        print(f"{'='*50}")
        
        # 1. Update Makefile
        create_makefile(design_name, module_name, error_dir)
        print("Generated Makefile.")
        
        # 2. Run 'make clean'
        print("Running 'make clean'...")
        subprocess.run(["make", "clean"])
        
        # 3. Run 'make'
        print("Running 'make'...")
        subprocess.run(["make"])
        
#         4. Run 'mapper' directly via Python function call
        print(f"Running Code Mapper for {error_dir}...")
        
        verilog_path = os.path.join(error_designs_dir, error_dir, f"{design_name}.v")
        failed_pin = get_failing_signal(error_dir)
        
        # Pyverilog expects file paths as a list, top_mod as a string, and failed_pin as a string
        mapper(file_paths=[verilog_path], top_mod=design_name, failed_pin=failed_pin)
        
        # 5. Rename generated graphs and data files
        rename_graphs(design_name, error_dir)
        
        # 6. Run the VCD Trimmer dynamically
        print(f"Running VCD Trimmer for {error_dir}...")
        
        # Construct paths
        vcd_path = os.path.join(error_designs_dir, error_dir, f"{design_name}.vcd")
        graph_txt_path = os.path.join("graphs", design_name, f"{error_dir}_pruned_data.txt")
        
        # --- NEW: Dynamically route the output directory! ---
        specific_out_dir = os.path.join("trimmed_vcds", design_name)
        
        if os.path.exists(vcd_path) and os.path.exists(graph_txt_path):
            print(f"Calculating Dynamic Latency for {error_dir}...")
            
            # 1. Auto-calculate the perfect window size using BFS
            dynamic_window = estimate_worst_case_latency(graph_txt_path, target_pin=None)
            
            # 2. Slice the VCD using that specific window
            trim_vcd(
                vcd_path=vcd_path,
                graph_txt_path=graph_txt_path,
                design_name=error_dir, 
                output_dir=specific_out_dir,
                window_size=dynamic_window,
                failing_signal=failed_pin
            )
        else:
            print(f"Warning: VCD file not found at {vcd_path}. Skipping trimming.")
        
        print(f"Running Code Slicer for {error_dir}...")
        run_slicer(
            v_path=os.path.join(error_designs_dir, error_dir, f"{design_name}.v"),
            graph_path=graph_txt_path,
            design_name=design_name,
            error_dir=error_dir,
            failing_signal=failed_pin
        )

# 8. Generate the LLM Prompt
        print(f"Building LLM Prompt for {error_dir}...")
        build_and_save_prompt(design_name, error_dir)
        
        # 9. Evaluate the LLM and save to local_results
        print(f"Sending to Local Qwen GPU for Evaluation...")
        evaluate_design_local(design_name, error_dir, output_dir="local_results") # CHANGED
        
        print(f"{'='*50}")
        print(f"Iteration for {error_dir} COMPLETE.")
        print(f"{'='*50}\n")

    # ... (End of your massive nested loops) ...
    

# 10. Print the Final Scoreboard
    print("\nAll designs processed! Calculating final metrics...")
    print_final_accuracy(results_file="local_results/master_results.jsonl") # CHANGED
    # at the end of main(), after all designs are processed:
    print_top5_accuracy(results_file="local_results/master_results.jsonl")


if __name__ == "__main__":
    main()

