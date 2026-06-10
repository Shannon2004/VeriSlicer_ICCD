import os
import random
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer, First, ReadOnly

error_dir = os.environ.get("ERROR_DIR", "error_design_default") #pass through from top script
error_designs_dir = "../Error_designs/"
# ============================================================
# Logging / failure helpers
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


async def monitor_all_signals(dut, file_handle):
    signals = [
        (dut.clk, "clk"),
        (dut.rst_n, "rst_n"),
        (dut.enable, "enable"),
        (dut.valid, "valid"),
        (dut.read, "read"),
        (dut.mode, "mode"),
        (dut.cfg, "cfg"),
        (dut.in_a, "in_a"),
        (dut.in_b, "in_b"),
        (dut.mac_out, "mac_out"),
        (dut.error, "error"),
    ]

    await ReadOnly()
    current_time = cocotb.utils.get_sim_time("ns")
    snapshot = [f"{name}={str(sig.value)}" for sig, name in signals]
    file_handle.write(f"[{current_time:.1f} ns] " + " | ".join(snapshot) + "\n")
    file_handle.flush()
    last_logged_time = current_time

    while True:
        triggers = [sig.value_change for sig, _ in signals if hasattr(sig, "value_change")]
        await First(*triggers)
        await ReadOnly()

        current_time = cocotb.utils.get_sim_time("ns")
        if current_time != last_logged_time:
            snapshot = [f"{name}={str(sig.value)}" for sig, name in signals]
            file_handle.write(f"[{current_time:.1f} ns] " + " | ".join(snapshot) + "\n")
            file_handle.flush()
            last_logged_time = current_time


def log_compact_result(dut):
    t = cocotb.utils.get_sim_time("ns")
    dut._log.info(
        f"T={t} | en={int(dut.enable.value)} valid={int(dut.valid.value)} "
        f"read={int(dut.read.value)} cfg={int(dut.cfg.value)} mode={int(dut.mode.value)} | "
        f"in_a={int(dut.in_a.value):04x} in_b={int(dut.in_b.value):04x} | "
        f"mac_out={int(dut.mac_out.value):04x} error={int(dut.error.value)}"
    )


def log_detailed_result(dut):
    t = cocotb.utils.get_sim_time("ns")
    dut._log.info("------------------------------------------------------------")
    dut._log.info(f"Time      : {t}")
    dut._log.info(f"clk       : {int(dut.clk.value)}")
    dut._log.info(f"rst_n     : {int(dut.rst_n.value)}")
    dut._log.info(f"enable    : {int(dut.enable.value)}")
    dut._log.info(f"valid     : {int(dut.valid.value)}")
    dut._log.info(f"read      : {int(dut.read.value)}")
    dut._log.info(f"cfg       : {int(dut.cfg.value)}")
    dut._log.info(f"mode      : {int(dut.mode.value)}")
    dut._log.info(f"in_a      : 0x{int(dut.in_a.value):04X}")
    dut._log.info(f"in_b      : 0x{int(dut.in_b.value):04X}")
    dut._log.info(f"mac_out   : 0x{int(dut.mac_out.value):04X}")
    dut._log.info(f"error     : {int(dut.error.value)}")
    dut._log.info("------------------------------------------------------------")


# ============================================================
# Small bit helpers
# ============================================================

def u16(x):
    return x & 0xFFFF

def u11(x):
    return x & 0x7FF

def u5(x):
    return x & 0x1F

def tc16_to_int(x):
    x &= 0xFFFF
    return x - 0x10000 if x & 0x8000 else x

def int_to_tc16(x):
    return x & 0xFFFF

def cla_add(a, b, ci, n):
    mask = (1 << n) - 1
    total = (a & mask) + (b & mask) + (ci & 1)
    s = total & mask
    co = (total >> n) & 1
    return s, co


# ============================================================
# Exact INT8-mode model from RTL
# ============================================================

def int8_signmag_to_mag16(v):
    """
    RTL:
      if a[7]==0: {9'b0,a[6:0]}
      else       : {9'b0,~a[6:0]+1'b1}
    """
    sign = (v >> 7) & 1
    mag7 = v & 0x7F
    if sign == 0:
        return mag7
    return ((~mag7) + 1) & 0x7F

def int8_mul_rtl(a, b):
    """
    Exact model of int_fp_mul for mode=0.
    Inputs are taken from bits [7:0] as sign-magnitude-ish format.
    Output is 16-bit two's complement.
    """
    a8 = a & 0xFF
    b8 = b & 0xFF

    m1 = int8_signmag_to_mag16(a8)
    m2 = int8_signmag_to_mag16(b8)
    prod = (m1 * m2) & 0xFFFF

    sign = ((a8 >> 7) & 1) ^ ((b8 >> 7) & 1)
    if sign == 0:
        return prod
    return u16((1 << 15) | (((~prod) + 1) & 0x7FFF))

def int_add_rtl(a, b):
    """
    Exact model of int_fp_add for mode=0.
    This is just 16-bit addition implemented as 11-bit + carry into 5-bit add.
    """
    low, c1 = cla_add(a & 0x7FF, b & 0x7FF, 0, 11)
    high, _ = cla_add((a >> 11) & 0x1F, (b >> 11) & 0x1F, c1, 5)
    return ((high & 0x1F) << 11) | low

def int_mac_step_rtl(acc, a, b):
    mul = int8_mul_rtl(a, b)
    out = int_add_rtl(mul, acc)
    return u16(out), 0


# ============================================================
# Exact FP-mode model from RTL
# ============================================================

def align_small(bigger, smaller):
    bigger_exp = (bigger >> 10) & 0x1F
    smaller_exp = (smaller >> 10) & 0x1F
    shift_bits, _ = cla_add(bigger_exp, ((~smaller_exp) + 1) & 0x1F, 0, 5)
    mant = (1 << 10) | (smaller & 0x3FF)
    return (mant >> shift_bits) & 0x7FF

def add_normalizer(sign, exponent, mantissa_add, if_carry, if_sub):
    mantissa_add &= 0x7FF
    exponent &= 0x1F

    if (mantissa_add >> 4) == 0b0000001:
        noz = 6
        norm = (mantissa_add << 6) & 0x7FF
    elif (mantissa_add >> 5) == 0b000001:
        noz = 5
        norm = (mantissa_add << 5) & 0x7FF
    elif (mantissa_add >> 6) == 0b00001:
        noz = 4
        norm = (mantissa_add << 4) & 0x7FF
    elif (mantissa_add >> 7) == 0b0001:
        noz = 3
        norm = (mantissa_add << 3) & 0x7FF
    elif (mantissa_add >> 8) == 0b001:
        noz = 2
        norm = (mantissa_add << 2) & 0x7FF
    elif (mantissa_add >> 9) == 0b01:
        noz = 1
        norm = (mantissa_add << 1) & 0x7FF
    else:
        noz = 0
        norm = mantissa_add

    shift_left_exp, _ = cla_add(exponent, ((~noz) + 1) & 0x1F, 0, 5)

    if not if_sub:
        res_exp = (exponent + 1) & 0x1F if if_carry else exponent
        res_man = (mantissa_add >> 1) & 0x3FF if if_carry else mantissa_add & 0x3FF
    else:
        res_exp = shift_left_exp & 0x1F
        res_man = norm & 0x3FF

    return ((sign & 1) << 15) | ((res_exp & 0x1F) << 10) | (res_man & 0x3FF)

def fp_add_rtl(a, b):
    a_sign = (a >> 15) & 1
    b_sign = (b >> 15) & 1
    if_sub = 0 if a_sign == b_sign else 1

    if (a & 0x7FFF) > (b & 0x7FFF):
        bigger = a & 0x7FFF
        smaller = b & 0x7FFF
        a_larger_b = 1
    else:
        bigger = b & 0x7FFF
        smaller = a & 0x7FFF
        a_larger_b = 0

    c_sign = a_sign if a_larger_b else b_sign
    aligned_small = align_small(bigger, smaller)

    adder_input_1 = (1 << 10) | (bigger & 0x3FF)
    if if_sub:
        adder_input_2 = ((~aligned_small) + 1) & 0x7FF
    else:
        adder_input_2 = aligned_small

    adder_output, c1 = cla_add(adder_input_1, adder_input_2, 0, 11)
    exponent = (bigger >> 10) & 0x1F
    return add_normalizer(c_sign, exponent, adder_output, c1, if_sub)

def mul_normalizer(exponent, mantissa_prod):
    exponent &= 0x1F
    mantissa_prod &= 0x3FFFFF

    if (mantissa_prod >> 21) & 1:
        result_exp = (exponent + 1) & 0x1F
        result_man = (mantissa_prod >> 11) & 0x3FF
    else:
        result_exp = exponent
        result_man = (mantissa_prod >> 10) & 0x3FF

    return ((result_exp & 0x1F) << 10) | (result_man & 0x3FF)

def fp_mul_rtl(a, b):
    a &= 0xFFFF
    b &= 0xFFFF

    overflow = 0
    underflow = 0

    a_zero = 1 if a == 0 else 0
    b_zero = 1 if b == 0 else 0
    c_sign = ((a >> 15) & 1) ^ ((b >> 15) & 1)

    m1 = (1 << 10) | (a & 0x3FF)
    m2 = (1 << 10) | (b & 0x3FF)
    mult = (m1 * m2) & 0xFFFFFFFF
    mantissa_prod = mult & 0x3FFFFF

    sum_exp, c1 = cla_add((a >> 10) & 0x1F, (b >> 10) & 0x1F, 0, 5)
    biased_sum_exp, c2 = cla_add(sum_exp, 0b10001, 0, 5)  # +17 => -15 mod 32

    overflow = 1 if (c1 == 1 and c2 == 1 and ((biased_sum_exp >> 4) & 1) == 0) else 0
    underflow = 1 if (c1 == 0 and c2 == 0 and ((biased_sum_exp >> 4) & 1) == 1) else 0
    error = 1 if (overflow or underflow) else 0

    normalized = mul_normalizer(biased_sum_exp, mantissa_prod)

    if error == 0:
        c_tmp = ((c_sign & 1) << 15) | normalized
    else:
        if underflow:
            c_tmp = ((c_sign & 1) << 15)
        else:
            c_tmp = ((c_sign & 1) << 15) | (0x1F << 10)

    if a_zero or b_zero:
        return 0, error

    return c_tmp & 0xFFFF, error

def fp_mac_step_rtl(acc, a, b):
    mul, error = fp_mul_rtl(a, b)
    out = fp_add_rtl(mul, acc)
    return out & 0xFFFF, error


# ============================================================
# Task-like helpers mirroring tb.v
# ============================================================

async def configure_mode(dut, mode_val):
    await FallingEdge(dut.clk)
    dut.enable.value = 0
    dut.valid.value = 0
    dut.read.value = 0
    dut.cfg.value = 1
    dut.mode.value = mode_val

    await FallingEdge(dut.clk)
    dut.cfg.value = 0
    dut._log.info(f"Configured mode = {mode_val} at T={cocotb.utils.get_sim_time('ns')}")

async def apply_mac_input(dut, a_val, b_val):
    await FallingEdge(dut.clk)
    dut.enable.value = 1
    dut.valid.value = 1
    dut.read.value = 0
    dut.in_a.value = a_val & 0xFFFF
    dut.in_b.value = b_val & 0xFFFF

    await FallingEdge(dut.clk)
    dut.valid.value = 0
    dut.in_a.value = 0
    dut.in_b.value = 0

async def read_mac_output(dut):
    await FallingEdge(dut.clk)
    dut.enable.value = 1
    dut.valid.value = 0
    dut.read.value = 1

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    log_detailed_result(dut)

    mac = int(dut.mac_out.value) & 0xFFFF
    err = int(dut.error.value)

    await FallingEdge(dut.clk)
    dut.read.value = 0
    return mac, err

async def idle_cycle(dut):
    await FallingEdge(dut.clk)
    dut.enable.value = 0
    dut.valid.value = 0
    dut.read.value = 0
    dut.cfg.value = 0
    dut.in_a.value = 0
    dut.in_b.value = 0


def check_eq(name, got, expected, file_path):
    if got != expected:
        report_error(f"Expected {name}=0x{expected:04X}, got 0x{got:04X}", name, file_path)

def check_bit(name, got, expected, file_path):
    if int(got) != int(expected):
        report_error(f"Expected {name}={expected}, got {got}", name, file_path)


# ============================================================
# Main testbench
# ============================================================

@cocotb.test()
async def bf16_testbench(dut):
    dut._log.info("--- Starting bf16 Simulation ---")

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    out_dir = os.path.join(error_designs_dir, error_dir)
    os.makedirs(out_dir, exist_ok=True)
    log_file_path = os.path.join(out_dir, os.path.basename(__file__).replace("test_", "").replace(".py", ".log"))
    error_file_path = os.path.join(out_dir, "error_timestamp.txt")

    log_file = open(log_file_path, "w")
    open(error_file_path, "w").close()

    try:
        cocotb.start_soon(monitor_all_signals(dut, log_file))

        # Initial values
        dut.rst_n.value = 0
        dut.enable.value = 0
        dut.valid.value = 0
        dut.read.value = 0
        dut.cfg.value = 0
        dut.mode.value = 0
        dut.in_a.value = 0
        dut.in_b.value = 0

        # Reset
        await Timer(2, unit="ns")
        await FallingEdge(dut.clk)
        dut.rst_n.value = 0
        await FallingEdge(dut.clk)
        dut.rst_n.value = 1
        dut._log.info(f"Reset released at T={cocotb.utils.get_sim_time('ns')}")

        # -------------------------------------------------
        # TEST 1: INT8 mode basic sequence
        # -------------------------------------------------
        dut._log.info("\n=== TEST 1 : INT8 MODE BASIC ===")
        await configure_mode(dut, 0)

        acc = 0
        for a, b in [(0x0003, 0x0004), (0x0002, 0x0005), (0x0001, 0x0006)]:
            acc, exp_err = int_mac_step_rtl(acc, a, b)
            await apply_mac_input(dut, a, b)
            log_compact_result(dut)
            check_bit("error", int(dut.error.value), exp_err, error_file_path)

        mac, err = await read_mac_output(dut)
        check_eq("mac_out", mac, acc, error_file_path)
        check_bit("error", err, 0, error_file_path)

        # read clears accumulator
        mac2, _ = await read_mac_output(dut)
        check_eq("mac_out", mac2, 0, error_file_path)

        # -------------------------------------------------
        # TEST 2: INT8 signed-like patterns
        # -------------------------------------------------
        dut._log.info("\n=== TEST 2 : INT8 MODE RANDOM / SIGNED-LIKE PATTERNS ===")
        await configure_mode(dut, 0)

        acc = 0
        for a, b in [(0x0081, 0x0002), (0x0084, 0x0003), (0x007F, 0x0002)]:
            acc, exp_err = int_mac_step_rtl(acc, a, b)
            await apply_mac_input(dut, a, b)
            log_compact_result(dut)
            check_bit("error", int(dut.error.value), exp_err, error_file_path)

        mac, err = await read_mac_output(dut)
        check_eq("mac_out", mac, acc, error_file_path)
        check_bit("error", err, 0, error_file_path)

        # -------------------------------------------------
        # TEST 3: FP16 mode basic patterns
        # -------------------------------------------------
        dut._log.info("\n=== TEST 3 : FP16 MODE BASIC ===")
        await configure_mode(dut, 1)

        acc = 0
        fp_err = 0
        for a, b in [(0x3C00, 0x3C00), (0x4000, 0x3C00), (0x4200, 0x3C00)]:
            acc, fp_err = fp_mac_step_rtl(acc, a, b)
            await apply_mac_input(dut, a, b)
            log_compact_result(dut)
            check_bit("error", int(dut.error.value), fp_err, error_file_path)

        mac, err = await read_mac_output(dut)
        check_eq("mac_out", mac, acc, error_file_path)
        check_bit("error", err, fp_err, error_file_path)

        # -------------------------------------------------
        # TEST 4: FP16 zero behavior
        # -------------------------------------------------
        dut._log.info("\n=== TEST 4 : FP16 ZERO BEHAVIOR ===")
        await configure_mode(dut, 1)

        acc = 0
        fp_err = 0
        for a, b in [(0x0000, 0x3C00), (0x3C00, 0x0000)]:
            acc, fp_err = fp_mac_step_rtl(acc, a, b)
            await apply_mac_input(dut, a, b)
            log_compact_result(dut)
            check_bit("error", int(dut.error.value), fp_err, error_file_path)

        mac, err = await read_mac_output(dut)
        check_eq("mac_out", mac, acc, error_file_path)
        check_bit("error", err, fp_err, error_file_path)

        # -------------------------------------------------
        # TEST 5: FP16 overflow/underflow exploration
        # -------------------------------------------------
        dut._log.info("\n=== TEST 5 : FP16 ERROR EXPLORATION ===")
        await configure_mode(dut, 1)

        acc = 0
        last_err = 0
        for a, b in [(0x7BFF, 0x7BFF), (0x0400, 0x0400)]:
            acc, last_err = fp_mac_step_rtl(acc, a, b)
            await apply_mac_input(dut, a, b)
            log_compact_result(dut)
            check_bit("error", int(dut.error.value), last_err, error_file_path)

        mac, err = await read_mac_output(dut)
        check_eq("mac_out", mac, acc, error_file_path)
        check_bit("error", err, last_err, error_file_path)

        # -------------------------------------------------
        # TEST 6: Random INT8 transactions
        # -------------------------------------------------
        dut._log.info("\n=== TEST 6 : RANDOM INT8 TESTING ===")
        await configure_mode(dut, 0)

        random.seed(7)
        acc = 0
        for _ in range(20):
            a = random.getrandbits(16)
            b = random.getrandbits(16)
            acc, exp_err = int_mac_step_rtl(acc, a, b)
            await apply_mac_input(dut, a, b)
            await Timer(1, unit="ns")
            log_compact_result(dut)
            check_bit("error", int(dut.error.value), exp_err, error_file_path)

        mac, err = await read_mac_output(dut)
        check_eq("mac_out", mac, acc, error_file_path)
        check_bit("error", err, 0, error_file_path)

        # -------------------------------------------------
        # TEST 7: Random FP16-pattern transactions
        # -------------------------------------------------
        dut._log.info("\n=== TEST 7 : RANDOM FP16 PATTERN TESTING ===")
        await configure_mode(dut, 1)

        random.seed(11)
        acc = 0
        last_err = 0
        for _ in range(20):
            a = random.getrandbits(16)
            b = random.getrandbits(16)
            acc, last_err = fp_mac_step_rtl(acc, a, b)
            await apply_mac_input(dut, a, b)
            await Timer(1, unit="ns")
            log_compact_result(dut)
            check_bit("error", int(dut.error.value), last_err, error_file_path)

        mac, err = await read_mac_output(dut)
        check_eq("mac_out", mac, acc, error_file_path)
        check_bit("error", err, last_err, error_file_path)

        # -------------------------------------------------
        # TEST 8: Read without valid
        # -------------------------------------------------
        dut._log.info("\n=== TEST 8 : READ BEHAVIOR ===")
        await configure_mode(dut, 0)
        mac, err = await read_mac_output(dut)
        check_eq("mac_out", mac, 0, error_file_path)
        check_bit("error", err, 0, error_file_path)

        # -------------------------------------------------
        # TEST 9: Disabled behavior
        # -------------------------------------------------
        dut._log.info("\n=== TEST 9 : DISABLED BEHAVIOR ===")
        await idle_cycle(dut)
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        log_detailed_result(dut)

        if int(dut.mac_out.value) != 0:
            report_error("mac_out should be 0 when disabled/idle", "mac_out", error_file_path)

        dut._log.info("Simulation complete. All checks passed.")

    finally:
        log_file.close()
        dut._log.info("Signal log file securely closed.")