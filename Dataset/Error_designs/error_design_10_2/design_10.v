module design_10 (
    input         clk,
    input         reset,
    output [31:0] pc,
    output [31:0] instr
);

    wire [31:0] pc_next;
    wire [31:0] pc_plus4;

    // -----------------------------
    // Program Counter
    // -----------------------------
    pc pc_inst (
        .clk     (clk),
        .reset   (reset),
        .pc_next (pc_next),
        .pc      (pc)
    );

    // -----------------------------
    // PC + 4 Adder
    // -----------------------------
    pc_adder pc_adder_inst (
        .pc       (pc),
        .pc_plus4 (pc_plus4)
    );

    // -----------------------------
    // Instruction Memory
    // -----------------------------
    instr_mem instr_mem_inst (
        .addr  (pc),
        .instr (instr)
    );

    // -----------------------------
    // Next PC selection
    // (for now: always PC + 4)
    // -----------------------------
    assign pc_next = pc_plus4;

endmodule


module pc(
    input         clk,
    input         reset,
    input  [31:0] pc_next,
    output reg [31:0] pc

    );
    always @(posedge clk) begin
        if (reset)
            pc <= 32'b0;
        else
            pc <= pc_next;
    end

endmodule


module pc_adder(
input [31:0] pc,
    output [31:0] pc_plus4
 );
  assign pc_plus4 = pc - 32'd4;
  
endmodule


module instr_mem (
    input  [31:0] addr,
    output [31:0] instr
);

    // ✅ THIS is a MEMORY (array)
    reg [31:0] mem [0:255];
   
    integer i;
    // Load program
    initial begin
    // Fill memory with NOPs
    for (i = 0; i < 256; i = i + 1)
        mem[i] = 32'h00000013;
        $readmemh("C:/Users/sagni/Desktop/program.hex", mem);
    end

    // Word-aligned access
    assign instr = mem[addr[9:2]];

endmodule
