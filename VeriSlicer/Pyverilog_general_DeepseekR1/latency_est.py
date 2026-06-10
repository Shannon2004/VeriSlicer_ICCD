import os
from collections import deque

def parse_graph_edges(txt_filepath):
    """Parses the pruned_data.txt file to build a reverse-lookup graph."""
    graph = {}
    is_edge_section = False
    
    if not os.path.exists(txt_filepath):
        return graph

    with open(txt_filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line == "=== EDGES (Driver -> Target) ===":
                is_edge_section = True
                continue
            if is_edge_section and line.startswith("==="):
                is_edge_section = False
                
            if is_edge_section and "->" in line:
                parts = line.split("->")
                if len(parts) == 2:
                    driver = parts[0].strip()
                    target = parts[1].strip()
                    if target not in graph:
                        graph[target] = []
                    graph[target].append(driver)
    return graph

def auto_detect_target(graph):
    """Finds the ultimate output node (a target that drives nothing else)."""
    all_targets = set(graph.keys())
    all_drivers = set()
    
    for drivers in graph.values():
        all_drivers.update(drivers)
        
    # The root is any node that is a target, but NEVER appears as a driver
    roots = all_targets - all_drivers
    if roots:
        # Sort to ensure deterministic behavior, return the primary one
        return sorted(list(roots))[0]
    return None

def estimate_worst_case_latency(txt_filepath, target_pin=None, buffer_cycles=5):
    """Calculates true max depth using DFS with cycle detection."""
    graph = parse_graph_edges(txt_filepath)
    
    if not graph:
        return 15 # Fallback
        
    if not target_pin:
        target_pin = auto_detect_target(graph)
        if not target_pin:
            print("Warning: Could not auto-detect target pin. Using default latency 15.")
            return 15
            
    print(f"[*] DFS Auto-Detected Target Pin: {target_pin}")
    
    # Memoization to speed up traversal (stores longest path from each node)
    memo = {}
    # Tracks nodes in the CURRENT path to detect and break feedback loops
    path_visited = set()
    
    def dfs_longest_path(node):
        # Base Case 1: We hit a feedback loop (State Machine) -> Break it safely
        if node in path_visited:
            return 0
            
        # Base Case 2: We already calculated the longest path for this node
        if node in memo:
            return memo[node]
            
        # Add to current path
        path_visited.add(node)
        max_d = 0
        
        # Traverse all drivers pushing data into this node
        if node in graph:
            for driver in graph[node]:
                # Recursively find the depth of the driver, add 1 for the current hop
                max_d = max(max_d, 1 + dfs_longest_path(driver))
                
        # Remove from current path (backtracking)
        path_visited.remove(node)
        
        # Save the result so we never calculate this sub-tree again
        memo[node] = max_d
        return max_d

    # Execute the DFS
    max_depth = dfs_longest_path(target_pin)
    
    worst_case_window = max_depth + buffer_cycles
    print(f"[*] Dynamic Window Set to: {worst_case_window} cycles (Graph Depth {max_depth} + {buffer_cycles} buffer)")
    
    return worst_case_window
