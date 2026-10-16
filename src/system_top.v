
`timescale 1ns/100ps

module system_top (
  output          MDIO_PHY_mdc,
  inout           MDIO_PHY_mdio_io,
  input [3:0]     RGMII_rd,
  input           RGMII_rx_ctl,
  input           RGMII_rxc,
  output [3:0]    RGMII_td,
  output          RGMII_tx_ctl,
  output          RGMII_txc,
  output          adf_spi_clk_0,
  output          adf_spi_cs_0,
  inout           adf_spi_dio_0,
  input           dp_aux_data_in_0,
  output [0:0]    dp_aux_data_oe_n_0,
  output          dp_aux_data_out_0,
  input           dp_hot_plug_detect_0,
  input           sys_clk_n,
  input           sys_clk_p,
  input           sys_rstn, 
  input           rx_clk_in_p,
  input           rx_clk_in_n,
  input           rx_frame_in_p,
  input           rx_frame_in_n,
  input   [ 5:0]  rx_data_in_p,
  input   [ 5:0]  rx_data_in_n,
  output          tx_clk_out_p,
  output          tx_clk_out_n,
  output          tx_frame_out_p,
  output          tx_frame_out_n,
  output  [ 5:0]  tx_data_out_p,
  output  [ 5:0]  tx_data_out_n,

  output          enable,
  output          txnrx,

  output          gpio_resetb,
  output          gpio_sync,
  output          gpio_en_agc,
  output  [ 3:0]  gpio_ctl,
  input   [ 7:0]  gpio_status,

  output          spi_csn,
  output          spi_clk,
  output          spi_mosi,
  input           spi_miso,
 
  output          fddtdd_sw,  
  output          trx_sw,     
  output          fddtdd_sw1,  
  output          trx_sw1,
  
  output   [1:0]  clk_en   
  
  );

  // internal signals

  wire    [94:0]  gpio_i;
  wire    [94:0]  gpio_o;
  wire    [ 2:0]  spi0_csn;

  wire  [12:0]  gpio_bd_i;
  wire  [ 7:0]  gpio_bd_o;

  // defaults

  assign gpio_resetb = gpio_o[46:46];
  assign gpio_sync = gpio_o[45:45];
  assign gpio_en_agc = gpio_o[44:44];
  assign gpio_ctl = gpio_o[43:40];
  assign gpio_bd_o = gpio_o[20:13];

  assign gpio_i[94:40] = gpio_o[94:40];
  assign gpio_i[39:32] = gpio_status;
  assign gpio_i[31:13] = gpio_o[31:13];
  assign gpio_i[12: 0] = gpio_bd_i;

  assign spi_csn = spi0_csn[0];


  assign fddtdd_sw  = 0;
  assign trx_sw     = 0;
  assign fddtdd_sw1 = 1; 
  assign trx_sw1    = 1;

  assign clk_en[0]=1;
  assign clk_en[1]=1;
  
  // MDIO pad: the generated block design exposes i/o/t, the board has one bidirectional pin
  wire mdio_phy_i, mdio_phy_o, mdio_phy_t;
  IOBUF i_mdio_iobuf (.I(mdio_phy_o), .IO(MDIO_PHY_mdio_io), .O(mdio_phy_i), .T(mdio_phy_t));

  // instantiations

  system_wrapper i_system_wrapper (
    .MDIO_PHY_mdc(MDIO_PHY_mdc),
    .MDIO_PHY_mdio_i(mdio_phy_i),
    .MDIO_PHY_mdio_o(mdio_phy_o),
    .MDIO_PHY_mdio_t(mdio_phy_t),
    .RGMII_rd(RGMII_rd),
    .RGMII_rx_ctl(RGMII_rx_ctl),
    .RGMII_rxc(RGMII_rxc),
    .RGMII_td(RGMII_td),
    .RGMII_tx_ctl(RGMII_tx_ctl),
    .RGMII_txc(RGMII_txc),  
    .adf_spi_clk_0        (adf_spi_clk_0       ),
    .adf_spi_cs_0         (adf_spi_cs_0        ),
    .adf_spi_dio_0        (adf_spi_dio_0       ),
    .dp_aux_data_in_0     (dp_aux_data_in_0    ),
    .dp_aux_data_oe_n_0   (dp_aux_data_oe_n_0  ),
    .dp_aux_data_out_0    (dp_aux_data_out_0   ),
    .dp_hot_plug_detect_0 (dp_hot_plug_detect_0),
    .enable (enable),
    .gpio_i (gpio_i),
    .gpio_o (gpio_o),
    .gpio_t (),
    .rx_clk_in_n (rx_clk_in_n),
    .rx_clk_in_p (rx_clk_in_p),
    .rx_data_in_n (rx_data_in_n),
    .rx_data_in_p (rx_data_in_p),
    .rx_frame_in_n (rx_frame_in_n),
    .rx_frame_in_p (rx_frame_in_p),
    .spi0_csn (spi0_csn),
    .spi0_miso (spi_miso),
    .spi0_mosi (spi_mosi),
    .spi0_sclk (spi_clk),
    .sys_clk_n(sys_clk_n),
    .sys_clk_p(sys_clk_p),
    .sys_rstn (sys_rstn ),
    .tdd_sync_i (1'b0),
    .tdd_sync_o (),
    .tdd_sync_t (),
    .tx_clk_out_n (tx_clk_out_n),
    .tx_clk_out_p (tx_clk_out_p),
    .tx_data_out_n (tx_data_out_n),
    .tx_data_out_p (tx_data_out_p),
    .tx_frame_out_n (tx_frame_out_n),
    .tx_frame_out_p (tx_frame_out_p),
    .txnrx (txnrx),
    .up_enable (gpio_o[47]),
    .up_txnrx (gpio_o[48]));



endmodule

// ***************************************************************************
// ***************************************************************************
