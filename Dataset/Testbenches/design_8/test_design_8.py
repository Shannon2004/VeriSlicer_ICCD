import os
import random
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer, First, ReadOnly

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

    try:
        with open(file_path, "a") as f:
            f.write(error_banner)
    except IOError as e:
        cocotb.log.error(f"Could not write error to file {file_path}: {e}")

    cocotb.log.error(error_banner)
    assert False, f"Signal '{signal_name}' failed."


async def monitor_all_signals(dut, file_handle):
    signals = [
        (dut.clk, "clk"),
        (dut.reset, "reset"),
        (dut.if_pc, "if_pc"),
        (dut.if_instr, "if_instr"),
        (dut.wb_reg_write, "wb_reg_write"),
        (dut.wb_rd, "wb_rd"),
        (dut.wb_wd, "wb_wd"),
        (dut.id_pc, "id_pc"),
        (dut.id_rd1, "id_rd1"),
        (dut.id_rd2, "id_rd2"),
        (dut.id_imm, "id_imm"),
        (dut.id_rs1, "id_rs1"),
        (dut.id_rs2, "id_rs2"),
        (dut.id_rd, "id_rd"),
        (dut.id_opcode, "id_opcode"),
        (dut.id_funct3, "id_funct3"),
        (dut.id_funct7, "id_funct7"),
    ]

    await ReadOnly()
    current_time = cocotb.utils.get_sim_time("ns")
    snapshot = [f"{name}={str(sig.value)}" for sig, name in signals]
    file_handle.write(f"[{current_time:.1f} ns] " + " | ".join(snapshot) + "\n")
    file_handle.flush()
    last_logged_time = current_time

    while True:
        triggers = [sig.value_change for sig, _ in signals if hasattr(sig, "value_change")]
        await First(*triggers)
        await ReadOnly()

        current_time = cocotb.utils.get_sim_time("ns")
        if current_time != last_logged_time:
            snapshot = [f"{name}={str(sig.value)}" for sig, name in signals]
            file_handle.write(f"[{current_time:.1f} ns] " + " | ".join(snapshot) + "\n")
            file_handle.flush()
            last_logged_time = current_time


def log_results(dut):
    t = cocotb.utils.get_sim_time("ns")
    dut._log.info(f"T={t} | PC={int(dut.id_pc.value):08X} | Instr={int(dut.if_instr.value):08X}")
    dut._log.info(
        f" opcode={int(dut.id_opcode.value):07b} rd={int(dut.id_rd.value)} "
        f"rs1={int(dut.id_rs1.value)} rs2={int(dut.id_rs2.value)} "
        f"funct3={int(dut.id_funct3.value):03b} funct7={int(dut.id_funct7.value):07b}"
    )
    dut._log.info(
        f" rd1={int(dut.id_rd1.value):08X} rd2={int(dut.id_rd2.value):08X} imm={int(dut.id_imm.value):08X}"
    )
    dut._log.info("--------------------------------------------------")


# ============================================================
# Reference model helpers
# ============================================================

def u32(x):
    return x & 0xFFFFFFFF

def sign_extend(value, bits):
    sign = 1 << (bits - 1)
    return ((value & ((1 << bits) - 1)) ^ sign) - sign

def decode_fields(instr):
    instr &= 0xFFFFFFFF
    return {
        "opcode": instr & 0x7F,
        "rd":     (instr >> 7) & 0x1F,
        "funct3": (instr >> 12) & 0x7,
        "rs1":    (instr >> 15) & 0x1F,
        "rs2":    (instr >> 20) & 0x1F,
        "funct7": (instr >> 25) & 0x7F,
    }

def imm_gen_model(instr):
    instr &= 0xFFFFFFFF
    opcode = instr & 0x7F

    # I-type
    if opcode in (0b0010011, 0b0000011, 0b1100111):
        imm12 = (instr >> 20) & 0xFFF
        return u32(sign_extend(imm12, 12))

    # S-type
    elif opcode == 0b0100011:
        imm12 = (((instr >> 25) & 0x7F) << 5) | ((instr >> 7) & 0x1F)
        return u32(sign_extend(imm12, 12))

    # B-type
    elif opcode == 0b1100011:
        imm13 = (
            (((instr >> 31) & 0x1) << 12) |
            (((instr >> 7)  & 0x1) << 11) |
            (((instr >> 25) & 0x3F) << 5) |
            (((instr >> 8)  & 0xF) << 1)
        )
        return u32(sign_extend(imm13, 13))

    # U-type
    elif opcode in (0b0110111, 0b0010111):
        return u32(instr & 0xFFFFF000)

    # J-type
    elif opcode == 0b1101111:
        imm21 = (
            (((instr >> 31) & 0x1) << 20) |
            (((instr >> 12) & 0xFF) << 12) |
            (((instr >> 20) & 0x1) << 11) |
            (((instr >> 21) & 0x3FF) << 1)
        )
        return u32(sign_extend(imm21, 21))

    else:
        return 0


# ============================================================
# Task-style helpers mirroring tb.v
# ============================================================

async def apply_instr(dut, instr, pc_val):
    await FallingEdge(dut.clk)
    dut.if_instr.value = instr & 0xFFFFFFFF
    dut.if_pc.value = pc_val & 0xFFFFFFFF

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    log_results(dut)


async def write_back(dut, rd, data):
    await FallingEdge(dut.clk)
    dut.wb_reg_write.value = 1
    dut.wb_rd.value = rd & 0x1F
    dut.wb_wd.value = data & 0xFFFFFFFF

    await RisingEdge(dut.clk)
    dut.wb_reg_write.value = 0


def check_eq(name, got, expected, file_path, width=None):
    if got != expected:
        if width is None:
            report_error(f"Expected {name}={expected}, got {got}", name, file_path)
        else:
            fmt = f"0x{{:0{width}X}}"
            report_error(
                f"Expected {name}={fmt.format(expected)}, got {fmt.format(got)}",
                name,
                file_path
            )


def check_instr_outputs(dut, instr_latched, expected_pc, regs, file_path):
    fields = decode_fields(instr_latched)
    exp_imm = imm_gen_model(instr_latched)

    rs1 = fields["rs1"]
    rs2 = fields["rs2"]

    exp_rd1 = 0 if rs1 == 0 else regs[rs1]
    exp_rd2 = 0 if rs2 == 0 else regs[rs2]

    check_eq("id_pc", int(dut.id_pc.value), expected_pc, file_path, width=8)
    check_eq("id_opcode", int(dut.id_opcode.value), fields["opcode"], file_path)
    check_eq("id_rd", int(dut.id_rd.value), fields["rd"], file_path)
    check_eq("id_funct3", int(dut.id_funct3.value), fields["funct3"], file_path)
    check_eq("id_rs1", int(dut.id_rs1.value), fields["rs1"], file_path)
    check_eq("id_rs2", int(dut.id_rs2.value), fields["rs2"], file_path)
    check_eq("id_funct7", int(dut.id_funct7.value), fields["funct7"], file_path)
    check_eq("id_imm", int(dut.id_imm.value), exp_imm, file_path, width=8)
    check_eq("id_rd1", int(dut.id_rd1.value), exp_rd1, file_path, width=8)
    check_eq("id_rd2", int(dut.id_rd2.value), exp_rd2, file_path, width=8)


# ============================================================
# Main testbench
# ============================================================

@cocotb.test()
async def id_stage_testbench(dut):
    dut._log.info("--- Starting ID Stage Simulation ---")

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    out_dir = os.path.join(error_designs_dir, error_dir)
    os.makedirs(out_dir, exist_ok=True)
    log_file_path = os.path.join(out_dir, os.path.basename(__file__).replace("test_", "").replace(".py", ".log"))
    error_file_path = os.path.join(out_dir, "error_timestamp.txt")

    log_file = open(log_file_path, "w")
    open(error_file_path, "w").close()

    # mirror regfile state
    regs = [0] * 32

    try:
        cocotb.start_soon(monitor_all_signals(dut, log_file))

        # Init
        dut.reset.value = 1
        dut.if_pc.value = 0
        dut.if_instr.value = 0
        dut.wb_reg_write.value = 0
        dut.wb_rd.value = 0
        dut.wb_wd.value = 0

        # Reset
        await RisingEdge(dut.clk)
        dut.reset.value = 1
        await RisingEdge(dut.clk)
        dut.reset.value = 0

        # Check reset outputs after reset cycle
        await Timer(1, unit="ns")
        check_eq("id_pc", int(dut.id_pc.value), 0, error_file_path, width=8)
        check_eq("id_imm", int(dut.id_imm.value), 0, error_file_path, width=8)

        # ---------------------------
        # Preload registers
        # ---------------------------
        await write_back(dut, 1, 0x0000000A)  # x1 = 10
        regs[1] = 0x0000000A

        await write_back(dut, 2, 0x00000014)  # x2 = 20
        regs[2] = 0x00000014

        await write_back(dut, 3, 0x00000005)  # x3 = 5
        regs[3] = 0x00000005

        # x0 must remain zero even if written
        await write_back(dut, 0, 0xDEADBEEF)
        regs[0] = 0

        # ---------------------------
        # Test 1: R-type (ADD)
        # add x5, x1, x2
        # ---------------------------
        instr = int("0000000_00010_00001_000_00101_0110011".replace("_", ""), 2)
        pc = 0x1000
        await apply_instr(dut, instr, pc)
        check_instr_outputs(dut, instr, pc, regs, error_file_path)

        # ---------------------------
        # Test 2: I-type (ADDI)
        # addi x6, x1, 10
        # ---------------------------
        instr = int("000000001010_00001_000_00110_0010011".replace("_", ""), 2)
        pc = 0x1004
        await apply_instr(dut, instr, pc)
        check_instr_outputs(dut, instr, pc, regs, error_file_path)

        # ---------------------------
        # Test 3: S-type (SW)
        # sw x2, 8(x1)
        # ---------------------------
        instr = int("0000000_00010_00001_010_01000_0100011".replace("_", ""), 2)
        pc = 0x1008
        await apply_instr(dut, instr, pc)
        check_instr_outputs(dut, instr, pc, regs, error_file_path)

        # ---------------------------
        # Test 4: B-type (BEQ)
        # beq x1, x2, offset
        # ---------------------------
        instr = int("0000000_00010_00001_000_00000_1100011".replace("_", ""), 2)
        pc = 0x100C
        await apply_instr(dut, instr, pc)
        check_instr_outputs(dut, instr, pc, regs, error_file_path)

        # ---------------------------
        # Test 5: U-type (LUI)
        # ---------------------------
        instr = int("00000000000000000001_00111_0110111".replace("_", ""), 2)
        pc = 0x1010
        await apply_instr(dut, instr, pc)
        check_instr_outputs(dut, instr, pc, regs, error_file_path)

        # ---------------------------
        # Test 6: J-type (JAL)
        # ---------------------------
        instr = int("00000000000100000000_01000_1101111".replace("_", ""), 2)
        pc = 0x1014
        await apply_instr(dut, instr, pc)
        check_instr_outputs(dut, instr, pc, regs, error_file_path)

        # ---------------------------
        # Extra: negative immediates
        # ---------------------------
        dut._log.info("\nExtra immediate sign-extension testing:")
        extra_instrs = [
            (0xFFF08093, 0x1100),  # addi x1, x1, -1
            (0xFE208CE3, 0x1104),  # beq x1, x2, negative offset-like pattern
            (0xFE20AE23, 0x1108),  # sw x2, negative offset-like pattern
            (0x8000006F, 0x110C),  # jal with sign bit set
        ]
        for instr, pc in extra_instrs:
            await apply_instr(dut, instr, pc)
            check_instr_outputs(dut, instr, pc, regs, error_file_path)

        # ---------------------------
        # Random instruction testing
        # ---------------------------
        dut._log.info("\nRandom instruction testing:")
        random.seed(23)
        for i in range(10):
            instr = random.getrandbits(32)
            pc = 0x2000 + i * 4
            await apply_instr(dut, instr, pc)
            check_instr_outputs(dut, instr, pc, regs, error_file_path)

        # ---------------------------
        # Register read verification
        # ---------------------------
        dut._log.info("\nRegister read verification:")
        instr = int("0000000_00001_00010_000_01001_0110011".replace("_", ""), 2)
        pc = 0x3000
        await apply_instr(dut, instr, pc)
        check_instr_outputs(dut, instr, pc, regs, error_file_path)

        # explicit x0 read verification
        dut._log.info("\nZero register verification:")
        instr = 0
        instr |= (0b0110011)          # opcode
        instr |= (10 << 7)            # rd = x10
        instr |= (0 << 12)            # funct3
        instr |= (0 << 15)            # rs1 = x0
        instr |= (1 << 20)            # rs2 = x1
        instr |= (0 << 25)            # funct7
        pc = 0x3004
        await apply_instr(dut, instr, pc)
        check_instr_outputs(dut, instr, pc, regs, error_file_path)

        dut._log.info("Simulation complete. All checks passed.")

    finally:
        log_file.close()
        dut._log.info("Signal log file securely closed.")