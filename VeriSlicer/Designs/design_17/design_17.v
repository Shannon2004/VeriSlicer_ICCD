module design_17 (
    input  [7:0] A,
    input  [7:0] B,
    input        Cin,
    output [7:0] Sum,
    output       Cout
);

assign {Cout, Sum} = A + B + Cin;

endmodule