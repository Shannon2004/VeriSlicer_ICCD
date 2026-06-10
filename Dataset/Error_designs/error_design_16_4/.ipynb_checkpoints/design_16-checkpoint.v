module design_16(clk, in1_m_kernel, in2_m_kernel, start_m, out_m, inf_m, zero_m, done_m);

parameter  N = 12;
parameter Bs = 4; 
parameter es = 2;



input [N-1:0] in1_m_kernel, in2_m_kernel;
input start_m, clk; 
output [N-1:0] out_m;
output inf_m, zero_m;
output done_m;

//reg [N-1:0] in1_m, in2_m;//, out_m;
////reg start_m, inf_m, zero_m, done_m;

//always @(posedge clk)   begin
//    in1_m = in1_m_kernel;
//    in2_m = in2_m_kernel;
//   // $display("start0_m = %b in1_m = %b in2_m = %b", start_m, in1_m, in2_m);
//end
//parameter N = 8;
wire [N-1:0] in1_m, in2_m;//, out_m;
//reg start_m, inf_m, zero_m, done_m;

//always @(posedge clk)   begin
    assign in1_m = in1_m_kernel;
    assign in2_m = in2_m_kernel;
   // $display("start0_m = %b in1_m = %b in2_m = %b", start_m, in1_m, in2_m);
//end


wire start0_m= start_m;
wire s1_m = in1_m[N-1];
wire s2_m = in2_m[N-1];
wire zero_tmp1_m = |in1_m[N-2:0];
wire zero_tmp2_m = |in2_m[N-2:0];
    wire inf1_m = in1_m[N-1] & (~zero_tmp1_m);
	wire inf2_m = in2_m[N-1] & (~zero_tmp2_m);
    wire zero1_m = ~(in1_m[N-1] | zero_tmp1_m);
	wire zero2_m = ~(in2_m[N-1] | zero_tmp2_m);
assign inf_m = inf1_m | inf2_m;
	assign zero_m = zero1_m & zero2_m;

//Data Extraction
wire rc1_m, rc2_m;
wire [Bs-1:0] regime1_m, regime2_m;
wire [es-1:0] e1_m, e2_m;
wire [N-es-1:0] mant1_m, mant2_m;
wire [N-1:0] xin1_m = s1_m ? -in1_m : in1_m;
wire [N-1:0] xin2_m = s2_m ? -in2_m : in2_m;
data_extract_v1 #(.N(N),.es(es)) uut_de1(.in(xin1_m), .rc(rc1_m), .regime(regime1_m), .exp(e1_m), .mant(mant1_m));
data_extract_v1 #(.N(N),.es(es)) uut_de2(.in(xin2_m), .rc(rc2_m), .regime(regime2_m), .exp(e2_m), .mant(mant2_m));

    wire [N-es:0] m1_m = {zero_tmp1_m,mant1_m};
	wire m2_m = {zero_tmp2_m,mant2_m};

//Sign, Exponent and Mantissa Computation
wire mult_s_m = s1_m ^ s2_m;

wire [2*(N-es)+1:0] mult_m = m1_m*m2_m;
wire mult_m_ovf_m = mult_m[2*(N-es)+1];
wire [2*(N-es)+1:0] mult_mN_m = ~mult_m_ovf_m ? mult_m << 1'b1 : mult_m;

wire [Bs+1:0] r1_m = rc1_m ? {2'b0,regime1_m} : -regime1_m;
wire [Bs+1:0] r2_m = rc2_m ? {2'b0,regime2_m} : -regime2_m;
wire [Bs+es+1:0] mult_e_m;
add_N_Cin #(.N(Bs+es+1)) uut_add_exp ({r1_m,e1_m}, {r2_m,e2_m}, mult_m_ovf_m, mult_e_m);

//Exponent and Regime Computation
wire [es-1:0] e_o_m;
wire [Bs:0] r_o_m;
reg_exp_op #(.es(es), .Bs(Bs)) uut_reg_ro (mult_e_m[es+Bs+1:0], e_o_m, r_o_m);

//Exponent, Mantissa and GRS Packing
wire [2*N-1+3:0]tmp_o_m = {{N{~mult_e_m[es+Bs+1]}},mult_e_m[es+Bs+1],e_o_m,mult_mN_m[2*(N-es):2*(N-es)-(N-es-1)+1], mult_mN_m[2*(N-es)-(N-es-1):2*(N-es)-(N-es-1)-1], |mult_mN_m[2*(N-es)-(N-es-1)-2:0] }; 


//Including Regime bits in Exponent-Mantissa Packing
wire [3*N-1+3:0] tmp1_o_m;
DSR_right_N_S #(.N(3*N+3), .S(Bs+1)) dsr2 (.a({tmp_o_m,{N{1'b0}}}), .b(r_o_m[Bs] ? {Bs{1'b1}} : r_o_m), .c(tmp1_o_m));

//Rounding RNE : ulp_add = G.(R + S) + L.G.(~(R+S))
    wire L_m = tmp1_o_m[N+4];
    wire G_m = tmp1_o_m[N+3];
    wire R_m = tmp1_o_m[N+2];
    wire St_m = |tmp1_o_m[N+1:0];
     wire ulp_m = ((G_m & (R_m | St_m)) | (L_m & G_m & ~(R_m | St_m)));
wire [N-1:0] rnd_ulp_m = {{N-1{1'b0}},ulp_m};

wire [N:0] tmp1_o_rnd_ulp_m;
add_N #(.N(N)) uut_add_ulp (tmp1_o_m[2*N-1+3:N+3], rnd_ulp_m, tmp1_o_rnd_ulp_m);
wire [N-1:0] tmp1_o_rnd_m = (r_o_m < N-es-2) ? tmp1_o_rnd_ulp_m[N-1:0] : tmp1_o_m[2*N-1+3:N+3];


//Final Output
wire [N-1:0] tmp1_oN_m = mult_s_m ? -tmp1_o_rnd_m : tmp1_o_rnd_m;
    assign out_m = inf_m|zero_m|(~mult_mN_m[2*(N-es)+1]) ? {inf_m,{N-1{1'b0}}} : {mult_s_m, tmp1_oN_m[N-1:1]};
	assign done_m = start0_m;
//always@(posedge clk)    begin
//$display("start0_m = %b done_m = %b in1_m = %b in2_m = %b", start0_m, done_m, in1_m, in2_m);
//end

endmodule
///////////////////////////////////////////////////////////////////////////////////////////////////
module data_extract_v1(in, rc, regime, exp, mant);


parameter N=16;
parameter Bs=4;
parameter es = 2;


input [N-1:0] in;
output rc;
output [Bs-1:0] regime;
output [es-1:0] exp;
output [N-es-1:0] mant;

wire [N-1:0] xin = in;
assign rc = xin[N-2];

wire [N-1:0] xin_r = rc ? ~xin : xin;

wire [Bs-1:0] k;
LOD_N #(.N(N)) xinst_k(.in({xin_r[N-2:0],rc^1'b0}), .out(k));

assign regime = rc ? k-1 : k;

wire [N-1:0] xin_tmp;
DSR_left_N_S #(.N(N), .S(Bs)) ls (.a({xin[N-3:0],2'b0}),.b(k),.c(xin_tmp));

assign exp= xin_tmp[N-1:N-es];
assign mant= xin_tmp[N-es-1:0];

endmodule

/////////////////
module sub_N (a,b,c);
parameter N=16;
input [N-1:0] a,b;
output [N:0] c;
wire [N:0] ain = {1'b0,a};
wire [N:0] bin = {1'b0,b};
sub_N_in #(.N(N)) s1 (ain,bin,c);
endmodule

/////////////////////////
module add_N (a,b,c);
parameter N=16;
input [N-1:0] a,b;
output [N:0] c;
wire [N:0] ain = {1'b0,a};
wire [N:0] bin = {1'b0,b};
add_N_in #(.N(N)) a1 (ain,bin,c);
endmodule

/////////////////////////

module add_N_Cin (a,b,cin,c);
parameter N=16;
input [N:0] a,b;
input cin;
output [N:0] c;
assign c = a + b + cin;
endmodule


/////////////////////////
module sub_N_in (a,b,c);
parameter N=8;
input [N:0] a,b;
output [N:0] c;
assign c = a - b;
endmodule

/////////////////////////
module add_N_in (a,b,c);
parameter N=16;
input [N:0] a,b;
output [N:0] c;
assign c = a + b;
endmodule

/////////////////////////
module add_sub_N (op,a,b,c);
parameter N=16;
input op;
input [N-1:0] a,b;
output [N:0] c;
wire [N:0] c_add, c_sub;

add_N #(.N(N)) a11 (a,b,c_add);
sub_N #(.N(N)) s11 (a,b,c_sub);
assign c = op ? c_add : c_sub;
endmodule

/////////////////////////
module add_1 (a,mant_ovf,c);
parameter N=16;
input [N:0] a;
input mant_ovf;
output [N:0] c;
assign c = a + mant_ovf;
endmodule

/////////////////////////
module abs_regime (rc, regime, regime_N);
parameter N = 16;
input rc;
input [N-1:0] regime;
output [N:0] regime_N;

assign regime_N = rc ? {1'b0,regime} : -{1'b0,regime};
endmodule

/////////////////////////
module conv_2c (a,c);
parameter N=16;
input [N:0] a;
output [N:0] c;
assign c = a + 1'b1;
endmodule
/////////////////
module reg_exp_op (exp_o, e_o, r_o);
parameter es=2;
parameter Bs=3;
input [es+Bs:0] exp_o;
output [es-1:0] e_o;
output [Bs:0] r_o;

assign e_o = exp_o[es-1:0];

wire [es+Bs:0] exp_oN_tmp;
conv_2c #(.N(es+Bs)) uut_conv_2c1 (~exp_o[es+Bs:0],exp_oN_tmp);
wire [es+Bs:0] exp_oN = exp_o[es+Bs] ? exp_oN_tmp[es+Bs:0] : exp_o[es+Bs:0];
assign r_o = (~exp_o[es+Bs] || |(exp_oN[es-1:0])) ? exp_oN[es+Bs-1:es] + 1 : exp_oN[es+Bs-1:es];
endmodule

/////////////////////////
module DSR_left_N_S(a,b,c);
        parameter N=16;
        parameter S=4;
        input [N-1:0] a;
        input [S-1:0] b;
        output [N-1:0] c;

wire [N-1:0] tmp [S-1:0];
assign tmp[0]  = b[0] ? a << 7'd1  : a; 
genvar i;
generate
	for (i=1; i<S; i=i+1)begin:loop_blk
		assign tmp[i] = b[i] ? tmp[i-1] << 2**i : tmp[i-1];
	end
endgenerate
assign c = tmp[S-1];

endmodule


/////////////////////////
module DSR_right_N_S(a,b,c);
        parameter N=16;
        parameter S=4;
        input [N-1:0] a;
        input [S-1:0] b;
        output [N-1:0] c;

wire [N-1:0] tmp [S-1:0];
assign tmp[0]  = b[0] ? a >> 7'd1  : a; 
genvar i;
generate
	for (i=1; i<S; i=i+1)begin:loop_blk
		assign tmp[i] = b[i] ? tmp[i-1] >> 2**i : tmp[i-1];
	end
endgenerate

assign c = tmp[S-1];

endmodule

//////////////////////////

module LOD_N (in, out);



parameter N = 64;
parameter S = 6; 
input [N-1:0] in;
output [S-1:0] out;

wire vld;
LOD #(.N(N)) l1 (in, out, vld);
endmodule
/////////////////////////////////////////

module LOD (in, out, vld);




parameter N = 64;
parameter S = 6;

   input [N-1:0] in;
   output [S-1:0] out;
   output vld;

  generate
    if(!(N == 2))
      begin
	assign vld = |in;
	assign out = ~in[1] & in[0];
      end
    else if (N & (N-1))
      //LOD #(1<<S) LOD ({1<<S {1'b0}} | in,out,vld);
      LOD #(1<<S) LOD ({in,{((1<<S) - N) {1'b0}}},out,vld);
    else
      begin
	wire [S-2:0] out_l, out_h;
	wire out_vl, out_vh;
	LOD #(N>>1) l(in[(N>>1)-1:0],out_l,out_vl);
	LOD #(N>>1) h(in[N-1:N>>1],out_h,out_vh);
	assign vld = out_vl | out_vh;
	assign out = out_vh ? {1'b0,out_h} : {out_vl,out_l};
      end
  endgenerate
endmodule


