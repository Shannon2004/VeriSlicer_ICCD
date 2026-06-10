import os
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer, ReadOnly

error_dir = os.environ.get("ERROR_DIR", "error_design_default") #pass through from top script
error_designs_dir = "../Error_designs/"
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

    with open(file_path, "a") as f:
        f.write(error_banner)

    cocotb.log.error(error_banner)
    assert False, f"{signal_name} failed"


def check_eq(name, got, expected, file_path):
    if got != expected:
        report_error(
            f"Expected {name}={hex(expected)}, got {hex(got)}",
            name,
            file_path
        )


# ============================================================
# Monitor (optional but useful)
# ============================================================

async def monitor_if_stage(dut, file_handle):
    signals = [
        (dut.pc, "pc"),
        (dut.instr, "instr"),
    ]

    while True:
        await RisingEdge(dut.clk)
        await ReadOnly()

        t = cocotb.utils.get_sim_time("ns")
        snapshot = [f"{name}={hex(int(sig.value))}" for sig, name in signals]
        file_handle.write(f"[{t} ns] " + " | ".join(snapshot) + "\n")
        file_handle.flush()


# ============================================================
# Helper: expected instruction from memory
# ============================================================

def get_expected_instr(mem, pc):
    index = (pc >> 2) & 0xFF  # addr[9:2]
    return mem[index]


# ============================================================
# Main Testbench
# ============================================================

@cocotb.test()
async def if_stage_testbench(dut):

    dut._log.info("==== IF STAGE TEST START ====")

    # Clock
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    # Files
    out_dir = os.path.join(error_designs_dir, error_dir)
    os.makedirs(out_dir, exist_ok=True)
    log_file_path = os.path.join(out_dir, os.path.basename(__file__).replace("test_", "").replace(".py", ".log"))
    error_file_path = os.path.join(out_dir, "error_timestamp.txt")

    log_file = open(log_file_path, "w")
    open(error_file_path, "w").close()

    # Start monitor
    cocotb.start_soon(monitor_if_stage(dut, log_file))

    # --------------------------------------------------
    # Build reference memory model (same as RTL)
    # --------------------------------------------------
    mem = [0x00000013] * 256  # default NOP

    # OPTIONAL: load same hex file used in RTL
    hex_path = "C:/Users/sagni/Desktop/program.hex"
    if os.path.exists(hex_path):
        with open(hex_path) as f:
            for i, line in enumerate(f):
                mem[i] = int(line.strip(), 16)

    # --------------------------------------------------
    # RESET TEST
    # --------------------------------------------------
    dut.reset.value = 1

    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)

    dut.reset.value = 0
    await Timer(1, unit="ns")

    check_eq("pc_after_reset", int(dut.pc.value), 0, error_file_path)

    # --------------------------------------------------
    # STEP-BY-STEP PC + INSTR CHECK
    # --------------------------------------------------
    NUM_CYCLES = 20
    expected_pc = 0

    for cycle in range(NUM_CYCLES):

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        # Check PC
        check_eq("pc", int(dut.pc.value), expected_pc, error_file_path)

        # Check instruction
        expected_instr = get_expected_instr(mem, expected_pc)
        check_eq("instr", int(dut.instr.value), expected_instr, error_file_path)

        dut._log.info(
            f"Cycle {cycle}: PC={hex(expected_pc)} Instr={hex(expected_instr)}"
        )

        # Next expected PC
        expected_pc += 4

    # --------------------------------------------------
    # CONTINUOUS RUN TEST
    # --------------------------------------------------
    dut._log.info("\nContinuous execution test")

    for _ in range(10):
        await RisingEdge(dut.clk)

    # --------------------------------------------------
    # RESET MID-EXECUTION
    # --------------------------------------------------
    dut._log.info("\nMid-execution reset test")

    dut.reset.value = 1
    await RisingEdge(dut.clk)
    dut.reset.value = 0

    await Timer(1, unit="ns")

    check_eq("pc_after_mid_reset", int(dut.pc.value), 0, error_file_path)

    # --------------------------------------------------
    # FINAL CHECK
    # --------------------------------------------------
    dut._log.info("==== IF STAGE TEST PASSED ====")

    log_file.close()