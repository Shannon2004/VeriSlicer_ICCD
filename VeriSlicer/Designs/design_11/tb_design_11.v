`timescale 1ns/1ns

module tb_hdc_controller;

  // ---------------------------------------
  // Parameters (match DUT)
  // ---------------------------------------
  parameter number_of_dimensions = 10;
  parameter D = 600;
  parameter chunk_size = D/100;
  parameter number_features = 784;
  parameter number_class = 10;

  // ---------------------------------------
  // Inputs
  // ---------------------------------------
  reg clk;
  reg reset;
  reg from_decoder_start;
  reg [31:0] value;
  reg [3:0] number_of_levels;
  reg [3:0] capture_cv_pointer;

  // ---------------------------------------
  // Outputs
  // ---------------------------------------
  wire [9:0] level_index;
  wire [12:0] feature_vector_pointer;
  wire [9:0] x_data_pointer;
  wire [6:0] class_vector_pointer;
  wire [3:0] hv_pointer;
  wire encode_enable;
  wire binarize_enable;
  wire accumulate_enable;
  wire similarity_check_enable;
  wire class_predictor_enable;
  wire SC_done;
  wire [3:0] predicted_class;

  // ---------------------------------------
  // DUT
  // ---------------------------------------
  hdc_controller DUT (
    .clk(clk),
    .reset(reset),
    .from_decoder_start(from_decoder_start),
    .value(value),
    .number_of_levels(number_of_levels),
    .capture_cv_pointer(capture_cv_pointer),
    .level_index(level_index),
    .feature_vector_pointer(feature_vector_pointer),
    .x_data_pointer(x_data_pointer),
    .class_vector_pointer(class_vector_pointer),
    .hv_pointer(hv_pointer),
    .encode_enable(encode_enable),
    .binarize_enable(binarize_enable),
    .accumulate_enable(accumulate_enable),
    .similarity_check_enable(similarity_check_enable),
    .class_predictor_enable(class_predictor_enable),
    .SC_done(SC_done),
    .predicted_class(predicted_class)
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
  // Task: Display key signals
  // ---------------------------------------
  task show_state;
    begin
      $display("T=%0t | state signals:", $time);
      $display(" lvl_idx=%d fv_ptr=%d x_ptr=%d",
                level_index, feature_vector_pointer, x_data_pointer);
      $display(" encode=%b bin=%b acc=%b",
                encode_enable, binarize_enable, accumulate_enable);
      $display(" sim=%b pred_en=%b hv_ptr=%d cv_ptr=%d",
                similarity_check_enable, class_predictor_enable,
                hv_pointer, class_vector_pointer);
      $display(" SC_done=%b predicted_class=%d",
                SC_done, predicted_class);
      $display("--------------------------------------------------");
    end
  endtask

  // ---------------------------------------
  // Task: Step clock
  // ---------------------------------------
  task step;
    begin
      @(posedge clk);
      #1;
      show_state();
    end
  endtask

  // ---------------------------------------
  // Stimulus
  // ---------------------------------------
  initial begin
    $display("Starting HDC Controller simulation...\n");

    // Init
    reset = 1;
    from_decoder_start = 0;
    value = 32'd5;
    number_of_levels = 4'd8;
    capture_cv_pointer = 4'd3;

    // Reset
    step();
    reset = 0;
    step();

    // ---------------------------
    // Start signal
    // ---------------------------
    $display("\n=== START TEST ===");
    from_decoder_start = 1;
    step();
    from_decoder_start = 0;

    // ---------------------------
    // Encoding phase
    // ---------------------------
    $display("\n=== ENCODING PHASE ===");
    for (i = 0; i < 20; i = i + 1) begin
      step();
    end

    // ---------------------------
    // Accumulation phase
    // ---------------------------
    $display("\n=== ACCUMULATION PHASE ===");
    for (i = 0; i < 10; i = i + 1) begin
      step();
    end

    // ---------------------------
    // Binarization phase
    // ---------------------------
    $display("\n=== BINARIZATION PHASE ===");
    for (i = 0; i < 10; i = i + 1) begin
      step();
    end

    // ---------------------------
    // Similarity check phase
    // ---------------------------
    $display("\n=== SIMILARITY CHECK PHASE ===");
    for (i = 0; i < 50; i = i + 1) begin
      step();
    end

    // ---------------------------
    // Wait for SC_done
    // ---------------------------
    $display("\n=== WAIT FOR SC_done ===");
    while (!SC_done) begin
      step();
    end

    $display("\nFinal predicted class = %d", predicted_class);

    // ---------------------------
    // Restart test
    // ---------------------------
    $display("\n=== RESTART TEST ===");
    from_decoder_start = 1;
    step();
    from_decoder_start = 0;

    for (i = 0; i < 20; i = i + 1) begin
      step();
    end

    $display("\nSimulation complete.");
    $finish;
  end

endmodule
