SIM ?= icarus
TOPLEVEL_LANG ?= verilog
ENABLE_DUMP ?= 1

# --- Testbench & Design Variables ---
DESIGN_NAME = design_6
# ERROR_DIR   = error_design_6_1
MODULE_NAME = test_design_6

# --- Paths ---
# Adjust capitalization (e.g., Testbenches vs testbenches) if Linux throws a path error
export PYTHONPATH := $(PWD)/../testbenches:$(PYTHONPATH)

VERILOG_SOURCES += $(PWD)/../$(DESIGN_NAME).v
TOPLEVEL = $(DESIGN_NAME)
MODULE = $(MODULE_NAME)

ifeq ($(ENABLE_DUMP), 1)
    VERILOG_SOURCES += iverilog_dump.v
    COMPILE_ARGS += -s iverilog_dump
endif

include $(shell cocotb-config --makefiles)/Makefile.sim

# --- Auto-generate VCD dumper ---
iverilog_dump.v:
	@echo 'module iverilog_dump();' > $@
	@echo 'initial begin' >> $@
	@echo '    $$dumpfile("$(PWD)/$(TOPLEVEL).vcd");' >> $@
	@echo '    $$dumpvars(0, $(TOPLEVEL));' >> $@
	@echo 'end' >> $@
	@echo 'endmodule' >> $@

# --- Cleanup ---
clean::
	rm -rf __pycache__ sim_build results.xml iverilog_dump.v *.vcd processor_signals.log processor_error.txt