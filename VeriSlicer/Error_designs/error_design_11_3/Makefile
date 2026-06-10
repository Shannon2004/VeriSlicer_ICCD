# Auto-generated Makefile
SIM ?= icarus
TOPLEVEL_LANG ?= verilog
ENABLE_DUMP ?= 1

export PYTHONPATH := $(PWD)/../Testbenches/design_11:$(PYTHONPATH)
export ERROR_DIR=error_design_11_3

VERILOG_SOURCES += $(PWD)/../Error_designs/error_design_11_3/design_11.v
TOPLEVEL = design_11
COCOTB_TEST_MODULES = test_design_11

ifeq ($(ENABLE_DUMP), 1)
    VERILOG_SOURCES += iverilog_dump.v
    COMPILE_ARGS += -s iverilog_dump
endif

include $(shell cocotb-config --makefiles)/Makefile.sim

iverilog_dump.v:
	echo '' > $@
	echo 'module iverilog_dump();' >> $@
	echo 'initial begin' >> $@
	echo '    $$dumpfile("$(PWD)/../Error_designs/error_design_11_3/$(TOPLEVEL).vcd");' >> $@
	echo '    $$dumpvars(0, $(TOPLEVEL));' >> $@
	echo 'end' >> $@
	echo 'endmodule' >> $@

clean::
	rm -rf __pycache__ sim_build results.xml iverilog_dump.v
