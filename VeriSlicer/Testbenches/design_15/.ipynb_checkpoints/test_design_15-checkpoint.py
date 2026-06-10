import os
import random
import cocotb
from cocotb.triggers import Timer

error_dir = os.environ.get("ERROR_DIR", "error_design_default") #pass through from top script
error_designs_dir = "../Error_designs/"
# ============================================================
# Helpers
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
# Apply stimulus
# ============================================================

async def apply_inputs(dut, le_o, e_o, dsr, r_o, ls, inf, zero, start):
    dut.le_o.value = le_o
    dut.e_o_m.value = e_o
    dut.DSR_left_out.value = dsr
    dut.r_o_m.value = r_o
    dut.ls.value = ls
    dut.inf_final.value = inf
    dut.zero_final.value = zero
    dut.start0_m.value = start

    await Timer(1, unit="ns")

    return (
        int(dut.out_m.value),
        int(dut.done_m.value)
    )


# ============================================================
# Main Test
# ============================================================

@cocotb.test()
async def posit_encoder_tb(dut):

    dut._log.info("==== POSIT ENCODER TEST START ====")

    out_dir = os.path.join(error_designs_dir, error_dir)
    os.makedirs(out_dir, exist_ok=True)
    log_file_path = os.path.join(out_dir, os.path.basename(__file__).replace("test_", "").replace(".py", ".log"))
    err_file = os.path.join(out_dir, "error_timestamp.txt")

    log_file = open(log_file_path, "w")
    open(err_file, "w").close()

    # --------------------------------------------------
    # TEST 1: ZERO CASE
    # --------------------------------------------------
    out, done = await apply_inputs(
        dut,
        le_o=0,
        e_o=0,
        dsr=0,
        r_o=0,
        ls=0,
        inf=0,
        zero=1,
        start=1
    )

    if out != 0:
        report_error("Zero output incorrect", "out_m", err_file)

    if done != 1:
        report_error("Done not asserted", "done_m", err_file)

    # --------------------------------------------------
    # TEST 2: INF CASE
    # --------------------------------------------------
    out, _ = await apply_inputs(
        dut,
        le_o=0,
        e_o=0,
        dsr=0,
        r_o=0,
        ls=0,
        inf=1,
        zero=0,
        start=1
    )

    if (out >> 15) != 1:
        report_error("INF MSB not set", "out_m", err_file)

    # --------------------------------------------------
    # TEST 3: SIGN HANDLING
    # --------------------------------------------------
    out_pos, _ = await apply_inputs(
        dut, 5, 2, 0x1FFFFF, 2, 0, 0, 0, 1
    )

    out_neg, _ = await apply_inputs(
        dut, 5, 2, 0x1FFFFF, 2, 1, 0, 0, 1
    )

    if out_pos == out_neg:
        report_error("Sign not applied correctly", "ls", err_file)

    # --------------------------------------------------
    # TEST 4: RANDOM TESTING
    # --------------------------------------------------
    dut._log.info("Running random tests")

    for _ in range(100):

        le_o = random.getrandbits(8)
        e_o = random.getrandbits(2)
        dsr = random.getrandbits(29)
        r_o = random.getrandbits(5)
        ls = random.getrandbits(1)
        inf = random.getrandbits(1)
        zero = random.getrandbits(1)

        out, done = await apply_inputs(
            dut, le_o, e_o, dsr, r_o, ls, inf, zero, 1
        )

        check_no_xz(dut.out_m.value, "out_m", err_file)

        if done != 1:
            report_error("Done not asserted", "done_m", err_file)

    # --------------------------------------------------
    # TEST 5: ROUNDING PATH ACTIVATION
    # --------------------------------------------------
    dut._log.info("Testing rounding behavior")

    # Force rounding bits (G,R,S)
    dsr = (1 << 20) | (1 << 5) | 1

    out1, _ = await apply_inputs(
        dut, 10, 1, dsr, 2, 0, 0, 0, 1
    )

    out2, _ = await apply_inputs(
        dut, 10, 1, dsr + 1, 2, 0, 0, 0, 1
    )

    if out1 == out2:
        report_error("Rounding not affecting output", "rounding", err_file)

    # --------------------------------------------------
    # TEST 6: STABILITY
    # --------------------------------------------------
    dut._log.info("Checking stability")

    out1, _ = await apply_inputs(
        dut, 7, 1, 0x1234567, 3, 0, 0, 0, 1
    )

    await Timer(1, unit="ns")
    out2 = int(dut.out_m.value)

    if out1 != out2:
        report_error("Output not stable", "out_m", err_file)

    dut._log.info("==== POSIT ENCODER TEST PASSED ====")