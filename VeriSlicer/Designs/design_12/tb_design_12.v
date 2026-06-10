`timescale 1ns/1ns

module tb_mmu180;

  // -------------------------------
  // Inputs
  // -------------------------------
  reg reset_n;
  reg en;
  reg iorq_n;
  reg mreq_n;
  reg rd_n;
  reg wr_n;
  reg phi;
  reg [23:0] addr_in;

  // -------------------------------
  // Inout (data bus)
  // -------------------------------
  reg  [7:0] dq_drive;
  wire [7:0] dq;

  assign dq = (!wr_n) ? dq_drive : 8'bz;

  // -------------------------------
  // Outputs
  // -------------------------------
  wire [19:12] addr_out;
  wire cbar_hinyb, cbar_lonyb;

  // -------------------------------
  // DUT
  // -------------------------------
  mmu180 DUT (
    .reset_n(reset_n),
    .en(en),
    .iorq_n(iorq_n),
    .mreq_n(mreq_n),
    .rd_n(rd_n),
    .wr_n(wr_n),
    .phi(phi),
    .addr_in(addr_in),
    .dq(dq),
    .addr_out(addr_out),
    .cbar_hinyb(cbar_hinyb),
    .cbar_lonyb(cbar_lonyb)
  );

  integer i;

  // -------------------------------
  // Clock (phi)
  // -------------------------------
  initial begin
    phi = 0;
    forever #5 phi = ~phi;
  end

  // -------------------------------
  // Task: Display state
  // -------------------------------
  task show_state;
    begin
      $display("T=%0t | addr_in=%h addr_out=%h | dq=%h",
                $time, addr_in, addr_out, dq);
      $display(" cbar_hi=%b cbar_lo=%b",
                cbar_hinyb, cbar_lonyb);
      $display("--------------------------------------------------");
    end
  endtask

  // -------------------------------
  // Task: IO Write
  // -------------------------------
  task io_write;
    input [15:0] addr;
    input [7:0] data;
    begin
      @(negedge phi);
      addr_in = {8'b0, addr};
      dq_drive = data;
      iorq_n = 0;
      wr_n   = 0;
      rd_n   = 1;

      @(posedge phi);
      #1;
      show_state();

      iorq_n = 1;
      wr_n   = 1;
      dq_drive = 8'bz;
    end
  endtask

  // -------------------------------
  // Task: IO Read
  // -------------------------------
  task io_read;
    input [15:0] addr;
    begin
      @(negedge phi);
      addr_in = {8'b0, addr};
      iorq_n = 0;
      rd_n   = 0;
      wr_n   = 1;

      @(posedge phi);
      #1;
      show_state();

      iorq_n = 1;
      rd_n   = 1;
    end
  endtask

  // -------------------------------
  // Task: Memory access
  // -------------------------------
  task mem_access;
    input [23:0] addr;
    begin
      @(negedge phi);
      addr_in = addr;
      mreq_n = 0;
      iorq_n = 1;
      rd_n   = 1;
      wr_n   = 1;

      @(posedge phi);
      #1;
      show_state();

      mreq_n = 1;
    end
  endtask

  // -------------------------------
  // Stimulus
  // -------------------------------
  initial begin
    $display("Starting MMU simulation...\n");

    // Init
    reset_n = 0;
    en = 1;
    iorq_n = 1;
    mreq_n = 1;
    rd_n   = 1;
    wr_n   = 1;
    dq_drive = 8'bz;
    addr_in = 0;

    // Reset
    #10;
    reset_n = 1;

    // ---------------------------
    // Write MMU registers
    // ---------------------------
    $display("\n=== WRITE MMU REGISTERS ===");

    io_write(16'h0038, 8'h12); // CBR
    io_write(16'h0039, 8'h34); // BBR
    io_write(16'h003A, 8'hF2); // CBAR

    // ---------------------------
    // Read back registers
    // ---------------------------
    $display("\n=== READ MMU REGISTERS ===");

    io_read(16'h0038);
    io_read(16'h0039);
    io_read(16'h003A);

    // ---------------------------
    // Memory translation tests
    // ---------------------------
    $display("\n=== MEMORY TRANSLATION TEST ===");

    // Address below 1MB (MMU active)
    mem_access(24'h000123);
    mem_access(24'h000ABC);

    // Address above 1MB (bypass MMU)
    mem_access(24'h100123);
    mem_access(24'hFF0123);

    // ---------------------------
    // Sweep addresses
    // ---------------------------
    $display("\n=== ADDRESS SWEEP TEST ===");
    for (i = 0; i < 10; i = i + 1) begin
      mem_access(24'h000000 + i*32);
    end

    // ---------------------------
    // Disable MMU
    // ---------------------------
    $display("\n=== MMU DISABLED TEST ===");
    en = 0;
    mem_access(24'h000456);
    en = 1;

    // ---------------------------
    // Random testing
    // ---------------------------
    $display("\n=== RANDOM TESTING ===");
    for (i = 0; i < 10; i = i + 1) begin
      mem_access($random);
    end

    $display("\nSimulation complete.");
    $finish;
  end

endmodule
