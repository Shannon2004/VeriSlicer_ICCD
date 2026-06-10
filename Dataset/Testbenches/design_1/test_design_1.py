import os
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer, First, ReadOnly

error_dir = os.environ.get("ERROR_DIR", "error_design_default") #pass through from top script
error_designs_dir = "../Error_designs/"

# Default Configuration Matching CORDIC Core Defaults
ITERATIONS = 16
CORDIC_1 = 19896  # Inverse CORDIC gain (~0.603)

# Data Tables Transcribed from tb_cordic.v (Index 0 to 90)
X_EXPECTED = (
    32768, 32763, 32748, 32723, 32688, 32643, 32588, 32523, 32449, 32364,
    32270, 32165, 32051, 31928, 31794, 31651, 31498, 31336, 31164, 30982,
    30791, 30591, 30381, 30163, 29935, 29697, 29451, 29196, 28932, 28659,
    28377, 28087, 27788, 27481, 27165, 26841, 26509, 26169, 25821, 25465,
    25101, 24730, 24351, 23964, 23571, 23170, 22762, 22347, 21926, 21497,
    21062, 20621, 20173, 19720, 19260, 18794, 18323, 17846, 17364, 16876,
    16384, 15886, 15383, 14876, 14364, 13848, 13327, 12803, 12275, 11743,
    11207, 10668, 10125,  9580,  9032,  8480,  7927,  7371,  6812,  6252,
     5690,  5126,  4560,  3993,  3425,  2855,  2285,  1714,  1143,   571, 0
)

Y_EXPECTED = (
        0,   571,  1143,  1714,  2285,  2855,  3425,  3993,  4560,  5126,
     5690,  6252,  6812,  7371,  7927,  8480,  9032,  9580, 10125, 10668,
    11207, 11743, 12275, 12803, 13327, 13848, 14364, 14876, 15383, 15886,
    16383, 16876, 17364, 17846, 18323, 18794, 19260, 19720, 20173, 20621,
    21062, 21497, 21926, 22347, 22762, 23170, 23571, 23964, 24351, 24730,
    25101, 25465, 25821, 26169, 26509, 26841, 27165, 27481, 27788, 28087,
    28377, 28659, 28932, 29196, 29451, 29697, 29935, 30163, 30381, 30591,
    30791, 30982, 31164, 31336, 31498, 31651, 31794, 31928, 32051, 32165,
    32270, 32364, 32449, 32523, 32588, 32643, 32688, 32723, 32748, 32763, 32768
)

Z_INPUTS = (
        0,   571,  1143,  1715,  2287,  2859,  3431,  4003,  4575,  5147,
     5719,  6291,  6862,  7434,  8006,  8578,  9150,  9722, 10294, 10866,
    11438, 12010, 12582, 13153, 13725, 14297, 14869, 15441, 16013, 16585,
    17157, 17729, 18301, 18873, 19444, 20016, 20588, 21160, 21732, 22304,
    22876, 23448, 24020, 24592, 25164, 25735, 26307, 26879, 27451, 28023,
    28595, 29167, 29739, 30311, 30883, 31455, 32026, 32598, 33170, 33742,
    34314, 34886, 35458, 36030, 36602, 37174, 37746, 38317, 38889, 39461,
    40033, 40605, 41177, 41749, 42321, 42893, 43465, 44037, 44608, 45180,
    45752, 46324, 46896, 47468, 48040, 48612, 49184, 49756, 50328, 50899, 51471
)

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

async def monitor_all_signals(dut, file_handle):
    """Monitors all input/output signals and logs a complete snapshot on any change."""
    
    # Setup the CORDIC signals to track
    signals = [
        (dut.clk, "clk"), (dut.rst, "rst"),
        (dut.x_i, "x_i"), (dut.y_i, "y_i"), (dut.theta_i, "theta_i"),
        (dut.x_o, "x_o"), (dut.y_o, "y_o"), (dut.theta_o, "theta_o")
    ]
    
    # Add optional architecture signals if present
    if hasattr(dut, "init"):
        signals.insert(2, (dut.init, "init"))
        
    await ReadOnly()
    current_time = cocotb.utils.get_sim_time('ns')
    
    snapshot = [f"{name}={str(sig.value)}" for sig, name in signals]
    file_handle.write(f"[{current_time:.1f} ns] " + " | ".join(snapshot) + "\n")
    file_handle.flush()
    
    last_logged_time = current_time

    while True:
        triggers = [sig.value_change for sig, _ in signals if hasattr(sig, 'value_change')]
        await First(*triggers)
        await ReadOnly()
        
        current_time = cocotb.utils.get_sim_time('ns')
        if current_time != last_logged_time:
            snapshot = [f"{name}={str(sig.value)}" for sig, name in signals]
            file_handle.write(f"[{current_time:.1f} ns] " + " | ".join(snapshot) + "\n")
            file_handle.flush()
            last_logged_time = current_time

def check_results(dut, angle_idx, lx, ly, ltheta, mode, file_path):
    """Validation logic mirroring 'show_results' task in Verilog."""
    if mode == "VECTOR":
        expected_rad = (angle_idx * 3.14) / 180.0
        computed_rad = ltheta / 32768.0
        error = abs(computed_rad - expected_rad)
        
        dut._log.info(f"Angle: {expected_rad:.6f} computed: {computed_rad:.6f} diff: {error:.6f}")
        
        if error > 0.001:
            expected_ltheta = int(expected_rad * 32768.0)
            msg = f"Expected theta_o to be {expected_ltheta}, got {ltheta}"
            report_error(msg, "theta_o", file_path)

    elif mode == "ROTATE":
        rx = lx / 32768.0
        ry = ly / 32768.0
        ex = abs(lx - X_EXPECTED[angle_idx])
        ey = abs(ly - Y_EXPECTED[angle_idx])
        
        err_str = f" errors ex={ex} ey={ey}" if (ex > 10 or ey > 10) else ""
        dut._log.info(f"Angle: {angle_idx:2d}  sin = {ry:.6f}  cos = {rx:.6f}{err_str}")
        
        if ex > 10:
            msg = f"Expected x_o to be {X_EXPECTED[angle_idx]}, got {lx}"
            report_error(msg, "x_o", file_path)
        if ey > 10:
            msg = f"Expected y_o to be {Y_EXPECTED[angle_idx]}, got {ly}"
            report_error(msg, "y_o", file_path)

@cocotb.test()
async def cordic_testbench(dut):
    """Cocotb translation of tb_cordic.v"""
    
    # Evaluate environment configs (defaults to your Verilog setup)
    MODE = os.environ.get("CORDIC_MODE", "ROTATE").upper()
    
    # Auto-detect Architecture
    if hasattr(dut, "init"):
        ARCH = "ITERATE"
    else:
        # User override, defaults to PIPELINE
        ARCH = os.environ.get("CORDIC_ARCH", "PIPELINE").upper()

    dut._log.info(f"--- Starting CORDIC Simulation ---")
    dut._log.info(f"Configuration: MODE = {MODE}, ARCH = {ARCH}")

    # Start 2ns Clock
    cocotb.start_soon(Clock(dut.clk, 2, unit="ns").start())

    out_dir = os.path.join(error_designs_dir, error_dir)
    os.makedirs(out_dir, exist_ok=True)
    log_file_path = os.path.join(out_dir, os.path.basename(__file__).replace("test_", "").replace(".py", ".log"))
    file_path = os.path.join(out_dir, "error_timestamp.txt")
    
    log_file = open(log_file_path, "w")
    open(file_path, 'w').close()
    
    try:
        # Start parallel task logging the signals to a file
        cocotb.start_soon(monitor_all_signals(dut, log_file))

        # Initialize Pins
        dut.rst.value = 1
        dut.x_i.value = 0
        dut.y_i.value = 0
        dut.theta_i.value = 0
        if ARCH == "ITERATE":
            dut.init.value = 0

        # Robust Reset Sequence: Wait for 3 falling edges to ensure pipeline flushes
        for _ in range(3):
            await FallingEdge(dut.clk)
        
        # Release reset and wait for one more falling edge so we are safely out of reset
        dut.rst.value = 0
        await FallingEdge(dut.clk)

        # -------------------------------------------------------------
        # STIMULUS GENERATION & CHECKING
        # -------------------------------------------------------------
        
        if ARCH == "PIPELINE":
            for j in range(91 + ITERATIONS - 2):
                
                # Drive Inputs
                if j <= 90:
                    if MODE == "ROTATE":
                        dut.x_i.value = CORDIC_1
                        dut.y_i.value = 0
                        dut.theta_i.value = Z_INPUTS[j]
                    elif MODE == "VECTOR":
                        dut.x_i.value = X_EXPECTED[j]
                        dut.y_i.value = Y_EXPECTED[j]
                        dut.theta_i.value = 0
                else:
                    # Drive zeroes to flush the rest
                    dut.x_i.value = 0
                    dut.y_i.value = 0
                    dut.theta_i.value = 0
                        
                # Wait for falling edge to evaluate (avoids delta-cycle race conditions)
                await FallingEdge(dut.clk)

                # Check Outputs (Wait for pipeline latency)
                if j >= (ITERATIONS - 2):
                    check_idx = j - (ITERATIONS - 2)
                    if check_idx <= 90:
                        lx = int(dut.x_o.value.to_signed())
                        ly = int(dut.y_o.value.to_signed())
                        ltheta = int(dut.theta_o.value.to_signed())
                        check_results(dut, check_idx, lx, ly, ltheta, MODE, file_path)

            # Flush pipe safely
            for _ in range(5):
                await FallingEdge(dut.clk)

        elif ARCH == "ITERATE":
            for j in range(91):
                if MODE == "ROTATE":
                    dut.x_i.value = CORDIC_1
                    dut.y_i.value = 0
                    dut.theta_i.value = Z_INPUTS[j]
                elif MODE == "VECTOR":
                    dut.x_i.value = X_EXPECTED[j]
                    dut.y_i.value = Y_EXPECTED[j]
                    dut.theta_i.value = 0

                # Toggle init on falling edges
                dut.init.value = 1
                await FallingEdge(dut.clk)
                dut.init.value = 0
                
                # Wait for calculation loop
                for _ in range(ITERATIONS):
                    await FallingEdge(dut.clk)
                
                lx = int(dut.x_o.value.to_signed())
                ly = int(dut.y_o.value.to_signed())
                ltheta = int(dut.theta_o.value.to_signed())
                check_results(dut, j, lx, ly, ltheta, MODE, file_path)

        elif ARCH == "COMBINATORIAL":
            for j in range(91):
                if MODE == "ROTATE":
                    dut.x_i.value = CORDIC_1
                    dut.y_i.value = 0
                    dut.theta_i.value = Z_INPUTS[j]
                elif MODE == "VECTOR":
                    dut.x_i.value = X_EXPECTED[j]
                    dut.y_i.value = Y_EXPECTED[j]
                    dut.theta_i.value = 0

                await Timer(1, unit="ns")
                
                lx = int(dut.x_o.value.to_signed())
                ly = int(dut.y_o.value.to_signed())
                ltheta = int(dut.theta_o.value.to_signed())
                check_results(dut, j, lx, ly, ltheta, MODE, file_path)

        dut._log.info("Simulation Complete. All checks passed.")
    
    finally:
        log_file.close()
        dut._log.info("Signal log file securely closed.")
