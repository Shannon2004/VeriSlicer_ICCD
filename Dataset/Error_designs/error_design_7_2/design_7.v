// No pipelined MAC(Multiplier accumulator)
// Version: 1.0 

// Description

	// Timing

	//  clk      __|--|__|--|__|--|__|--|__|--|__|--|__|--|__|--|__|--|__|--|__|
	//  enable   ________|-----------------------------------------------|_____
	//  valid    ______________|-----------------|____________________________
	//  read     ____________________________________________|----|___________
	//  cfg      _|----|_|xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx|____  
	//  in_a     ______________|abcde|abcde|abcde|____________________________
	//  in_b     ______________|abcde|abcde|abcde|____________________________
	//  mac_out  ____________________________________________|jklm|___________
	//  mode     _|----|______________________________________________________


module design_7
(
	input                    clk, 
	input                    rst_n,        // asynchronous reset
	input					 enable,
	input 					 valid,
	input 					 read,   // read:1 == read behave  ;  read:0 == write behave
	input                    mode,   // 1:fp16,0:int8
	input					 cfg,
	input             [15:0] in_a, 
	input             [15:0] in_b, 
	output            [15:0] mac_out,
	output					 error
);

	reg [15:0] a_reg, b_reg, c_reg;
	reg mode_reg;

	wire [15:0] a,b,c,mac_out_tmp;
	wire float_int;

	assign a         = a_reg;
	assign b         = b_reg;
	assign c         = c_reg;
	assign float_int = mode_reg;
	assign mac_out   = (read && enable && ~valid) ? mac_out_tmp : 16'b0 ; // read out mac_out with condition

//---------------------------------------------------------
//   MAC
//---------------------------------------------------------	
	always @ ( posedge clk or negedge rst_n ) begin
		if ( ! rst_n ) begin
			a_reg    <= 16'b0 ;
			b_reg    <= 16'b0 ;
			c_reg    <= 16'b0;
			mode_reg <= 1'b0;
		end else if(enable) begin

			if (valid) begin 
				a_reg   <= in_a ;
				b_reg   <= in_b ;
				c_reg   <= mac_out_tmp;
			end
			else if (read) begin // reset data after read operation
				c_reg <= 16'b0;
				a_reg <= 16'b0;
				b_reg <= 16'b0;
			end

		end else if (cfg) begin
			mode_reg <= mode;
		end 
	end 

	mac_unit u_mac (
	`ifdef PIPLINE
		 .clk     (clk        ),
		 .rst_n   (rst_n      ),
	`endif
		 .in_a    (a          ),
		 .in_b    (b          ),
		 .in_c    (c          ),
		 .mode    (float_int  ),
		 .mac_out (mac_out_tmp),
		 .error	  (error      )
	);

endmodule	

module mac_unit
(
`ifdef PIPLINE
	input            clk,
	input            rst_n,
`endif
	input     [15:0] in_a, // multiplier input1
	input     [15:0] in_b, // multiplier input2
	input     [15:0] in_c, // adder input2 ; adder input1 = in_a*in_b
	input 	     	 mode,
	output    [15:0] mac_out,
	output 		     error
);

	wire [15:0] mul_out;

	int_fp_add add(
	`ifdef PIPLINE
		.clk   (clk    ),
		.rst_n (rst_n  ),
	`endif 
		.mode  ( mode  ) ,
		.a     (mul_out) ,
		.b     ( in_c  ) ,
		.c     (mac_out)
	);


	int_fp_mul mul(
	`ifdef PIPLINE
		.clk   (clk    ),
		.rst_n (rst_n  ),
	`endif 
		.mode  ( mode  ) ,
		.a     ( in_a  ) ,
		.b     ( in_b  ) ,
		.c     (mul_out),
		.error (error  )
	);

endmodule	


module int_fp_add (
`ifdef PIPLINE
    input         clk,
    input         rst_n,
`endif
    input         mode,
    input  [15:0] a,
    input  [15:0] b,
    output [15:0] c
    );

    wire [10:0] adder_input_1,adder_input_2,aligned_small,adder_output;
    wire if_sub,a_sign, b_sign, c_sign,c1;
    wire [15:0] normalized_out;

    // only used in INT8 MAC mode
    wire [4:0] higher_add,higher_a,higher_b;

    wire [15:0] result;
    reg [14:0] bigger, smaller;
    reg a_larger_b;

`ifdef PIPLINE
    reg [14:0] bigger_reg, smaller_reg;
    reg [10:0] adder_output_reg;
    wire [14:0] bigger_tmp, smaller_tmp;
    wire [10:0] adder_output_tmp;
`endif  


    assign a_sign        = a[15];
    assign b_sign        = b[15];
    assign if_sub        = (a_sign == b_sign) ? 1'b0 : 1'b1;
    assign c_sign        = a_larger_b ? a_sign : b_sign;
    assign higher_a      = (mode == 1'b0) ? a[15:11] : 5'b0;
    assign higher_b      = (mode == 1'b0) ? b[15:11] : 5'b0;
    assign adder_input_1 = (mode==1'b0) ? a[10:0] :{1'b1,bigger[9:0]};
    assign adder_input_2 = (mode==1'b0) ? b[10:0] : (if_sub ? ~aligned_small + 1'b1 : aligned_small);
    assign c             = (mode == 1'b0) ? {higher_add,adder_output} : result;

    //compare two number regardless sign
    always @(*) begin
        if (a[14:0] < b[14:0]) begin 
            bigger = a[14:0];
            smaller = b[14:0];
            a_larger_b = 1'b1;
        end else begin 
            bigger = b[14:0];
            smaller = a[14:0];
            a_larger_b = 1'b0;
        end 
    end

`ifdef PIPLINE 
    always @ (posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            bigger_reg <= 15'b0;
            smaller_reg <= 15'b0;
            adder_output_reg <= 11'b0;
        end else begin
            bigger_reg <= bigger;
            smaller_reg <= smaller;
            adder_output_reg <= adder_output;
        end
    end
    assign bigger_tmp = bigger_reg[14:0];
    assign smaller_tmp = smaller_reg[14:0];
    assign adder_output_tmp = adder_output_reg[10:0];
`endif

`ifdef PIPLINE
    // align small number
    alignment u1(bigger_tmp,smaller_tmp,aligned_small);
`else 
    // align small number
    alignment u1(bigger,smaller,aligned_small);
`endif

    cla_nbit #(.n(11)) u2(adder_input_1,adder_input_2,1'b0,adder_output,c1);

    // This 5 bit adder only used in INT8 MAC mode
    cla_nbit #(.n(5)) u3(higher_a,higher_b,c1,higher_add,c2);

`ifdef PIPLINE
    add_normalizer u4(c_sign,bigger[14:10],adder_output_tmp,result,c1,if_sub);
`else 
    add_normalizer u4(c_sign,bigger[14:10],adder_output,result,c1,if_sub);
`endif

endmodule


module alignment (
	input  [14:0] bigger, 
	input  [14:0] smaller,
	output [10:0] aligned_small
	);

	wire c1;
	wire [4:0] bigger_exponent, smaller_exponent,shift_bits;

	assign bigger_exponent  = bigger  [14:10];
	assign smaller_exponent = smaller [14:10];
	assign aligned_small    = ({1'b1,smaller[9:0]} >> shift_bits);

	cla_nbit #(.n(5)) u1(bigger_exponent,~smaller_exponent+1'b1,1'b0,shift_bits,c1);

endmodule


module add_normalizer (
    input             sign,
    input      [ 4:0] exponent,
    input      [10:0] mantissa_add,
    output reg [15:0] result,
    input             if_carray,
    input             if_sub
    );

    reg [4:0] number_of_zero_lead;
    reg [10:0] norm_mantissa_add;
    reg [9:0] mantissa_tmp;

    wire [4:0] shift_left_exp;
    wire c1;

    always @ (*) begin
        if (mantissa_add[10:4] == 7'b0000_001) begin
            number_of_zero_lead = 5'd6;
            norm_mantissa_add   = (mantissa_add << 4'd6);
        end else if (mantissa_add[10:5] == 6'b0000_01) begin 
            number_of_zero_lead = 5'd5;
            norm_mantissa_add   = (mantissa_add << 4'd5);
        end else if (mantissa_add[10:6] == 5'b0000_1) begin
            number_of_zero_lead = 5'd4;
            norm_mantissa_add   = (mantissa_add << 4'd4);
        end else if (mantissa_add[10:7] == 4'b0001) begin
            number_of_zero_lead = 5'd3;
            norm_mantissa_add   = (mantissa_add << 4'd3);
        end else if (mantissa_add[10:8] == 3'b001) begin
            number_of_zero_lead = 5'd2;
            norm_mantissa_add   = (mantissa_add << 4'd2);
        end else if (mantissa_add[10:9] == 2'b01) begin
            number_of_zero_lead = 5'd1;
            norm_mantissa_add   = (mantissa_add << 4'd1);
        end else begin 
            number_of_zero_lead = 5'd0;
            norm_mantissa_add   = mantissa_add[10:0];
        end 
    end

    always @(*) begin
        result[15]        = sign;
        if (!if_sub) begin 
            result[14:10] = if_carray ? exponent + 1'b1 : exponent;
            result[9:0]   = if_carray ? mantissa_add[10:1] : mantissa_add[9:0];
        end else begin 
            result[14:10] = shift_left_exp;
            result[9:0]   = norm_mantissa_add[9:0];
        end 
    end

    cla_nbit #(.n(5)) u1(exponent,~number_of_zero_lead+1'b1,1'b0,shift_left_exp,c1);


endmodule


module cla_nbit #(
    parameter n = 4
) (
  input   [n-1:0] a,
  input   [n-1:0] b,
  input           ci,
  output  [n-1:0] s,
  output          co
  );

  wire [n-1:0] g;
  wire [n-1:0] p;
  wire [  n:0] c;

  assign c[0] = ci;
  assign co   = c[n];

  genvar i;  /* i - generate index variable */

  generate
    for (i = 0; i < n; i = i + 1) begin : addbit
      assign s[i] = a[i] ^ b[i] ^ c[i];
      assign g[i] = a[i] & b[i];
      assign p[i] = a[i] & b[i];
      assign c[i + 1] = g[i] | (p[i] & c[i]);
    end
  endgenerate
  
endmodule


module int_fp_mul (
`ifdef PIPLINE
    input         clk,
    input         rst_n,
`endif
    input         mode,
    input  [15:0] a,
    input  [15:0] b,
    output [15:0] c,
    output        error // valid in fp16 mode 
    );

    wire [15:0] c_tmp;
    wire        c_sign,a_zero,b_zero;
    wire [4:0] sum_exponent, biased_sum_exponent;
    wire [15:0] multiplier_input1,multiplier_input2;

    wire [31:0] multiplier_output;
    wire [14:0] normalized_out;
    wire [21:0] mantissa_prod;
    wire c1,c2,underflow,overflow;

    assign overflow = (c1 && c2 && ~biased_sum_exponent[4]) ? 1'b1 :1'b0;
    assign underflow = (~c1 && ~c2 && biased_sum_exponent[4]) ? 1'b1:1'b0;

    assign a_zero = ~(|a);
    assign b_zero = ~(|b);
    assign c_sign = a[15] ^ b[15];
    assign multiplier_input1 = mode ? {5'b0,1'b1,a[9:0]} : ((a[7]==1'b0) ? {9'b0,a[6:0]} : {9'b0,~a[6:0]+1'b1});
    assign multiplier_input2 = mode ? {5'b0,1'b1,b[9:0]} : ((b[7]==1'b0) ? {9'b0,b[6:0]} : {9'b0,~b[6:0]+1'b1});
    
    assign c = mode ? ((a_zero | b_zero) ? 16'b0 : c_tmp) : ((a[7]^b[7] == 1'b0) ? multiplier_output[15:0] : {1'b1,~multiplier_output[14:0]+1'b1});
    //error detect
    assign c_tmp = (~error) ? {c_sign,normalized_out} : (underflow ? {c_sign,15'b0000_0000_0000_000} : {c_sign,5'b1111_1,10'b0000_0000_00});
    
    assign error = overflow | underflow; 

    
`ifdef PIPLINE

    reg [31:0] multiplier_output_tmp;
    
    always @ (posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            multiplier_output_tmp <= 32'b0;
        end else begin
            multiplier_output_tmp <= multiplier_output;
        end
    end
    
    assign mantissa_prod = multiplier_output_tmp[21:0];
    mul16x16 u1(clk,rst_n,multiplier_input1,multiplier_input2,multiplier_output);

`else 

    assign mantissa_prod = multiplier_output[21:0];
    mul16x16 u1(multiplier_input1,multiplier_input2,multiplier_output);

`endif
    
    cla_nbit #(.n(5)) u2(a[14:10],b[14:10],1'b0,sum_exponent,c1); // add exponent
    cla_nbit #(.n(5)) u3(sum_exponent, 5'b10001,1'b0,biased_sum_exponent,c2); // minus bias
    mul_normalizer u4(biased_sum_exponent,mantissa_prod,normalized_out);

endmodule

module mul_normalizer (
	input  [ 4:0] exponent,
	input  [21:0] mantissa_prod,
	output [14:0] result
);

	wire [4:0] result_exponent;
	wire [9:0] result_mantissa;

	assign result_exponent = (mantissa_prod[21]) ? (exponent + 1'b1): exponent;
	assign result_mantissa = (mantissa_prod[21]) ? mantissa_prod[20:11]:mantissa_prod[19:10];
	assign result 		   = {result_exponent,result_mantissa};

// No rounding and No overflow/underflow detection

endmodule


module mul16x16(
`ifdef PIPLINE
    input clk,
    input rst_n,
`endif
    input  [15:0] a,
    input  [15:0] b,
    output [31:0] c);

    wire [63:0] tmp1,tmp2;
    wire [23:0] result1;
    wire [23:0] result2;
    wire co1,co2,co3;

`ifdef PIPLINE
	// one stage pipline
	reg [63:0] tmp1_reg;
    always @ (posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tmp1_reg <= 64'b0;
        end else begin
            tmp1_reg <= tmp1;
        end
    end
    assign tmp2 = tmp1_reg;

`else 
	assign tmp2 = tmp1;

`endif

    mul8x8 u1(a[15:8],b[15:8],tmp1[63:48]);
    mul8x8 u2(a[7:0] ,b[15:8],tmp1[47:32]);
    mul8x8 u3(a[15:8],b[ 7:0],tmp1[31:16]);
    mul8x8 u4(a[7:0] ,b[ 7:0],tmp1[15:0]);

    cla_nbit #(.n(24)) u5({tmp2[63:48],8'b0} ,{8'b0,tmp2[47:32]} ,1'b0 ,result1 ,co1);
    cla_nbit #(.n(24)) u6({8'b0,tmp2[31:16]} ,{16'b0,tmp2[15:8]} ,co1  ,result2 ,co2);
    cla_nbit #(.n(24)) u7(result1            ,result2            ,co2  ,c[31:8] ,co3);

    assign c[7:0] = tmp2[7:0];

endmodule


module mul8x8(
	input  [ 7:0] a,
	input  [ 7:0] b,
	output [15:0] c
);

	wire [31:0] tmp1;
	wire [11:0] result1;
	wire [11:0] result2;
	wire co1,co2,co3;

	mul4x4 u1(a[7:4],b[7:4],tmp1[31:24]);
	mul4x4 u2(a[3:0],b[7:4],tmp1[23:16]);
	mul4x4 u3(a[7:4],b[3:0],tmp1[15:8]);
	mul4x4 u4(a[3:0],b[3:0],tmp1[7:0]);

	cla_nbit #(.n(12)) u5({tmp1[31:24],4'b0} ,{4'b0,tmp1[23:16]} ,1'b0 ,result1 ,co1);
	cla_nbit #(.n(12)) u6({4'b0,tmp1[15:8]}  ,{8'b0,tmp1[7:4]}   ,co1  ,result2 ,co2);
	cla_nbit #(.n(12)) u7(result1			 ,result2			 ,co2  ,c[15:4] ,co3);

	assign c[3:0] = tmp1[3:0];

endmodule


module mul4x4(
	input  [3:0] a,
	input  [3:0] b,
	output [7:0] c
	);

	wire [15:0] tmp1;
	wire [ 5:0] result1;
	wire [ 5:0] result2;
	wire 		co1,co2,co3;

	mul2x2 u1(a[3:2],b[3:2],tmp1[15:12]);
	mul2x2 u2(a[1:0],b[3:2],tmp1[11:8]);
	mul2x2 u3(a[3:2],b[1:0],tmp1[7:4]);
	mul2x2 u4(a[1:0],b[1:0],tmp1[3:0]);

	cla_nbit #(.n(6)) u5({tmp1[15:12],2'b0},{2'b0,tmp1[11:8]},1'b0	,result1	,co1);
	cla_nbit #(.n(6)) u6({2'b0,tmp1[7:4]}  ,{4'b0,tmp1[3:2]} ,co1 	,result2	,co2);
	cla_nbit #(.n(6)) u7(result1		   ,result2			 ,co2 	,c[7:2] 	,co3);

	assign c[1:0] = tmp1[1:0];

endmodule


module mul2x2(
	input  [1:0] a,
	input  [1:0] b,
	output [3:0] c
	);

	wire [3:0] tmp;
	
	assign tmp[0] = a[0] & b[0];
	assign tmp[1] = (a[1]&b[0]) ^ (a[0]&b[1]);
	assign tmp[2] = (a[0]&b[1]) & (a[1]&b[0]) ^ (a[1]&b[1]);
	assign tmp[3] = (a[0]&b[1]) & (a[1]&b[0]) & (a[1]&b[1]);
	assign c 	  = {tmp[3],tmp[2],tmp[1],tmp[0]};

endmodule
