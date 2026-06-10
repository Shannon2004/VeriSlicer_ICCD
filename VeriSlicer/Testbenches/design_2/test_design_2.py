import os
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer, RisingEdge, ReadOnly, First
from cocotb.utils import get_sim_time

error_dir = os.environ.get("ERROR_DIR", "error_design_default") #pass through from top script
error_designs_dir = "../Error_designs/"

def report_error(msg, signal_name, file_path):
    """Formats, prints, and writes a highly visible error banner to a file, then fails."""
    current_time = get_sim_time('ns')
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

async def monitor_all_signals(dut, file_handle):
    """Monitors all input/output signals and logs a complete snapshot on any change."""
    
    signals = [
        (dut.clk, "clk"),
        (dut.i_Read_Request, "i_Read_Request"),
        (dut.i_Write_Request, "i_Write_Request"),
        (dut.i_Read_Address, "i_Read_Address"),
        (dut.i_Write_Address, "i_Write_Address"),
        (dut.i_Write_Data, "i_Write_Data"),
        (dut.o_Write_Grant, "o_Write_Grant"),
        (dut.o_Read_Grant, "o_Read_Grant"),
        (dut.o_Data_Valid, "o_Data_Valid")
    ]
    
    await ReadOnly()
    current_time = get_sim_time('ns')
    
    snapshot = [f"{name}={str(sig.value)}" for sig, name in signals]
    file_handle.write(f"[{current_time:.1f} ns] " + " | ".join(snapshot) + "\n")
    file_handle.flush()
    
    last_logged_time = current_time

    while True:
        triggers = [sig.value_change for sig, _ in signals if hasattr(sig, 'value_change')]
        await First(*triggers)
        await ReadOnly()
        
        current_time = get_sim_time('ns')
        if current_time != last_logged_time:
            snapshot = [f"{name}={str(sig.value)}" for sig, name in signals]
            file_handle.write(f"[{current_time:.1f} ns] " + " | ".join(snapshot) + "\n")
            file_handle.flush()
            last_logged_time = current_time

@cocotb.test()
async def sd_controller_robust_test(dut):
    """
    Comprehensive, self-checking testbench to catch FSM and timing bugs.
    """
    out_dir = os.environ.get("OUT_DIR", ".")

    # Safely construct the full paths
    out_dir = os.path.join(error_designs_dir, error_dir)
    os.makedirs(out_dir, exist_ok=True)
    log_file_path = os.path.join(out_dir, os.path.basename(__file__).replace("test_", "").replace(".py", ".log"))
    file_path = os.path.join(out_dir, "error_timestamp.txt")
    log_file = open(log_file_path, "w")
    open(file_path, 'w').close()
    
    try:
        # Start parallel task logging the signals to a file
        cocotb.start_soon(monitor_all_signals(dut, log_file))

        # 1. Initialize
        dut.i_Read_Request.value = 0
        dut.i_Write_Request.value = 0
        dut.i_Read_Address.value = 0
        dut.i_Write_Address.value = 0
        dut.i_Write_Data.value = 0

        # Start the clock starting at 0
        clock = Clock(dut.clk, 2, unit="ns")
        cocotb.start_soon(clock.start(start_high=False))

        # --- CHECK 1: Idle State ---
        dut._log.info("Checking initial Idle state...")
        await Timer(10, unit="ns")
        await ReadOnly()
        
        if dut.o_Write_Grant.value != 0:
            report_error("Bug Caught: WriteGrant should be 0 at startup.", "o_Write_Grant", file_path)
        if dut.o_Read_Grant.value != 0:
            report_error("Bug Caught: ReadGrant should be 0 at startup.", "o_Read_Grant", file_path)
        if dut.o_Data_Valid.value != 0:
            report_error("Bug Caught: DataValid should be 0 at startup.", "o_Data_Valid", file_path)

        # --- CHECK 2: Write Phase ---
        dut._log.info("Checking Write Phase & Hold...")
        await RisingEdge(dut.clk)
        dut.i_Write_Request.value = 1
        dut.i_Write_Address.value = 1
        dut.i_Write_Data.value = 12
        
        await ReadOnly()
        if dut.o_Write_Grant.value != 1:
            report_error("Bug Caught: WriteGrant did not assert immediately in Idle.", "o_Write_Grant", file_path)
        
        # Wait 3 cycles to ensure it holds the write grant in State 1
        for _ in range(3):
            await RisingEdge(dut.clk)
        await ReadOnly()
        if dut.o_Write_Grant.value != 1:
            report_error("Bug Caught: WriteGrant dropped prematurely while WriteReq was high.", "o_Write_Grant", file_path)

        # --- CHECK 3: Turnaround (Write -> Precharge -> Read) ---
        dut._log.info("Checking Write-to-Read Turnaround (Precharge Timing)...")
        # ADD THIS LINE: Move out of ReadOnly phase to the next active clock edge
        await RisingEdge(dut.clk)
        dut.i_Read_Request.value = 1
        dut.i_Write_Request.value = 0
        dut.i_Read_Address.value = 1

        # Cycle 1: FSM leaves State 1 (Active) and enters State 2 (Precharge)
        await RisingEdge(dut.clk)
        await ReadOnly()
        if dut.o_Write_Grant.value != 0:
            report_error("Bug Caught: WriteGrant did not deassert during Precharge.", "o_Write_Grant", file_path)
        if dut.o_Read_Grant.value != 0:
            report_error("Bug Caught: ReadGrant asserted too early (during Precharge).", "o_Read_Grant", file_path)

        # Cycle 2: FSM leaves State 2 (Precharge) and enters State 0 (Idle)
        # ReadReq is still 1, so ReadGrant should combinationally assert here
        await RisingEdge(dut.clk)
        await ReadOnly()
        if dut.o_Read_Grant.value != 1:
            report_error("Bug Caught: ReadGrant failed to assert when returning to Idle.", "o_Read_Grant", file_path)

        # Cycle 3: FSM enters State 1 (Active/Read)
        await RisingEdge(dut.clk)
        await ReadOnly()
        if dut.o_Read_Grant.value != 1:
            report_error("Bug Caught: ReadGrant dropped after entering Read state.", "o_Read_Grant", file_path)

        # --- CHECK 4: Data Valid Pipeline Latency (TOTAL_READ_LATENCY = 4) ---
        dut._log.info("Checking Data Valid Pipeline Latency...")
        
        # We are currently in Cycle 1 of the Read state. The pipeline is shifting.
        if dut.o_Data_Valid.value != 0:
            report_error("Bug Caught: DataValid asserted before pipeline latency finished.", "o_Data_Valid", file_path)
        
        # Edge 1, 2, 3: Pipeline is shifting, Data Valid should remain 0
        for i in range(1, 4):
            await RisingEdge(dut.clk)
            await ReadOnly()
            if dut.o_Data_Valid.value != 0:
                report_error(f"Bug Caught: DataValid asserted too early at latency {i}.", "o_Data_Valid", file_path)
        
        # Edge 4: The pipeline bit finally reaches the end (TOTAL_READ_LATENCY-1)
        await RisingEdge(dut.clk)
        await ReadOnly()
        if dut.o_Data_Valid.value != 1:
            report_error("Bug Caught: DataValid failed to assert exactly 4 cycles after Read began.", "o_Data_Valid", file_path)

        dut._log.info("All robust checks passed! The controller is bug-free.")

    finally:
        log_file.close()
        dut._log.info("Signal log file securely closed.")
