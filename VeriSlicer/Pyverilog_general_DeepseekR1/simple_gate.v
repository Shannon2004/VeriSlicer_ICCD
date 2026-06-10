// simple_gate.v
module simple_gate(
    input a,
    input b,
    input c,
    input d,
    output y1,
    output y2,
    output y3
);
    wire e;
    assign y1 = a & b;
    assign y2 = b|c;
    assign e = d;
    assign y3 = e;

endmodule
