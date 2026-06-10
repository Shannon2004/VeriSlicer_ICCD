`timescale 1ns/1ns

module tb_posit_encoder;

  // Parameters (must match DUT)
  parameter N  = 16;
  parameter es = 2;
  parameter Bs = 4;

  // -------------------------------
  // DUT Inputs
  // -------------------------------
  reg [es+Bs+2:0] le_o;          // 8 bits
  reg [es-1:0]    e_o_m;         // 2 bits
  reg [2*(N-es):0] DSR_left_out; // 29 bits
  reg [Bs:0]      r_o_m;         // 5 bits (note: defined as Bs:0)
  reg ls;
  reg inf_final;
  reg zero_final;
  reg start0_m;

  // -------------------------------
  // DUT Outputs
  // -------------------------------
  wire [N-1:0] out_m;
  wire done_m;

  // -------------------------------
  // Instantiate DUT
  // -------------------------------
  posit_encoder DUT (
    .le_o(le_o),
    .e_o_m(e_o_m),
    .DSR_left_out(DSR_left_out),
    .r_o_m(r_o_m),
    .ls(ls),
    .inf_final(inf_final),
    .zero_final(zero_final),
    .start0_m(start0_m),
    .out_m(out_m),
    .done_m(done_m)
  );

  integer i;

  // -------------------------------
  // Task: Basic result display
  // -------------------------------
  task show_results;
    begin
      $display("le_o=%b e=%b r=%d ls=%b | out=%b done=%b",
                le_o, e_o_m, r_o_m, ls, out_m, done_m);
    end
  endtask

  // -------------------------------
  // Task: Detailed debug display
  // -------------------------------
  task show_detailed;
    begin
      $display("--------------------------------------------------");
      $display("le_o           : %b", le_o);
      $display("exp            : %b", e_o_m);
      $display("regime (r_o_m) : %d", r_o_m);
      $display("DSR_left_out   : %b", DSR_left_out);
      $display("ls             : %b", ls);
      $display("inf_final      : %b", inf_final);
      $display("zero_final     : %b", zero_final);
      $display("start0_m       : %b", start0_m);
      $display("OUTPUT         : %b", out_m);
      $display("DONE           : %b", done_m);
      $display("--------------------------------------------------");
    end
  endtask

  // -------------------------------
  // Test sequence
  // -------------------------------
  initial begin
    $display("Starting posit_encoder simulation...");

    // ---------------------------
    // Reset-like initialization
    // ---------------------------
    le_o = 0;
    e_o_m = 0;
    DSR_left_out = 0;
    r_o_m = 0;
    ls = 0;
    inf_final = 0;
    zero_final = 0;
    start0_m = 0;

    #5;

    // ---------------------------
    // Edge cases
    // ---------------------------
    start0_m = 1;

    // Zero case
    zero_final = 1;
    #5;
    show_detailed();
    zero_final = 0;

    // Infinity case
    inf_final = 1;
    #5;
    show_detailed();
    inf_final = 0;

    // ---------------------------
    // Basic functional test
    // ---------------------------
    le_o = 8'b01010101;
    e_o_m = 2'b10;
    DSR_left_out = 29'h1ABCDE;
    r_o_m = 5'd3;
    ls = 0;
    #5;
    show_detailed();

    // Negative number test
    ls = 1;
    #5;
    show_detailed();
    ls = 0;

    // ---------------------------
    // Random testing loop
    // ---------------------------
    $display("\nRandom Testing:");
    for (i = 0; i < 50; i = i + 1) begin
      le_o = $random;
      e_o_m = $random;
      DSR_left_out = $random;
      r_o_m = $random;
      ls = $random;
      inf_final = 0;
      zero_final = 0;
      start0_m = 1;

      #5;
      show_results();
    end

    // ---------------------------
    // Regime sweep testing
    // ---------------------------
    $display("\nRegime Sweep:");
    for (i = 0; i < 10; i = i + 1) begin
      r_o_m = i;
      le_o = 8'hAA;
      e_o_m = 2'b01;
      DSR_left_out = 29'h1234567;
      ls = 0;

      #5;
      show_results();
    end

    // ---------------------------
    // Bit pattern testing
    // ---------------------------
    $display("\nBit Pattern Testing:");
    for (i = 0; i < 16; i = i + 1) begin
      le_o = 1 << i;
      e_o_m = i[1:0];
      DSR_left_out = 1 << i;
      r_o_m = i;
      ls = i[0];

      #5;
      show_results();
    end

    $display("Simulation complete.");
    $finish;
  end

endmodule
