import os
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer, ReadOnly

error_dir = os.environ.get("ERROR_DIR", "error_design_default") #pass through from top script
error_designs_dir = "../Error_designs/"
# ============================================================
# Constants (match RTL)
# ============================================================
CBR_ADDR  = 0x0038
BBR_ADDR  = 0x0039
CBAR_ADDR = 0x003A


# ============================================================
# Error helpers
# ============================================================

def report_error(msg, name, file_path):
    t = cocotb.utils.get_sim_time("ns")
    banner = f"\nFAIL @{t}ns | {name} | {msg}\n"
    with open(file_path, "a") as f:
        f.write(banner)

    cocotb.log.error(banner)
    assert False


def check_eq(name, got, exp, file_path):
    if got != exp:
        report_error(f"Expected {hex(exp)}, got {hex(got)}", name, file_path)


# ============================================================
# Bus helpers
# ============================================================

async def io_write(dut, addr, data):
    dut.addr_in.value = addr
    dut.dq.value = data

    dut.iorq_n.value = 0
    dut.wr_n.value = 0
    dut.rd_n.value = 1
    dut.phi.value = 0

    await Timer(5, unit="ns")

    dut.wr_n.value = 1
    dut.iorq_n.value = 1

    await Timer(5, unit="ns")


async def io_read(dut, addr):
    dut.addr_in.value = addr

    dut.iorq_n.value = 0
    dut.rd_n.value = 0
    dut.wr_n.value = 1
    dut.phi.value = 0

    await Timer(5, unit="ns")
    val = int(dut.dq.value)

    dut.rd_n.value = 1
    dut.iorq_n.value = 1

    return val


# ============================================================
# Monitor
# ============================================================

async def monitor(dut, f):
    while True:
        await RisingEdge(dut.phi)
        await ReadOnly()

        t = cocotb.utils.get_sim_time("ns")
        f.write(
            f"[{t}] addr_in={hex(int(dut.addr_in.value))} "
            f"addr_out={hex(int(dut.addr_out.value))} "
            f"dq={dut.dq.value}\n"
        )
        f.flush()


# ============================================================
# Main Test
# ============================================================

@cocotb.test()
async def mmu180_testbench(dut):

    dut._log.info("==== MMU TEST START ====")

    # Clock (phi)
    cocotb.start_soon(Clock(dut.phi, 10, unit="ns").start())

    # Files
    out_dir = os.path.join(error_designs_dir, error_dir)
    os.makedirs(out_dir, exist_ok=True)
    log_file_path = os.path.join(out_dir, os.path.basename(__file__).replace("test_", "").replace(".py", ".log"))
    err_file = os.path.join(out_dir, "error_timestamp.txt")
    
    log_file = open(log_file_path, "w")
    err_file = os.path.join(out_dir, "mmu_error.log")
    open(err_file, "w").close()

    cocotb.start_soon(monitor(dut, log_file))

    # --------------------------------------------------
    # INIT
    # --------------------------------------------------
    dut.reset_n.value = 0
    dut.en.value = 1

    dut.iorq_n.value = 1
    dut.mreq_n.value = 1
    dut.rd_n.value = 1
    dut.wr_n.value = 1

    dut.addr_in.value = 0
    dut.dq.value = 0

    await Timer(20, unit="ns")

    dut.reset_n.value = 1
    await Timer(10, unit="ns")

    # --------------------------------------------------
    # WRITE REGISTERS
    # --------------------------------------------------
    dut._log.info("Writing MMU registers")

    await io_write(dut, CBR_ADDR, 0x12)
    await io_write(dut, BBR_ADDR, 0x34)
    await io_write(dut, CBAR_ADDR, 0xF2)

    # --------------------------------------------------
    # READ BACK
    # --------------------------------------------------
    dut._log.info("Reading back registers")

    cbr = await io_read(dut, CBR_ADDR)
    bbr = await io_read(dut, BBR_ADDR)
    cbar = await io_read(dut, CBAR_ADDR)

    check_eq("CBR", cbr, 0x12, err_file)
    check_eq("BBR", bbr, 0x34, err_file)
    check_eq("CBAR", cbar, 0xF2, err_file)

    # --------------------------------------------------
    # ADDRESS TRANSLATION TEST
    # --------------------------------------------------
    dut._log.info("Testing address translation")

    # Case 1: normal (no translation)
    dut.mreq_n.value = 0
    dut.addr_in.value = 0x000100

    await Timer(5, unit="ns")

    check_eq(
        "addr_out_no_translation",
        int(dut.addr_out.value),
        (0x000100 >> 12) & 0xFF,
        err_file
    )

    # Case 2: translated region
    dut.addr_in.value = 0x000F00  # high nibble region

    await Timer(5, unit="ns")

    # Expected (approx model)
    hi_nibble = (0x000F00 >> 12) & 0xF
    expected = (0x12 + hi_nibble) & 0xFF  # using CBR

    check_eq(
        "addr_out_translated",
        int(dut.addr_out.value),
        expected,
        err_file
    )

    # --------------------------------------------------
    # HIGH ADDRESS BYPASS
    # --------------------------------------------------
    dut._log.info("Testing high address bypass")

    dut.addr_in.value = 0x01000000  # addr_in[23:16] != 0

    await Timer(5, unit="ns")

    check_eq(
        "addr_out_bypass",
        int(dut.addr_out.value),
        (0x01000000 >> 12) & 0xFF,
        err_file
    )

    dut._log.info("==== MMU TEST PASSED ====")

    log_file.close()