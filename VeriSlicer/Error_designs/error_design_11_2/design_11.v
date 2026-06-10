`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company: 
// Engineer: 
// 
// Create Date: 08.04.2025 15:43:54
// Design Name: 
// Module Name: hdc_controller
// Project Name: 
// Target Devices: 
// Tool Versions: 
// Description: 
// 
// Dependencies: 
// 
// Revision:
// Revision 0.01 - File Created
// Additional Comments:
// 
//////////////////////////////////////////////////////////////////////////////////


module design_11
    #(parameter number_of_dimensions = 10,  //number of levels
  parameter D = 600,                   //pruned dimension size
  parameter chunk_size = D/100,        //each vector passed in chunks of 100
  parameter number_features = 784,     //number of features in the current class
  parameter number_class = 10 )        //number of unique class vectors
 (
    input   clk,
    input   reset,
    input   from_decoder_start,
    input  [31:0]    value,
    input  [3:0]     number_of_levels,
    input  [3:0]     capture_cv_pointer,
    output reg [9:0]     level_index, 
    output reg [12:0] feature_vector_pointer, //parameterize this to D/100
    //output [4:0] level_vector_pointer,
    output reg [9:0] x_data_pointer,
    output reg [6:0] class_vector_pointer,
    output reg [3:0] hv_pointer,
    output reg       encode_enable,
    output reg       binarize_enable,
    output reg       accumulate_enable,
    output reg       similarity_check_enable,
    output reg       class_predictor_enable,
    output reg       SC_done,
    output reg [3:0] predicted_class
    );
    //should add more states
    parameter initial_state = 4'b0000;
    parameter increment_x_pointer_state = 4'b0100;
    parameter encode_enable_state = 4'b0010;
    parameter index_generator = 4'b0001;
    parameter binaize_state = 4'b0011;
    
    //state variable
    reg   [3:0] state;
    wire  [35:0]temp_level_index;
    //reg   [9:0] level_index;
    reg   [9:0] count, count2;
    reg         similarity_fsm_enable;
    reg   [1:0] similarity_state;
    //reg         SC_done;
    
    assign temp_level_index = value * (number_of_levels-1);
       
       
    always @(posedge clk or posedge reset)
    begin
        if (reset) begin
        feature_vector_pointer  <=0;
        x_data_pointer          <=0;
        encode_enable           <=0;
        accumulate_enable       <=0;
        binarize_enable         <=0;
        similarity_fsm_enable   <= 0;
        count                   <= 0;
        level_index             <= 0;
        state = 4'b0000;
      end
      else
        case(state)
            initial_state: begin
                    if(from_decoder_start)
                      begin
                        feature_vector_pointer  <=0;
                        x_data_pointer          <=0;
                        encode_enable           <=0;
                        accumulate_enable       <=0;
                        binarize_enable         <=0;
                        similarity_fsm_enable   <= 0;
                        count                   <= 0;
                        level_index             <= 0;
                        state                   <= 4'b0001;
                     end
                end
            4'b0001: begin
                    similarity_fsm_enable   <= 0;
                    level_index <= temp_level_index[35:32]*number_of_dimensions;    //pointer to select 100 bits of level vectors from BRAM
                    count       <= 0;    
                    state       <= 4'b0010;   //SC_done? 4'b0010 : 4'b0001;
                end
                
            4'b0010: begin
                    encode_enable           <= 1;
                    level_index             <= level_index + 1;    //pointer to select 100 bits of level vectors from BRAM
                    feature_vector_pointer  <= feature_vector_pointer + 1;
                    count                   <= 0;    
                    state                   <= 4'b0011;
                end    
                
            4'b0011: begin
                    encode_enable          <= 1;
                    binarize_enable        <= 0;
                    level_index            <= (count <= (chunk_size-3))? level_index + 1 : level_index;
                    count                  <= count + 1;
                    feature_vector_pointer <= (count <= (chunk_size-3))? feature_vector_pointer + 1 : feature_vector_pointer;
                    x_data_pointer         <= ((count == (chunk_size-4)) & (x_data_pointer == number_features))? x_data_pointer + 1 : x_data_pointer;
              //      accumulate_enable      <= (count == (chunk_size-2))? 1 : 0;
                    state                  <= (count == (chunk_size-2))? 4'b0100 : 4'b0011;
                end 
                   
            4'b0100: begin
                    count                  <= 0;
                    
                    encode_enable          <= 0;
                    binarize_enable        <= 0 ;//should 
                    accumulate_enable      <= 1;
                    level_index            <= temp_level_index[35:32]*number_of_dimensions;
                    feature_vector_pointer <= (feature_vector_pointer == number_features*chunk_size - 1 )? feature_vector_pointer : feature_vector_pointer + 1;
                    state                  <= 4'b0101;
                end
                  
            4'b0101:  begin
                    encode_enable          <= 1;
                    //should 
                    accumulate_enable      <= 0;
                    if ((feature_vector_pointer == number_features*chunk_size -1 ))
                      begin
                        binarize_enable        <= 1;
                        similarity_fsm_enable  <= 0;
                        state                  <= 4'b0110;   
                      end
                    else
                      begin
                        level_index            <= level_index + 1;
                        feature_vector_pointer <= feature_vector_pointer + 1;
                        state                  <= 4'b0011;
                      end
                       
                end
                
            4'b0110: begin
                        binarize_enable        <= 0;
                        similarity_fsm_enable  <= 1;
                        state                  <= 4'b0111;  
                     end   
                   
             4'b0111: begin
                     similarity_fsm_enable      <= 0;  
                     if ( SC_done )
                       begin    
                            state                  <= 4'b0000;  
                            
                       end
                    end   
        endcase 
    end
    
   always @ (posedge clk or posedge reset)
     begin
        if (reset)
          begin
            similarity_check_enable <= 0;
            class_predictor_enable  <= 0;
            class_vector_pointer    <= 0;
            hv_pointer              <= 0;
            count2                  <= 0;
            similarity_state        <= 2'b00;
            SC_done                 <= 0;
            predicted_class         <= 0;
          end
        else
          case (similarity_state)
          2'b00: begin
                similarity_check_enable <= 0;
                class_vector_pointer    <= 0;
                SC_done                 <= SC_done & from_decoder_start;
                predicted_class         <= SC_done? capture_cv_pointer : predicted_class;
                if (similarity_fsm_enable)
                  begin 
                        class_vector_pointer    <= class_vector_pointer + 1;
                        hv_pointer              <= hv_pointer;
                        similarity_state        <= 2'b01;
                        similarity_check_enable <= 1;
                  end
            end 
         2'b01: begin
             SC_done                    <= 0;
             similarity_check_enable    <= 1;
             class_predictor_enable     <= (count2 == (chunk_size - 1))? 1:0;
             hv_pointer                 <= hv_pointer + 1;
             class_vector_pointer       <= (count2 < (chunk_size - 2))? class_vector_pointer + 1 : class_vector_pointer;
             count2                     <= count2 + 1;
             similarity_state           <= (count2 == (chunk_size - 2))? 2'b10 : 2'b01;
           end
           
         2'b10: begin
             hv_pointer                 <= 0;
             similarity_check_enable    <= 0;           
             class_predictor_enable     <= 1;
             class_vector_pointer       <= (class_vector_pointer < (chunk_size*number_class - 2))? class_vector_pointer + 1 : class_vector_pointer;
             count2                     <= 0;
             similarity_state           <= 2'b11;
           end
           
          2'b11: begin 
             similarity_check_enable    <= (class_vector_pointer < (chunk_size*number_class - 2))? 1 : 0;         
             class_predictor_enable     <= 0;
             count2                     <= 0;
             hv_pointer                 <= 0;
             class_vector_pointer       <= (class_vector_pointer < (chunk_size*number_class - 2))? class_vector_pointer + 1 : 0;
             similarity_state           <= (class_vector_pointer < (chunk_size*number_class - 2))? 2'b01 : 2'b00;
              SC_done                    <= (class_vector_pointer >= (chunk_size*number_class - 1))? 1 : 0;
           end  
     endcase
   end       
            
            
endmodule
