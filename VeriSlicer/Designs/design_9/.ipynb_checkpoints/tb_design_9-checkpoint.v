`timescale 1ns/1ns

module tb_ex_stage;

  // -------------------------------
  // Inputs
  // -------------------------------
  reg [31:0] ex_rd1;
  reg [31:0] ex_rd2;
  reg [31:0] ex_imm;
  reg [6:0]  ex_opcode;
  reg [2:0]  ex_funct3;
  reg [6:0]  ex_funct7;

  // -------------------------------
  // Outputs
  // -------------------------------
  wire [31:0] alu_result;
  wire        zero;

  // -------------------------------
  // DUT
  // -------------------------------
  ex_stage DUT (
    .ex_rd1(ex_rd1),
    .ex_rd2(ex_rd2),
    .ex_imm(ex_imm),
    .ex_opcode(ex_opcode),
    .ex_funct3(ex_funct3),
    .ex_funct7(ex_funct7),
    .alu_result(alu_result),
    .zero(zero)
  );

  integer i;

  // -------------------------------
  // Task: Display results
  // -------------------------------
  task show_results;
    begin
      $display("A=%h B=%h IMM=%h | opcode=%b f3=%b f7=%b | result=%h zero=%b",
                ex_rd1, ex_rd2, ex_imm,
                ex_opcode, ex_funct3, ex_funct7,
                alu_result, zero);
    end
  endtask

  // -------------------------------
  // Task: Apply R-type instruction
  // -------------------------------
  task test_rtype;
    input [31:0] a;
    input [31:0] b;
    input [2:0] funct3;
    input [6:0] funct7;
    begin
      ex_rd1    = a;
      ex_rd2    = b;
      ex_opcode = 7'b0110011;
      ex_funct3 = funct3;
      ex_funct7 = funct7;
      #1;
      show_results();
    end
  endtask

  // -------------------------------
  // Task: Apply I-type instruction
  // -------------------------------
  task test_itype;
    input [31:0] a;
    input [31:0] imm;
    input [2:0] funct3;
    begin
      ex_rd1    = a;
      ex_imm    = imm;
      ex_opcode = 7'b0010011;
      ex_funct3 = funct3;
      ex_funct7 = 7'b0000000;
      #1;
      show_results();
    end
  endtask

  // -------------------------------
  // Stimulus
  // -------------------------------
  initial begin
    $display("Starting EX stage simulation...\n");

    // ---------------------------
    // R-type tests
    // ---------------------------
    $display("=== R-TYPE TESTS ===");

    // ADD
    test_rtype(32'd10, 32'd5, 3'b000, 7'b0000000);

    // SUB
    test_rtype(32'd10, 32'd5, 3'b000, 7'b0100000);

    // AND
    test_rtype(32'hF0F0, 32'h0FF0, 3'b111, 7'b0000000);

    // OR
    test_rtype(32'hF0F0, 32'h0FF0, 3'b110, 7'b0000000);

    // XOR
    test_rtype(32'hAAAA, 32'h5555, 3'b100, 7'b0000000);

    // SLT
    test_rtype(32'd5, 32'd10, 3'b010, 7'b0000000);

    // ---------------------------
    // I-type tests
    // ---------------------------
    $display("\n=== I-TYPE TESTS ===");

    // ADDI
    test_itype(32'd10, 32'd20, 3'b000);

    // ANDI
    test_itype(32'hF0F0, 32'h0FF0, 3'b111);

    // ORI
    test_itype(32'hF0F0, 32'h0FF0, 3'b110);

    // XORI
    test_itype(32'hAAAA, 32'h5555, 3'b100);

    // ---------------------------
    // Zero flag test
    // ---------------------------
    $display("\n=== ZERO FLAG TEST ===");

    test_rtype(32'd10, 32'd10, 3'b000, 7'b0100000); // SUB -> 0

    // ---------------------------
    // Edge cases
    // ---------------------------
    $display("\n=== EDGE CASES ===");

    test_rtype(32'hFFFFFFFF, 32'h1, 3'b000, 7'b0000000); // overflow-like
    test_rtype(32'd0, 32'd0, 3'b000, 7'b0000000);

    // ---------------------------
    // Random testing
    // ---------------------------
    $display("\n=== RANDOM TESTING ===");

    for (i = 0; i < 10; i = i + 1) begin
      test_rtype($random, $random, 3'b000, 7'b0000000);
    end

    for (i = 0; i < 10; i = i + 1) begin
      test_itype($random, $random, 3'b000);
    end

    $display("\nSimulation complete.");
    $finish;
  end

endmodule
