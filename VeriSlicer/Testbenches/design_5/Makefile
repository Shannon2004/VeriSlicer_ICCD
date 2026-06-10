# Default simulator
SIM ?= icarus
TOPLEVEL_LANG ?= verilog

# Export the current directory path to Python
export OUT_DIR := $(PWD)

VERILOG_SOURCES += $(PWD)/../../Designs/design_5/design_5.v

# Define the relative path to the testbench directory
# TB_DIR := $(PWD)/../../Testbenches/design_4

# # Add the testbench directory to PYTHONPATH
# export PYTHONPATH := $(TB_DIR):$(PYTHONPATH)

TOPLEVEL = design_5
MODULE = test_design_5

include $(shell cocotb-config --makefiles)/Makefile.sim

clean::
	rm -rf __pycache__ sim_build results.xml uart_signal_changes.log *.vcd