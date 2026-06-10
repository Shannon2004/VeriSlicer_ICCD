//======================================================================
//
// sha1_w_mem_reg.v
// -----------------
// The SHA-1 W memory. This memory includes functionality to
// expand the block into 80 words.
//
//
// Copyright (c) 2013 Secworks Sweden AB
// All rights reserved.
//
// Redistribution and use in source and binary forms, with or
// without modification, are permitted provided that the following
// conditions are met:
//
// 1. Redistributions of source code must retain the above copyright
//    notice, this list of conditions and the following disclaimer.
//
// 2. Redistributions in binary form must reproduce the above copyright
//    notice, this list of conditions and the following disclaimer in
//    the documentation and/or other materials provided with the
//    distribution.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
// "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
// LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
// FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
// COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
// INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
// BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
// LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
// CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
// STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
// ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
// ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
//
//======================================================================

`default_nettype none

module sha1_w_mem(
                  input wire           clk,
                  input wire           reset_n,

                  input wire [511 : 0] block,

                  input wire           init,
                  input wire           next,

                  output wire [31 : 0] w
                 );


  //----------------------------------------------------------------
  // Registers including update variables and write enable.
  //----------------------------------------------------------------
  reg [31 : 0] w_mem [0 : 15];
  reg [31 : 0] w_mem00_new;
  reg [31 : 0] w_mem01_new;
  reg [31 : 0] w_mem02_new;
  reg [31 : 0] w_mem03_new;
  reg [31 : 0] w_mem04_new;
  reg [31 : 0] w_mem05_new;
  reg [31 : 0] w_mem06_new;
  reg [31 : 0] w_mem07_new;
  reg [31 : 0] w_mem08_new;
  reg [31 : 0] w_mem09_new;
  reg [31 : 0] w_mem10_new;
  reg [31 : 0] w_mem11_new;
  reg [31 : 0] w_mem12_new;
  reg [31 : 0] w_mem13_new;
  reg [31 : 0] w_mem14_new;
  reg [31 : 0] w_mem15_new;
  reg          w_mem_we;

  reg [6 : 0] w_ctr_reg;
  reg [6 : 0] w_ctr_new;
  reg         w_ctr_we;


  //----------------------------------------------------------------
  // Wires.
  //----------------------------------------------------------------
  reg [31 : 0] w_tmp;
  reg [31 : 0] w_new;


  //----------------------------------------------------------------
  // Concurrent connectivity for ports etc.
  //----------------------------------------------------------------
  assign w = w_tmp;


  //----------------------------------------------------------------
  // reg_update
  //
  // Update functionality for all registers in the core.
  // All registers are positive edge triggered with
  // asynchronous active low reset.
  //----------------------------------------------------------------
  always @ (posedge clk or negedge reset_n)
    begin : reg_update
      integer i;

      if (!reset_n)
        begin
          for (i = 0 ; i < 16 ; i = i + 1)
            w_mem[i] <= 32'h0;

          w_ctr_reg <= 7'h0;
        end
      else
        begin
          if (w_mem_we)
            begin
              w_mem[00] <= w_mem00_new;
              w_mem[01] <= w_mem01_new;
              w_mem[02] <= w_mem02_new;
              w_mem[03] <= w_mem03_new;
              w_mem[04] <= w_mem04_new;
              w_mem[05] <= w_mem05_new;
              w_mem[06] <= w_mem06_new;
              w_mem[07] <= w_mem07_new;
              w_mem[08] <= w_mem08_new;
              w_mem[09] <= w_mem09_new;
              w_mem[10] <= w_mem10_new;
              w_mem[11] <= w_mem11_new;
              w_mem[12] <= w_mem12_new;
              w_mem[13] <= w_mem13_new;
              w_mem[14] <= w_mem14_new;
              w_mem[15] <= w_mem15_new;
            end

          if (w_ctr_we)
            w_ctr_reg <= w_ctr_new;
        end
    end // reg_update


  //----------------------------------------------------------------
  // select_w
  //
  // W word selection logic. Returns either directly from the
  // memory or the next w value calculated.
  //----------------------------------------------------------------
  always @*
    begin : select_w
      if (w_ctr_reg < 16)
        w_tmp = w_mem[w_ctr_reg[3 : 0]];
      else
        w_tmp = w_new;
    end // select_w


  //----------------------------------------------------------------
  // w_mem_update_logic
  //
  // Update logic for the W memory. This is where the scheduling
  // based on a sliding window is implemented.
  //----------------------------------------------------------------
  always @*
    begin : w_mem_update_logic
      reg [31 : 0] w_0;
      reg [31 : 0] w_2;
      reg [31 : 0] w_8;
      reg [31 : 0] w_13;
      reg [31 : 0] w_16;

      w_mem00_new = 32'h0;
      w_mem01_new = 32'h0;
      w_mem02_new = 32'h0;
      w_mem03_new = 32'h0;
      w_mem04_new = 32'h0;
      w_mem05_new = 32'h0;
      w_mem06_new = 32'h0;
      w_mem07_new = 32'h0;
      w_mem08_new = 32'h0;
      w_mem09_new = 32'h0;
      w_mem10_new = 32'h0;
      w_mem11_new = 32'h0;
      w_mem12_new = 32'h0;
      w_mem13_new = 32'h0;
      w_mem14_new = 32'h0;
      w_mem15_new = 32'h0;
      w_mem_we    = 1'h0;

      w_0   = w_mem[0];
      w_2   = w_mem[2];
      w_8   = w_mem[8];
      w_13  = w_mem[13];
      w_16  = w_13 ^ w_8 ^ w_2 ^ w_0;
      w_new = {w_16[30 : 0], w_16[31]};

      if (init)
        begin
          w_mem00_new = block[511 : 480];
          w_mem01_new = block[479 : 448];
          w_mem02_new = block[447 : 416];
          w_mem03_new = block[415 : 384];
          w_mem04_new = block[383 : 352];
          w_mem05_new = block[351 : 320];
          w_mem06_new = block[319 : 288];
          w_mem07_new = block[287 : 256];
          w_mem08_new = block[255 : 224];
          w_mem09_new = block[223 : 192];
          w_mem10_new = block[191 : 160];
          w_mem11_new = block[159 : 128];
          w_mem12_new = block[127 :  96];
          w_mem13_new = block[95  :  64];
          w_mem14_new = block[63  :  32];
          w_mem15_new = block[31  :   0];
          w_mem_we    = 1'h1;
        end

      if (next && (w_ctr_reg > 15))
        begin
          w_mem00_new = w_mem[01];
          w_mem01_new = w_mem[02];
          w_mem02_new = w_mem[03];
          w_mem03_new = w_mem[04];
          w_mem04_new = w_mem[05];
          w_mem05_new = w_mem[06];
          w_mem06_new = w_mem[07];
          w_mem07_new = w_mem[08];
          w_mem08_new = w_mem[09];
          w_mem09_new = w_mem[10];
          w_mem10_new = w_mem[11];
          w_mem11_new = w_mem[12];
          w_mem12_new = w_mem[13];
          w_mem13_new = w_mem[14];
          w_mem14_new = w_mem[15];
          w_mem15_new = w_new;
          w_mem_we    = 1'h1;
        end
    end // w_mem_update_logic


  //----------------------------------------------------------------
  // w_ctr
  //
  // W schedule adress counter. Counts from 0x10 to 0x3f and
  // is used to expand the block into words.
  //----------------------------------------------------------------
  always @*
    begin : w_ctr
      w_ctr_new = 7'h0;
      w_ctr_we  = 1'h0;

      if (init)
        begin
          w_ctr_new = 7'h0;
          w_ctr_we  = 1'h1;
        end

      if (next)
        begin
          w_ctr_new = w_ctr_reg + 7'h01;
          w_ctr_we  = 1'h1;
        end
    end // w_ctr
endmodule // sha1_w_mem

//======================================================================
// sha1_w_mem.v
//======================================================================


//======================================================================
//
// sha1_core.v
// -----------
// Verilog 2001 implementation of the SHA-1 hash function.
// This is the internal core with wide interfaces.
//
//
// Copyright (c) 2013 Secworks Sweden AB
// All rights reserved.
//
// Redistribution and use in source and binary forms, with or
// without modification, are permitted provided that the following
// conditions are met:
//
// 1. Redistributions of source code must retain the above copyright
//    notice, this list of conditions and the following disclaimer.
//
// 2. Redistributions in binary form must reproduce the above copyright
//    notice, this list of conditions and the following disclaimer in
//    the documentation and/or other materials provided with the
//    distribution.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
// "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
// LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
// FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
// COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
// INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
// BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
// LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
// CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
// STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
// ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
// ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
//
//======================================================================

`default_nettype none

module sha1_core(
                 input wire            clk,
                 input wire            reset_n,

                 input wire            init,
                 input wire            next,

                 input wire [511 : 0]  block,

                 output wire           ready,

                 output wire [159 : 0] digest,
                 output wire           digest_valid
                );


  //----------------------------------------------------------------
  // Internal constant and parameter definitions.
  //----------------------------------------------------------------
  parameter H0_0 = 32'h67452301;
  parameter H0_1 = 32'hefcdab89;
  parameter H0_2 = 32'h98badcfe;
  parameter H0_3 = 32'h10325476;
  parameter H0_4 = 32'hc3d2e1f0;

  parameter SHA1_ROUNDS = 79;

  parameter CTRL_IDLE   = 0;
  parameter CTRL_ROUNDS = 1;
  parameter CTRL_DONE   = 2;


  //----------------------------------------------------------------
  // Registers including update variables and write enable.
  //----------------------------------------------------------------
  reg [31 : 0] a_reg;
  reg [31 : 0] a_new;
  reg [31 : 0] b_reg;
  reg [31 : 0] b_new;
  reg [31 : 0] c_reg;
  reg [31 : 0] c_new;
  reg [31 : 0] d_reg;
  reg [31 : 0] d_new;
  reg [31 : 0] e_reg;
  reg [31 : 0] e_new;
  reg          a_e_we;

  reg [31 : 0] H0_reg;
  reg [31 : 0] H0_new;
  reg [31 : 0] H1_reg;
  reg [31 : 0] H1_new;
  reg [31 : 0] H2_reg;
  reg [31 : 0] H2_new;
  reg [31 : 0] H3_reg;
  reg [31 : 0] H3_new;
  reg [31 : 0] H4_reg;
  reg [31 : 0] H4_new;
  reg          H_we;

  reg [6 : 0] round_ctr_reg;
  reg [6 : 0] round_ctr_new;
  reg         round_ctr_we;
  reg         round_ctr_inc;
  reg         round_ctr_rst;

  reg digest_valid_reg;
  reg digest_valid_new;
  reg digest_valid_we;

  reg [1 : 0] sha1_ctrl_reg;
  reg [1 : 0] sha1_ctrl_new;
  reg         sha1_ctrl_we;


  //----------------------------------------------------------------
  // Wires.
  //----------------------------------------------------------------
  reg           digest_init;
  reg           digest_update;
  reg           state_init;
  reg           state_update;
  reg           first_block;
  reg           ready_flag;
  reg           w_init;
  reg           w_next;
  wire [31 : 0] w;


  //----------------------------------------------------------------
  // Module instantiantions.
  //----------------------------------------------------------------
  sha1_w_mem w_mem_inst(
                        .clk(clk),
                        .reset_n(reset_n),

                        .block(block),

                        .init(w_init),
                        .next(w_next),

                        .w(w)
                       );


  //----------------------------------------------------------------
  // Concurrent connectivity for ports etc.
  //----------------------------------------------------------------
  assign ready        = ready_flag;
  assign digest       = {H0_reg, H1_reg, H2_reg, H3_reg, H4_reg};
  assign digest_valid = digest_valid_reg;


  //----------------------------------------------------------------
  // reg_update
  // Update functionality for all registers in the core.
  // All registers are positive edge triggered with
  // asynchronous active low reset.
  //----------------------------------------------------------------
  always @ (posedge clk or negedge reset_n)
    begin : reg_update
      if (!reset_n)
        begin
          a_reg            <= 32'h0;
          b_reg            <= 32'h0;
          c_reg            <= 32'h0;
          d_reg            <= 32'h0;
          e_reg            <= 32'h0;
          H0_reg           <= 32'h0;
          H1_reg           <= 32'h0;
          H2_reg           <= 32'h0;
          H3_reg           <= 32'h0;
          H4_reg           <= 32'h0;
          digest_valid_reg <= 1'h0;
          round_ctr_reg    <= 7'h0;
          sha1_ctrl_reg    <= CTRL_IDLE;
        end
      else
        begin
          if (a_e_we)
            begin
              a_reg <= a_new;
              b_reg <= b_new;
              c_reg <= c_new;
              d_reg <= d_new;
              e_reg <= e_new;
            end

          if (H_we)
            begin
              H0_reg <= H0_new;
              H1_reg <= H1_new;
              H2_reg <= H2_new;
              H3_reg <= H3_new;
              H4_reg <= H4_new;
            end

          if (round_ctr_we)
            round_ctr_reg <= round_ctr_new;

          if (digest_valid_we)
            digest_valid_reg <= digest_valid_new;

          if (sha1_ctrl_we)
            sha1_ctrl_reg <= sha1_ctrl_new;
        end
    end // reg_update


  //----------------------------------------------------------------
  // digest_logic
  //
  // The logic needed to init as well as update the digest.
  //----------------------------------------------------------------
  always @*
    begin : digest_logic
      H0_new = 32'h0;
      H1_new = 32'h0;
      H2_new = 32'h0;
      H3_new = 32'h0;
      H4_new = 32'h0;
      H_we = 0;

      if (digest_init)
        begin
          H0_new = H0_0;
          H1_new = H0_1;
          H2_new = H0_2;
          H3_new = H0_3;
          H4_new = H0_4;
          H_we = 1;
        end

      if (digest_update)
        begin
          H0_new = H0_reg + a_reg;
          H1_new = H1_reg + b_reg;
          H2_new = H2_reg + c_reg;
          H3_new = H3_reg + d_reg;
          H4_new = H4_reg + e_reg;
          H_we = 1;
        end
    end // digest_logic


  //----------------------------------------------------------------
  // state_logic
  //
  // The logic needed to init as well as update the state during
  // round processing.
  //----------------------------------------------------------------
  always @*
    begin : state_logic
      reg [31 : 0] a5;
      reg [31 : 0] f;
      reg [31 : 0] k;
      reg [31 : 0] t;

      a5     = 32'h0;
      f      = 32'h0;
      k      = 32'h0;
      t      = 32'h0;
      a_new  = 32'h0;
      b_new  = 32'h0;
      c_new  = 32'h0;
      d_new  = 32'h0;
      e_new  = 32'h0;
      a_e_we = 1'h0;

      if (state_init)
        begin
          if (first_block)
            begin
              a_new  = H0_0;
              b_new  = H0_1;
              c_new  = H0_2;
              d_new  = H0_3;
              e_new  = H0_4;
              a_e_we = 1;
            end
          else
            begin
              a_new  = H0_reg;
              b_new  = H1_reg;
              c_new  = H2_reg;
              d_new  = H3_reg;
              e_new  = H4_reg;
              a_e_we = 1;
            end
        end

      if (state_update)
        begin
          if (round_ctr_reg <= 19)
            begin
              k = 32'h5a827999;
              f =  ((b_reg & c_reg) ^ (~b_reg & d_reg));
            end
          else if ((round_ctr_reg >= 20) && (round_ctr_reg <= 39))
            begin
              k = 32'h6ed9eba1;
              f = b_reg ^ c_reg ^ d_reg;
            end
          else if ((round_ctr_reg >= 40) && (round_ctr_reg <= 59))
            begin
              k = 32'h8f1bbcdc;
              f = ((b_reg | c_reg) ^ (b_reg | d_reg) ^ (c_reg | d_reg));
            end
          else if (round_ctr_reg >= 60)
            begin
              k = 32'hca62c1d6;
              f = b_reg ^ c_reg ^ d_reg;
            end

          a5 = {a_reg[26 : 0], a_reg[31 : 27]};
          t = a5 + e_reg + f + k + w;

          a_new  = t;
          b_new  = a_reg;
          c_new  = {b_reg[1 : 0], b_reg[31 : 2]};
          d_new  = c_reg;
          e_new  = d_reg;
          a_e_we = 1;
        end
    end // state_logic


  //----------------------------------------------------------------
  // round_ctr
  //
  // Update logic for the round counter, a monotonically
  // increasing counter with reset.
  //----------------------------------------------------------------
  always @*
    begin : round_ctr
      round_ctr_new = 7'h0;
      round_ctr_we  = 1'h0;

      if (round_ctr_rst)
        begin
          round_ctr_new = 7'h0;
          round_ctr_we  = 1'h1;
        end

      if (round_ctr_inc)
        begin
          round_ctr_new = round_ctr_reg + 1'h1;
          round_ctr_we  = 1;
        end
    end // round_ctr


  //----------------------------------------------------------------
  // sha1_ctrl_fsm
  // Logic for the state machine controlling the core behaviour.
  //----------------------------------------------------------------
  always @*
    begin : sha1_ctrl_fsm
      digest_init      = 1'h0;
      digest_update    = 1'h0;
      state_init       = 1'h0;
      state_update     = 1'h0;
      first_block      = 1'h0;
      ready_flag       = 1'h0;
      w_init           = 1'h0;
      w_next           = 1'h0;
      round_ctr_inc    = 1'h0;
      round_ctr_rst    = 1'h0;
      digest_valid_new = 1'h0;
      digest_valid_we  = 1'h0;
      sha1_ctrl_new    = CTRL_IDLE;
      sha1_ctrl_we     = 1'h0;

      case (sha1_ctrl_reg)
        CTRL_IDLE:
          begin
            ready_flag = 1;

            if (init)
              begin
                digest_init      = 1'h1;
                w_init           = 1'h1;
                state_init       = 1'h1;
                first_block      = 1'h1;
                round_ctr_rst    = 1'h1;
                digest_valid_new = 1'h0;
                digest_valid_we  = 1'h1;
                sha1_ctrl_new    = CTRL_ROUNDS;
                sha1_ctrl_we     = 1'h1;
              end

            if (next)
              begin
                w_init           = 1'h1;
                state_init       = 1'h1;
                round_ctr_rst    = 1'h1;
                digest_valid_new = 1'h0;
                digest_valid_we  = 1'h1;
                sha1_ctrl_new    = CTRL_ROUNDS;
                sha1_ctrl_we     = 1'h1;
              end
          end


        CTRL_ROUNDS:
          begin
            state_update  = 1'h1;
            round_ctr_inc = 1'h1;
            w_next        = 1'h1;

            if (round_ctr_reg == SHA1_ROUNDS)
              begin
                sha1_ctrl_new = CTRL_DONE;
                sha1_ctrl_we  = 1'h1;
              end
          end


        CTRL_DONE:
          begin
            digest_update    = 1'h1;
            digest_valid_new = 1'h1;
            digest_valid_we  = 1'h1;
            sha1_ctrl_new    = CTRL_IDLE;
            sha1_ctrl_we     = 1'h1;
          end
      endcase // case (sha1_ctrl_reg)
    end // sha1_ctrl_fsm

endmodule // sha1_core

//======================================================================
// EOF sha1_core.v
//======================================================================


//======================================================================
//
// sha1.v
// ------
// Top level wrapper for the SHA-1 hash function providing
// a simple memory like interface with 32 bit data access.
//
//
// Author: Joachim Strombergson
// Copyright (c) 2013  Secworks Sweden AB
//
// Redistribution and use in source and binary forms, with or
// without modification, are permitted provided that the following
// conditions are met:
//
// 1. Redistributions of source code must retain the above copyright
//    notice, this list of conditions and the following disclaimer.
//
// 2. Redistributions in binary form must reproduce the above copyright
//    notice, this list of conditions and the following disclaimer in
//    the documentation and/or other materials provided with the
//    distribution.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
// "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
// LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
// FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
// COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
// INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
// BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
// LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
// CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
// STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
// ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
// ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
//
//======================================================================

`default_nettype none

module design_3(
            // Clock and reset.
            input wire           clk,
            input wire           reset_n,

            // Control.
            input wire           cs,
            input wire           we,

            // Data ports.
            input wire  [7 : 0]  address,
            input wire  [31 : 0] write_data,
            output wire [31 : 0] read_data,
            output wire          error
           );

  //----------------------------------------------------------------
  // Internal constant and parameter definitions.
  //----------------------------------------------------------------
  localparam ADDR_NAME0       = 8'h00;
  localparam ADDR_NAME1       = 8'h01;
  localparam ADDR_VERSION     = 8'h02;

  localparam ADDR_CTRL        = 8'h08;
  localparam CTRL_INIT_BIT    = 0;
  localparam CTRL_NEXT_BIT    = 1;

  localparam ADDR_STATUS      = 8'h09;
  localparam STATUS_READY_BIT = 0;
  localparam STATUS_VALID_BIT = 1;

  localparam ADDR_BLOCK0    = 8'h10;
  localparam ADDR_BLOCK15   = 8'h1f;

  localparam ADDR_DIGEST0   = 8'h20;
  localparam ADDR_DIGEST4   = 8'h24;

  localparam CORE_NAME0     = 32'h73686131; // "sha1"
  localparam CORE_NAME1     = 32'h20202020; // "    "
  localparam CORE_VERSION   = 32'h302e3630; // "0.60"


  //----------------------------------------------------------------
  // Registers including update variables and write enable.
  //----------------------------------------------------------------
  reg init_reg;
  reg init_new;

  reg next_reg;
  reg next_new;

  reg ready_reg;

  reg [31 : 0] block_reg [0 : 15];
  reg          block_we;

  reg [159 : 0] digest_reg;

  reg digest_valid_reg;


  //----------------------------------------------------------------
  // Wires.
  //----------------------------------------------------------------
  wire           core_ready;
  wire [511 : 0] core_block;
  wire [159 : 0] core_digest;
  wire           core_digest_valid;

  reg [31 : 0]   tmp_read_data;
  reg            tmp_error;


  //----------------------------------------------------------------
  // Concurrent connectivity for ports etc.
  //----------------------------------------------------------------
  assign core_block = {block_reg[00], block_reg[01], block_reg[02], block_reg[03],
                       block_reg[04], block_reg[05], block_reg[06], block_reg[07],
                       block_reg[08], block_reg[09], block_reg[10], block_reg[11],
                       block_reg[12], block_reg[13], block_reg[14], block_reg[15]};

  assign read_data = tmp_read_data;
  assign error     = tmp_error;


  //----------------------------------------------------------------
  // core instantiation.
  //----------------------------------------------------------------
  sha1_core core(
                 .clk(clk),
                 .reset_n(reset_n),

                 .init(init_reg),
                 .next(next_reg),

                 .block(core_block),

                 .ready(core_ready),

                 .digest(core_digest),
                 .digest_valid(core_digest_valid)
                );


  //----------------------------------------------------------------
  // reg_update
  // Update functionality for all registers in the core.
  // All registers are positive edge triggered with
  // asynchronous active low reset.
  //----------------------------------------------------------------
  always @ (posedge clk or negedge reset_n)
    begin : reg_update
      integer i;

      if (!reset_n)
        begin
          init_reg         <= 1'h0;
          next_reg         <= 1'h0;
          ready_reg        <= 1'h0;
          digest_reg       <= 160'h0;
          digest_valid_reg <= 1'h0;

          for (i = 0 ; i < 16 ; i = i + 1)
            block_reg[i] <= 32'h0;
        end
      else
        begin
          ready_reg        <= core_ready;
          digest_valid_reg <= core_digest_valid;
          init_reg         <= init_new;
          next_reg         <= next_new;

          if (block_we)
            block_reg[address[3 : 0]] <= write_data;

          if (core_digest_valid)
            digest_reg <= core_digest;
        end
    end // reg_update

  //----------------------------------------------------------------
  // api
  //
  // The interface command decoding logic.
  //----------------------------------------------------------------
  always @*
    begin : api
      init_new      = 1'h0;
      next_new      = 1'h0;
      block_we      = 1'h0;
      tmp_read_data = 32'h0;
      tmp_error     = 1'h0;

      if (cs)
        begin
          if (we)
            begin
              if ((address >= ADDR_BLOCK0) && (address <= ADDR_BLOCK15))
                block_we = 1'h1;

              if (address == ADDR_CTRL)
                begin
                  init_new = write_data[CTRL_INIT_BIT];
                  next_new = write_data[CTRL_NEXT_BIT];
                end
            end // if (write_read)
          else
            begin
              if ((address >= ADDR_BLOCK0) && (address <= ADDR_BLOCK15))
                tmp_read_data = block_reg[address[3 : 0]];

              if ((address >= ADDR_DIGEST0) && (address <= ADDR_DIGEST4))
                tmp_read_data = digest_reg[(4 - (address - ADDR_DIGEST0)) * 32 +: 32];

              case (address)
                // Read operations.
                ADDR_NAME0:
                  tmp_read_data = CORE_NAME0;

                ADDR_NAME1:
                  tmp_read_data = CORE_NAME1;

                ADDR_VERSION:
                  tmp_read_data = CORE_VERSION;

                ADDR_CTRL:
                  tmp_read_data = {30'h0, next_reg, init_reg};

                ADDR_STATUS:
                  tmp_read_data = {30'h0, digest_valid_reg, ready_reg};

                default:
                  begin
                    tmp_error = 1'h1;
                  end
              endcase // case (addr)
            end
        end
    end // addr_decoder
endmodule // sha1

//======================================================================
// EOF sha1.v
//======================================================================
