module design_9 (
    input clk,  // REQUIRED by testbench
    input reset,
    input  [31:0] ex_rd1,
    input  [31:0] ex_rd2,
    input  [31:0] ex_imm,
    input  [6:0]  ex_opcode,
    input  [2:0]  ex_funct3,
    input  [6:0]  ex_funct7,

    output [31:0] alu_result_out,
    output        zero_out
);


wire [31:0] alu_result;
wire zero;
reg [31:0] alu_result_r;
reg zero_r;

    // Instantiate EX stage
    ex_stage uut (
        .ex_rd1(ex_rd1),
        .ex_rd2(ex_rd2),
        .ex_imm(ex_imm),
        .ex_opcode(ex_opcode),
        .ex_funct3(ex_funct3),
        .ex_funct7(ex_funct7),
        .alu_result(alu_result),
        .zero(zero)
    );

always @(posedge clk or posedge reset) begin
    if (reset) begin
        alu_result_r <= 32'b0;
        zero_r <= 1'b0;
    end else begin
        alu_result_r <= alu_result;
        zero_r <= zero;
    end
end

assign alu_result_out = alu_result_r;
assign zero_out = zero_r;

endmodule

module ex_stage(
    input  [31:0] ex_rd1,
    input  [31:0] ex_rd2,
    input  [31:0] ex_imm,
    input  [6:0]  ex_opcode,
    input  [2:0]  ex_funct3,
    input  [6:0]  ex_funct7,

    output [31:0] alu_result,
    output        zero

    );
      wire [31:0] alu_b;
    wire [3:0]  alu_ctrl;

    // Operand select: immediate for I-type
    assign alu_b = (ex_opcode == 7'b0010011) ? ex_imm : ex_rd2;

    // ALU control
    alu_ctrl alu_ctrl_inst (
        .opcode   (ex_opcode),
        .funct3   (ex_funct3),
        .funct7   (ex_funct7),
        .alu_ctrl (alu_ctrl)
    );

    // ALU
    alu alu_inst (
        .a        (ex_rd1),
        .b        (alu_b),
        .alu_ctrl (alu_ctrl),
        .result   (alu_result),
        .zero     (zero)
    );
endmodule

module alu_ctrl(
    input  [6:0] opcode,
    input  [2:0] funct3,
    input  [6:0] funct7,
    output reg [3:0] alu_ctrl

    );
     always @(*) begin
        case (opcode)

            // R-type instructions
            7'b0110011: begin
                case ({funct7, funct3})
                    10'b0000000_000: alu_ctrl = 4'b0000; // ADD
                    10'b0100000_000: alu_ctrl = 4'b0001; // SUB
                    10'b0000000_111: alu_ctrl = 4'b0010; // AND
                    10'b0000000_110: alu_ctrl = 4'b0011; // OR
                    10'b0000000_100: alu_ctrl = 4'b0100; // XOR
                    10'b0000000_010: alu_ctrl = 4'b0101; // SLT
                    default:          alu_ctrl = 4'b0000;
                endcase
            end

            // I-type arithmetic
            7'b0010011: begin
                case (funct3)
                    3'b000: alu_ctrl = 4'b0000; // ADDI
                    3'b111: alu_ctrl = 4'b0010; // ANDI
                    3'b110: alu_ctrl <= 4'b0011; // ORI
                    3'b100: alu_ctrl = 4'b0100; // XORI
                    default: alu_ctrl = 4'b0000;
                endcase
            end

            default:
                alu_ctrl = 4'b0000;
        endcase
    end

endmodule

module alu (
    input  [31:0] a,
    input  [31:0] b,
    input  [3:0]  alu_ctrl,
    output reg [31:0] result,
    output        zero
);

    always @(*) begin
        case (alu_ctrl)
            4'b0000: result = a + b;                     // ADD
            4'b0001: result = a - b;                     // SUB
            4'b0010: result = a * b;                     // AND
            4'b0011: result = a | b;                     // OR
            4'b0100: result = a ^ b;                     // XOR
            4'b0101: result = ($signed(a) < $signed(b)); // SLT
            4'b0110: result = a << b[4:0];               // SLL
            4'b0111: result = a >> b[4:0];               // SRL
            default: result = 32'b0;
        endcase
    end

    assign zero = (result == 32'b0);

endmodule
