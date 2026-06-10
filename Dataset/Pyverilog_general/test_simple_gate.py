import cocotb
from cocotb.triggers import Timer, First, ReadOnly

def report_error(msg, signal_name):
    """Formats the error banner, writes to error_timestamp.txt, and fails the test."""
    current_time = cocotb.utils.get_sim_time('ns')
    
    error_banner = (
        f"\n{'='*65}\n"
        f"TEST FAILED AT {current_time} ns\n"
        f"FAILING SIGNAL : {signal_name}\n"
        f"ERROR DETAILS  : {msg}\n"
        f"{'='*65}"
    )
    cocotb.log.error(error_banner)
    
    with open("error_timestamp.txt", "a") as err_file:
        err_file.write(error_banner)
        
    assert False, f"Signal '{signal_name}' failed."

async def monitor_all_signals(dut, file_handle):
    """Monitors all input/output signals and logs a complete snapshot on any change."""
    
    signals = [
        (dut.a, "a"), (dut.b, "b"), (dut.c, "c"), (dut.d, "d"),
        (dut.y1, "y1"), (dut.y2, "y2"), (dut.y3, "y3")
    ]
    
    await ReadOnly()
    current_time = cocotb.utils.get_sim_time('ns')
    
    snapshot = [f"{name}={str(sig.value)}" for sig, name in signals]
    file_handle.write(f"[{current_time} ns] " + " | ".join(snapshot) + "\n")
    file_handle.flush()
    
    last_logged_time = current_time

    while True:
        triggers = [sig.value_change for sig, _ in signals if hasattr(sig, 'value_change')]
        await First(*triggers)
        await ReadOnly()
        
        current_time = cocotb.utils.get_sim_time('ns')
        if current_time != last_logged_time:
            snapshot = [f"{name}={str(sig.value)}" for sig, name in signals]
            file_handle.write(f"[{current_time} ns] " + " | ".join(snapshot) + "\n")
            file_handle.flush()
            last_logged_time = current_time

@cocotb.test()
async def test_simple_gate(dut):
    """Exhaustive self-checking test for simple_gate combinational logic."""
    
    open("error_timestamp.txt", "w").close()
    log_file = open("topmodule.log", "w")
    
    try:
        cocotb.start_soon(monitor_all_signals(dut, log_file))
        cocotb.log.info("Starting exhaustive combinational test...")

        for a_val in (0, 1):
            for b_val in (0, 1):
                for c_val in (0, 1):
                    for d_val in (0, 1):
                        
                        # 1. Drive inputs
                        dut.a.value = a_val
                        dut.b.value = b_val
                        dut.c.value = c_val
                        dut.d.value = d_val
                        
                        # 2. Wait 5 nanoseconds for propagation
                        await Timer(5, unit='ns')
                        
                        # Lock into ReadOnly phase to safely sample outputs
                        await ReadOnly()
                        
                        # 3. Calculate expected Golden Reference values
                        expected_y1 = a_val & b_val
                        expected_y2 = b_val & c_val
                        expected_y3 = d_val
                        
                        # 4. Read actual output values from DUT
                        actual_y1 = int(dut.y1.value) if dut.y1.value.is_resolvable else -1
                        actual_y2 = int(dut.y2.value) if dut.y2.value.is_resolvable else -1
                        actual_y3 = int(dut.y3.value) if dut.y3.value.is_resolvable else -1
                        
                        # 5. Self-Checking Assertions
                        if actual_y1 != expected_y1:
                            report_error(f"Expected {expected_y1} (from {a_val}&{b_val}), got {actual_y1}", "y1")
                            
                        if actual_y2 != expected_y2:
                            report_error(f"Expected {expected_y2} (from {b_val}&{c_val}), got {actual_y2}", "y2")
                            
                        if actual_y3 != expected_y3:
                            report_error(f"Expected {expected_y3} (from wire d), got {actual_y3}", "y3")

                        # ---> THE FIX <---
                        # Advance time by 1ns to exit the ReadOnly phase before the next loop iteration begins
                        await Timer(1, unit='ns')

        cocotb.log.info("✅ SUCCESS! simple_gate perfectly matched all 16 states!")

    finally:
        log_file.close()
        cocotb.log.info("Signal log file 'topmodule.log' securely closed.")