import os
import random
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

error_dir = os.environ.get("ERROR_DIR", "error_design_default") #pass through from top script
error_designs_dir = "../Error_designs/"
# ============================================================
# Constants
# ============================================================
N = 12


# ============================================================
# Error helpers
# ============================================================

def report_error(msg, signal_name, file_path):
    """Formats, prints, and writes a highly visible error banner to a file, then fails."""
    current_time = cocotb.utils.get_sim_time('ns')
    error_banner = (
        f"\n{'='*65}\n"
        f"TEST FAILED AT {current_time} ns\n"
        f"FAILING SIGNAL : {signal_name}\n"
        f"ERROR DETAILS  : {msg}\n"
        f"{'='*65}\n"
    )
    
    # Write the error banner to the specified file path
    try:
        with open(file_path, 'a') as f:
            f.write(error_banner)
    except IOError as e:
        cocotb.log.error(f"Could not write error to file {file_path}: {e}")

    # Log to console and fail the test
    cocotb.log.error(error_banner)
    assert False, f"Signal '{signal_name}' failed."


def check_no_xz(value, name, file_path):
    if 'x' in str(value).lower() or 'z' in str(value).lower():
        report_error(f"{name} has X/Z: {value}", name, file_path)


# ============================================================
# Apply operation
# ============================================================

async def run_add(dut, a, b):

    dut.in1_svm.value = a
    dut.in2_svm.value = b
    dut.start.value = 1

    await RisingEdge(dut.clk)

    dut.start.value = 0

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    return (
        int(dut.out.value),
        int(dut.inf.value),
        int(dut.zero.value),
        int(dut.done.value)
    )


# ============================================================
# Main Test
# ============================================================

@cocotb.test()
async def posit_add_tb(dut):

    dut._log.info("==== POSIT ADD TEST START ====")

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    out_dir = os.path.join(error_designs_dir, error_dir)
    os.makedirs(out_dir, exist_ok=True)
    log_file_path = os.path.join(out_dir, os.path.basename(__file__).replace("test_", "").replace(".py", ".log"))
    err_file = os.path.join(out_dir, "error_timestamp.txt")

    log_file = open(log_file_path, "w")
    open(err_file, "w").close()

    # --------------------------------------------------
    # INIT
    # --------------------------------------------------
    dut.start.value = 0
    dut.in1_svm.value = 0
    dut.in2_svm.value = 0

    await Timer(20, unit="ns")

    # --------------------------------------------------
    # TEST 1: ZERO + ZERO
    # --------------------------------------------------
    out, inf, zero, done = await run_add(dut, 0x000, 0x000)

    if zero != 1:
        report_error("Zero flag not set", "zero", err_file)

    # --------------------------------------------------
    # TEST 2: INF cases
    # --------------------------------------------------
    inf_val = (1 << (N-1))  # MSB=1, rest 0 → inf pattern

    out, inf, zero, done = await run_add(dut, inf_val, 0x123)

    if inf != 1:
        report_error("INF not detected", "inf", err_file)

    # --------------------------------------------------
    # TEST 3: SIMPLE VALUES
    # --------------------------------------------------
    test_vectors = [
        (0x100, 0x100),
        (0x200, 0x100),
        (0x050, 0x020),
        (0x300, 0x100),
    ]

    for a, b in test_vectors:
        out, inf, zero, done = await run_add(dut, a, b)

        check_no_xz(dut.out.value, "out", err_file)

        # Symmetry check
        out2, _, _, _ = await run_add(dut, b, a)

        if out != out2:
            report_error("Addition not commutative", "out", err_file)

    # --------------------------------------------------
    # TEST 4: SIGNED BEHAVIOR
    # --------------------------------------------------
    for _ in range(10):
        a = random.getrandbits(N)
        b = random.getrandbits(N)

        out, inf, zero, done = await run_add(dut, a, b)

        check_no_xz(dut.out.value, "out", err_file)

    # --------------------------------------------------
    # TEST 5: RANDOM STRESS
    # --------------------------------------------------
    dut._log.info("Running random tests")

    for i in range(50):
        a = random.getrandbits(N)
        b = random.getrandbits(N)

        out, inf, zero, done = await run_add(dut, a, b)

        if done != 1:
            report_error("Done not asserted", "done", err_file)

        check_no_xz(dut.out.value, "out", err_file)

    # --------------------------------------------------
    # TEST 6: STABILITY CHECK
    # --------------------------------------------------
    dut._log.info("Checking output stability")

    a = 0x120
    b = 0x220

    out1, _, _, _ = await run_add(dut, a, b)

    await RisingEdge(dut.clk)
    out2 = int(dut.out.value)

    if out1 != out2:
        report_error("Output not stable", "out", err_file)

    dut._log.info("==== POSIT ADD TEST PASSED ====")