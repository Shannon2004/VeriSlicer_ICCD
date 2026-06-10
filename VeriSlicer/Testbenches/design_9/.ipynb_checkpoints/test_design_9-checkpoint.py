import os
import random
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer, First, ReadOnly

error_dir = os.environ.get("ERROR_DIR", "error_design_default")
error_designs_dir = "../Error_designs/"

# ============================================================
# ERROR HANDLING
# ============================================================

def report_error(msg, signal_name, file_path):
    current_time = cocotb.utils.get_sim_time("ns")
    banner = (
        f"\n{'='*70}\n"
        f"TEST FAILED AT {current_time} ns\n"
        f"FAILING SIGNAL : {signal_name}\n"
        f"ERROR DETAILS  : {msg}\n"
        f"{'='*70}\n"
    )

    with open(file_path, "a") as f:
        f.write(banner)

    cocotb.log.error(banner)
    assert False, msg


# ============================================================
# SIGNAL MONITOR (FIXED)
# ============================================================

def get_all_signals(dut):
    """Recursively collect all HDL signals"""
    signals = []

    def recurse(obj, prefix=""):
        for name in dir(obj):
            if name.startswith("_"):
                continue
            try:
                handle = getattr(obj, name)
            except Exception:
                continue

            # Only keep objects that look like signals
            if hasattr(handle, "value"):
                signals.append((handle, f"{prefix}{name}"))

            # Recurse into hierarchy
            if hasattr(handle, "__iter__"):
                try:
                    recurse(handle, f"{prefix}{name}.")
                except Exception:
                    pass

    recurse(dut)
    return signals


async def monitor_all_signals(dut, file_handle):
    signals = get_all_signals(dut)

    await ReadOnly()
    last_time = cocotb.utils.get_sim_time("ns")

    while True:
        triggers = []
        for sig, _ in signals:
            if hasattr(sig, "value_change"):
                triggers.append(sig.value_change)

        if not triggers:
            await Timer(1, unit="ns")
            continue

        await First(*triggers)
        await ReadOnly()

        now = cocotb.utils.get_sim_time("ns")
        if now != last_time:
            snapshot = []
            for sig, name in signals:
                try:
                    snapshot.append(f"{name}={str(sig.value)}")
                except Exception:
                    pass

            file_handle.write(f"[{now:.1f} ns] " + " | ".join(snapshot) + "\n")
            file_handle.flush()
            last_time = now


# ============================================================
# UTILS
# ============================================================

def u32(x): return x & 0xFFFFFFFF


def to_signed32(val):
    """Convert Python int to 32-bit signed representation"""
    val &= 0xFFFFFFFF
    return val if val < 0x80000000 else val - 0x100000000


# ============================================================
# REFERENCE MODEL
# ============================================================

def alu_ref(opcode, funct3, funct7, a, b, imm):

    a = to_signed32(a)
    b = to_signed32(b)
    imm = to_signed32(imm)

    # R-type
    if opcode == 0b0110011:
        key = (funct7 << 3) | funct3

        if key == 0b0000000000: return u32(a + b)
        if key == 0b0100000000: return u32(a - b)
        if key == 0b0000000111: return u32(a & b)
        if key == 0b0000000110: return u32(a | b)
        if key == 0b0000000100: return u32(a ^ b)
        if key == 0b0000000010: return int(a < b)

    # I-type
    elif opcode == 0b0010011:
        if funct3 == 0b000: return u32(a + imm)
        if funct3 == 0b111: return u32(a & imm)
        if funct3 == 0b110: return u32(a | imm)
        if funct3 == 0b100: return u32(a ^ imm)

    return 0


# ============================================================
# APPLY INPUTS
# ============================================================

async def apply_inputs(dut, **kwargs):
    await FallingEdge(dut.clk)

    for k, v in kwargs.items():
        getattr(dut, k).value = v

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")


def check_eq(name, got, exp, file_path):
    if got != exp:
        report_error(f"{name}: expected {exp}, got {got}", name, file_path)


# ============================================================
# MAIN TEST
# ============================================================

@cocotb.test()
async def design9_testbench(dut):

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    out_dir = os.path.join(error_designs_dir, error_dir)
    os.makedirs(out_dir, exist_ok=True)

    log_file_path = os.path.join(
        out_dir,
        os.path.basename(__file__).replace("test_", "").replace(".py", ".log")
    )
    err_file_path = os.path.join(out_dir, "error_timestamp.txt")

    log_file = open(log_file_path, "w")
    open(err_file_path, "w").close()

    cocotb.start_soon(monitor_all_signals(dut, log_file))

    dut._log.info("=== Starting design_9 test ===")

    # RESET
    dut.reset.value = 1
    await RisingEdge(dut.clk)
    dut.reset.value = 0

    # TEST 1: R-TYPE
    r_ops = [
        (0b0000000, 0b000),
        (0b0100000, 0b000),
        (0b0000000, 0b111),
        (0b0000000, 0b110),
        (0b0000000, 0b100),
        (0b0000000, 0b010),
    ]

    for _ in range(20):
        a = random.getrandbits(32)
        b = random.getrandbits(32)
        funct7, funct3 = random.choice(r_ops)

        await apply_inputs(dut,
            ex_rd1=a,
            ex_rd2=b,
            ex_imm=0,
            ex_opcode=0b0110011,
            ex_funct3=funct3,
            ex_funct7=funct7
        )

        expected = alu_ref(0b0110011, funct3, funct7, a, b, 0)
        got = int(dut.alu_result.value)

        check_eq("alu_result", got, expected, err_file_path)

    # TEST 2: I-TYPE
    funct3_list = [0b000, 0b111, 0b110, 0b100]

    for _ in range(20):
        a = random.getrandbits(32)
        imm = random.randint(-2048, 2047)
        funct3 = random.choice(funct3_list)

        await apply_inputs(dut,
            ex_rd1=a,
            ex_rd2=0,
            ex_imm=imm,
            ex_opcode=0b0010011,
            ex_funct3=funct3,
            ex_funct7=0
        )

        expected = alu_ref(0b0010011, funct3, 0, a, 0, imm)
        got = int(dut.alu_result.value)

        check_eq("alu_result", got, expected, err_file_path)

    # TEST 3: ZERO FLAG
    await apply_inputs(dut,
        ex_rd1=10,
        ex_rd2=10,
        ex_opcode=0b0110011,
        ex_funct3=0b000,
        ex_funct7=0b0100000
    )

    check_eq("zero", int(dut.zero.value), 1, err_file_path)

    dut._log.info("Simulation complete. All checks passed.")
    log_file.close()