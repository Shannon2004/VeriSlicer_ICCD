
module iverilog_dump();
initial begin
    $dumpfile("/home/shannon/VeriSlicer_test/Dataset/Pyverilog_general/../Error_designs/error_design_10_1/design_10.vcd");
    $dumpvars(0, design_10);
end
endmodule
