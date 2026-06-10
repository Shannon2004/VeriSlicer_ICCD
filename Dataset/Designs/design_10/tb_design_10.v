`timescale 1ns/1ns

module tb_if_stage;

  // -------------------------------
  // Inputs
  // -------------------------------
  reg clk;
  reg reset;

  // -------------------------------
  // Outputs
  // -------------------------------
  wire [31:0] pc;
  wire [31:0] instr;

  // -------------------------------
  // DUT
  // -------------------------------
  if_stage DUT (
    .clk(clk),
    .reset(reset),
    .pc(pc),
    .instr(instr)
  );

  integer i;

  // -------------------------------
  // Clock generation
  // -------------------------------
  initial begin
    clk = 0;
    forever #5 clk = ~clk;
  end

  // -------------------------------
  // Task: Display state
  // -------------------------------
  task show_state;
    begin
      $display("T=%0t | PC=%h | INSTR=%h", $time, pc, instr);
    end
  endtask

  // -------------------------------
  // Task: Step one cycle
  // -------------------------------
  task step;
    begin
      @(posedge clk);
      #1;
      show_state();
    end
  endtask

  // -------------------------------
  // Stimulus
  // -------------------------------
  initial begin
    $display("Starting IF stage simulation...\n");

    // ---------------------------
    // Reset
    // ---------------------------
    reset = 1;
    #2;
    step();

    reset = 0;
    step();

    // ---------------------------
    // Sequential fetch test
    // ---------------------------
    $display("\n=== SEQUENTIAL FETCH TEST ===");
    for (i = 0; i < 10; i = i + 1) begin
      step();
    end

    // ---------------------------
    // Check PC increment
    // ---------------------------
    $display("\n=== PC INCREMENT CHECK ===");
    for (i = 0; i < 5; i = i + 1) begin
      @(posedge clk);
      #1;
      if (pc !== (i+2)*4) // approximate expected progression
        $display("WARNING: Unexpected PC value: %h", pc);
      show_state();
    end

    // ---------------------------
    // Reset during operation
    // ---------------------------
    $display("\n=== MID-RUN RESET TEST ===");
    reset = 1;
    step();
    reset = 0;
    step();

    // ---------------------------
    // Instruction memory test
    // (depends on your program.hex)
    // ---------------------------
    $display("\n=== INSTRUCTION MEMORY TEST ===");
    for (i = 0; i < 8; i = i + 1) begin
      step();
    end

    // ---------------------------
    // Long run test
    // ---------------------------
    $display("\n=== LONG RUN TEST ===");
    for (i = 0; i < 20; i = i + 1) begin
      step();
    end

    $display("\nSimulation complete.");
    $finish;
  end

endmodule
