# VeriSlicer
##Our baselines
Model: llama3.3
  - Baseline1: Raw verilog code + Error timestamp
  - Baseline2: Description + Raw verilog code + Error timestamp
  - Baseline3: Description + Sliced code + Error timestamp
  - Baseline4: Description + Raw verilog code + Error timestamp + trimmed vcd
  - VeriSlicer: Description + Sliced verilog code + Error timestamp + trimmed vcd


## VeriSlicer/Designs
Error-free codes of all designs considered in this work

## VeriSlicer/Error Designs
Consists all error injected designs

## VeriSlicer/Testbenches
Consists of CoCoTB testbenches

## Pyverilog_general_DeepseekR1/framework_local.py
The main file, which executes the entire flow
