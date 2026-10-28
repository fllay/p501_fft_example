# QPSK step 2 - the transmitter (rtl/qpsk_tx.v with rtl/qpsk_rrc_coef.v): PRBS-15 -> differential QPSK -> RRC pulse, one sample per dac_valid.
current_bd_design system

create_bd_cell -type ip -vlnv xilinx.com:ip:util_vector_logic:2.0 qpsk_rstn_inv
set_property -dict [list CONFIG.C_OPERATION {not} CONFIG.C_SIZE {1}] [get_bd_cells qpsk_rstn_inv]
connect_bd_net [get_bd_pins axi_ad9361/rst] [get_bd_pins qpsk_rstn_inv/Op1]

set txmod qpsk_tx
if {[info exists ::p501_qpsk_tx_module]} { set txmod $::p501_qpsk_tx_module }       ;# qpsk_tx_fr: the transmitter with frames (chapter 4e), its configuration comes from the FTW register
create_bd_cell -type module -reference $txmod qpsk_tx
connect_bd_net [get_bd_pins axi_ad9361/l_clk]        [get_bd_pins qpsk_tx/clk]
connect_bd_net [get_bd_pins qpsk_rstn_inv/Res]       [get_bd_pins qpsk_tx/resetn]
connect_bd_net [get_bd_pins axi_ad9361/dac_valid_i0] [get_bd_pins qpsk_tx/ce]
connect_bd_net [get_bd_pins qpsk_regs/enable]        [get_bd_pins qpsk_tx/enable]
connect_bd_net [get_bd_pins qpsk_regs/amp]           [get_bd_pins qpsk_tx/amp]
if {$txmod eq "ofdm_tx"} {                                                                          ;# the OFDM transmitter makes its symbols (IFFT) on the AXI clock
  if {[info exists ::p501_ofdm_tx_sts] && $::p501_ofdm_tx_sts} { set_property CONFIG.STS 1 [get_bd_cells qpsk_tx] }
  connect_bd_net [get_bd_pins sys_ps8/pl_clk0]               [get_bd_pins qpsk_tx/fclk]
  connect_bd_net [get_bd_pins sys_rstgen/peripheral_aresetn] [get_bd_pins qpsk_tx/fresetn]
}
if {$txmod eq "qpsk_tx_fr" || $txmod eq "qam16_tx_fr" || $txmod eq "ofdm_tx"} { connect_bd_net [get_bd_pins qpsk_regs/ftw] [get_bd_pins qpsk_tx/cfg] }
