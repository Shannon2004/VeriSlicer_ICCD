import os
import random
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

error_dir = os.environ.get("ERROR_DIR", "error_design_default") #pass through from top script
error_designs_dir = "../Error_designs/"
# ============================================================
# Parameters
# ============================================================
N = 12
INF_PATTERN = 1 << (N - 1)   # 1000...0


# ============================================================
# Failure / logging helpers
# ============================================================

def report_error(msg, signal_name, file_path):
    current_time = cocotb.utils.get_sim_time("ns")
    error_banner = (
        f"\n{'='*70}\n"
        f"TEST FAILED AT {current_time} ns\n"
        f"FAILING SIGNAL : {signal_name}\n"
        f"ERROR DETAILS  : {msg}\n"
        f"{'='*70}\n"
    )

    try:
        with open(file_path, "a") as f:
            f.write(error_banner)
    except IOError as e:
        cocotb.log.error(f"Could not write error to file {file_path}: {e}")

    cocotb.log.error(error_banner)
    assert False, f"Signal '{signal_name}' failed."


def check_eq(name, got, expected, file_path, width=None):
    if got != expected:
        if width is None:
            report_error(f"Expected {name}={expected}, got {got}", name, file_path)
        else:
            fmt = f"0x{{:0{width}X}}"
            report_error(
                f"Expected {name}={fmt.format(expected)}, got {fmt.format(got)}",
                name,
                file_path
            )


def check_no_xz(value, signal_name, file_path):
    s = str(value).lower()
    if "x" in s or "z" in s:
        report_error(f"{signal_name} contains X/Z: {value}", signal_name, file_path)


def log_results(dut):
    t = cocotb.utils.get_sim_time("ns")
    dut._log.info(
        f"T={t} | in1={int(dut.in1_m_kernel.value):03X} "
        f"in2={int(dut.in2_m_kernel.value):03X} "
        f"out={int(dut.out_m.value):03X} "
        f"inf={int(dut.inf_m.value)} zero={int(dut.zero_m.value)} "
        f"done={int(dut.done_m.value)}"
    )


# ============================================================
# Driver helper
# ============================================================

async def apply_mult(dut, a, b, start=1):
    dut.in1_m_kernel.value = a & ((1 << N) - 1)
    dut.in2_m_kernel.value = b & ((1 << N) - 1)
    dut.start_m.value = start

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    out  = dut.out_m.value
    inf  = dut.inf_m.value
    zero = dut.zero_m.value
    done = dut.done_m.value

    check_no_xz(out, "out_m", "error_timestamp.txt")
    check_no_xz(inf, "inf_m", "error_timestamp.txt")
    check_no_xz(zero, "zero_m", "error_timestamp.txt")
    check_no_xz(done, "done_m", "error_timestamp.txt")

    log_results(dut)

    return int(out), int(inf), int(zero), int(done)


# ============================================================
# Main testbench
# ============================================================

@cocotb.test()
async def posit_mult_testbench(dut):
    dut._log.info("--- Starting posit_mult Simulation ---")

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    out_dir = os.path.join(error_designs_dir, error_dir)
    os.makedirs(out_dir, exist_ok=True)
    log_file_path = os.path.join(out_dir, os.path.basename(__file__).replace("test_", "").replace(".py", ".log"))
    error_file_path = os.path.join(out_dir, "error_timestamp.txt")

    open(log_file_path, "w").close()
    open(error_file_path, "w").close()

    try:
        # ---------------------------
        # Init
        # ---------------------------
        dut.in1_m_kernel.value = 0
        dut.in2_m_kernel.value = 0
        dut.start_m.value = 0

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        # done_m is directly assigned from start_m in RTL
        check_eq("done_m", int(dut.done_m.value), 0, error_file_path)

        # ---------------------------
        # Test 1: zero * zero
        # ---------------------------
        out, inf, zero, done = await apply_mult(dut, 0x000, 0x000, start=1)
        check_eq("zero_m", zero, 1, error_file_path)
        check_eq("inf_m", inf, 0, error_file_path)
        check_eq("done_m", done, 1, error_file_path)

        # ---------------------------
        # Test 2: zero * nonzero
        # ---------------------------
        out, inf, zero, done = await apply_mult(dut, 0x000, 0x155, start=1)
        check_eq("zero_m", zero, 0, error_file_path)  # per RTL: zero only if both inputs zero
        check_eq("inf_m", inf, 0, error_file_path)
        check_eq("done_m", done, 1, error_file_path)

        # ---------------------------
        # Test 3: inf detection
        # inf pattern = 1000...0
        # ---------------------------
        out, inf, zero, done = await apply_mult(dut, INF_PATTERN, 0x111, start=1)
        check_eq("inf_m", inf, 1, error_file_path)
        check_eq("done_m", done, 1, error_file_path)

        out, inf, zero, done = await apply_mult(dut, 0x111, INF_PATTERN, start=1)
        check_eq("inf_m", inf, 1, error_file_path)

        # ---------------------------
        # Test 4: done follows start
        # ---------------------------
        dut.in1_m_kernel.value = 0x100
        dut.in2_m_kernel.value = 0x080
        dut.start_m.value = 0
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        check_eq("done_m", int(dut.done_m.value), 0, error_file_path)

        dut.start_m.value = 1
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        check_eq("done_m", int(dut.done_m.value), 1, error_file_path)

        # ---------------------------
        # Test 5: commutativity
        # a * b should match b * a
        # ---------------------------
        directed_vectors = [
            (0x100, 0x100),
            (0x120, 0x080),
            (0x055, 0x033),
            (0x3AA, 0x011),
            (0x200, 0x004),
        ]

        for a, b in directed_vectors:
            out1, inf1, zero1, _ = await apply_mult(dut, a, b, start=1)
            out2, inf2, zero2, _ = await apply_mult(dut, b, a, start=1)

            check_eq("comm_inf_m", inf1, inf2, error_file_path)
            check_eq("comm_zero_m", zero1, zero2, error_file_path)
            check_eq("comm_out_m", out1, out2, error_file_path, width=3)

        # ---------------------------
        # Test 6: sign sensitivity
        # flip sign bit of one operand
        # ---------------------------
        a = 0x120
        b = 0x088

        out_pos, inf_pos, zero_pos, _ = await apply_mult(dut, a, b, start=1)
        out_neg, inf_neg, zero_neg, _ = await apply_mult(dut, a ^ INF_PATTERN, b, start=1)

        # For a meaningful non-special pair, output should usually change
        if (inf_pos == 0 and zero_pos == 0 and inf_neg == 0 and zero_neg == 0) and (out_pos == out_neg):
            report_error("Output did not change when sign bit changed", "out_m", error_file_path)

        # ---------------------------
        # Test 7: output stability
        # ---------------------------
        dut.in1_m_kernel.value = 0x144
        dut.in2_m_kernel.value = 0x066
        dut.start_m.value = 1

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        out1 = int(dut.out_m.value)

        await Timer(5, unit="ns")
        out2 = int(dut.out_m.value)

        check_eq("stable_out_m", out2, out1, error_file_path, width=3)

        # ---------------------------
        # Test 8: random testing
        # ---------------------------
        dut._log.info("Random multiplication testing:")
        random.seed(42)

        for i in range(50):
            a = random.getrandbits(N)
            b = random.getrandbits(N)

            out1, inf1, zero1, done1 = await apply_mult(dut, a, b, start=1)
            check_eq("done_m", done1, 1, error_file_path)

            out2, inf2, zero2, done2 = await apply_mult(dut, b, a, start=1)

            check_eq(f"rand_comm_inf_{i}", inf1, inf2, error_file_path)
            check_eq(f"rand_comm_zero_{i}", zero1, zero2, error_file_path)
            check_eq(f"rand_comm_out_{i}", out1, out2, error_file_path, width=3)

        dut._log.info("Simulation complete. All checks passed.")

    finally:
        dut.start_m.value = 0
        dut._log.info("posit_mult testbench finished.")