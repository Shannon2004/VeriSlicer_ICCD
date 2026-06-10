import os
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer, ReadOnly

# Optional error directory handling (same style as your CORDIC TB)
error_dir = os.environ.get("ERROR_DIR", "error_full_adder_default")

# ----------------------------
# ERROR REPORTING FUNCTION
# ----------------------------
def report_error(msg, signal_name):
    time_ns = cocotb.utils.get_sim_time("ns")
    banner = (
        f"\n{'='*60}\n"
        f"FULL ADDER TEST FAILED @ {time_ns} ns\n"
        f"SIGNAL : {signal_name}\n"
        f"ERROR  : {msg}\n"
        f"{'='*60}\n"
    )
    cocotb.log.error(banner)
    assert False, banner


# ----------------------------
# MONITOR TASK (like CORDIC snapshot logger)
# ----------------------------
async def monitor_signals(dut):
    await ReadOnly()
    while True:
        await RisingEdge(dut.A[0])  # dummy trigger (we override below)
        await ReadOnly()

        cocotb.log.info(
            f"A={dut.A.value} B={dut.B.value} Cin={dut.Cin.value} "
            f"| Sum={dut.Sum.value} Cout={dut.Cout.value}"
        )


# ----------------------------
# CHECK FUNCTION
# ----------------------------
def check_results(dut, a, b, cin):
    expected = a + b + cin

    expected_sum = expected & 0xFF
    expected_cout = (expected >> 8) & 0x1

    got_sum = int(dut.Sum.value)
    got_cout = int(dut.Cout.value)

    if got_sum != expected_sum:
        report_error(
            f"Sum mismatch: expected {expected_sum}, got {got_sum}",
            "Sum"
        )

    if got_cout != expected_cout:
        report_error(
            f"Cout mismatch: expected {expected_cout}, got {got_cout}",
            "Cout"
        )

    cocotb.log.info(
        f"PASS A={a} B={b} Cin={cin} -> Sum={got_sum} Cout={got_cout}"
    )


# ----------------------------
# MAIN TESTBENCH
# ----------------------------
@cocotb.test()
async def full_adder_testbench(dut):

    cocotb.log.info("--- Starting 8-bit Full Adder Testbench ---")

    # Clock (not strictly needed but kept for structural similarity)
    cocotb.start_soon(Clock(dut.A[0], 1, unit="ns").start())

    # Start monitor (optional debug style like CORDIC)
    cocotb.start_soon(monitor_signals(dut))

    # ----------------------------
    # EXHAUSTIVE STIMULUS
    # ----------------------------
    for a in range(256):
        for b in range(256):
            for cin in range(2):

                dut.A.value = a
                dut.B.value = b
                dut.Cin.value = cin

                await Timer(1, unit="ns")

                check_results(dut, a, b, cin)

    cocotb.log.info("Simulation Complete: Full Adder Verified Successfully")