"""
vcd_summarizer.py
─────────────────
Creates an ultra-compact, LLM-optimized failure analysis from the trimmed
trace files produced by trimmer.py.

Instead of dumping raw multi-cycle hex traces (which waste tokens and are
opaque to small models), this version produces a STRUCTURED FAILURE ANALYSIS:

  1. Show ONLY the failure-time snapshot (not multi-cycle history)
  2. Pre-compute the XOR diff between expected and actual values
  3. Identify which bits differ and suggest likely operator swaps
  4. Include test case context (what operation was being performed)

Called by llm_request.py as:
    summarize_vcd(trimmed_vcd_path, error_timestamp_path, max_cycles=3, char_budget=3000)
"""

import os
import re


def _bin_to_hex(bin_str):
    """Convert a binary string to a hex string. Handles 'x' and 'z' gracefully."""
    bin_str = bin_str.strip()
    if not bin_str or bin_str in ('x', 'z', 'X', 'Z'):
        return bin_str
    if 'x' in bin_str.lower() or 'z' in bin_str.lower():
        return bin_str
    try:
        return hex(int(bin_str, 2))
    except ValueError:
        return bin_str


def _bin_to_int(bin_str):
    """Convert a binary string to an integer. Returns None on failure."""
    bin_str = bin_str.strip()
    if not bin_str or 'x' in bin_str.lower() or 'z' in bin_str.lower():
        return None
    try:
        return int(bin_str, 2)
    except ValueError:
        return None


def _strip_module_prefix(signal_name):
    """Remove the top-level module prefix for readability."""
    parts = signal_name.split('.')
    if len(parts) > 1:
        return '.'.join(parts[1:])
    return signal_name


def parse_trimmed_vcd(trimmed_vcd_path):
    """Parse a trimmed VCD trace file into a list of cycle dictionaries."""
    if not os.path.exists(trimmed_vcd_path):
        return []

    cycles = []
    current_cycle = None

    with open(trimmed_vcd_path, 'r') as f:
        for line in f:
            line = line.rstrip()

            m = re.match(r'(Cycle|Event)\s+[-\d]+\s+\(Time:\s*([\d.]+)\s*ns\)', line)
            if m:
                if current_cycle is not None:
                    cycles.append(current_cycle)
                current_cycle = {"time": m.group(2), "signals": {}}
                continue

            m = re.match(r'\s+(\S+)\s*=\s*(.+)', line)
            if m and current_cycle is not None:
                sig_name = m.group(1).strip()
                sig_val = m.group(2).strip()
                current_cycle["signals"][sig_name] = sig_val

    if current_cycle is not None:
        cycles.append(current_cycle)

    return cycles


def _parse_error_timestamp(error_timestamp_path):
    """Parse error_timestamp.txt to extract structured failure info.
    
    Returns dict with keys: time_ns, failing_signal, expected, actual, details
    """
    info = {}
    if not error_timestamp_path or not os.path.exists(error_timestamp_path):
        return info
    
    with open(error_timestamp_path, 'r') as f:
        content = f.read()
    
    m = re.search(r'TEST FAILED AT\s+([\d.]+)\s*ns', content)
    if m:
        info['time_ns'] = m.group(1)
    
    m = re.search(r'FAILING SIGNAL\s*:\s*(\w+)', content, re.IGNORECASE)
    if m:
        info['failing_signal'] = m.group(1)
    
    m = re.search(r'ERROR DETAILS\s*:\s*(.+)', content, re.IGNORECASE)
    if m:
        info['details'] = m.group(1).strip()
    
    # Try to parse expected/actual from details
    details = info.get('details', '')
    
    # Pattern: "Expected X to be VALUE, got VALUE"
    m = re.search(r'Expected\s+\w+\s+to be\s+(\S+),?\s+[Gg]ot\s+(\S+)', details)
    if m:
        info['expected'] = m.group(1).rstrip(',')
        info['actual'] = m.group(2).rstrip(',')
    
    # Pattern: "Expected Data=VALUE, Got VALUE" or "Expected VALUE, Got VALUE"
    if 'expected' not in info:
        m = re.search(r'Expected\s+(?:\w+=)?(\S+),?\s+[Gg]ot\s+(\S+)', details)
        if m:
            info['expected'] = m.group(1).rstrip(',')
            info['actual'] = m.group(2).rstrip(',')
    
    # Pattern: "Expected 0xABC..., Got 0xDEF..."
    if 'expected' not in info:
        m = re.search(r'Expected\s+(0x[0-9a-fA-F]+),?\s+[Gg]ot\s+(0x[0-9a-fA-F]+)', details)
        if m:
            info['expected'] = m.group(1)
            info['actual'] = m.group(2)
    
    return info


def _compute_numerical_analysis(expected_str, actual_str):
    """Compute numerical relationship between expected and actual values.
    
    Returns a list of analysis strings.
    """
    analysis = []
    
    # Parse values
    def parse_val(s):
        s = s.strip().rstrip(',')
        if s.startswith('0x') or s.startswith('0X'):
            return int(s, 16)
        try:
            return int(s)
        except ValueError:
            return None
    
    exp = parse_val(expected_str)
    act = parse_val(actual_str)
    
    if exp is None or act is None:
        return analysis
    
    # Basic relationship
    if exp != 0 and act != 0:
        if act == exp * 2:
            analysis.append(f"CLUE: Actual is EXACTLY 2x Expected → look for extra *2 or <<1")
        elif act == exp // 2 and exp % 2 == 0:
            analysis.append(f"CLUE: Actual is EXACTLY half of Expected → look for extra >>1 or missing <<1")
        elif act == exp + 1:
            analysis.append(f"CLUE: Actual is Expected+1 → look for off-by-one (>= vs >, <= vs <)")
        elif act == exp - 1:
            analysis.append(f"CLUE: Actual is Expected-1 → look for off-by-one")
        elif act == ~exp & ((1 << max(exp.bit_length(), act.bit_length())) - 1):
            analysis.append(f"CLUE: Actual is bitwise NOT of Expected → look for extra/missing ~ or !")
        elif exp == 0 and act != 0:
            analysis.append(f"CLUE: Expected 0 but got non-zero → signal incorrectly asserted")
        elif act == 0 and exp != 0:
            analysis.append(f"CLUE: Expected non-zero but got 0 → signal not asserted when it should be")
    
    # XOR analysis for bitwise ops
    if exp >= 0 and act >= 0:
        xor_val = exp ^ act
        if xor_val > 0:
            bit_width = max(exp.bit_length(), act.bit_length(), 1)
            differing_bits = []
            for b in range(bit_width):
                if xor_val & (1 << b):
                    differing_bits.append(b)
            
            # Check if this looks like an & vs | swap
            and_result = exp & act
            or_result = exp | act
            
            if len(differing_bits) <= 8:
                analysis.append(f"Bits that differ: {differing_bits}")
            
            if or_result == act and exp != act:
                analysis.append(f"STRONG CLUE: a|b would produce the actual output → operator should be & not |")
            elif and_result == act and exp != act:
                analysis.append(f"STRONG CLUE: a&b would produce the actual output → operator should be | not &")
    
    # Ratio analysis
    if exp != 0:
        ratio = act / exp
        if abs(ratio - 3) < 0.01:
            analysis.append(f"CLUE: Actual ≈ 3x Expected → look for extra *3")
        elif abs(ratio - 0.5) < 0.01:
            analysis.append(f"CLUE: Actual ≈ 0.5x Expected → look for missing factor or extra >>1")
    
    return analysis


def summarize_vcd(trimmed_vcd_path, error_timestamp_path=None, max_cycles=3, char_budget=3000):
    """Create an ultra-compact, LLM-optimized failure analysis.
    
    Strategy:
      1. Parse the error symptom for structured expected/actual values
      2. Show ONLY 2-3 cycles (not 5+) — just enough for the LLM to see context
      3. Pre-compute numerical analysis (XOR diff, operator hints)
      4. Always include a failure snapshot with hex-converted values
    
    Args:
        trimmed_vcd_path: Path to the trimmed trace produced by trimmer.py
        error_timestamp_path: Path to error_timestamp.txt for structured analysis
        max_cycles: Max cycles to include (default 3)
        char_budget: Maximum character count for output
    
    Returns:
        str: Compact failure analysis text, or empty string if no data.
    """
    # ── Parse error_timestamp for expected/actual ─────────────────────────
    error_info = _parse_error_timestamp(error_timestamp_path) if error_timestamp_path else {}
    
    lines = []
    
    # ── Section 1: Numerical Analysis (highest value) ────────────────────
    if 'expected' in error_info and 'actual' in error_info:
        exp_str = error_info['expected']
        act_str = error_info['actual']
        
        analysis = _compute_numerical_analysis(exp_str, act_str)
        if analysis:
            lines.append("--- NUMERICAL ANALYSIS ---")
            lines.append(f"Expected: {exp_str}")
            lines.append(f"Actual:   {act_str}")
            for hint in analysis:
                lines.append(f"  → {hint}")
            lines.append("")
    
    # ── Section 2: Compact Signal Snapshot ────────────────────────────────
    if not trimmed_vcd_path or not os.path.exists(trimmed_vcd_path):
        return "\n".join(lines) if lines else ""
    
    cycles = parse_trimmed_vcd(trimmed_vcd_path)
    if not cycles:
        return "\n".join(lines) if lines else ""
    
    # Take only the last max_cycles
    cycles = cycles[-max_cycles:]
    
    # Show the failure snapshot (last cycle) with clean hex values
    last_cycle = cycles[-1]
    lines.append(f"--- SIGNAL VALUES AT FAILURE (t={last_cycle['time']}ns) ---")
    for sig in sorted(last_cycle["signals"].keys()):
        short = _strip_module_prefix(sig)
        hex_val = _bin_to_hex(last_cycle["signals"][sig])
        lines.append(f"  {short} = {hex_val}")
    
    # If we have preceding cycles, show ONE delta summary
    if len(cycles) > 1:
        prev = cycles[-2]
        changes = {}
        for sig in sorted(last_cycle["signals"].keys()):
            new_val = last_cycle["signals"][sig]
            old_val = prev["signals"].get(sig, None)
            if new_val != old_val:
                changes[sig] = (_bin_to_hex(old_val) if old_val else "?", _bin_to_hex(new_val))
        
        if changes:
            lines.append(f"\nSignals that CHANGED in the last cycle:")
            for sig in sorted(changes.keys()):
                short = _strip_module_prefix(sig)
                old, new = changes[sig]
                lines.append(f"  {short}: {old} → {new}")
    
    result = "\n".join(lines)
    
    # Enforce budget
    if len(result) > char_budget:
        result = result[:char_budget - 50] + "\n... [TRUNCATED]"
    
    return result


def save_compact_vcd(trimmed_vcd_path, output_path, error_timestamp_path=None,
                     max_cycles=3, char_budget=3000):
    """Summarize and save to disk."""
    summary = summarize_vcd(trimmed_vcd_path, error_timestamp_path=error_timestamp_path,
                            max_cycles=max_cycles, char_budget=char_budget)
    if summary:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(summary)
        print(f"Compact VCD summary saved to: {output_path} ({len(summary)} chars)")
    else:
        print(f"Warning: No VCD data to summarize from {trimmed_vcd_path}")
    return summary


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 2:
        ts_path = sys.argv[2] if len(sys.argv) > 2 else None
        print(summarize_vcd(sys.argv[1], error_timestamp_path=ts_path))
    else:
        print("Usage: vcd_summarizer.py <trimmed_vcd_path> [error_timestamp_path]")
