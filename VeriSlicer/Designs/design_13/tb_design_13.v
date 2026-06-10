`timescale 1ns/1ns

module tb_posit_add;

  // ---------------------------------------
  // Parameters (match DUT)
  // ---------------------------------------
  parameter N  = 12;

  // ---------------------------------------
  // Inputs
  // ---------------------------------------
  reg clk;
  reg start;
  reg [N-1:0] in1_svm;
  reg [N-1:0] in2_svm;

  // ---------------------------------------
  // Outputs
  // ---------------------------------------
  wire [N-1:0] out;
  wire inf;
  wire zero;
  wire done;

  // ---------------------------------------
  // DUT
  // ---------------------------------------
  posit_add DUT (
    .clk(clk),
    .in1_svm(in1_svm),
    .in2_svm(in2_svm),
    .start(start),
    .out(out),
    .inf(inf),
    .zero(zero),
    .done(done)
  );

  integer i;

  // ---------------------------------------
  // Clock generation
  // ---------------------------------------
  initial begin
    clk = 0;
    forever #5 clk = ~clk;
  end

  // ---------------------------------------
  // Task: Display results
  // ---------------------------------------
  task show_results;
    begin
      $display("T=%0t | in1=%b in2=%b | out=%b | inf=%b zero=%b done=%b",
                $time, in1_svm, in2_svm, out, inf, zero, done);
    end
  endtask

  // ---------------------------------------
  // Task: Apply test
  // ---------------------------------------
  task apply_test;
    input [N-1:0] a;
    input [N-1:0] b;
    begin
      @(negedge clk);
      in1_svm = a;
      in2_svm = b;
      start   = 1;

      @(posedge clk);
      start   = 0;

      #1;
      show_results();
    end
  endtask

  // ---------------------------------------
  // Stimulus
  // ---------------------------------------
  initial begin
    $display("Starting posit_add simulation...\n");

    // Init
    start = 0;
    in1_svm = 0;
    in2_svm = 0;

    // ---------------------------
    // Basic tests
    // ---------------------------
    $display("\n=== BASIC TESTS ===");

    apply_test(12'b010000000000, 12'b010000000000); // ~1 + 1
    apply_test(12'b001000000000, 12'b001000000000); // small + small
    apply_test(12'b011000000000, 12'b001000000000); // large + small

    // ---------------------------
    // Opposite signs
    // ---------------------------
    $display("\n=== SIGN TESTS ===");

    apply_test(12'b010000000000, 12'b110000000000); // +1 + (-1)
    apply_test(12'b011000000000, 12'b101000000000);

    // ---------------------------
    // Zero cases
    // ---------------------------
    $display("\n=== ZERO TESTS ===");

    apply_test(12'b000000000000, 12'b000000000000);
    apply_test(12'b010000000000, 12'b000000000000);
    apply_test(12'b000000000000, 12'b010000000000);

    // ---------------------------
    // Infinity cases
    // (MSB=1 and rest zero)
    // ---------------------------
    $display("\n=== INF TESTS ===");

    apply_test(12'b100000000000, 12'b010000000000);
    apply_test(12'b100000000000, 12'b100000000000);

    // ---------------------------
    // Edge cases
    // ---------------------------
    $display("\n=== EDGE CASES ===");

    apply_test(12'b111111111111, 12'b000000000001);
    apply_test(12'b011111111111, 12'b011111111111);

    // ---------------------------
    // Random testing
    // ---------------------------
    $display("\n=== RANDOM TESTING ===");

    for (i = 0; i < 20; i = i + 1) begin
      apply_test($random, $random);
    end

    $display("\nSimulation complete.");
    $finish;
  end

endmodule
