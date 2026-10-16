
module spi_config
(
	input              rst,
	input              clk,
	input[15:0]        clk_div_cnt,
	output reg[9:0]    lut_index,
	input[15:0]        lut_reg_addr,
	input[7:0]         lut_reg_data,
	output reg         error,
	output             done,
	input				pll_check,
	output				pll_locked,
	output             spi_ce,
	output             spi_sclk,
	output              spi_dir,
	input			   spi_in,
	output			   spi_out
);

reg spi_read_req;
wire spi_read_req_ack;
reg spi_write_req;
wire spi_write_req_ack;
wire[15:0] spi_slave_reg_addr;
wire[7:0] spi_write_data;
wire[7:0] spi_read_data;
reg read_check_error ;

reg [31:0]	 spi_cnt ;
reg [7:0]	 pll_readback ;
wire err;
reg[3:0] state;

localparam S_IDLE                =  0;
localparam S_WR_SPI_CHECK        =  1;
localparam S_WR_SPI              =  2;
localparam S_RD_SPI_CHECK        =  3;
localparam S_RD_SPI              =  4;
localparam S_WR_SPI_DONE         =  5;
localparam S_WR_TEST             =  6;
localparam S_RD_TEST             =  7;
localparam S_PLL_STATUS_CHECK             =  8;
localparam S_PLL_SPI            =  9;

assign done = (state == S_WR_SPI_DONE);
assign spi_slave_reg_addr = (state == S_PLL_STATUS_CHECK )?16'hFFFF:lut_reg_addr[15:0];
assign spi_write_data  = lut_reg_data;

assign pll_locked = pll_readback[0] ;


reg [23:0]vio_data;
always@(posedge clk or posedge rst)
begin
	if(rst)
	begin
		state <= S_IDLE;
		lut_index <= 8'd0;
		read_check_error <= 1'b0 ;
		spi_cnt <= 0 ;
		pll_readback <= 0 ;
		vio_data<=0;
	end
	else 
		case(state)
			S_IDLE:
			begin
				state <= S_WR_SPI_CHECK;
				lut_index <= 8'd0;
			end
		
			S_WR_SPI_CHECK:
			begin
				if(spi_slave_reg_addr != 16'hffff)
				begin
					spi_write_req <= 1'b1;
					state <= S_WR_SPI;
				end
				else
				begin
					state <= S_WR_SPI_DONE;
					lut_index <= 8'd0;
				end
		
			end
			
			S_WR_SPI:
			begin
				if(spi_write_req_ack)
				begin
					lut_index <= lut_index + 8'd1;
					spi_write_req <= 1'b0;
					state <= S_WR_SPI_CHECK;
				end
			end			
	
			S_WR_SPI_DONE:
			begin				
				state <= S_WR_SPI_DONE;
			end
			
			default:
				state <= S_IDLE;
		endcase
end


adc_spi adc_spi_m0(
	.clk             (clk                 ),
	.rst             (rst                 ),
	.spi_ce          (spi_ce              ),
	.spi_sclk        (spi_sclk            ),
	.spi_dir          (spi_dir              ),
	.spi_in          (spi_in              ),
	.spi_out         (spi_out              ),
	.cmd_read        (spi_read_req        ),
	.cmd_write       (spi_write_req       ),
	.cmd_read_ack    (spi_read_req_ack    ),
	.cmd_write_ack   (spi_write_req_ack   ),
	.read_addr       (spi_slave_reg_addr ),
	.write_addr      (spi_slave_reg_addr  ),
	.read_data       (spi_read_data       ),
	.write_data      (spi_write_data      )
);
endmodule