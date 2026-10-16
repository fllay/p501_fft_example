`timescale 1ns / 1ps


module adf4002_dri(
input  sys_clk,
input  sys_rstn,
output adf_spi_clk,
output adf_spi_cs,
inout  adf_spi_dio   
    );
 
 
 


    wire     [9:0]    adf_lut_index1;
    wire     [24:0]   adf_lut_data1;   
  adf4002_config u0(
	.lut_index                  (adf_lut_index1           ),
	.lut_data                   (adf_lut_data1            )
);  
    
     wire                adf_spi_ce  ;
     wire                adf_spi_dir  ;
     wire			     adf_spi_in   ;
     wire			     adf_spi_out  ;
     wire			     adf_spi_clki  ;

assign  adf_spi_clk=adf_spi_clki;

assign  adf_spi_cs =adf_spi_ce;

// Explicit IOBUF for bidirectional SPI data pin.
// adf_spi_dir: 0 = output (write to ADF4002), 1 = input (read from ADF4002)
// T pin is active-high tri-state: T=1 disables output (input mode),
//                                  T=0 enables output (write mode)
IOBUF #(
    .IOSTANDARD ("LVCMOS33")
) i_adf_spi_iobuf (
    .IO (adf_spi_dio),     // bidirectional pad
    .I  (adf_spi_out),     // data to pad (write)
    .O  (adf_spi_in),      // data from pad (read)
    .T  (adf_spi_dir)      // tri-state control: 1=input, 0=output
);

 spi_config u1(
	.rst                        (!sys_rstn              ),
	.clk                        (sys_clk             ),
	.clk_div_cnt                (16'd500             ),
	.lut_index                  (adf_lut_index1           ),
	.lut_reg_addr               (adf_lut_data1[23:8]      ),
	.lut_reg_data               (adf_lut_data1[7:0]       ),
	.pll_check                  (   0        ),
	.pll_locked                 (          ),
	.error                      (                    ),
	.done                       (                ),	
	.spi_ce                     (adf_spi_ce              ),
	.spi_sclk                   (adf_spi_clki             ),
	.spi_dir          			(adf_spi_dir             ),
	.spi_in          			(adf_spi_in              ),
	.spi_out         			(adf_spi_out             )
); 
   
endmodule
