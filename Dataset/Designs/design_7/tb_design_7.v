`timescale 1ns/1ns

module tb_bf16;

  // ---------------------------------------
  // DUT inputs
  // ---------------------------------------
  reg         clk;
  reg         rst_n;
  reg         enable;
  reg         valid;
  reg         read;
  reg         mode;     // 1: fp16, 0: int8
  reg         cfg;
  reg  [15:0] in_a;
  reg  [15:0] in_b;

  // ---------------------------------------
  // DUT outputs
  // ---------------------------------------
  wire [15:0] mac_out;
  wire        error;

  // ---------------------------------------
  // Instantiate DUT
  // ---------------------------------------
  bf16 DUT (
    .clk    (clk),
    .rst_n  (rst_n),
    .enable (enable),
    .valid  (valid),
    .read   (read),
    .mode   (mode),
    .cfg    (cfg),
    .in_a   (in_a),
    .in_b   (in_b),
    .mac_out(mac_out),
    .error  (error)
  );

  integer i;

  // ---------------------------------------
  // Clock generation
  // ---------------------------------------
  initial begin
    clk = 0;
    forever #5 clk = ~clk;
  end

  // ---------------------------------------
  // Task: display compact result
  // ---------------------------------------
  task show_results;
    begin
      $display("T=%0t | en=%b valid=%b read=%b cfg=%b mode=%b | in_a=%h in_b=%h | mac_out=%h error=%b",
               $time, enable, valid, read, cfg, mode, in_a, in_b, mac_out, error);
    end
  endtask

  // ---------------------------------------
  // Task: display detailed result
  // ---------------------------------------
  task show_detailed;
    begin
      $display("------------------------------------------------------------");
      $display("Time      : %0t", $time);
      $display("clk       : %b", clk);
      $display("rst_n     : %b", rst_n);
      $display("enable    : %b", enable);
      $display("valid     : %b", valid);
      $display("read      : %b", read);
      $display("cfg       : %b", cfg);
      $display("mode      : %b", mode);
      $display("in_a      : 0x%h", in_a);
      $display("in_b      : 0x%h", in_b);
      $display("mac_out   : 0x%h", mac_out);
      $display("error     : %b", error);
      $display("------------------------------------------------------------");
    end
  endtask

  // ---------------------------------------
  // Task: configure mode
  // IMPORTANT:
  // In your RTL, mode_reg updates only in:
  //   else if (cfg) begin mode_reg <= mode; end
  // which means enable must be 0 when cfg=1
  // ---------------------------------------
  task configure_mode;
    input mode_val;
    begin
      @(negedge clk);
      enable = 0;
      valid  = 0;
      read   = 0;
      cfg    = 1;
      mode   = mode_val;
      @(negedge clk);
      cfg    = 0;
      $display("Configured mode = %b at T=%0t", mode_val, $time);
    end
  endtask

  // ---------------------------------------
  // Task: feed one MAC input pair
  // ---------------------------------------
  task apply_mac_input;
    input [15:0] a_val;
    input [15:0] b_val;
    begin
      @(negedge clk);
      enable = 1;
      valid  = 1;
      read   = 0;
      in_a   = a_val;
      in_b   = b_val;
      @(negedge clk);
      valid  = 0;
      in_a   = 16'b0;
      in_b   = 16'b0;
    end
  endtask

  // ---------------------------------------
  // Task: read MAC output
  // In RTL, mac_out is visible when:
  // (read && enable && ~valid)
  // ---------------------------------------
  task read_mac_output;
    begin
      @(negedge clk);
      enable = 1;
      valid  = 0;
      read   = 1;
      @(posedge clk);
      #1;
      show_detailed();
      @(negedge clk);
      read   = 0;
    end
  endtask

  // ---------------------------------------
  // Task: clear/idle
  // ---------------------------------------
  task idle_cycle;
    begin
      @(negedge clk);
      enable = 0;
      valid  = 0;
      read   = 0;
      cfg    = 0;
      in_a   = 16'b0;
      in_b   = 16'b0;
    end
  endtask

  // ---------------------------------------
  // Stimulus
  // ---------------------------------------
  initial begin
    $display("Starting bf16 MAC simulation...");

    // Initial values
    rst_n   = 0;
    enable  = 0;
    valid   = 0;
    read    = 0;
    cfg     = 0;
    mode    = 0;
    in_a    = 0;
    in_b    = 0;

    // Reset
    #2;
    @(negedge clk);
    rst_n = 0;
    @(negedge clk);
    rst_n = 1;
    $display("Reset released at T=%0t", $time);

    // -------------------------------------------------
    // Test 1: INT8 mode basic sequence
    // -------------------------------------------------
    $display("\n=== TEST 1 : INT8 MODE BASIC ===");
    configure_mode(1'b0);

    apply_mac_input(16'h0003, 16'h0004); // 3 * 4
    show_results();

    apply_mac_input(16'h0002, 16'h0005); // 2 * 5 + prev
    show_results();

    apply_mac_input(16'h0001, 16'h0006); // 1 * 6 + prev
    show_results();

    read_mac_output();

    // -------------------------------------------------
    // Test 2: INT8 mode with negative-style patterns
    // -------------------------------------------------
    $display("\n=== TEST 2 : INT8 MODE RANDOM / SIGNED-LIKE PATTERNS ===");
    configure_mode(1'b0);

    apply_mac_input(16'h0081, 16'h0002);
    show_results();

    apply_mac_input(16'h0084, 16'h0003);
    show_results();

    apply_mac_input(16'h007F, 16'h0002);
    show_results();

    read_mac_output();

    // -------------------------------------------------
    // Test 3: FP16 mode basic patterns
    // Common half/fp-style encodings used as raw patterns
    // 3C00 = 1.0
    // 4000 = 2.0
    // 4200 = 3.0
    // -------------------------------------------------
    $display("\n=== TEST 3 : FP16 MODE BASIC ===");
    configure_mode(1'b1);

    apply_mac_input(16'h3C00, 16'h3C00); // 1.0 * 1.0
    show_results();

    apply_mac_input(16'h4000, 16'h3C00); // 2.0 * 1.0 + prev
    show_results();

    apply_mac_input(16'h4200, 16'h3C00); // 3.0 * 1.0 + prev
    show_results();

    read_mac_output();

    // -------------------------------------------------
    // Test 4: FP16 zero behavior
    // -------------------------------------------------
    $display("\n=== TEST 4 : FP16 ZERO BEHAVIOR ===");
    configure_mode(1'b1);

    apply_mac_input(16'h0000, 16'h3C00);
    show_results();

    apply_mac_input(16'h3C00, 16'h0000);
    show_results();

    read_mac_output();

    // -------------------------------------------------
    // Test 5: FP16 possible overflow/underflow patterns
    // Raw patterns to provoke error behavior
    // -------------------------------------------------
    $display("\n=== TEST 5 : FP16 ERROR EXPLORATION ===");
    configure_mode(1'b1);

    apply_mac_input(16'h7BFF, 16'h7BFF);
    show_results();

    apply_mac_input(16'h0400, 16'h0400);
    show_results();

    read_mac_output();

    // -------------------------------------------------
    // Test 6: Random INT8 transactions
    // -------------------------------------------------
    $display("\n=== TEST 6 : RANDOM INT8 TESTING ===");
    configure_mode(1'b0);
    for (i = 0; i < 20; i = i + 1) begin
      apply_mac_input($random, $random);
      #1;
      show_results();
    end
    read_mac_output();

    // -------------------------------------------------
    // Test 7: Random FP16-pattern transactions
    // -------------------------------------------------
    $display("\n=== TEST 7 : RANDOM FP16 PATTERN TESTING ===");
    configure_mode(1'b1);
    for (i = 0; i < 20; i = i + 1) begin
      apply_mac_input($random, $random);
      #1;
      show_results();
    end
    read_mac_output();

    // -------------------------------------------------
    // Test 8: Read without valid
    // -------------------------------------------------
    $display("\n=== TEST 8 : READ BEHAVIOR ===");
    configure_mode(1'b0);
    read_mac_output();

    // -------------------------------------------------
    // Test 9: Disabled behavior
    // -------------------------------------------------
    $display("\n=== TEST 9 : DISABLED BEHAVIOR ===");
    idle_cycle();
    @(posedge clk);
    #1;
    show_detailed();

    $display("Simulation complete.");
    $finish;
  end

endmodule
