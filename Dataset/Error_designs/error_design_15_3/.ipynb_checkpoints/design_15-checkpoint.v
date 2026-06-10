module design_15(
le_o, //8 bits
e_o_m, //2bits
DSR_left_out, //29bits
r_o_m, //4 bits
ls,
inf_final,
zero_final,
start0_m,	
out_m, // 16 bits
done_m
	
);


parameter N=16;
parameter Bs=4; //4
parameter es = 2;

input [es+Bs+2:0] le_o; //8 bits
input [es-1:0] e_o_m; //2bits
input [2*(N-es):0] DSR_left_out; //29bits
input [Bs:0] r_o_m; //4 bits
input ls;
input inf_final;
input zero_final;
input start0_m;
output [N-1:0] out_m; // 16 bits
output done_m;


wire [2*N-1+3:0]tmp_o_m;
assign tmp_o_m = {{N{~le_o[es+Bs]}},le_o[es+Bs],e_o_m,DSR_left_out[2*(N-es)-1:2*(N-es)-(N-es-1)], DSR_left_out[2*(N-es)-(N-es-1)-1:2*(N-es)-(N-es-1)-2], |DSR_left_out[2*(N-es)-(N-es-1)-3:0] }; 

//Including Regime bits in Exponent-Mantissa Packing
//output [3*N-1+3:0] tmp1_o_m;
wire [3*N-1+3:0] tmp1_o_m;
DSR_right_N_S #(.N(3*N+3), .S(Bs+1)) dsr2 (.a({tmp_o_m,{N{1'b0}}}), .b(r_o_m[Bs] ? {Bs{1'b1}} : r_o_m), .c(tmp1_o_m));

//Rounding RNE : ulp_add = G.(R + S) + L.G.(~(R+S))
    wire L_m = tmp1_o_m[N+4];
    wire G_m = tmp1_o_m[N+3];
    wire R_m = tmp1_o_m[N+2];
    wire St_m = |tmp1_o_m[N+1:0];
//output ulp_m;
wire ulp_m;
 assign    ulp_m = ((G_m & (R_m | St_m)) | (L_m & G_m & ~(R_m | St_m)));
wire [N-1:0] rnd_ulp_m = {{N-1{1'b0}},ulp_m};

//output [N:0] tmp1_o_rnd_ulp_m;
wire [N:0] tmp1_o_rnd_ulp_m;
add_N #(.N(N)) uut_add_ulp (tmp1_o_m[2*N-1+3:N+3], rnd_ulp_m, tmp1_o_rnd_ulp_m);
//output [N-1:0]tmp1_o_rnd_m;
wire [N-1:0]tmp1_o_rnd_m;
assign tmp1_o_rnd_m = (r_o_m < N-es-2) ? tmp1_o_rnd_ulp_m[N-1:0] : tmp1_o_m[2*N-1+3:N+3];

//Final Output
//output [N-1:0] tmp1_oN_m ;
wire [N-1:0] tmp1_oN_m ;
assign tmp1_oN_m = ls ? -tmp1_o_rnd_m : tmp1_o_rnd_m;
    assign out_m = inf_final|zero_final|(~DSR_left_out[2*(N-es)]) ? {inf_final,{N-1{1'b0}}} : {ls, tmp1_oN_m[N-1:1]};
    
	assign done_m = start0_m;
	
endmodule


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


module add_N (a,b,c);
parameter N=16;
input [N-1:0] a,b;
output [N:0] c;
wire [N:0] ain = {1'b0,a};
wire [N:0] bin = {1'b0,b};
add_N_in #(.N(N)) a1 (ain,bin,c);
endmodule


module add_N_in (a,b,c);
parameter N=16;
input [N:0] a,b;
output [N:0] c;
assign c = a + b;
endmodule
