`timescale 1ns/1ns

module tb_posit_mult;

  // ---------------------------------------
  // Parameters (match DUT)
  // ---------------------------------------
  parameter N = 12;

  // ---------------------------------------
  // Inputs
  // ---------------------------------------
  reg clk;
  reg start_m;
  reg [N-1:0] in1_m_kernel;
  reg [N-1:0] in2_m_kernel;

  // ---------------------------------------
  // Outputs
  // ---------------------------------------
  wire [N-1:0] out_m;
  wire inf_m;
  wire zero_m;
  wire done_m;

  // ---------------------------------------
  // DUT
  // ---------------------------------------
  posit_mult DUT (
    .clk(clk),
    .in1_m_kernel(in1_m_kernel),
    .in2_m_kernel(in2_m_kernel),
    .start_m(start_m),
    .out_m(out_m),
    .inf_m(inf_m),
    .zero_m(zero_m),
    .done_m(done_m)
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
                $time, in1_m_kernel, in2_m_kernel,
                out_m, inf_m, zero_m, done_m);
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
      in1_m_kernel = a;
      in2_m_kernel = b;
      start_m      = 1;

      @(posedge clk);
      start_m      = 0;

      #1;
      show_results();
    end
  endtask

  // ---------------------------------------
  // Stimulus
  // ---------------------------------------
  initial begin
    $display("Starting posit_mult simulation...\n");

    // Init
    start_m = 0;
    in1_m_kernel = 0;
    in2_m_kernel = 0;

    // ---------------------------
    // Basic tests
    // ---------------------------
    $display("\n=== BASIC TESTS ===");

    apply_test(12'b010000000000, 12'b010000000000); // ~1 * 1
    apply_test(12'b001000000000, 12'b001000000000); // small * small
    apply_test(12'b011000000000, 12'b001000000000); // large * small

    // ---------------------------
    // Sign tests
    // ---------------------------
    $display("\n=== SIGN TESTS ===");

    apply_test(12'b010000000000, 12'b110000000000); // + * -
    apply_test(12'b110000000000, 12'b110000000000); // - * -

    // ---------------------------
    // Zero cases
    // ---------------------------
    $display("\n=== ZERO TESTS ===");

    apply_test(12'b000000000000, 12'b000000000000);
    apply_test(12'b010000000000, 12'b000000000000);
    apply_test(12'b000000000000, 12'b010000000000);

    // ---------------------------
    // Infinity cases
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
