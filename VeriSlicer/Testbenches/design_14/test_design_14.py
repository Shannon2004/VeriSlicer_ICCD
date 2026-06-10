import os
import random
import cocotb
from cocotb.triggers import Timer

error_dir = os.environ.get("ERROR_DIR", "error_design_default") #pass through from top script
error_designs_dir = "../Error_designs/"

# ============================================================
# Error helpers
# ============================================================

def report_error(msg, signal, file_path):
    t = cocotb.utils.get_sim_time("ns")
    banner = f"\nFAIL @{t}ns | {signal} | {msg}\n"
    with open(file_path, "a") as f:
        f.write(banner)

    cocotb.log.error(banner)
    assert False


def check_no_xz(value, name, file_path):
    if 'x' in str(value).lower() or 'z' in str(value).lower():
        report_error(f"{name} has X/Z: {value}", name, file_path)


# ============================================================
# Reference model (simplified)
# ============================================================

def leading_one_pos(value, width):
    for i in range(width):
        if value & (1 << (width - 1 - i)):
            return i
    return width


def model_decode(x, N=16, es=2):
    rc = (x >> (N-2)) & 1

    xin_r = (~x & ((1 << N) - 1)) if rc else x

    k = leading_one_pos(((xin_r >> 0) & ((1 << (N-1)) - 1)) << 1 | (rc ^ 0), N)

    regime = k - 1 if rc else k

    shifted = ((x & ((1 << (N-2)) - 1)) << 2) & ((1 << N) - 1)
    shifted = (shifted << k) & ((1 << N) - 1)

    exp = (shifted >> (N-es)) & ((1 << es) - 1)
    mant = shifted & ((1 << (N-es)) - 1)

    return rc, regime, exp, mant


# ============================================================
# Main Test
# ============================================================

@cocotb.test()
async def posit_decoder_tb(dut):

    dut._log.info("==== POSIT DECODER TEST START ====")

    out_dir = os.path.join(error_designs_dir, error_dir)
    os.makedirs(out_dir, exist_ok=True)
    log_file_path = os.path.join(out_dir, os.path.basename(__file__).replace("test_", "").replace(".py", ".log"))
    err_file = os.path.join(out_dir, "error_timestamp.txt")

    log_file = open(log_file_path, "w")
    open(err_file, "w").close()

    # --------------------------------------------------
    # TEST 1: ZERO INPUT
    # --------------------------------------------------
    dut.posit_in.value = 0x0000
    await Timer(1, unit="ns")

    check_no_xz(dut.rc.value, "rc", err_file)
    check_no_xz(dut.regime.value, "regime", err_file)

    # --------------------------------------------------
    # TEST 2: ALL ONES
    # --------------------------------------------------
    dut.posit_in.value = 0xFFFF
    await Timer(1, unit="ns")

    check_no_xz(dut.exp.value, "exp", err_file)

    # --------------------------------------------------
    # TEST 3: SINGLE BIT PATTERNS
    # --------------------------------------------------
    for i in range(16):
        dut.posit_in.value = (1 << i)
        await Timer(1, unit="ns")

        check_no_xz(dut.mant.value, "mant", err_file)

    # --------------------------------------------------
    # TEST 4: DIRECTED TESTS
    # --------------------------------------------------
    test_vectors = [
        0x4000,
        0x2000,
        0x1000,
        0x0800,
        0x0400,
        0x0200,
    ]

    for val in test_vectors:
        dut.posit_in.value = val
        await Timer(1, unit="ns")

        rc, regime, exp, mant = model_decode(val)

        if int(dut.rc.value) != rc:
            report_error("RC mismatch", "rc", err_file)

    # --------------------------------------------------
    # TEST 5: RANDOM TESTING
    # --------------------------------------------------
    dut._log.info("Running random tests")

    for _ in range(100):
        val = random.getrandbits(16)

        dut.posit_in.value = val
        await Timer(1, unit="ns")

        check_no_xz(dut.rc.value, "rc", err_file)
        check_no_xz(dut.regime.value, "regime", err_file)
        check_no_xz(dut.exp.value, "exp", err_file)
        check_no_xz(dut.mant.value, "mant", err_file)

    # --------------------------------------------------
    # TEST 6: CONSISTENCY CHECK
    # --------------------------------------------------
    dut._log.info("Checking stability")

    val = 0x1234
    dut.posit_in.value = val

    await Timer(1, unit="ns")
    r1 = int(dut.regime.value)

    await Timer(1, unit="ns")
    r2 = int(dut.regime.value)

    if r1 != r2:
        report_error("Output not stable", "regime", err_file)

    dut._log.info("==== POSIT DECODER TEST PASSED ====")