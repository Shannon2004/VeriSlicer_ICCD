`timescale 1ns/1ns

module tb_id_stage;

  // -------------------------------
  // Inputs
  // -------------------------------
  reg clk;
  reg reset;

  reg [31:0] if_pc;
  reg [31:0] if_instr;

  reg        wb_reg_write;
  reg [4:0]  wb_rd;
  reg [31:0] wb_wd;

  // -------------------------------
  // Outputs
  // -------------------------------
  wire [31:0] id_pc;
  wire [31:0] id_rd1;
  wire [31:0] id_rd2;
  wire [31:0] id_imm;
  wire [4:0]  id_rs1;
  wire [4:0]  id_rs2;
  wire [4:0]  id_rd;
  wire [6:0]  id_opcode;
  wire [2:0]  id_funct3;
  wire [6:0]  id_funct7;

  // -------------------------------
  // DUT
  // -------------------------------
  id_stage DUT (
    .clk(clk),
    .reset(reset),
    .if_pc(if_pc),
    .if_instr(if_instr),
    .wb_reg_write(wb_reg_write),
    .wb_rd(wb_rd),
    .wb_wd(wb_wd),
    .id_pc(id_pc),
    .id_rd1(id_rd1),
    .id_rd2(id_rd2),
    .id_imm(id_imm),
    .id_rs1(id_rs1),
    .id_rs2(id_rs2),
    .id_rd(id_rd),
    .id_opcode(id_opcode),
    .id_funct3(id_funct3),
    .id_funct7(id_funct7)
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
  // Task: Display results
  // -------------------------------
  task show_results;
    begin
      $display("T=%0t | PC=%h | Instr=%h", $time, id_pc, if_instr);
      $display(" opcode=%b rd=%0d rs1=%0d rs2=%0d funct3=%b funct7=%b",
                id_opcode, id_rd, id_rs1, id_rs2, id_funct3, id_funct7);
      $display(" rd1=%h rd2=%h imm=%h", id_rd1, id_rd2, id_imm);
      $display("--------------------------------------------------");
    end
  endtask

  // -------------------------------
  // Task: Apply instruction
  // -------------------------------
  task apply_instr;
    input [31:0] instr;
    input [31:0] pc_val;
    begin
      @(negedge clk);
      if_instr = instr;
      if_pc    = pc_val;
      @(posedge clk);
      #1;
      show_results();
    end
  endtask

  // -------------------------------
  // Task: Write back to register file
  // -------------------------------
  task write_back;
    input [4:0] rd;
    input [31:0] data;
    begin
      @(negedge clk);
      wb_reg_write = 1;
      wb_rd        = rd;
      wb_wd        = data;
      @(posedge clk);
      wb_reg_write = 0;
    end
  endtask

  // -------------------------------
  // Stimulus
  // -------------------------------
  initial begin
    $display("Starting ID stage simulation...");

    // Init
    reset = 1;
    if_pc = 0;
    if_instr = 0;
    wb_reg_write = 0;
    wb_rd = 0;
    wb_wd = 0;

    // Reset
    @(posedge clk);
    reset = 1;
    @(posedge clk);
    reset = 0;

    // ---------------------------
    // Preload registers
    // ---------------------------
    write_back(5'd1, 32'h0000000A); // x1 = 10
    write_back(5'd2, 32'h00000014); // x2 = 20
    write_back(5'd3, 32'h00000005); // x3 = 5

    // ---------------------------
    // Test 1: R-type (ADD)
    // add x5, x1, x2
    // opcode=0110011 funct3=000 funct7=0000000
    // ---------------------------
    apply_instr(32'b0000000_00010_00001_000_00101_0110011, 32'h1000);

    // ---------------------------
    // Test 2: I-type (ADDI)
    // addi x6, x1, 10
    // ---------------------------
    apply_instr(32'b000000001010_00001_000_00110_0010011, 32'h1004);

    // ---------------------------
    // Test 3: S-type (SW)
    // sw x2, 8(x1)
    // ---------------------------
    apply_instr(32'b0000000_00010_00001_010_01000_0100011, 32'h1008);

    // ---------------------------
    // Test 4: B-type (BEQ)
    // beq x1, x2, offset
    // ---------------------------
    apply_instr(32'b0000000_00010_00001_000_00000_1100011, 32'h100C);

    // ---------------------------
    // Test 5: U-type (LUI)
    // ---------------------------
    apply_instr(32'b00000000000000000001_00111_0110111, 32'h1010);

    // ---------------------------
    // Test 6: J-type (JAL)
    // ---------------------------
    apply_instr(32'b00000000000100000000_01000_1101111, 32'h1014);

    // ---------------------------
    // Random instruction testing
    // ---------------------------
    $display("\nRandom instruction testing:");
    for (i = 0; i < 10; i = i + 1) begin
      apply_instr($random, 32'h2000 + i*4);
    end

    // ---------------------------
    // Register read verification
    // ---------------------------
    $display("\nRegister read verification:");
    apply_instr(32'b0000000_00001_00010_000_01001_0110011, 32'h3000);

    $display("Simulation complete.");
    $finish;
  end

endmodule
