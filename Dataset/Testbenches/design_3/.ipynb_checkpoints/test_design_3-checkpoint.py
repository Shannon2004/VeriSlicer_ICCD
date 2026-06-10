import cocotb
import os
import random
import struct
import hashlib
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer, First, ReadOnly
from cocotb.utils import get_sim_time

error_dir = os.environ.get("ERROR_DIR", "error_design_default") #pass through from top script
error_designs_dir = "../Error_designs/"
# ----------------------------------------------------------------
# Constants and Address Map
# ----------------------------------------------------------------
ADDR_NAME0       = 0x00
ADDR_NAME1       = 0x01
ADDR_VERSION     = 0x02
ADDR_CTRL        = 0x08
CTRL_INIT_VALUE  = 0x01
CTRL_NEXT_VALUE  = 0x02
ADDR_STATUS      = 0x09
STATUS_VALID_BIT = 1  
ADDR_BLOCK0      = 0x10
ADDR_DIGEST0     = 0x20

# ----------------------------------------------------------------
# Helper Coroutines & Functions
# ----------------------------------------------------------------
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
        (dut.reset_n, "reset_n"),
        (dut.cs, "cs"),
        (dut.we, "we"),
        (dut.address, "address"),
        (dut.write_data, "write_data"),
        (dut.read_data, "read_data")
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

async def reset_dut(dut):
    dut.reset_n.value = 0
    await Timer(4, unit="ns")
    dut.reset_n.value = 1
    await RisingEdge(dut.clk)

async def write_word(dut, address, data):
    dut.address.value = address
    dut.write_data.value = data
    dut.cs.value = 1
    dut.we.value = 1
    await RisingEdge(dut.clk)
    dut.cs.value = 0
    dut.we.value = 0

async def read_word(dut, address):
    dut.address.value = address
    dut.cs.value = 1
    dut.we.value = 0
    await RisingEdge(dut.clk)
    data = int(dut.read_data.value)
    dut.cs.value = 0
    return data

async def write_block(dut, block_val):
    for i in range(16):
        shift = (15 - i) * 32
        word = (block_val >> shift) & 0xFFFFFFFF
        await write_word(dut, ADDR_BLOCK0 + i, word)

async def wait_ready(dut):
    for _ in range(4):
        await RisingEdge(dut.clk)
    valid = 0
    while valid == 0:
        status = await read_word(dut, ADDR_STATUS)
        valid = (status >> STATUS_VALID_BIT) & 1

async def read_digest(dut):
    digest = 0
    for i in range(5):
        word = await read_word(dut, ADDR_DIGEST0 + i)
        digest = (digest << 32) | word
    return digest

def pad_message(msg: bytes) -> bytes:
    original_bit_len = len(msg) * 8
    msg += b'\x80'
    while len(msg) % 64 != 56:
        msg += b'\x00'
    msg += struct.pack('>Q', original_bit_len)
    return msg

# ----------------------------------------------------------------
# Main Test Case
# ----------------------------------------------------------------
@cocotb.test()
async def test_sha1_randomized(dut):
    dut._log.info("   -- Testbench for sha1 started --")
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

        dut.reset_n.value = 0
        dut.cs.value = 0
        dut.we.value = 0
        dut.address.value = 0
        dut.write_data.value = 0

        await reset_dut(dut)

        NUM_TESTS = 50
        dut._log.info(f"*** Starting {NUM_TESTS} randomized dynamic test cases...")

        for i in range(NUM_TESTS):
            msg_len = random.randint(0, 150)
            raw_msg = os.urandom(msg_len)
            expected_hex = hashlib.sha1(raw_msg).hexdigest()
            expected_int = int(expected_hex, 16)

            padded_msg = pad_message(raw_msg)
            num_blocks = len(padded_msg) // 64

            # Log the raw input being tested
            dut._log.info(f"--- TC {i+1} | Input Length: {msg_len} bytes")
            dut._log.info(f"    Raw Input (Hex): {raw_msg.hex() if msg_len > 0 else '<empty>'}")

            for b in range(num_blocks):
                block_bytes = padded_msg[b*64 : (b+1)*64]
                block_int = int.from_bytes(block_bytes, byteorder='big')
                await write_block(dut, block_int)
                
                if b == 0:
                    await write_word(dut, ADDR_CTRL, CTRL_INIT_VALUE)
                else:
                    await write_word(dut, ADDR_CTRL, CTRL_NEXT_VALUE)
                await wait_ready(dut)
            
            hardware_digest = await read_digest(dut)
            
            # Log the output from the hardware
            dut._log.info(f"    Output Hash    : {hex(hardware_digest)[2:].zfill(40)}")
            
            # Replaced standard assert with the nicely formatted report_error function
            if hardware_digest != expected_int:
                msg = f"Expected {hex(expected_int)}, Got {hex(hardware_digest)}"
                report_error(msg, "digest_output", file_path)
                
        dut._log.info(f"*** All {NUM_TESTS} dynamic test cases completed and matched Python's hashlib!")
    
    finally:
        log_file.close()
        dut._log.info("Signal log file securely closed.")
