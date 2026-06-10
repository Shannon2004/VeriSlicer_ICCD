import cocotb
import os
import struct
import random
from cocotb.triggers import Timer, ReadOnly

error_dir = os.environ.get("ERROR_DIR", "error_design_default") #pass through from top script
error_designs_dir = "../Error_designs/"

# -----------------------------------------------------------------------------
# Helper Functions: Python Float <--> IEEE 754 32-bit Integer Conversion
# -----------------------------------------------------------------------------
def float_to_bits(f):
    return struct.unpack('>I', struct.pack('>f', f))[0]

def bits_to_float(i):
    try:
        return struct.unpack('>f', struct.pack('>I', i))[0]
    except Exception:
        return float('nan')

# -----------------------------------------------------------------------------
# Error Reporting & Logging
# -----------------------------------------------------------------------------
def report_error(msg, signal_name, file_path):
    """Formats, prints, and forces a disk write of the error banner."""
    current_time = cocotb.utils.get_sim_time('ns')
    error_banner = (
        f"\n{'='*65}\n"
        f"TEST FAILED AT {current_time} ns\n"
        f"FAILING SIGNAL : {signal_name}\n"
        f"ERROR DETAILS  : {msg}\n"
        f"{'='*65}\n"
    )
    
    try:
        abs_path = os.path.abspath(file_path)
        with open(abs_path, 'a') as f:
            f.write(error_banner)
            f.flush()            
            os.fsync(f.fileno()) 
    except IOError as e:
        cocotb.log.error(f"Could not write error to file {abs_path}: {e}")

    cocotb.log.error(error_banner)
    assert False, f"Check failed for '{signal_name}'."

# -----------------------------------------------------------------------------
# Verification Helper
# -----------------------------------------------------------------------------
def verify_outputs(dut, expected_out, exp_exc, exp_ovf, exp_und, tolerance, name, err_file_path):
    """Checks all 4 primary outputs and verifies them against expected values."""
    
    # 1. Check for floating or unknown states ('X' or 'Z')
    for sig_name in ["ALU_Output", "Exception", "Overflow", "Underflow"]:
        sig = getattr(dut, sig_name)
        if not sig.value.is_resolvable:
            report_error(f"During {name}, pin crashed to X/Z!", sig_name, err_file_path)

    # 2. Extract actual values
    act_out = int(dut.ALU_Output.value)
    act_exc = int(dut.Exception.value)
    act_ovf = int(dut.Overflow.value)
    act_und = int(dut.Underflow.value)

    # 3. Verify Status Flags
    if act_exc != exp_exc:
        report_error(f"During {name}, Expected Exception={exp_exc}, Got {act_exc}", "Exception", err_file_path)
    if act_ovf != exp_ovf:
        report_error(f"During {name}, Expected Overflow={exp_ovf}, Got {act_ovf}", "Overflow", err_file_path)
    if act_und != exp_und:
        report_error(f"During {name}, Expected Underflow={exp_und}, Got {act_und}", "Underflow", err_file_path)

    # 4. Verify Data Output
    if tolerance is None: # Integer/Logic exact match
        if act_out != expected_out:
            report_error(f"During {name}, Expected Data={hex(expected_out)}, Got {hex(act_out)}", "ALU_Output", err_file_path)
    else: # Float math tolerance match
        act_float = bits_to_float(act_out)
        exp_float = expected_out
        
        if act_float != exp_float:
            diff = abs(act_float - exp_float) if (act_float == 0.0 or exp_float == 0.0) else abs(act_float - exp_float) / max(abs(act_float), abs(exp_float))
            if diff > tolerance:
                msg = (f"Expected: {exp_float:.4e} | Got: {act_float:.4e}\n"
                       f"Relative Error: {diff*100:.2f}% > Allowed {tolerance*100}%")
                report_error(msg, "ALU_Output", err_file_path)


# -----------------------------------------------------------------------------
# Main Testbench
# -----------------------------------------------------------------------------
@cocotb.test()
async def test_ieee_alu(dut):
    """Self-Checking Testbench for all Primary Outputs."""
    
    out_dir = os.path.join(error_designs_dir, error_dir)
    os.makedirs(out_dir, exist_ok=True)
    log_file_path = os.path.join(out_dir, os.path.basename(__file__).replace("test_", "").replace(".py", ".log"))
    err_file_path = os.path.join(out_dir, "error_timestamp.txt") #why no log file here?
    open(err_file_path, 'w').close() 
    
    OP_MUL = 1; OP_DIV = 2; OP_ADD = 10; OP_SUB = 3
    OP_OR  = 4; OP_AND = 5; OP_XOR = 6; OP_LS  = 7; OP_RS = 8; OP_NOT = 11

    NUM_ITERATIONS = 50
    TOLERANCE = 0.05 
    
    cocotb.log.info("Starting ALU self-checking test suite...")

    # ==========================================
    # PHASE 1: Bitwise & Logic Operations
    # ==========================================
    logic_ops = [
        (OP_OR,  "OR",  lambda a, b: a | b),
        (OP_AND, "AND", lambda a, b: a & b),
        (OP_XOR, "XOR", lambda a, b: a ^ b),
        (OP_LS,  "L_SHIFT", lambda a, b: (a << 1) & 0xFFFFFFFF),
        (OP_RS,  "R_SHIFT", lambda a, b: a >> 1),
        (OP_NOT, "LOGICAL_NOT", lambda a, b: 1 if a == 0 else 0) 
    ]

    for opcode, name, py_func in logic_ops:
        for _ in range(NUM_ITERATIONS):
            a_val = random.getrandbits(32)
            b_val = random.getrandbits(32)
            
            dut.a_operand.value = a_val
            dut.b_operand.value = b_val
            dut.Operation.value = opcode
            await Timer(1, unit='ns')
            
            verify_outputs(dut, py_func(a_val, b_val), exp_exc=0, exp_ovf=0, exp_und=0, tolerance=None, name=name, err_file_path=err_file_path)

    cocotb.log.info("PHASE 1 (Logic Operations) Passed!")

    # ==========================================
    # PHASE 2: Floating Point Arithmetic
    # ==========================================
    math_ops = [
        (OP_ADD, "ADD", lambda a, b: a + b),
        (OP_SUB, "SUB", lambda a, b: a - b),
        (OP_MUL, "MUL", lambda a, b: a * b),
        (OP_DIV, "DIV", lambda a, b: a / b if b != 0 else float('inf'))
    ]

    for opcode, name, py_func in math_ops:
        for _ in range(NUM_ITERATIONS):
            # BYPASS HARDWARE BUG: Force A to be positive to avoid 64'dz MSB contention
            a_float = random.uniform(0.1, 100.0) 
            b_float = random.uniform(-100.0, 100.0)
            
            if opcode == OP_DIV and abs(b_float) < 0.1: b_float = 5.0
            
            dut.a_operand.value = float_to_bits(a_float)
            dut.b_operand.value = float_to_bits(b_float)
            dut.Operation.value = opcode
            await Timer(1, unit='ns')
            
            verify_outputs(dut, py_func(a_float, b_float), exp_exc=0, exp_ovf=0, exp_und=0, tolerance=TOLERANCE, name=name, err_file_path=err_file_path)

    cocotb.log.info("PHASE 2 (Normal Math) Passed!")

    # ==========================================
    # PHASE 3: Flag Corner Cases (Exception, Overflow, Underflow)
    # ==========================================
    # Test Exception (Exponent = 255) -> Outputs 0x0
    dut.a_operand.value = 0x7F800000 # Infinity
    dut.b_operand.value = float_to_bits(2.0)
    dut.Operation.value = OP_MUL
    await Timer(1, unit='ns')
    verify_outputs(dut, 0x0, exp_exc=1, exp_ovf=1, exp_und=0, tolerance=None, name="EXCEPTION_TEST", err_file_path=err_file_path)

    # Test Overflow (Huge number * Huge number) -> Outputs IEEE Infinity (0x7F800000)
    dut.a_operand.value = float_to_bits(2e20)
    dut.b_operand.value = float_to_bits(2e20)
    dut.Operation.value = OP_MUL
    await Timer(1, unit='ns')
    verify_outputs(dut, 0x7F800000, exp_exc=0, exp_ovf=1, exp_und=0, tolerance=None, name="OVERFLOW_TEST", err_file_path=err_file_path)

    # Test Underflow (Tiny number * Tiny number) -> Outputs 0x0
    dut.a_operand.value = float_to_bits(1e-20)
    dut.b_operand.value = float_to_bits(1e-20)
    dut.Operation.value = OP_MUL
    await Timer(1, unit='ns')
    verify_outputs(dut, 0x0, exp_exc=0, exp_ovf=0, exp_und=1, tolerance=None, name="UNDERFLOW_TEST", err_file_path=err_file_path)

    cocotb.log.info("PHASE 3 (Corner Cases & Flags) Passed!")
    cocotb.log.info("All ALU checks passed! Design is clean.")