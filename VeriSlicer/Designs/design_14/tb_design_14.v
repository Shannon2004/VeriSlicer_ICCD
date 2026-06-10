`timescale 1ns/1ns

module tb_posit_decoder;

  // Parameters (must match DUT)
  parameter N  = 16;
  parameter es = 2;
  parameter Bs = 4;

  // DUT inputs
  reg  [N-1:0] in;

  // DUT outputs
  wire rc;
  wire [Bs-1:0] regime;
  wire [es-1:0] exp;
  wire [N-es-1:0] mant;

  // Instantiate DUT
  posit_decoder DUT (
    .in(in),
    .rc(rc),
    .regime(regime),
    .exp(exp),
    .mant(mant)
  );

  integer i;

  // -------------------------------
  // Task to display results
  // -------------------------------
  task show_results;
    input [N-1:0] val;
    begin
      $display("Input = %b | rc = %b | regime = %d | exp = %d | mant = %b",
                val, rc, regime, exp, mant);
    end
  endtask

  // -------------------------------
  // Task for detailed decode view
  // -------------------------------
  task show_detailed;
    input [N-1:0] val;
    begin
      $display("--------------------------------------------------");
      $display("Input (hex) : 0x%h", val);
      $display("Binary      : %b", val);
      $display("rc          : %b", rc);
      $display("regime      : %d", regime);
      $display("exponent    : %d", exp);
      $display("mantissa    : %b", mant);
      $display("--------------------------------------------------");
    end
  endtask

  // -------------------------------
  // Test sequence
  // -------------------------------
  initial begin
    $display("Starting posit_decoder simulation...");

    // Edge cases
    in = 0; #5;
    show_detailed(in);

    in = 16'hFFFF; #5;
    show_detailed(in);

    in = 16'h8000; #5;
    show_detailed(in);

    in = 16'h0001; #5;
    show_detailed(in);

    // Sweep through multiple values (like CORDIC loop)
    for (i = 0; i < 50; i = i + 1) begin
      in = $random;
      #5;
      show_results(in);
    end

    // Structured pattern testing
    $display("\nPattern Testing:");
    for (i = 0; i < 16; i = i + 1) begin
      in = 16'b1 << i;  // single-bit inputs
      #5;
      show_results(in);
    end

    // Incremental values
    $display("\nIncremental Testing:");
    for (i = 0; i < 32; i = i + 1) begin
      in = i;
      #5;
      show_results(in);
    end

    $display("Simulation complete.");
    $finish;
  end

endmodule
