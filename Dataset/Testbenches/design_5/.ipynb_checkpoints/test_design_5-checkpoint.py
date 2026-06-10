import cocotb
import os
from cocotb.clock import Clock
from cocotb.triggers import Timer, RisingEdge, FallingEdge, First, ReadOnly
import random

error_dir = os.environ.get("ERROR_DIR", "error_design_default") #pass through from top script
error_designs_dir = "../Error_designs/"
CLK_HZ = 50_000_000

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
    
    try:
        with open(file_path, 'a') as f:
            f.write(error_banner)
    except IOError as e:
        cocotb.log.error(f"Could not write error to file {file_path}: {e}")

    cocotb.log.error(error_banner)
    assert False, f"Signal '{signal_name}' failed."

async def monitor_all_signals(dut, file_handle):
    """Monitors all input/output signals and logs a complete snapshot on any change."""
    
    signals = [(dut.clk, "clk"), (dut.rst, "rst"), (dut.done, "done")]
    for i in (0, 4, 8, 12):
        signals.append((getattr(dut, f"inp_west{i}"), f"inp_west{i}"))
    for i in range(4):
        signals.append((getattr(dut, f"inp_north{i}"), f"inp_north{i}"))
    for i in range(16):
        signals.append((getattr(dut, f"result{i}"), f"result{i}"))
    
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

def generate_random_matrix(size=4, max_val=15):
    """Generates a random square matrix for testing."""
    return [[random.randint(0, max_val) for _ in range(size)] for _ in range(size)]

def matmul(A, B):
    """Pure software reference model for matrix multiplication."""
    size = len(A)
    C = [[0]*size for _ in range(size)]
    for i in range(size):
        for j in range(size):
            for k in range(size):
                C[i][j] += A[i][k] * B[k][j]
    return C

async def drive_systolic_array(dut, A, B):
    """Drives the skewed input matrices into the systolic array."""
    for cycle in range(10):
        dut.inp_west0.value  = A[0][cycle]   if 0 <= cycle < 4 else 0
        dut.inp_west4.value  = A[1][cycle-1] if 1 <= cycle < 5 else 0
        dut.inp_west8.value  = A[2][cycle-2] if 2 <= cycle < 6 else 0
        dut.inp_west12.value = A[3][cycle-3] if 3 <= cycle < 7 else 0
        
        dut.inp_north0.value = B[cycle][0]   if 0 <= cycle < 4 else 0
        dut.inp_north1.value = B[cycle-1][1] if 1 <= cycle < 5 else 0
        dut.inp_north2.value = B[cycle-2][2] if 2 <= cycle < 6 else 0
        dut.inp_north3.value = B[cycle-3][3] if 3 <= cycle < 7 else 0
        
        await RisingEdge(dut.clk)

@cocotb.test()
async def test_systolic_matmul(dut):
    """Main self-checking test for the Systolic Array."""
    
    clock_period_ns = int(1e9 / CLK_HZ)
    cocotb.start_soon(Clock(dut.clk, clock_period_ns, unit="ns").start())
    out_dir = os.path.join(error_designs_dir, error_dir)
    os.makedirs(out_dir, exist_ok=True)
    log_file_path = os.path.join(out_dir, os.path.basename(__file__).replace("test_", "").replace(".py", ".log"))
    file_path = os.path.join(out_dir, "error_timestamp.txt")
    log_file = open(log_file_path, "w")
    open(file_path, 'w').close()
    
    try:
        cocotb.start_soon(monitor_all_signals(dut, log_file))
        
        # Set how many test cases you want to run
        NUM_TESTS = 50
        cocotb.log.info(f"Starting {NUM_TESTS} consecutive matrix multiplications...")
        
        for test_idx in range(NUM_TESTS):

            await FallingEdge(dut.clk)
            
            # 1. Apply active-HIGH reset to clear out the MAC accumulators for the new matrix
            dut.rst.value = 1
            dut.inp_west0.value = 0; dut.inp_west4.value = 0; dut.inp_west8.value = 0; dut.inp_west12.value = 0
            dut.inp_north0.value = 0; dut.inp_north1.value = 0; dut.inp_north2.value = 0; dut.inp_north3.value = 0
            
            await Timer(clock_period_ns * 2, unit='ns')
            await RisingEdge(dut.clk)
            dut.rst.value = 0
            
            # 2. Generate random test matrices
            A = generate_random_matrix(4, 15)
            B = generate_random_matrix(4, 15)
            expected_C = matmul(A, B)
            
            # 3. Launch the coroutine to pipe data in over the next 10 cycles
            drive_task = cocotb.start_soon(drive_systolic_array(dut, A, B))
            
            # 4. Wait for the 'done' signal 
            for _ in range(20):
                await RisingEdge(dut.clk)
                if int(dut.done.value) == 1:
                    break
            else:
                report_error(f"Test {test_idx+1}: 'done' signal never asserted.", "done", file_path)
                
            # Ensure the driver finishes cleanly before sampling
            await drive_task 
            
            await ReadOnly()
            
            # 5. Collect results from the DUT
            results = [
                [int(dut.result0.value),  int(dut.result1.value),  int(dut.result2.value),  int(dut.result3.value)],
                [int(dut.result4.value),  int(dut.result5.value),  int(dut.result6.value),  int(dut.result7.value)],
                [int(dut.result8.value),  int(dut.result9.value),  int(dut.result10.value), int(dut.result11.value)],
                [int(dut.result12.value), int(dut.result13.value), int(dut.result14.value), int(dut.result15.value)]
            ]
            
            # 6. Self-Check Assertion Loop
            for i in range(4):
                for j in range(4):
                    if results[i][j] != expected_C[i][j]:
                        sig_num = i * 4 + j 
                        report_error(f"Test {test_idx+1}: Mismatch at Matrix C[{i}][{j}]. Expected {expected_C[i][j]}, got {results[i][j]}", f"result{sig_num}", file_path)
            
            # Optional: Log progress every 10 tests so your console doesn't get totally swamped
            if (test_idx + 1) % 10 == 0:
                cocotb.log.info(f"Completed {test_idx + 1}/{NUM_TESTS} tests successfully...")
        
        cocotb.log.info(f"SUCCESS! Systolic Array perfectly matched all {NUM_TESTS} tests!")
        
    finally:
        log_file.close()
        cocotb.log.info("Signal log file securely closed.")