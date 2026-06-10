module iverilog_dump();
initial begin
    $dumpfile("/home/shannon/Downloads/design_6/testbenches/design_6.vcd");
    $dumpvars(0, design_6);
end
endmodule
