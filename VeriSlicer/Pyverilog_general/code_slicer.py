import os
import re

# ---------------------------------------------------------------------------
# Signals too ubiquitous to be useful as weak "mentioned" triggers.
# Only included when they appear on the LHS (declared or assigned).
# ---------------------------------------------------------------------------
UBIQUITOUS = {'clk', 'rst', 'reset', 'clock', 'rst_n', 'reset_n', 'clk_i', 'vcc', 'gnd'}

# ---------------------------------------------------------------------------
# Hardcoded active `ifdef macros per design (from the design .v headers).
# Design 1 (CORDIC): RADIAN_16, PIPELINE, ROTATE, GENERATE_LOOP
# Designs 2-6: No ifdef directives.
# ---------------------------------------------------------------------------
DESIGN_IFDEFS = {
    'design_1': {
        'RADIAN_16', 'PIPELINE', 'ROTATE', 'GENERATE_LOOP',
        'XY_BITS', 'THETA_BITS', 'ITERATIONS', 'ITERATION_BITS',
        'CORDIC_GAIN', 'CORDIC_1',
    },
    # Designs 2-6 have no ifdefs
}


# ===========================================================================
# 0.  Ifdef preprocessor  —  strips dead conditional branches
# ===========================================================================

def preprocess_ifdefs(lines, design_name):
    """
    Strip dead `ifdef / `ifndef / `else / `endif branches.
    
    Only active for designs that have hardcoded macro definitions in
    DESIGN_IFDEFS.  For other designs, returns lines unchanged.
    """
    active_macros = DESIGN_IFDEFS.get(design_name)
    if not active_macros:
        return lines          # no ifdefs to process

    result = []
    # Stack tracks (emit_current_branch, has_emitted_a_branch)
    # emit_current_branch = True means we are inside an active branch
    stack = [(True, False)]   # base level: always emit

    for line in lines:
        stripped = line.strip()

        # `ifdef MACRO
        m = re.match(r'^`ifdef\s+(\w+)', stripped)
        if m:
            macro = m.group(1)
            parent_emitting = stack[-1][0]
            this_branch_active = parent_emitting and (macro in active_macros)
            stack.append((this_branch_active, this_branch_active))
            continue          # don't emit the directive line itself

        # `ifndef MACRO
        m = re.match(r'^`ifndef\s+(\w+)', stripped)
        if m:
            macro = m.group(1)
            parent_emitting = stack[-1][0]
            this_branch_active = parent_emitting and (macro not in active_macros)
            stack.append((this_branch_active, this_branch_active))
            continue

        # `else
        if stripped == '`else':
            if len(stack) > 1:
                _, has_emitted = stack[-1]
                parent_emitting = stack[-2][0] if len(stack) >= 2 else True
                # Emit else branch only if parent is emitting AND no branch has emitted yet
                new_emit = parent_emitting and not has_emitted
                stack[-1] = (new_emit, has_emitted or new_emit)
            continue

        # `endif
        if stripped == '`endif':
            if len(stack) > 1:
                stack.pop()
            continue

        # Normal line: emit if current branch is active
        if stack[-1][0]:
            result.append(line)

    return result


# ===========================================================================
# 0b.  Repetition compressor  —  collapses structurally identical runs
# ===========================================================================

def compress_repetitions(output_lines, threshold=5):
    """
    When >threshold consecutive lines in the output are structurally
    identical (differ only in numeric constants), collapse them to:
      first_line
      ... [N similar lines omitted for brevity] ...
      last_line
    
    Takes and returns a list of (line_number, content) tuples.
    """
    if not output_lines:
        return output_lines

    # Structural signature: replace all numbers with '#'
    def signature(content):
        return re.sub(r'\d+', '#', content.strip())

    # First pass: single-line compression
    result = []
    run_start = 0

    while run_start < len(output_lines):
        sig = signature(output_lines[run_start][1])
        run_end = run_start + 1

        while run_end < len(output_lines) and signature(output_lines[run_end][1]) == sig:
            run_end += 1

        run_len = run_end - run_start

        if run_len > threshold:
            # Keep first 2 and last 2, collapse the middle
            result.append(output_lines[run_start])
            result.append(output_lines[run_start + 1])
            omitted = run_len - 4
            result.append((-1, f"      ... [{omitted} similar lines omitted for brevity] ...\n"))
            result.append(output_lines[run_end - 2])
            result.append(output_lines[run_end - 1])
        else:
            for i in range(run_start, run_end):
                result.append(output_lines[i])

        run_start = run_end

    # Second pass: multi-line block compression
    # Detect repeating blocks of size 2-4 lines with same structural pattern
    for block_size in [4, 3, 2]:
        new_result = []
        i = 0
        while i < len(result):
            # Try to match a block of block_size lines, repeated >threshold times
            if i + block_size <= len(result):
                block_sig = tuple(signature(result[j][1]) for j in range(i, i + block_size))
                run_count = 1
                pos = i + block_size
                while pos + block_size <= len(result):
                    next_sig = tuple(signature(result[j][1]) for j in range(pos, pos + block_size))
                    if next_sig == block_sig:
                        run_count += 1
                        pos += block_size
                    else:
                        break
                
                if run_count > threshold // block_size + 1 and run_count > 2:
                    # Compress: keep first block, omission note, last block
                    for j in range(i, i + block_size):
                        new_result.append(result[j])
                    omitted_blocks = run_count - 2
                    new_result.append((-1, f"      ... [{omitted_blocks} similar blocks omitted] ...\n"))
                    for j in range(pos - block_size, pos):
                        new_result.append(result[j])
                    i = pos
                    continue
            
            new_result.append(result[i])
            i += 1
        
        result = new_result

    return result


# ===========================================================================
# 1.  Target extraction from pruned-graph file
# ===========================================================================

def load_targets(graph_path):
    """Extract base signal names from the pruned graph data."""
    targets = set()
    if not os.path.exists(graph_path):
        return targets
    with open(graph_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('=') or line.startswith('#'):
                continue
            if '->' in line:
                for part in line.split('->'):
                    targets.add(part.strip().split('.')[-1])
            else:
                targets.add(line.split('.')[-1])
    return targets


# ===========================================================================
# 2.  Low-level text utilities
# ===========================================================================

def strip_comments(line):
    """Remove // single-line comments."""
    return re.sub(r'//.*', '', line)


def next_real_line(lines, start):
    """
    Return the index of the next non-blank, non-comment-only line >= start.
    Returns len(lines) if none is found.
    """
    n = len(lines)
    i = start
    while i < n:
        if strip_comments(lines[i]).strip():
            return i
        i += 1
    return n


def has_stmt_semicolon(clean, initial_paren_depth=0):
    """
    Return True if `clean` contains a ';' that lies OUTSIDE parentheses.

    `initial_paren_depth` carries the running paren balance accumulated from
    previous lines (important for multi-line for-loop headers like
        for (i = 0;   <- opens paren, ';' is inside -> not a stmt terminator
             i < n;
             i = i+1)
    ).

    This prevents 'for (i=0; i<n; i=i+1)' from being mistaken for a
    statement end.
    """
    depth = initial_paren_depth
    for ch in clean:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif ch == ';' and depth <= 0:
            return True
    return False


# ===========================================================================
# 3.  Block-level parser
# ===========================================================================

def parse_verilog_blocks(lines):
    """
    Walk the source once and decompose it into logical Verilog blocks.

    Returns a list of dicts: {'start': int, 'end': int, 'type': str}

    Block types
    -----------
    module_header   – module ... ( ... );
    endmodule       – endmodule
    declaration     – input/output/wire/reg/localparam/parameter ...;
    assign          – assign lhs = rhs;
    always          – complete always block (ALL if/else/case branches)
    initial         – complete initial block
    generate        – generate ... endgenerate
    instantiation   – ModuleName inst_name ( ... );
    other           – anything else (stray lines, `directives, comments)
    """
    n = len(lines)
    blocks = []

    # ------------------------------------------------------------------
    # find_semicolon: first line at or after start_i containing ';'
    # ------------------------------------------------------------------
    def find_semicolon(start_i):
        j = start_i
        while j < n:
            if ';' in strip_comments(lines[j]):
                return j
            j += 1
        return n - 1

    # ------------------------------------------------------------------
    # find_close_paren_semi: first line containing ');'
    # ------------------------------------------------------------------
    def find_close_paren_semi(start_i):
        j = start_i
        while j < n:
            if ');' in strip_comments(lines[j]):
                return j
            j += 1
        return n - 1

    # ------------------------------------------------------------------
    # find_proc_body_end
    #
    # THE core routine.  Given that we are about to consume one complete
    # procedural statement/block, starting at line start_i, consume it
    # (including any trailing else/else-if chain) and return the index of
    # the last line.
    #
    # Handles correctly:
    #   • begin…end  (with arbitrary nesting)
    #   • case/casex/casez…endcase
    #   • if (cond) <body> [else if (cond) <body>]* [else <body>]
    #   • single statements ending with ';'
    #   • for/while headers whose parens contain ';' (Bug 4 fix)
    #   • all of the above mixed on single lines, e.g.
    #       always @(*) begin      ← begin on same line as sensitivity
    #       end else begin         ← else+begin on same line as end
    #       else if (en) begin     ← begin on same line as else if
    #
    # Design
    # ------
    # We use a single iterative loop with four state variables:
    #
    #   depth         – net open-block depth  (begin/case add, end/endcase sub)
    #   seen_any_block – True once we have opened at least one begin/case block
    #   paren_balance  – running '(' minus ')' count across lines, used to
    #                    distinguish ';' inside a for-header from a real
    #                    statement terminator
    #
    # A statement is complete when:
    #   (a) seen_any_block and depth drops back to 0   [block form]
    #   (b) not seen_any_block and a ';' outside parens is found  [simple form]
    #
    # After either completion, we peek at the next non-blank line.
    # If it starts with 'else', we:
    #   • set j to THAT LINE (not j+1 — Bug 3 fix)
    #   • reset depth/seen_any_block/paren_balance
    #   • continue the loop so the else-line's keywords are counted normally
    #     (this correctly handles 'else begin', 'else if (en) begin', etc.)
    # ------------------------------------------------------------------
    def find_proc_body_end(start_i):
        j = start_i
        depth = 0
        seen_any_block = False
        paren_balance = 0           # accumulated across lines for for-loop fix

        while j < n:
            j = next_real_line(lines, j)
            if j >= n:
                return n - 1

            clean = strip_comments(lines[j]).strip()
            old_depth = depth

            # ---- count block-structuring keywords -------------------------
            n_begin   = len(re.findall(r'\bbegin\b',            clean))
            n_end     = len(re.findall(r'\bend\b',              clean))
            n_case    = len(re.findall(r'\b(case|casex|casez)\b', clean))
            n_endcase = len(re.findall(r'\bendcase\b',          clean))

            depth += n_begin + n_case - n_end - n_endcase
            if depth < 0:
                depth = 0           # guard: tolerate minor malformations

            if n_begin + n_case > 0:
                seen_any_block = True

            # ---- update paren balance for for-loop ';' detection ----------
            paren_balance_before = paren_balance
            paren_balance += clean.count('(') - clean.count(')')

            # ---- check for completion ------------------------------------
            done = False
            if seen_any_block and old_depth > 0 and depth == 0:
                # A begin/case block just closed.
                done = True
            elif not seen_any_block and depth == 0:
                # Single-statement form: look for ';' outside parens.
                if has_stmt_semicolon(clean, paren_balance_before):
                    done = True

            if done:
                # Peek ahead for an else/else-if continuation.
                k = next_real_line(lines, j + 1)
                if k < n and re.match(r'\belse\b',
                                      strip_comments(lines[k]).strip()):
                    # BUG-3 FIX: jump to the else LINE ITSELF (not k+1).
                    # The loop will re-process line k, so any 'begin' or
                    # 'if' keyword on that line is counted correctly.
                    j = k
                    depth = 0
                    seen_any_block = False
                    paren_balance = 0
                    # Do NOT increment j here – 'continue' re-enters the loop
                    # and the first thing it does is next_real_line(j), which
                    # returns j itself (line k is non-blank).
                    continue
                else:
                    return j

            j += 1

        return n - 1

    # ------------------------------------------------------------------
    # find_always_end
    #
    # Consumes a complete always block:
    #   1. Skip past the @(sensitivity-list), which may span multiple lines.
    #   2. Call find_proc_body_end starting FROM THE SAME LINE j that ended
    #      the sensitivity list (not j+1) so that 'begin' on the same line
    #      as '@(...)' is counted. (Bug 1 & 2 fix.)
    # ------------------------------------------------------------------
    def find_always_end(start_i):
        j = start_i
        line0 = strip_comments(lines[j]).strip()

        # Consume @(...) sensitivity list (may span lines).
        if '@' in line0:
            at_text = line0[line0.index('@'):]
            paren_d = at_text.count('(') - at_text.count(')')
            while paren_d > 0 and j < n - 1:
                j += 1
                seg = strip_comments(lines[j])
                paren_d += seg.count('(') - seg.count(')')
        # else: always without @(...), e.g. 'always #10 clk = ~clk;'

        # BUG 1 & 2 FIX: start body search from j (not j+1).
        # If 'begin' sits on the same line as the closing ')', it is on
        # line j and must be counted by find_proc_body_end.
        return find_proc_body_end(j)

    # ------------------------------------------------------------------
    # find_matching_endgenerate: for generate...endgenerate blocks
    # ------------------------------------------------------------------
    def find_matching_endgenerate(start_i):
        j = start_i
        while j < n:
            if re.search(r'\bendgenerate\b', strip_comments(lines[j])):
                return j
            j += 1
        return n - 1

    # ==================================================================
    # Main parse loop
    # ==================================================================
    i = 0
    while i < n:
        stripped = strip_comments(lines[i]).strip()

        # Skip blank / pure-comment lines
        if not stripped:
            i += 1
            continue

        # ---- module header ----------------------------------------
        if re.match(r'\bmodule\b', stripped):
            end = find_semicolon(i)
            blocks.append({'start': i, 'end': end, 'type': 'module_header'})
            i = end + 1
            continue

        # ---- endmodule -------------------------------------------
        if re.match(r'\bendmodule\b', stripped):
            blocks.append({'start': i, 'end': i, 'type': 'endmodule'})
            i += 1
            continue

        # ---- always block ----------------------------------------
        if re.match(r'\balways\b', stripped):
            end = find_always_end(i)
            blocks.append({'start': i, 'end': end, 'type': 'always'})
            i = end + 1
            continue

        # ---- initial block ---------------------------------------
        if re.match(r'\binitial\b', stripped):
            # Same fix as find_always_end: start from i (not i+1) so
            # 'initial begin' on one line has its 'begin' counted.
            end = find_proc_body_end(i)
            blocks.append({'start': i, 'end': end, 'type': 'initial'})
            i = end + 1
            continue

        # ---- generate block --------------------------------------
        if re.match(r'\bgenerate\b', stripped):
            end = find_matching_endgenerate(i)
            blocks.append({'start': i, 'end': end, 'type': 'generate'})
            i = end + 1
            continue

        # ---- continuous assignment --------------------------------
        if re.match(r'\bassign\b', stripped):
            end = find_semicolon(i)
            blocks.append({'start': i, 'end': end, 'type': 'assign'})
            i = end + 1
            continue

        # ---- port / signal declarations --------------------------
        if re.match(r'(input|output|inout|wire|reg|integer|'
                    r'localparam|parameter)\b', stripped):
            end = find_semicolon(i)
            blocks.append({'start': i, 'end': end, 'type': 'declaration'})
            i = end + 1
            continue

        # ---- module instantiation --------------------------------
        # Heuristic: <TypeName> [#(...)] <InstName> (  ...  );
        if (re.match(r'\w+\s+(?:#\s*\(.*?\)\s*)?\w+\s*\(', stripped) or
                re.match(r'\w+\s*#\s*\(', stripped)):
            end = find_close_paren_semi(i)
            blocks.append({'start': i, 'end': end, 'type': 'instantiation'})
            i = end + 1
            continue

        # ---- compiler directives (`define / `ifdef / …) ----------
        if stripped.startswith('`'):
            blocks.append({'start': i, 'end': i, 'type': 'other'})
            i += 1
            continue

        # ---- fallback --------------------------------------------
        blocks.append({'start': i, 'end': i, 'type': 'other'})
        i += 1

    return blocks


# ===========================================================================
# 4.  Per-block signal relevance checkers
# ===========================================================================

def _driven_targets(lines, start, end, targets):
    """
    Return the subset of *targets* that are driven (LHS) in lines[start..end].

    Joins the full block text so multi-line assignments work correctly.
    Recognises:
      • Continuous:    assign <t>[bits] = ...
      • Non-blocking:  <t>[bits] <= ...
      • Blocking:      <t>[bits]  = ...  (not ==, !=, >=)
    """
    full_text = ''.join(strip_comments(lines[i]) for i in range(start, end + 1))
    driven = set()
    for t in targets:
        te = re.escape(t)
        if re.search(rf'\bassign\s+{te}\b\s*(?:\[[\s\S]*?\])?\s*=(?!=)',
                     full_text):
            driven.add(t)
            continue
        if re.search(rf'\b{te}\b\s*(?:\[[\s\S]*?\])?\s*<=', full_text):
            driven.add(t)
            continue
        if re.search(rf'\b{te}\b\s*(?:\[[\s\S]*?\])?\s*(?<![=!<>])=(?!=)',
                     full_text):
            driven.add(t)
    return driven


def _declared_targets(lines, start, end, targets):
    """Return targets declared (input/output/wire/reg/…) in the range."""
    decl_kw = r'\b(input|output|inout|wire|reg|integer|localparam|parameter)\b'
    declared = set()
    for i in range(start, end + 1):
        if re.search(decl_kw, lines[i]):
            for t in targets:
                if re.search(rf'\b{re.escape(t)}\b', lines[i]):
                    declared.add(t)
    return declared


def _mentioned_targets(lines, start, end, targets):
    """Return non-ubiquitous targets mentioned anywhere in the range."""
    mentioned = set()
    for i in range(start, end + 1):
        clean = strip_comments(lines[i])
        for t in targets:
            if t not in UBIQUITOUS and re.search(rf'\b{re.escape(t)}\b', clean):
                mentioned.add(t)
    return mentioned


# ===========================================================================
# 5.  Main slicer
# ===========================================================================

def slice_verilog(v_path, targets, output_path, design_name=None):
    """
    Include a block in the output when it:
      • is a module boundary               (always)
      • declares a target signal
      • drives  a target on the LHS       (always / initial / assign)
      • mentions a non-ubiquitous target  (RHS of assign / instantiation / generate)

    Entire syntactic blocks are always emitted – never partial fragments.
    Preprocesses ifdef blocks and compresses repetitive patterns.
    """
    if not os.path.exists(v_path):
        print(f"Error: {v_path} not found.")
        return

    with open(v_path, 'r') as f:
        raw_lines = f.readlines()

    # ---- Ifdef preprocessing (strip dead branches) --------------------
    if design_name:
        processed_lines = preprocess_ifdefs(raw_lines, design_name)
    else:
        processed_lines = raw_lines

    # Build line-number mapping: processed index → original line number
    # We need this because the LLM must see original line numbers.
    orig_line_map = {}      # processed_idx → original 0-based line number
    if design_name and design_name in DESIGN_IFDEFS:
        # Match processed lines back to original positions
        proc_idx = 0
        for orig_idx, orig_line in enumerate(raw_lines):
            if proc_idx >= len(processed_lines):
                break
            if orig_line == processed_lines[proc_idx]:
                orig_line_map[proc_idx] = orig_idx
                proc_idx += 1
    else:
        # No preprocessing: identity mapping
        for i in range(len(processed_lines)):
            orig_line_map[i] = i

    lines = processed_lines
    blocks = parse_verilog_blocks(lines)
    keep_lines = set()

    for b in blocks:
        s, e, btype = b['start'], b['end'], b['type']

        if btype in ('module_header', 'endmodule'):
            keep_lines.update(range(s, e + 1))

        elif btype == 'declaration':
            if _declared_targets(lines, s, e, targets):
                keep_lines.update(range(s, e + 1))

        elif btype in ('always', 'initial'):
            # Include if drives OR mentions any target (broader inclusion)
            if _driven_targets(lines, s, e, targets) or _mentioned_targets(lines, s, e, targets):
                keep_lines.update(range(s, e + 1))

        elif btype == 'assign':
            # Include if drives a target OR mentions a target on RHS
            # This catches cases like: assign AND_Output = ... a_operand ...
            # where AND_Output isn't in the graph but a_operand is.
            if _driven_targets(lines, s, e, targets) or _mentioned_targets(lines, s, e, targets):
                keep_lines.update(range(s, e + 1))

        elif btype in ('instantiation', 'generate'):
            if _mentioned_targets(lines, s, e, targets):
                keep_lines.update(range(s, e + 1))

        # 'other' blocks intentionally skipped

    # ---- noise patterns to strip (simulation-only, not synthesizable) --
    _SIM_NOISE = re.compile(
        r'\$display\b|\$write\b|\$monitor\b|\$strobe\b|\$fwrite\b', re.IGNORECASE
    )

    # ---- collect output lines with original line numbers ---------------
    output_lines = []
    for i in sorted(keep_lines):
        if i >= len(lines):
            continue
        line_content = lines[i]
        clean = strip_comments(line_content).strip()

        # Skip simulation-only noise lines
        if _SIM_NOISE.search(clean):
            continue

        # Skip pure blank lines
        if not clean:
            continue

        # Get original line number (1-indexed)
        orig_num = orig_line_map.get(i, i) + 1
        output_lines.append((orig_num, line_content))

    # ---- compress repetitive patterns ----------------------------------
    output_lines = compress_repetitions(output_lines, threshold=5)

    # ---- write output ------------------------------------------------
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        f.write("--- SLICED VERILOG CODE ---\n")
        f.write(f"--- Extracted from {os.path.basename(v_path)} ---\n\n")

        last_num = -100
        for line_num, content in output_lines:
            if line_num == -1:
                # Compression marker
                f.write(content)
            else:
                if line_num - last_num > 1 and last_num > 0:
                    f.write("...\n")
                f.write(f"{line_num:4d}: {content}")
                last_num = line_num

    print(f"Success! Sliced code saved to: {output_path}")


# ===========================================================================
# 6.  Debug helper
# ===========================================================================

def debug_blocks(v_path, graph_path):
    """Print detected block structure and which targets each block drives."""
    targets = load_targets(graph_path)
    with open(v_path, 'r') as f:
        lines = f.readlines()

    blocks = parse_verilog_blocks(lines)
    print(f"\n{'START':>6}  {'END':>6}  {'TYPE':<16}  RELEVANT TARGETS")
    print("-" * 72)
    for b in blocks:
        s, e, btype = b['start'], b['end'], b['type']
        if btype in ('always', 'initial', 'assign'):
            hits = _driven_targets(lines, s, e, targets)
        elif btype == 'declaration':
            hits = _declared_targets(lines, s, e, targets)
        elif btype in ('instantiation', 'generate'):
            hits = _mentioned_targets(lines, s, e, targets)
        else:
            hits = set()
        included = btype in ('module_header', 'endmodule') or bool(hits)
        marker = " ✓" if included else ""
        print(f"{s + 1:>6}  {e + 1:>6}  {btype:<16}  {sorted(hits)}{marker}")


# ===========================================================================
# 7.  Entry point
# ===========================================================================

def _extract_output_ports(v_path):
    """Extract output port names from the Verilog file header."""
    ports = set()
    if not os.path.exists(v_path):
        return ports
    with open(v_path, 'r') as f:
        for line in f:
            clean = strip_comments(line).strip()
            if re.match(r'\b(output)\b', clean):
                # Extract signal names from output declarations
                # Remove keywords, width specs, reg/wire
                clean = re.sub(r'\boutput\b|\breg\b|\bwire\b|\bsigned\b', '', clean)
                clean = re.sub(r'\[[^\]]*\]', '', clean)  # remove [N:M]
                clean = re.sub(r'[;,]', ' ', clean)
                for word in clean.split():
                    word = word.strip()
                    if word and re.match(r'^[a-zA-Z_]\w*$', word):
                        ports.add(word)
            # Stop after endmodule or a non-port declaration line
            if re.match(r'\b(always|assign|wire|reg|initial)\b', clean) and not re.match(r'\boutput\b', clean):
                break
    return ports


def run_slicer(v_path, graph_path, design_name, error_dir, failing_signal=None):
    """Main callable function for the framework loop.
    
    Args:
        failing_signal: If provided, added as a mandatory slicer target.
                       This ensures signals related to the failing output
                       are always included in the sliced code.
    """
    targets = load_targets(graph_path)
    
    # Add the failing signal (and its base name) as a target
    if failing_signal:
        targets.add(failing_signal)
        # Also add without module prefix
        base = failing_signal.split('.')[-1]
        targets.add(base)
        print(f"  Added failing signal '{base}' to slicer targets.")
    
    # Also add all output ports from the design as targets.
    # This ensures the slicer includes any assign block that feeds an output,
    # even if Pyverilog's graph missed the dependency (common with high-Z muxes).
    output_ports = _extract_output_ports(v_path)
    if output_ports:
        for port in output_ports:
            targets.add(port)
        print(f"  Added {len(output_ports)} output ports to slicer targets: {sorted(output_ports)}")
    
    out_dir = os.path.join("sliced_code", design_name, error_dir)
    out_path = os.path.join(out_dir, "sliced_code.txt")
    if targets:
        slice_verilog(v_path, targets, out_path, design_name=design_name)
    else:
        print(f"Warning: No targets found in {graph_path}. Skipping.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 5:
        failing = sys.argv[5] if len(sys.argv) > 5 else None
        run_slicer(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], failing)
    elif len(sys.argv) == 4 and sys.argv[1] == '--debug':
        debug_blocks(sys.argv[2], sys.argv[3])
    else:
        print("Usage:")
        print("  Slice: code_slicer.py <verilog> <graph> <design_name> <error_dir> [failing_signal]")
        print("  Debug: code_slicer.py --debug  <verilog> <graph>")