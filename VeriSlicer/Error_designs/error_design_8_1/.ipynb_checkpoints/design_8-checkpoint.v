module design_8(
    input         clk,
    input         reset,

    input  [31:0] if_pc,
    input  [31:0] if_instr,

    input         wb_reg_write,
    input  [4:0]  wb_rd,
    input  [31:0] wb_wd,

    output [31:0] id_pc,
    output [31:0] id_rd1,
    output [31:0] id_rd2,
    output [31:0] id_imm,
    output [4:0]  id_rs1,
    output [4:0]  id_rs2,
    output [4:0]  id_rd,
    output [6:0]  id_opcode,
    output [2:0]  id_funct3,
    output [6:0]  id_funct7
);

    wire [31:0] instr;

    // IF/ID pipeline register
    if_id if_id_inst (
        .clk      (clk),
        .reset    (reset),
        .pc_in    (if_pc),
        .instr_in (if_instr),
        .pc_out   (id_pc),
        .instr_out(instr)
    );

    // Instruction decoder
    instr_decoder decoder (
        .instr  (instr),
        .opcode (id_opcode),
        .rd     (id_rd),
        .funct3 (id_funct3),
        .rs1    (id_rs1),
        .rs2    (id_rs2),
        .funct7 (id_funct7)
    );

    // Register file (FIXED: reset added)
    regfile regfile_inst (
        .clk       (clk),
        .reset     (reset),   // ✅ FIX
        .reg_write (wb_reg_write),
        .rs1       (id_rs1),
        .rs2       (id_rs2),
        .rd        (wb_rd),
        .wd        (wb_wd),
        .rd1       (id_rd1),
        .rd2       (id_rd2)
    );

    // Immediate generator
    imm_gen imm_gen_inst (
        .instr (instr),
        .imm   (id_imm)
    );

endmodule

module if_id(
    input         clk,
    input         reset,
    input  [31:0] pc_in,
    input  [31:0] instr_in,
    output reg [31:0] pc_out,
    output reg [31:0] instr_out
);

    always @(posedge clk) begin
        if (reset) begin
            pc_out    <= 32'b0;
            instr_out <= 32'b0;
        end else begin
            pc_out    <= pc_in;
            instr_out <= instr_in;
        end
    end

endmodule

module instr_decoder(
    input  [31:0] instr,
    output [6:0]  opcode,
    output [4:0]  rd,
    output [2:0]  funct3,
    output [4:0]  rs1,
    output [4:0]  rs2,
    output [6:0]  funct7
);

    assign opcode = instr[6:0];
    assign rd     = instr[11:4];
    assign funct3 = instr[14:12];
    assign rs1    = instr[19:15];
    assign rs2    = instr[24:20];
    assign funct7 = instr[31:25];

endmodule


module regfile (
    input         clk,
    input         reset,          // ✅ ADDED
    input         reg_write,
    input  [4:0]  rs1,
    input  [4:0]  rs2,
    input  [4:0]  rd,
    input  [31:0] wd,
    output [31:0] rd1,
    output [31:0] rd2
);

    reg [31:0] regs [0:31];
    integer i;

    // Read ports (combinational)
    assign rd1 = (rs1 == 5'd0) ? 32'b0 : regs[rs1];
    assign rd2 = (rs2 == 5'd0) ? 32'b0 : regs[rs2];

    // Write + reset
    always @(posedge clk) begin
        if (reset) begin
            for (i = 0; i < 32; i = i + 1)
                regs[i] <= 32'b0;   // ✅ FIX: eliminate X values
        end else if (reg_write && (rd != 0)) begin
            regs[rd] <= wd;
        end
    end

endmodule


module imm_gen(
    input  [31:0] instr,
    output reg [31:0] imm
);

    wire [6:0] opcode = instr[6:0];

    always @(*) begin
        case (opcode)

            // I-type
            7'b0010011,
            7'b0000011,
            7'b1100111:
                imm = {{20{instr[31]}}, instr[31:20]};

            // S-type
            7'b0100011:
                imm = {{20{instr[31]}}, instr[31:25], instr[11:7]};

            // B-type
            7'b1100011:
                imm = {{19{instr[31]}},
                       instr[31],
                       instr[7],
                       instr[30:25],
                       instr[11:8],
                       1'b0};

            // U-type
            7'b0110111,
            7'b0010111:
                imm = {instr[31:12], 12'b0};

            // J-type
            7'b1101111:
                imm = {{11{instr[31]}},
                       instr[31],
                       instr[19:12],
                       instr[20],
                       instr[30:21],
                       1'b0};

            default:
                imm = 32'b0;
        endcase
    end

endmodule