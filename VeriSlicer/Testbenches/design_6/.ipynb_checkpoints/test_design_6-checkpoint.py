import cocotb
import os
from cocotb.clock import Clock
from cocotb.triggers import Timer, RisingEdge, FallingEdge, ReadOnly

CLK_HZ = 50_000_000
error_dir = os.environ.get("ERROR_DIR", "error_design_default") #pass through from top script
error_designs_dir = "../Error_designs/"
def report_error(msg, signal_name, file_path):
    """Formats, prints, and forces a disk write of the error banner, then fails."""
    current_time = cocotb.utils.get_sim_time('ns')
    error_banner = (
        f"\n{'='*65}\n"
        f"TEST FAILED AT {current_time} ns\n"
        f"FAILING SIGNAL : {signal_name}\n"
        f"ERROR DETAILS  : {msg}\n"
        f"{'='*65}\n"
    )
    
    try:
        # Resolve absolute path to avoid directory confusion during crash
        abs_path = os.path.abspath(file_path)
        with open(abs_path, 'a') as f:
            f.write(error_banner)
            f.flush()            # Push out of Python's internal memory buffer
            os.fsync(f.fileno()) # Force the operating system to write to the physical disk
    except IOError as e:
        cocotb.log.error(f"Could not write error to file {abs_path}: {e}")

    cocotb.log.error(error_banner)
    assert False, f"Check failed for '{signal_name}'."

async def monitor_all_signals(dut, file_handle):
    """Monitors processor signals and logs a snapshot on clock edges."""
    signals = [
        (dut.clk, "clk"), (dut.rst, "rst"),
        (dut.instruction_address, "inst_addr"),
        (dut.instruction_in, "inst_in"),
        (dut.data_address, "data_addr"),
        (dut.data_R, "data_R"), (dut.data_W, "data_W"),
        (dut.data_in, "data_in"), (dut.data_out, "data_out"),
        (dut.done, "done")
    ]
    
    while True:
        await FallingEdge(dut.clk)
        await ReadOnly()
        
        current_time = cocotb.utils.get_sim_time('ns')
        
        snapshot = []
        for sig, name in signals:
            try:
                val = str(sig.value)
            except ValueError:
                val = "x"
            snapshot.append(f"{name}={val}")
            
        file_handle.write(f"[{current_time} ns] " + " | ".join(snapshot) + "\n")
        file_handle.flush()

async def memory_model(dut, inst_mem, data_mem):
    """Simulates the external instruction ROM and data RAM."""
    while True:
        await FallingEdge(dut.clk)
        
        # --- Instruction ROM Read ---
        addr = int(dut.instruction_address.value) if dut.instruction_address.value.is_resolvable else 0
        if addr < len(inst_mem):
            dut.instruction_in.value = inst_mem[addr]
        else:
            dut.instruction_in.value = 0 
            
        # --- Data RAM Read/Write ---
        if dut.data_R.value == 1:
            d_addr = int(dut.data_address.value) if dut.data_address.value.is_resolvable else 0
            if dut.data_W.value == 1:
                data_val = int(dut.data_out.value)
                data_mem[d_addr] = data_val
                cocotb.log.debug(f"[MEM WRITE] Addr {d_addr} = {data_val}")
            else:
                dut.data_in.value = data_mem.get(d_addr, 0)

async def output_protocol_checker(dut, err_file_path):
    """Continuously monitors CPU primary outputs for invalid states or illegal behavior."""
    MAX_INSTRUCTIONS = 100 
    MAX_RAM_ADDR = 1023    
    
    while True:
        await ReadOnly() 
        
        # 1. Verify no primary output signal is floating or unknown
        control_signals = [
            ("instruction_address", dut.instruction_address),
            ("data_address", dut.data_address),
            ("data_R", dut.data_R),
            ("data_W", dut.data_W),
            ("done", dut.done)
        ]
        
        for name, sig in control_signals:
            if not sig.value.is_resolvable:
                report_error(f"Signal '{name}' went to unknown state 'X' or 'Z'.", name, err_file_path)

        # 2. Verify primary output: instruction_address
        pc = int(dut.instruction_address.value)
        if pc > MAX_INSTRUCTIONS:
            report_error(f"Program Counter jumped out of bounds: PC={pc}", "instruction_address", err_file_path)

        # 3. Verify primary output: data_address
        d_addr = int(dut.data_address.value)
        if d_addr > MAX_RAM_ADDR:
            report_error(f"Data Address out of bounds: {d_addr}", "data_address", err_file_path)

        # 4. Verify primary output: data_out (Only checked when data_W is high)
        if dut.data_W.value == 1:
            if not dut.data_out.value.is_resolvable:
                report_error(f"CPU attempted to write 'X' to RAM at address {d_addr}", "data_out", err_file_path)

        await RisingEdge(dut.clk)

@cocotb.test()
async def test_simd_processor(dut):
    """End-to-end test of the SIMD CPU executing instructions from memory."""
    
    clock_period_ns = int(1e9 / CLK_HZ)
    cocotb.start_soon(Clock(dut.clk, clock_period_ns, unit="ns").start())
    
    out_dir = os.path.join(error_designs_dir, error_dir)
    os.makedirs(out_dir, exist_ok=True)
    log_file_path = os.path.join(out_dir, os.path.basename(__file__).replace("test_", "").replace(".py", ".log"))
    err_file_path = os.path.join(out_dir, "error_timestamp.txt")
    log_file = open(log_file_path, "w")
    open(err_file_path, 'w').close() # Ensure fresh error file
    
    cocotb.start_soon(monitor_all_signals(dut, log_file))

    inst_binary_strings = [
        "100110000000000000", "100110010000000001", "100110100000000010", "000000000000000001",
        "000000000000001000", "101001000000000000", "101100010100100010", "000000000000000110",
        "101001010000000011", "101001100000000100", "101001000000000101", "100111010000000010",
        "100111100000000011", "100111000000000100", "101101010001011010", "100101000000000010",
        "000001000000000001", "000001000000001000", "000111000000001001", "001101000000001001",
        "101010010000000101", "101010100000000110", "101010000000000111", "100110010000000101",
        "100110100000000111", "001100000000001001", "000110000000001001", "011000000000000001",
        "010101000000000010", "000011100000001110", "001001100000001110", "100001000000000010",
        "011011000000000100", "011110000000001001", "101100000000001111", "101100010000000100",
        "101100100000000010", "010010000000000110", "001001000000001000", "001111010000001101",
        "101001010000000111", "101001100000000100", "101001000000001000", "100111010000000110",
        "100111100000000111", "100111000000001000", "011001000000000001", "010110000000000010",
        "000100100000001110", "001010100000001110", "100010000000000010", "011100000000000100",
        "011111000000001001", "101101000000001111", "101101010000000100", "101101100000000010",
        "010011000000000110", "001010000000001000", "010000010000001101", "101010010000001001",
        "101010100000000110", "101010000000000111", "101000010000001001", "101000100000000110",
        "101000000000000111", "101110100001011010", "011010000000000001", "010111000000000010",
        "000101100000001110", "001011100000001110", "100011000000000010", "011101000000000100",
        "100000000000001001", "101110000000001111", "101110010000000100", "101110100000000010",
        "010100000000000110", "001011000000001000", "010001010000000101", "101110010001011010",
        "000010000000000001", "000010000000001000", "001000000000001001", "001110000000001001",
        "101011010000001001", "101011100000000110", "101011000000000111", "100100000000010000",
        "111111000000000000"
    ]
    
    INST_MEM = [int(b, 2) for b in inst_binary_strings]
    DATA_MEM = {0: 5, 1: 15, 2: 4} 
    
    cocotb.start_soon(memory_model(dut, INST_MEM, DATA_MEM))

    try:
        dut.rst.value = 1
        dut.instruction_in.value = 0
        dut.data_in.value = 0
        await Timer(clock_period_ns * 2, unit='ns')
        
        await FallingEdge(dut.clk)
        dut.rst.value = 0
        cocotb.log.info("Reset de-asserted. Processor starting...")
        
        # Start the continuous cycle-by-cycle output monitor
        cocotb.start_soon(output_protocol_checker(dut, err_file_path))
        
        # Verify primary output: done (timeout check)
        timeout_cycles = 2500
        cycles = 0
        
        while int(dut.done.value) != 1:
            await RisingEdge(dut.clk)
            cycles += 1
            if cycles > timeout_cycles:
                report_error("Simulation timed out. 'done' signal never asserted.", "done", err_file_path)
                
        cocotb.log.info(f"Processor halted successfully after {cycles} cycles.")
        
        expected_final_memory = {
            0: 20,         
            1: 15,         
            2: 4,          
            3: 314,        
            4: 2,          
            5: 13364,      
            6: 43690,      
            7: 39321,      
            8: 15,         
            9: 43690       
        }
        
        # 5a. Verify primary output: data_out (Checks math/logic accuracy)
        for addr, expected_val in expected_final_memory.items():
            actual_val = DATA_MEM.get(addr, -1)
            if actual_val != expected_val:
                report_error(f"Mismatch at RAM[{addr}]: Expected {expected_val}, Got {actual_val}", "data_out", err_file_path)
                
        # 5b. Verify primary output: data_address & data_W (Checks illegal write locations)
        for addr in DATA_MEM.keys():
            if addr not in expected_final_memory:
                report_error(f"CPU illegally wrote to RAM[{addr}] (Value: {DATA_MEM[addr]})", "data_address", err_file_path)
                
        cocotb.log.info("All final memory state assertions passed! Design is clean.")

    finally:
        log_file.close()
        cocotb.log.info(f"Signal log file saved to {log_file_path}")