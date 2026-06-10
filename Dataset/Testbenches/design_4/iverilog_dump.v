module iverilog_dump();
initial begin
    $dumpfile("/home/shannon/Downloads/design_4/ALU/testbenches/design_4.vcd");
    $dumpvars(0, design_4);
end
endmodule
