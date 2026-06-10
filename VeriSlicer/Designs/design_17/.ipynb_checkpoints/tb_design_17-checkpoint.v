`timescale 1ns/1ns
`include "design_17.v"

module tb;

  reg  [7:0] A, B;
  reg        Cin;
  wire [7:0] Sum;
  wire       Cout;

  integer i, j, k;

  // Instantiate DUT
  design_17 UUT (
    .A(A),
    .B(B),
    .Cin(Cin),
    .Sum(Sum),
    .Cout(Cout)
  );

  // Task to display results
  task show_results;
    input [7:0] a, b;
    input cin;
    input [7:0] sum;
    input cout;
    reg [8:0] expected;
    begin
      expected = a + b + cin;

      if ({cout, sum} !== expected)
        $display("ERROR: A=%d B=%d Cin=%d -> Sum=%d Cout=%d | Expected=%d",
                  a, b, cin, sum, cout, expected);
      else
        $display("PASS : A=%d B=%d Cin=%d -> Sum=%d Cout=%d",
                  a, b, cin, sum, cout);
    end
  endtask

  initial begin
    $display("Starting Full Adder Testbench");

    // Apply test vectors (similar looping style to your reference)
    for (i = 0; i < 256; i = i + 1) begin
      for (j = 0; j < 256; j = j + 1) begin
        for (k = 0; k < 2; k = k + 1) begin
          
          A   = i;
          B   = j;
          Cin = k;

          #1;  // small delay

          show_results(A, B, Cin, Sum, Cout);

        end
      end
    end

    $display("Simulation Finished");
    $finish;
  end

endmodule