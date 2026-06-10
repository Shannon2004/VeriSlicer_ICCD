`timescale 1ns / 100ps

// User-defined I/O addresses from eZ80 address bus;
// these match the original Z180 MMU defaults at reset.
// These must not be defined within eZ80 on-chip i/o space (7F..FF)
/*`define CBR_IO_ADDR     16'h0038  // Common Bank Register
`define BBR_IO_ADDR     16'h0039  // Bank Base Register
`define CBAR_IO_ADDR    16'h003A  // Common/Bank Address Register
*/
module design_12(reset_n, en, iorq_n, mreq_n, rd_n, wr_n, phi, addr_in, dq, addr_out,
        cbar_hinyb, cbar_lonyb);

input           reset_n, en, iorq_n, mreq_n, rd_n, wr_n, phi;
input   [23:0]  addr_in; //processor address bus
output   [7:0]   dq;     // processor data bus
output  [19:12]  addr_out; // memory address bus
output cbar_hinyb, cbar_lonyb;

reg [7:0]  cpu_data_buf;

wire cbar_hinyb_gteq;   // for CBR valid address match
wire cbar_lonyb_gteq;   // for BBR valid address match

    parameter CBR_IO_ADDR  =   16'h0038;
    parameter BBR_IO_ADDR  =   16'h0039 ;
    parameter CBAR_IO_ADDR =   16'h003A;
    parameter INIT_VAL  = 8'b0 ;
// These are for verification only

// These are for verification only
assign cbar_hinyb = cbar_hinyb_gteq;
assign cbar_lonyb = cbar_lonyb_gteq;

/** *************************************************************** */
/** define 3 I/O Ports, 1 each for CBR, BBR, and CBAR               */

wire [7:0] iolatched_oup_CBR;
wire [7:0] iolatched_oup_BBR;
wire [7:0] iolatched_oup_CBAR;


/**************
wire addr16_msb_zero;
assign addr16_msb_zero = (addr_in[15:8] == 8'b0);

wire iosel_CBR, iosel_BBR, iosel_CBAR;
assign iosel_CBR = (addr16_msb_zero && (addr_in[7:0] == `CBR_IO_ADDR) && ! iorq_n && ! phi);
assign iosel_BBR = (addr16_msb_zero && (addr_in[7:0] == `BBR_IO_ADDR) && ! iorq_n && ! phi);
assign iosel_CBAR = (addr16_msb_zero && (addr_in[7:0] == `CBAR_IO_ADDR) && ! iorq_n && ! phi);
********************/
wire iosel_CBR;
    wire iosel_BBR;
    wire iosel_CBAR;
assign iosel_CBR = ((addr_in[15:0] == CBR_IO_ADDR) && ! iorq_n && ! phi);
assign iosel_BBR = ((addr_in[15:0] == BBR_IO_ADDR) && ! iorq_n && ! phi);
assign iosel_CBAR = ((addr_in[15:0] == CBAR_IO_ADDR) && ! iorq_n && ! phi);


wire iosel_CBR_wr;
    wire iosel_BBR_wr;
    wire iosel_CBAR_wr;
assign iosel_CBR_wr = ! (iosel_CBR & ! wr_n);
assign iosel_BBR_wr = ! (iosel_BBR &  wr_n);
assign iosel_CBAR_wr = ! (iosel_CBAR & ! wr_n);

    assign dq = ( (iosel_CBR | iosel_BBR | iosel_CBAR) & (! rd_n)) ? cpu_data_buf : 8'b00;

wire iosel;
assign iosel = (! iorq_n && ! phi);
always  @ (posedge iosel)
    if (! rd_n) begin
        case (addr_in[15:0])
            CBR_IO_ADDR: begin
                cpu_data_buf <= iolatched_oup_CBR;
            end
            BBR_IO_ADDR: begin
                cpu_data_buf <= iolatched_oup_BBR;
            end
            CBAR_IO_ADDR: begin
                cpu_data_buf <= iolatched_oup_CBAR;
            end
        endcase
    end

/// define I/O port to read/write CBR
ioport_a16_d8_wo   ioport_CBR(
    .reset_n   (reset_n),
//    .rd_n   (iosel_CBR_rd),
    .wr_n   (iosel_CBR_wr),
    .data_in   (dq),
    .ouplatched_bus (iolatched_oup_CBR)
);

/// define I/O port to read/write BBR
ioport_a16_d8_wo  ioport_BBR(
    .reset_n   (reset_n),
//    .rd_n   (iosel_BBR_rd),
    .wr_n   (iosel_BBR_wr),
    .data_in   (dq),
    .ouplatched_bus (iolatched_oup_BBR)
);

/// define I/O port to read/write CBAR
ioport_a16_d8_wo  ioport_CBAR(
    .reset_n   (reset_n),
//    .rd_n   (iosel_CBAR_rd),
    .wr_n   (iosel_CBAR_wr),
    .data_in   (dq),
    .ouplatched_bus (iolatched_oup_CBAR)
);

/** **************************************************************** */
/** define MMU compare and adder logic                               */


// Compare CBAR high nybble for Common Area 1 address ("use CBR?")
assign cbar_hinyb_gteq = (addr_in[15:12] >= iolatched_oup_CBAR[7:4]);

// Compare CBAR low nybble for Bank Area address  ("use BBR?")
assign cbar_lonyb_gteq = (addr_in[15:12] >= iolatched_oup_CBAR[3:0]);

wire cbar_is_valid;
assign cbar_is_valid = (iolatched_oup_CBAR[7:4] >= iolatched_oup_CBAR[3:0]);

wire    [7:0]   bbr_cbr_mux;
assign bbr_cbr_mux =
        (cbar_is_valid & cbar_hinyb_gteq) ? iolatched_oup_CBR :
        (cbar_is_valid & cbar_lonyb_gteq) ? iolatched_oup_BBR : 8'b0;

wire    [7:0]   hiaddr_1meg;
assign hiaddr_1meg = bbr_cbr_mux + {4'b0,addr_in[15:12]};

//define when hiaddr_1meg is to be used instead of normal a[19..12]
assign addr_out = (/*en &&*/ (addr_in[23:16] != 0)) ?
                    addr_in[19:12] : (en && (! mreq_n) && (cbar_hinyb_gteq | cbar_lonyb_gteq)) ?
                    hiaddr_1meg : addr_in[19:12];// : 8'bz;

/**
                    addr_in[19:12] : (en_mmu && (! mreq_n) && (cbar_hinyb_gteq | cbar_lonyb_gteq)) ?
                    hiaddr_1meg : (en_mod4 && (! mreq_n)) ? {addr_in[19:17], adj_a16, adj_a15, addr_in[14:12] }
                        : addr_in[19:12];// : 8'bz;

*/

endmodule

module ioport_a16_d8_wo(reset_n, wr_n, data_in, ouplatched_bus);
input           reset_n, wr_n;
input   [7:0]   data_in;
output reg  [7:0]   ouplatched_bus;
parameter INIT_VAL  = 8'hF0 ;

always  @ (posedge wr_n or negedge reset_n)
    if (! reset_n)
        ouplatched_bus <=  INIT_VAL;

    else if (wr_n)
        ouplatched_bus <=  data_in;

endmodule



