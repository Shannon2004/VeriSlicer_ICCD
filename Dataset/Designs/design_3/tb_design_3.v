`default_nettype none

module tb_sha1();

  //----------------------------------------------------------------
  // Internal constant and parameter definitions.
  //----------------------------------------------------------------
  parameter CLK_HALF_PERIOD = 1;
  parameter CLK_PERIOD = CLK_HALF_PERIOD * 2;

  parameter ADDR_NAME0       = 8'h00;
  parameter ADDR_NAME1       = 8'h01;
  parameter ADDR_VERSION     = 8'h02;
  parameter ADDR_CTRL        = 8'h08;
  parameter CTRL_INIT_VALUE  = 8'h01;
  parameter CTRL_NEXT_VALUE  = 8'h02;
  parameter ADDR_STATUS      = 8'h09;

  parameter ADDR_BLOCK0      = 8'h10;
  parameter ADDR_BLOCK15     = 8'h1f;

  parameter ADDR_DIGEST0     = 8'h20;
  parameter ADDR_DIGEST4     = 8'h24;

  //----------------------------------------------------------------
  // Register and Wire declarations.
  //----------------------------------------------------------------
  reg [31 : 0] error_ctr;
  reg [31 : 0] tc_ctr;
  reg          tb_clk;
  reg          tb_reset_n;
  reg          tb_cs;
  reg          tb_write_read;
  reg [7 : 0]  tb_address;
  reg [31 : 0] tb_data_in;
  wire [31 : 0] tb_data_out;
  wire          tb_error;

  reg [31 : 0]  read_data;
  reg [159 : 0] digest_data;

  //----------------------------------------------------------------
  // Device Under Test.
  //----------------------------------------------------------------
  design_3 dut(
           .clk(tb_clk),
           .reset_n(tb_reset_n),
           .cs(tb_cs),
           .we(tb_write_read),
           .address(tb_address),
           .write_data(tb_data_in),
           .read_data(tb_data_out),
           .error(tb_error)
          );

  //----------------------------------------------------------------
  // Clock Generator
  //----------------------------------------------------------------
  always #CLK_HALF_PERIOD tb_clk = !tb_clk;

  //----------------------------------------------------------------
  // Helper Tasks
  //----------------------------------------------------------------
  task reset_dut;
    begin
      $display("*** Toggle reset.");
      tb_reset_n = 0;
      #(4 * CLK_HALF_PERIOD);
      tb_reset_n = 1;
    end
  endtask

  task init_sim;
    begin
      error_ctr     = 32'h0;
      tc_ctr        = 32'h0;
      tb_clk        = 0;
      tb_reset_n    = 0;
      tb_cs         = 0;
      tb_write_read = 0;
      tb_address    = 8'h0;
      tb_data_in    = 32'h0;
    end
  endtask

  task wait_ready;
    begin
      read_data = 0;
      while (read_data == 0) begin
          read_word(ADDR_STATUS);
      end
    end
  endtask

  task read_word(input [7 : 0] address);
    begin
      tb_address = address;
      tb_cs = 1;
      tb_write_read = 0;
      #(CLK_PERIOD);
      read_data = tb_data_out;
      tb_cs = 0;
    end
  endtask

  task write_word(input [7 : 0] address, input [31 : 0] word);
    begin
      tb_address = address;
      tb_data_in = word;
      tb_cs = 1;
      tb_write_read = 1;
      #(CLK_PERIOD);
      tb_cs = 0;
      tb_write_read = 0;
    end
  endtask

  task write_block(input [511 : 0] block);
    integer i;
    begin
      for (i = 0; i < 16; i = i + 1) begin
          write_word(ADDR_BLOCK0 + i, block[((15-i)*32) +: 32]);
      end
    end
  endtask

  task check_name_version;
    reg [31 : 0] n0, n1, v;
    begin
      read_word(ADDR_NAME0); n0 = read_data;
      read_word(ADDR_NAME1); n1 = read_data;
      read_word(ADDR_VERSION); v = read_data;
      $display("DUT name: %c%c%c%c%c%c%c%c", n0[31:24], n0[23:16], n0[15:8], n0[7:0], n1[31:24], n1[23:16], n1[15:8], n1[7:0]);
      $display("DUT version: %c%c%c%c", v[31:24], v[23:16], v[15:8], v[7:0]);
    end
  endtask

  task read_digest;
    integer i;
    begin
      for (i = 0; i < 5; i = i + 1) begin
          read_word(ADDR_DIGEST0 + i);
          digest_data[((4-i)*32) +: 32] = read_data;
      end
    end
  endtask

  //----------------------------------------------------------------
  // File-Driven Test Execution
  //----------------------------------------------------------------
  integer file_fd;
  integer scan_res;
  integer num_blocks;
  integer current_block;
  reg [511:0] loaded_block;
  reg [159:0] expected_hash;

  initial begin : sha1_test
      $display("   -- File-Driven Testbench for sha1 started --");
      init_sim();
      reset_dut();
      check_name_version();

      file_fd = $fopen("test_vectors.txt", "r");
      if (file_fd == 0) begin
          $display("ERROR: Could not open test_vectors.txt! Run the python generator first.");
          $finish;
      end

      while (!$feof(file_fd)) begin
          scan_res = $fscanf(file_fd, "%d\n", num_blocks);
          if (scan_res == 1) begin
              $display("----------------------------------------------------------------");
              $display("*** TC%02d started (%0d blocks).", tc_ctr, num_blocks);
              
              for (current_block = 0; current_block < num_blocks; current_block = current_block + 1) begin
                  scan_res = $fscanf(file_fd, "%h\n", loaded_block);
                  $display("    Input Block %0d : 0x%h", current_block, loaded_block);
                  
                  write_block(loaded_block);
                  if (current_block == 0)
                      write_word(ADDR_CTRL, CTRL_INIT_VALUE);
                  else
                      write_word(ADDR_CTRL, CTRL_NEXT_VALUE);
                  
                  #(CLK_PERIOD);
                  wait_ready();
              end
              
              scan_res = $fscanf(file_fd, "%h\n", expected_hash);
              read_digest();
              $display("    Output Hash   : 0x%h", digest_data);
              
              if (digest_data === expected_hash)
                  $display("    Result        : MATCH");
              else begin
                  $display("    Result        : MISMATCH! Expected 0x%h", expected_hash);
                  error_ctr = error_ctr + 1;
              end
              tc_ctr = tc_ctr + 1;
          end
      end
      
      $fclose(file_fd);
      $display("----------------------------------------------------------------");
      if (error_ctr == 0)
          $display("*** All %0d test cases completed successfully.", tc_ctr);
      else
          $display("*** %0d errors detected during testing.", error_ctr);
      
      $finish;
  end

endmodule