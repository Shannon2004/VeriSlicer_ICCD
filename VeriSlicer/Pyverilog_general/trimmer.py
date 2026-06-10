import os
import collections
import re

def load_pruned_signals(graph_txt_path):
    """Loads the list of critical signals to keep."""
    if not os.path.exists(graph_txt_path):
        print(f"Warning: Could not find {graph_txt_path}. Returning empty set.")
        return set()
        
    with open(graph_txt_path, 'r') as f:
        # Assumes one hierarchical signal name per line
        return set(line.strip() for line in f if line.strip())

def trim_vcd(vcd_path, graph_txt_path, design_name, output_dir="trimmed_vcds", clock_name="clk", window_size=15, failing_signal=None):
    """
    Parses a VCD file, filters by the causal graph, and extracts the history.
    Automatically handles both Sequential (clocked) and Combinational (unclocked) designs.
    
    Now also captures:
    - All primary I/O signals (top-level module scope)
    - The failing signal explicitly
    """
    pruned_signals = load_pruned_signals(graph_txt_path)
    
    # Extract base signal names from pruned set for fuzzy matching
    pruned_bases = set()
    for sig in pruned_signals:
        pruned_bases.add(sig.split('.')[-1])
    
    symbol_to_name = {}
    current_scope = []
    current_state = {}
    
    # Deque automatically drops old history, keeping only the final N events!
    cycle_history = collections.deque(maxlen=window_size)
    
    clock_symbol = None
    has_clock = False
    last_clock_val = '0'
    
    current_time = "0"
    top_module_name = None

    if not os.path.exists(vcd_path):
        print(f"Error: VCD file {vcd_path} not found!")
        return None

    print(f"Trimming VCD: {vcd_path}...")

    with open(vcd_path, 'r') as f:
        lines = f.readlines()
        
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 1. Track Module Hierarchy
        if line.startswith("$scope"):
            parts = line.split()
            if len(parts) >= 3:
                current_scope.append(parts[2])
                if top_module_name is None:
                    top_module_name = parts[2]
                
        elif line.startswith("$upscope"):
            if current_scope:
                current_scope.pop()
                
        # 2. Map Signals to Symbols
        elif line.startswith("$var"):
            parts = line.split()
            if len(parts) >= 5:
                symbol = parts[3]
                name = parts[4]
                full_name = ".".join(current_scope + [name])
                
                # Check if this is the clock
                if name == clock_name or full_name.endswith(f".{clock_name}"):
                    clock_symbol = symbol
                    has_clock = True
                
                # Register signal if:
                # (a) It's in the pruned causal graph, OR
                # (b) It's at top-level scope depth (primary I/O), OR
                # (c) Its base name matches a pruned signal base name
                is_top_level = (len(current_scope) == 1)
                in_pruned = full_name in pruned_signals
                base_match = name in pruned_bases
                is_failing = (failing_signal and name == failing_signal)
                
                if in_pruned or (is_top_level and name != clock_name) or base_match or is_failing:
                    symbol_to_name[symbol] = full_name
                    current_state[full_name] = "x"
                    
        # 3. Handle Timestamps (Combinational Snapshot Trigger)
        elif line.startswith("#"):
            new_time = line[1:]
            # If there is NO clock, the timestamp advancing means the previous event is finished.
            if not has_clock and current_time != "0":
                snapshot = {
                    "time_ns": current_time,
                    "signals": dict(current_state)
                }
                cycle_history.append(snapshot)
            current_time = new_time
            
        # 4. Handle Value Changes (Sequential Snapshot Trigger)
        elif line.startswith(("0", "1", "x", "z", "b", "r")):
            # Extract value and symbol
            if line.startswith("b") or line.startswith("r"):
                parts = line.split()
                val = parts[0][1:]
                symbol = parts[1] if len(parts) > 1 else ""
            else:
                val = line[0]
                symbol = line[1:]
                
            # If Sequential: Trigger snapshot on Clock Rising Edge
            if has_clock and symbol == clock_symbol:
                if last_clock_val == '0' and val == '1':
                    snapshot = {
                        "time_ns": current_time,
                        "signals": dict(current_state)
                    }
                    cycle_history.append(snapshot)
                last_clock_val = val
                
            # Update wire state
            if symbol in symbol_to_name:
                current_state[symbol_to_name[symbol]] = val

    # Combinational designs need one last snapshot at the very end of the file
    if not has_clock:
        snapshot = {
            "time_ns": current_time,
            "signals": dict(current_state)
        }
        cycle_history.append(snapshot)

    # --- WRITING THE LLM-FRIENDLY OUTPUT ---
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"{design_name}_trimmed_trace.txt")
    
    with open(out_path, 'w') as f:
        step_type = "CYCLES" if has_clock else "STATE CHANGES"
        hw_type = "Sequential" if has_clock else "Combinational"
        
        f.write(f"--- TRACE HISTORY ({len(cycle_history)} {step_type} BEFORE CRASH) ---\n")
        f.write(f"Hardware Type: {hw_type}\n\n")
        
        for i, snapshot in enumerate(cycle_history):
            label = "Cycle" if has_clock else "Event"
            f.write(f"{label} {-len(cycle_history) + i} (Time: {snapshot['time_ns']} ns)\n")
            for sig, val in sorted(snapshot["signals"].items()):
                f.write(f"  {sig} = {val}\n")
            f.write("-" * 40 + "\n")
            
    print(f"Success! Trace saved to: {out_path}")
    return out_path
