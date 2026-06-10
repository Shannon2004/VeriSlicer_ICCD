import os
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer, ReadOnly

error_dir = os.environ.get("ERROR_DIR", "error_design_default") #pass through from top script
error_designs_dir = "../Error_designs/"
# ============================================================
# Failure helpers
# ============================================================

def report_error(msg, signal_name, file_path):
    t = cocotb.utils.get_sim_time("ns")
    banner = (
        f"\n{'='*70}\n"
        f"FAIL @ {t} ns\n"
        f"SIGNAL: {signal_name}\n"
        f"ERROR : {msg}\n"
        f"{'='*70}\n"
    )
    with open(file_path, "a") as f:
        f.write(banner)

    cocotb.log.error(banner)
    assert False


def check_eq(name, got, exp, file_path):
    if got != exp:
        report_error(f"Expected {exp}, got {got}", name, file_path)


# ============================================================
# Monitor
# ============================================================

async def monitor(dut, f):
    signals = [
        (dut.feature_vector_pointer, "f_ptr"),
        (dut.x_data_pointer, "x_ptr"),
        (dut.class_vector_pointer, "class_ptr"),
        (dut.hv_pointer, "hv_ptr"),
        (dut.encode_enable, "encode"),
        (dut.binarize_enable, "binarize"),
        (dut.accumulate_enable, "accumulate"),
        (dut.similarity_check_enable, "sim_check"),
        (dut.class_predictor_enable, "predict"),
        (dut.SC_done, "SC_done"),
    ]

    while True:
        await RisingEdge(dut.clk)
        await ReadOnly()

        t = cocotb.utils.get_sim_time("ns")
        snapshot = [f"{n}={int(s.value)}" for s, n in signals]
        f.write(f"[{t}] " + " | ".join(snapshot) + "\n")
        f.flush()


# ============================================================
# Main Test
# ============================================================

@cocotb.test()
async def hdc_controller_tb(dut):

    dut._log.info("==== HDC CONTROLLER TEST START ====")

    # Clock
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    # Logs
    out_dir = os.path.join(error_designs_dir, error_dir)
    os.makedirs(out_dir, exist_ok=True)
    log_file_path = os.path.join(out_dir, os.path.basename(__file__).replace("test_", "").replace(".py", ".log"))
    err_path = os.path.join(out_dir, "error_timestamp.txt")

    log_file = open(log_file_path, "w")
    open(err_path, "w").close()

    cocotb.start_soon(monitor(dut, log_file))

    # --------------------------------------------------
    # INITIAL INPUTS
    # --------------------------------------------------
    dut.reset.value = 1
    dut.from_decoder_start.value = 0
    dut.value.value = 5
    dut.number_of_levels.value = 10
    dut.capture_cv_pointer.value = 3

    # Reset cycles
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)

    dut.reset.value = 0
    await Timer(1, unit="ns")

    # --------------------------------------------------
    # RESET CHECKS
    # --------------------------------------------------
    check_eq("feature_vector_pointer", int(dut.feature_vector_pointer.value), 0, err_path)
    check_eq("x_data_pointer", int(dut.x_data_pointer.value), 0, err_path)
    check_eq("encode_enable", int(dut.encode_enable.value), 0, err_path)

    # --------------------------------------------------
    # START FSM
    # --------------------------------------------------
    dut._log.info("Triggering start signal")
    dut.from_decoder_start.value = 1

    await RisingEdge(dut.clk)
    dut.from_decoder_start.value = 0

    # --------------------------------------------------
    # FSM PROGRESSION TEST
    # --------------------------------------------------
    dut._log.info("Observing FSM transitions...")

    for cycle in range(200):

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        # Basic sanity checks
        assert int(dut.feature_vector_pointer.value) >= 0
        assert int(dut.x_data_pointer.value) >= 0

        # Encode should eventually go high
        if cycle > 5:
            if int(dut.encode_enable.value):
                dut._log.info(f"Encode active at cycle {cycle}")

        # Accumulate should trigger at some point
        if int(dut.accumulate_enable.value):
            dut._log.info(f"Accumulate active at cycle {cycle}")

        # Binarize should trigger near end
        if int(dut.binarize_enable.value):
            dut._log.info(f"Binarize active at cycle {cycle}")

        # Similarity phase
        if int(dut.similarity_check_enable.value):
            dut._log.info(f"Similarity check active at cycle {cycle}")

        # Completion check
        if int(dut.SC_done.value):
            dut._log.info(f"SC_done asserted at cycle {cycle}")
            break

    # --------------------------------------------------
    # FINAL CHECKS
    # --------------------------------------------------
    check_eq("SC_done", int(dut.SC_done.value), 1, err_path)

    # Predicted class should match capture_cv_pointer
    check_eq(
        "predicted_class",
        int(dut.predicted_class.value),
        int(dut.capture_cv_pointer.value),
        err_path
    )

    dut._log.info("==== TEST PASSED ====")

    log_file.close()