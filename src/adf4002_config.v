`timescale 1ns / 1ps


module adf4002_config(
	input[9:0]             lut_index,   //Look-up table address
	output reg[24:0]       lut_data     //reg address reg data
);

always@(*)
begin
	case(lut_index)			  
		10'd  0: lut_data <= {24'h0000C8};  
		10'd  1: lut_data <= {24'h00C801};  
		10'd  2: lut_data <= {24'h0D80A2};  
		default:lut_data <= {16'hffff,8'hff};
	endcase
end


endmodule 