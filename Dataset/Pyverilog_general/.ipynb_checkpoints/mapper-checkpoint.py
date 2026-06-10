import os
import sys
import re
import argparse
import difflib
import json
import time
import networkx as nx
import matplotlib.pyplot as plt
from pyverilog.dataflow.dataflow_analyzer import VerilogDataflowAnalyzer

# --- PYVERILOG BUG FIXES (MONKEY PATCHES) ---
# Unified patches to handle missing widths, lost loop variables, ternary ops, unsupported AST nodes, and dynamic loops.
import pyverilog.dataflow.signalvisitor as signalvisitor
import pyverilog.dataflow.bindvisitor as bindvisitor
from pyverilog.utils.verror import DefinitionError, FormatError
from pyverilog.dataflow.dataflow import DFIntConst, DFBranch
import pyverilog.dataflow.reorder as reorder

# Patch 1: Fix NoneType crashes on implicit widths
_orig_makeConstantTerm = signalvisitor.SignalVisitor.makeConstantTerm
def _patched_makeConstantTerm(self, name, node, scope):
    if hasattr(node, 'width') and node.width is not None:
        if getattr(node.width, 'msb', None) is None or getattr(node.width, 'lsb', None) is None:
            node.width = None 
    return _orig_makeConstantTerm(self, name, node, scope)
signalvisitor.SignalVisitor.makeConstantTerm = _patched_makeConstantTerm

# Patch 2: Fix DefinitionError crashes on lost loop variables (like 'i')
_orig_getConstant = signalvisitor.SignalVisitor.getConstant
def _patched_getConstant(self, name):
    try:
        return _orig_getConstant(self, name)
    except DefinitionError:
        return DFIntConst('0')
signalvisitor.SignalVisitor.getConstant = _patched_getConstant

# Patch 3: Fix AttributeError on missing 'insertCond' for ternary operators
if not hasattr(reorder, 'insertCond'):
    def _patched_insertCond(cond_df, true_df, false_df):
        return DFBranch(cond_df, true_df, false_df)
    reorder.insertCond = _patched_insertCond

# Patch 4: Prevent FormatError on unsupported AST nodes (like FunctionCalls)
_orig_makeDFTree = signalvisitor.SignalVisitor.makeDFTree
def _patched_makeDFTree(self, expr, scope):
    try:
        return _orig_makeDFTree(self, expr, scope)
    except FormatError:
        return DFIntConst('0')
signalvisitor.SignalVisitor.makeDFTree = _patched_makeDFTree

# Patch 5: Fix FormatError on dynamic for-loops (non-static conditions)
_orig_bind_visit_ForStatement = bindvisitor.BindVisitor.visit_ForStatement
def _patched_bind_visit_ForStatement(self, node):
    try:
        _orig_bind_visit_ForStatement(self, node)
    except FormatError:
        self.visit(node.statement)
bindvisitor.BindVisitor.visit_ForStatement = _patched_bind_visit_ForStatement

_orig_signal_visit_ForStatement = signalvisitor.SignalVisitor.visit_ForStatement
def _patched_signal_visit_ForStatement(self, node):
    try:
        _orig_signal_visit_ForStatement(self, node)
    except FormatError:
        self.visit(node.statement)
signalvisitor.SignalVisitor.visit_ForStatement = _patched_signal_visit_ForStatement
# --------------------------------------------

def sanitize_verilog_files(v_files):
    """Creates temporary sanitized versions of the verilog files to avoid pyverilog parser crashes."""
    sanitized_files = []
    for filepath in v_files:
        if not os.path.exists(filepath):
            print(f"Error: File {filepath} not found.")
            continue
            
        with open(filepath, 'r') as f:
            content = f.read()
            
        # Hide illegal generate-block defparams from PyVerilog using block comments
        content = re.sub(r'\bdefparam\b([^;]+);', r'/* defparam \1; */', content)
        
        # Safely patch known missing assignment operators (common typo in some benchmark modules)
        content = re.sub(r'assign\s+(\w+)\s+(\w+)(?!\s*=)', r'assign \1 = \2', content)
        
        base_dir = os.path.dirname(filepath)
        file_name = os.path.basename(filepath)
        temp_filepath = os.path.join(base_dir, f"temp_sanitized_{file_name}")
        
        with open(temp_filepath, 'w') as f:
            f.write(content)
            
        sanitized_files.append(temp_filepath)
        
    return sanitized_files

def cleanup_temp_files(temp_files):
    """Removes the temporary sanitized files."""
    for filepath in temp_files:
        if os.path.exists(filepath):
            os.remove(filepath)

def get_dependencies(node):
    """Recursively fetches dependencies from a given pyverilog AST node."""
    deps = []
    if node is None: return deps
    if hasattr(node, 'name') and node.name is not None:
        deps.append(str(node.name))
    
    if hasattr(node, 'nextnodes'):
        for n in node.nextnodes: deps.extend(get_dependencies(n))
            
    for attr in ['condnode', 'truenode', 'falsenode', 'var']:
        if hasattr(node, attr):
            deps.extend(get_dependencies(getattr(node, attr)))
            
    return deps

def build_raw_map(verilog_files, top_module):
    """Runs VerilogDataflowAnalyzer to generate a complete pin-to-pin dependency map."""
    analyzer = VerilogDataflowAnalyzer(verilog_files, top_module)
    analyzer.generate()
    binddict = analyzer.getBinddict()
    
    raw_map = {}
    for signal_obj, bindings in binddict.items():
        target = str(signal_obj)
        deps = set()
        
        for binding in bindings:
            extracted_terms = get_dependencies(binding.tree)
            for term in extracted_terms:
                term_str = str(term)
                # Filter out pure constants
                if not term_str.startswith("'") and not term_str[0].isdigit():
                    deps.add(term_str)
                    
        if deps:
            raw_map[target] = list(deps)
            
    return raw_map

def trace_causal_path(raw_map, failed_output):
    """Performs a breadth-first search backwards from the failing pin to find all influential pins."""
    causal_set = set()
    queue = [failed_output]
    
    while queue:
        current_signal = queue.pop(0)
        if current_signal not in causal_set:
            causal_set.add(current_signal)
            if current_signal in raw_map:
                for driver in raw_map[current_signal]:
                    queue.append(driver)
                    
    return causal_set

def save_graph(graph_dict, module_name, filename, failed_pin=None, title=""):
    """Visualizes the dataflow graph using NetworkX and Matplotlib."""
    out_dir = os.path.join("graphs", module_name)
    os.makedirs(out_dir, exist_ok=True)
    
    G = nx.DiGraph()
    for target, drivers in graph_dict.items():
        for driver in drivers:
            G.add_edge(driver, target)
            
    if len(G.nodes) == 0:
        print(f"Warning: The graph {filename} has no nodes to draw!")
        return
            
    plt.figure(figsize=(14, 12)) 
    
    color_map = ['lightcoral' if node == failed_pin else 'lightblue' for node in G]
    pos = nx.spring_layout(G, k=0.9, seed=42)
    
    nx.draw(G, pos, node_color=color_map, with_labels=True, 
            node_size=2500, font_size=8, font_weight='bold', 
            arrows=True, arrowsize=15)
            
    plt.title(title, fontsize=16, fontweight='bold')
    filepath = os.path.join(out_dir, filename)
    plt.savefig(filepath, format="png", bbox_inches="tight")
    plt.close()
    
    print(f"Success: Graph plotted and saved to '{filepath}'")

def save_pruned_graph_data(graph_dict, out_dir, source_file_path):
    """Saves vertices and edges of the pruned graph to a specifically named text file."""
    
    # Extract the immediate directory containing the design file
    if source_file_path:
        # 1. Get the full absolute path
        abs_path = os.path.abspath(source_file_path)
        
        # 2. Get the directory containing the file
        file_dir = os.path.dirname(abs_path)
        
        # 3. Extract just that folder's name (This will grab 'error_design_1_1')
        base_name = os.path.basename(file_dir)
        
        # Fallback if the path is somehow empty
        if not base_name:
            base_name = os.path.splitext(os.path.basename(source_file_path))[0]
    else:
        base_name = "module"
        
    # Generate the exact requested filename
    filename = f"{base_name}_pruned_data.txt"
    filepath = os.path.join(out_dir, filename)
    
    vertices = set()
    edges = []
    
    # Extract nodes and edges
    for target, drivers in graph_dict.items():
        vertices.add(target)
        for driver in drivers:
            vertices.add(driver)
            edges.append((driver, target))
            
    with open(filepath, "w") as f:
        # Write Metadata
        f.write(f"# Source File: {source_file_path}\n")
        f.write(f"# Project Dir: {base_name}\n")
        f.write(f"# Total Vertices: {len(vertices)}\n")
        f.write(f"# Total Edges: {len(edges)}\n\n")
        
        # Write Vertices
        f.write("=== VERTICES ===\n")
        for v in sorted(list(vertices)):
            f.write(f"{v}\n")
            
        f.write("\n")
        
        # Write Edges
        f.write("=== EDGES (Driver -> Target) ===\n")
        for driver, target in edges:
            f.write(f"{driver} -> {target}\n")
            
    print(f"Success: Pruned graph text data saved to '{filepath}'")

def get_config_from_makefile(makefile_path="Makefile"):
    """Extracts VERILOG_SOURCES and TOPLEVEL from the local Makefile."""
    v_files = []
    top_mod = ""
    if not os.path.exists(makefile_path):
        return v_files, top_mod
        
    with open(makefile_path, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("VERILOG_SOURCES"):
                raw_paths = line.split("=")[-1].strip().split()
                for path in raw_paths:
                    actual_path = path.replace("$(PWD)", os.getcwd())
                    v_files.append(actual_path)
            elif line.startswith("TOPLEVEL"):
                top_mod = line.split("=")[-1].strip()
    return v_files, top_mod

def get_failed_pin_from_log(log_path="error_timestamp.txt", top_mod=""):
    """Scans the error log to find the FAILING SIGNAL generated by a testbench."""
    pin_name = ""
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            for line in f:
                if "FAILING SIGNAL" in line:
                    pin_name = line.split(":")[-1].strip()
                    break
    
    if pin_name:
        return f"{top_mod}.{pin_name}"
    else:
        print("Warning: Could not find failing pin in log. Using fallback 'y2'.")
        return f"{top_mod}.y2"

def mapper(file_paths, top_mod=None, failed_pin=None):
    print("Initializing Mapper Tool...")
    """Main orchestration function for analyzing dataflow and generating graphs."""
    if isinstance(file_paths, str):
        file_paths = [file_paths]
        
    # Fallbacks to auto-discovery if args aren't explicitly provided
    if not top_mod:
        makefile_files, top_mod = get_config_from_makefile()
        if not file_paths or file_paths == [None]:
            file_paths = makefile_files
            
    if not failed_pin:
        failed_pin = get_failed_pin_from_log("error_timestamp.txt", top_mod)
        
    # Normalize pin name
    if top_mod and failed_pin and not failed_pin.startswith(f"{top_mod}."):
        failed_pin = f"{top_mod}.{failed_pin}"
        
    if not file_paths or not top_mod:
        print("Error: Could not determine Verilog sources or Top Module.")
        sys.exit(1)
        
    print(f'Configuration -> Files: {file_paths}, Top Module: {top_mod}, Target Pin: {failed_pin}')
    
    print(f"\n--- Running Pre-processor ---")
    temp_v_files = sanitize_verilog_files(file_paths)
    
    print(f"\n--- Running Mapper ---")
    try:
        print(f"Analyzing source files...")
        raw_map = build_raw_map(temp_v_files, top_mod)
        
        # --- ADVANCED FUZZY MATCHING FOR THE FAILING PIN ---
        if failed_pin not in raw_map:
            print(f"\nWarning: Exact pin '{failed_pin}' not found in AST. Searching for alternatives...")
            base_pin = failed_pin.split('.')[-1].lower()
            
            possible_matches = []
            
            # Strategy 1: Try exact suffix match
            possible_matches = [k for k in raw_map.keys() if k.lower().endswith(base_pin)]
            
            # Strategy 2: Try keyword overlap (e.g., 'digest_output' matches 'core_digest' via 'digest')
            if not possible_matches:
                base_words = set(base_pin.split('_'))
                for k in raw_map.keys():
                    k_words = set(k.split('.')[-1].lower().split('_'))
                    if base_words.intersection(k_words):
                        possible_matches.append(k)
            
            # Strategy 3: String similarity fallback
            if not possible_matches:
                all_bases = [k.split('.')[-1] for k in raw_map.keys()]
                closest = difflib.get_close_matches(base_pin, all_bases, n=1, cutoff=0.5)
                if closest:
                    possible_matches = [k for k in raw_map.keys() if k.endswith(closest[0])]

            if possible_matches:
                failed_pin = possible_matches[0]
                print(f"Auto-corrected target pin to: '{failed_pin}'")
            else:
                print(f"CRITICAL: Could not find any signal related to '{base_pin}' in the design.")
                if raw_map:
                    print(f"Available top-level signals: {list(raw_map.keys())[:10]}...")
                else:
                    print("No signals found. Module may be empty or failed to parse.")
        # -----------------------------------------------
        
        print(f"Tracing causal path for '{failed_pin}'...")
        critical_signals = trace_causal_path(raw_map, failed_pin)
        
        pruned_map = {}
        for target in critical_signals:
            if target in raw_map:
                valid_drivers = [d for d in raw_map[target] if d in critical_signals]
                if valid_drivers:
                    pruned_map[target] = valid_drivers
        
        print("\nDrawing Original Graph...")
        save_graph(raw_map, top_mod, "original_graph.png", failed_pin, "Original Complete AST Dataflow")
        
        print("Drawing Pruned Graph...")
        save_graph(pruned_map, top_mod, "pruned_graph.png", failed_pin, f"Pruned Causal Dataflow (Target: {failed_pin})")
        
        # --- NEW CODE: Save the vertices and edges to a unique JSON file ---
        out_dir = os.path.join("graphs", top_mod)
        os.makedirs(out_dir, exist_ok=True)
        
        # Grab the first file path to use for naming
        source_name = file_paths[0] if file_paths else top_mod
        save_pruned_graph_data(pruned_map, out_dir, source_name)
        # -------------------------------------------------------------------
        
        print(f"\nDone! Check the 'graphs/{top_mod}/' folder.")
        
    finally:
        cleanup_temp_files(temp_v_files)
        print("Cleaned up temporary sanitized files.")

