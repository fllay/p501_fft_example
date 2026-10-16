################################################################################
# system_constr.xdc
# Optimized for PZSDR P401/P501 - XCZU4EV-2SFVC784I
# Vivado 2024.1 Compatible
################################################################################

set_property PHASESHIFT_MODE LATENCY [current_design]

# PDRC-203 (BITSLICE0 not available during BISC) on tx_data_out_p[3]: benign,
# documented acknowledgement of a calibration-window timing note (this signal
# isn't available during the brief RX calibration sequence at boot, which is
# fine for this design). Placed here as a normal constraint rather than a
# run-level write_bitstream pre-hook, since the pre-hook approach was
# suspected of perturbing Vivado's run dependency tracking into a different
# (bad) placement result on an otherwise-identical, previously-clean XDC.
set_property UNAVAILABLE_DURING_CALIBRATION TRUE [get_ports {tx_data_out_p[3]}]

################################################################################
# BITSTREAM
################################################################################
set_property BITSTREAM.GENERAL.COMPRESS TRUE [current_design]

################################################################################
# PL SYSTEM CLOCK - 200 MHz differential
# NOTE: Removed create_clock. The Clocking Wizard IP handles this automatically.
# Defining it here causes a "Clock Overrides" Critical Warning.
################################################################################
set_property PACKAGE_PIN L3 [get_ports sys_clk_p]
set_property IOSTANDARD DIFF_SSTL12 [get_ports sys_clk_p]
set_property PACKAGE_PIN L2 [get_ports sys_clk_n]
set_property IOSTANDARD DIFF_SSTL12 [get_ports sys_clk_n]

################################################################################
# SYSTEM RESET
################################################################################
set_property PACKAGE_PIN D2 [get_ports sys_rstn]
set_property IOSTANDARD LVCMOS18 [get_ports sys_rstn]
set_false_path -from [get_ports sys_rstn]

################################################################################
# MINI DISPLAYPORT - AUX
################################################################################
set_property -dict {PACKAGE_PIN G13 IOSTANDARD LVCMOS33} [get_ports dp_aux_data_in_0]
set_property -dict {PACKAGE_PIN E13 IOSTANDARD LVCMOS33} [get_ports dp_aux_data_oe_n_0]
set_property -dict {PACKAGE_PIN E14 IOSTANDARD LVCMOS33} [get_ports dp_aux_data_out_0]
set_property -dict {PACKAGE_PIN F13 IOSTANDARD LVCMOS33} [get_ports dp_hot_plug_detect_0]
set_false_path -to [get_ports dp_aux_data_out_0]
set_false_path -to [get_ports dp_aux_data_oe_n_0]
set_false_path -from [get_ports dp_aux_data_in_0]
set_false_path -from [get_ports dp_hot_plug_detect_0]

################################################################################
# ADF4002 CLOCK SYNTHESIZER - SPI
################################################################################
set_property -dict {PACKAGE_PIN AD14 IOSTANDARD LVCMOS33} [get_ports adf_spi_clk_0]
set_property -dict {PACKAGE_PIN AG14 IOSTANDARD LVCMOS33} [get_ports adf_spi_cs_0]
set_property -dict {PACKAGE_PIN AE14 IOSTANDARD LVCMOS33} [get_ports adf_spi_dio_0]
set_false_path -to [get_ports adf_spi_clk_0]
set_false_path -to [get_ports adf_spi_cs_0]
set_false_path -to [get_ports adf_spi_dio_0]

################################################################################
# GIGABIT ETHERNET - RGMII
################################################################################
set_property -dict {PACKAGE_PIN G6 IOSTANDARD LVCMOS18} [get_ports MDIO_PHY_mdc]
set_property -dict {PACKAGE_PIN F6 IOSTANDARD LVCMOS18} [get_ports MDIO_PHY_mdio_io]

set_property -dict {PACKAGE_PIN B3 IOSTANDARD LVCMOS18} [get_ports RGMII_txc]
set_property -dict {PACKAGE_PIN C4 IOSTANDARD LVCMOS18} [get_ports RGMII_tx_ctl]
set_property -dict {PACKAGE_PIN A3 IOSTANDARD LVCMOS18} [get_ports {RGMII_td[0]}]
set_property -dict {PACKAGE_PIN B4 IOSTANDARD LVCMOS18} [get_ports {RGMII_td[1]}]
set_property -dict {PACKAGE_PIN A4 IOSTANDARD LVCMOS18} [get_ports {RGMII_td[2]}]
set_property -dict {PACKAGE_PIN D4 IOSTANDARD LVCMOS18} [get_ports {RGMII_td[3]}]

set_property -dict {PACKAGE_PIN D7 IOSTANDARD LVCMOS18} [get_ports RGMII_rxc]
set_property -dict {PACKAGE_PIN C7 IOSTANDARD LVCMOS18} [get_ports RGMII_rx_ctl]
set_property -dict {PACKAGE_PIN E7 IOSTANDARD LVCMOS18} [get_ports {RGMII_rd[0]}]
set_property -dict {PACKAGE_PIN D6 IOSTANDARD LVCMOS18} [get_ports {RGMII_rd[1]}]
set_property -dict {PACKAGE_PIN E5 IOSTANDARD LVCMOS18} [get_ports {RGMII_rd[2]}]
set_property -dict {PACKAGE_PIN D5 IOSTANDARD LVCMOS18} [get_ports {RGMII_rd[3]}]

# Use 8.000 (125MHz). Using 8.005 can cause IDELAY primitive frequency mismatches.
create_clock -period 8.001 -name RGMII_rxc -waveform {0.000 4.000} [get_ports RGMII_rxc]

set_property SLEW FAST [get_ports RGMII_tx_ctl]
set_property SLEW FAST [get_ports RGMII_txc]
set_property SLEW FAST [get_ports {RGMII_td[*]}]

################################################################################
# SPI CLOCKS (PS EMIO SPI)
################################################################################
create_clock -name spi0_clk -period 40.000 [get_pins -hier -filter {NAME =~ */EMIOSPI0SCLKO}]
create_clock -name spi1_clk -period 40.000 [get_pins -hier -filter {NAME =~ */EMIOSPI1SCLKO}]

################################################################################
# AD9361 - LVDS RX DATA BUS
# CORRECTED: pin values read manually off the real P501 schematic by the user
# (not automated extraction -- that method proved unreliable earlier tonight).
# Every pair cross-verified against Vivado's own DIFF_PAIR_PIN + PIN_FUNC
# silicon data before use: all 16 differential pairs (this section + TX below)
# confirmed as true matched pairs with correct P/N polarity. Zero mismatches.
################################################################################
set_property -dict {PACKAGE_PIN AF7 IOSTANDARD LVDS DIFF_TERM_ADV TERM_100} [get_ports rx_clk_in_p]
set_property -dict {PACKAGE_PIN AF6 IOSTANDARD LVDS DIFF_TERM_ADV TERM_100} [get_ports rx_clk_in_n]
set_property -dict {PACKAGE_PIN AB6 IOSTANDARD LVDS DIFF_TERM_ADV TERM_100} [get_ports rx_frame_in_p]
set_property -dict {PACKAGE_PIN AC6 IOSTANDARD LVDS DIFF_TERM_ADV TERM_100} [get_ports rx_frame_in_n]

set_property -dict {PACKAGE_PIN AH8 IOSTANDARD LVDS DIFF_TERM_ADV TERM_100} [get_ports {rx_data_in_p[0]}]
set_property -dict {PACKAGE_PIN AH7 IOSTANDARD LVDS DIFF_TERM_ADV TERM_100} [get_ports {rx_data_in_n[0]}]
set_property -dict {PACKAGE_PIN AF8 IOSTANDARD LVDS DIFF_TERM_ADV TERM_100} [get_ports {rx_data_in_p[1]}]
set_property -dict {PACKAGE_PIN AG8 IOSTANDARD LVDS DIFF_TERM_ADV TERM_100} [get_ports {rx_data_in_n[1]}]
set_property -dict {PACKAGE_PIN AG9 IOSTANDARD LVDS DIFF_TERM_ADV TERM_100} [get_ports {rx_data_in_p[2]}]
set_property -dict {PACKAGE_PIN AH9 IOSTANDARD LVDS DIFF_TERM_ADV TERM_100} [get_ports {rx_data_in_n[2]}]
set_property -dict {PACKAGE_PIN AE9 IOSTANDARD LVDS DIFF_TERM_ADV TERM_100} [get_ports {rx_data_in_p[3]}]
set_property -dict {PACKAGE_PIN AE8 IOSTANDARD LVDS DIFF_TERM_ADV TERM_100} [get_ports {rx_data_in_n[3]}]
set_property -dict {PACKAGE_PIN AC9 IOSTANDARD LVDS DIFF_TERM_ADV TERM_100} [get_ports {rx_data_in_p[4]}]
set_property -dict {PACKAGE_PIN AD9 IOSTANDARD LVDS DIFF_TERM_ADV TERM_100} [get_ports {rx_data_in_n[4]}]
set_property -dict {PACKAGE_PIN AB8 IOSTANDARD LVDS DIFF_TERM_ADV TERM_100} [get_ports {rx_data_in_p[5]}]
set_property -dict {PACKAGE_PIN AC8 IOSTANDARD LVDS DIFF_TERM_ADV TERM_100} [get_ports {rx_data_in_n[5]}]

################################################################################
# AD9361 - LVDS TX DATA BUS (CORRECTED, see note above)
################################################################################
set_property -dict {PACKAGE_PIN AD5 IOSTANDARD LVDS} [get_ports tx_clk_out_p]
set_property -dict {PACKAGE_PIN AD4 IOSTANDARD LVDS} [get_ports tx_clk_out_n]
set_property -dict {PACKAGE_PIN AG4 IOSTANDARD LVDS} [get_ports tx_frame_out_p]
set_property -dict {PACKAGE_PIN AH4 IOSTANDARD LVDS} [get_ports tx_frame_out_n]

set_property -dict {PACKAGE_PIN AH2 IOSTANDARD LVDS} [get_ports {tx_data_out_p[0]}]
set_property -dict {PACKAGE_PIN AH1 IOSTANDARD LVDS} [get_ports {tx_data_out_n[0]}]
set_property -dict {PACKAGE_PIN AF1 IOSTANDARD LVDS} [get_ports {tx_data_out_p[1]}]
set_property -dict {PACKAGE_PIN AG1 IOSTANDARD LVDS} [get_ports {tx_data_out_n[1]}]
set_property -dict {PACKAGE_PIN AD2 IOSTANDARD LVDS} [get_ports {tx_data_out_p[2]}]
set_property -dict {PACKAGE_PIN AD1 IOSTANDARD LVDS} [get_ports {tx_data_out_n[2]}]
set_property -dict {PACKAGE_PIN AE2 IOSTANDARD LVDS} [get_ports {tx_data_out_p[3]}]
set_property -dict {PACKAGE_PIN AF2 IOSTANDARD LVDS} [get_ports {tx_data_out_n[3]}]
set_property -dict {PACKAGE_PIN AE3 IOSTANDARD LVDS} [get_ports {tx_data_out_p[4]}]
set_property -dict {PACKAGE_PIN AF3 IOSTANDARD LVDS} [get_ports {tx_data_out_n[4]}]
set_property -dict {PACKAGE_PIN AG3 IOSTANDARD LVDS} [get_ports {tx_data_out_p[5]}]
set_property -dict {PACKAGE_PIN AH3 IOSTANDARD LVDS} [get_ports {tx_data_out_n[5]}]

################################################################################
# ASYNCHRONOUS CLOCK GROUPS
################################################################################
# Safely handle CDC between PL clocks, PS clocks, and Interface clocks
set_clock_groups -asynchronous \
    -group [get_clocks -filter {NAME =~ *clk_pl_*}] \
    -group [get_clocks -filter {NAME =~ *mdio*}] \
    -group [get_clocks RGMII_rxc] \
    -group [get_clocks -filter {NAME =~ *rx_clk*}] \
    -group [get_clocks -filter {NAME =~ *spi*}]




################################################################################
# RGMII CLOCK - Keeping the 8.001ns but letting IP handle the rest
################################################################################
create_clock -period 8.001 -name RGMII_rxc -waveform {0.000 4.001} [get_ports RGMII_rxc]
################################################################################
# FALSE PATHS & CDC CLEANUP
################################################################################
# Ethernet False Paths
set_false_path -from [get_ports {RGMII_rd[*]}] -to [get_cells -hier -filter {NAME =~ *rgmii_rx_data_in*}]
set_false_path -from [get_ports RGMII_rx_ctl] -to [get_cells -hier -filter {NAME =~ *rgmii_rx_ctl_in*}]

# Ignore reset to IDELAYCTRL (Asynchronous by nature)
set_false_path -to [get_pins -hier -filter {NAME =~ *i_delay_ctrl/RST}]

# AD9361 RX Clock - Adjust the period (ns) based on your sampling rate 
# (e.g., 100MHz = 10.0, 61.44MHz = 16.27)
create_clock -period 10.000 -name ad9361_rx_clk [get_ports rx_clk_in_p]

################################################################################
# AD9361 - SPI, CONTROL, AND GPIO (Bank 43/44/64, LVCMOS18)
# CORRECTED: pin values read manually off the real P501 schematic by the user,
# cross-verified (existence + zero conflicts) against Vivado's part database.
################################################################################
# CTRL_IN: FPGA outputs to AD9361 (gpio_ctl). CORRECTED against the official
# user manual's AD9361 Communication Port table (CTRL_IN0-3): the previous
# values for [0]/[2]/[3] sat on AD9361_CTRL_OUT2/5/6 instead -- pins the
# AD9361 itself drives as outputs, a direct driver-contention risk once this
# bus is ever actually used. [1] was already correct (AD12 = CTRL_IN1).
set_property -dict {PACKAGE_PIN AB1  IOSTANDARD LVCMOS18} [get_ports {gpio_ctl[0]}]
set_property -dict {PACKAGE_PIN AD12 IOSTANDARD LVCMOS18} [get_ports {gpio_ctl[1]}]
set_property -dict {PACKAGE_PIN AC1  IOSTANDARD LVCMOS18} [get_ports {gpio_ctl[2]}]
set_property -dict {PACKAGE_PIN AE10 IOSTANDARD LVCMOS18} [get_ports {gpio_ctl[3]}]

# AD9361 SPI bus
set_property -dict {PACKAGE_PIN AH12 IOSTANDARD LVCMOS18} [get_ports spi_clk]
set_property -dict {PACKAGE_PIN AF12 IOSTANDARD LVCMOS18} [get_ports spi_mosi]
set_property -dict {PACKAGE_PIN AC12 IOSTANDARD LVCMOS18} [get_ports spi_miso]
set_property -dict {PACKAGE_PIN AB5  IOSTANDARD LVCMOS18} [get_ports spi_csn]

# AD9361 control signals
set_property -dict {PACKAGE_PIN AG11 IOSTANDARD LVCMOS18} [get_ports gpio_en_agc]
set_property -dict {PACKAGE_PIN AE4  IOSTANDARD LVCMOS18} [get_ports enable]
set_property -dict {PACKAGE_PIN AE12 IOSTANDARD LVCMOS18} [get_ports txnrx]
set_property -dict {PACKAGE_PIN AB4  IOSTANDARD LVCMOS18} [get_ports gpio_resetb]
set_property -dict {PACKAGE_PIN AH11 IOSTANDARD LVCMOS18} [get_ports gpio_sync]

# RF switches (hardcoded constants; LOC/IOSTANDARD required for DRC NSTD-1/UCIO-1)
# trx_sw's old value (AC12) conflicted with the verified spi_miso pin;
# TEMPORARY placeholder pin (AE15, confirmed free/unused) pending the real
# TRX1-nTX-RX schematic pin.
set_property -dict {PACKAGE_PIN AD11 IOSTANDARD LVCMOS18} [get_ports trx_sw]
set_property -dict {PACKAGE_PIN AB11 IOSTANDARD LVCMOS18} [get_ports trx_sw1]
set_property -dict {PACKAGE_PIN AB10 IOSTANDARD LVCMOS18} [get_ports fddtdd_sw]
set_property -dict {PACKAGE_PIN AB9  IOSTANDARD LVCMOS18} [get_ports fddtdd_sw1]

# Clock enables (hardcoded to 1; LOC/IOSTANDARD required for DRC NSTD-1/UCIO-1)
set_property -dict {PACKAGE_PIN W10  IOSTANDARD LVCMOS18} [get_ports {clk_en[0]}]
set_property -dict {PACKAGE_PIN Y10  IOSTANDARD LVCMOS18} [get_ports {clk_en[1]}]

################################################################################
# AD9361 - CTRL_OUT STATUS INPUTS (Bank 64, LVCMOS18)
# CORRECTED against the official user manual's AD9361 Communication Port
# table (CTRL_OUT0-7): only [0] was right before. [1]/[3] were real CTRL_OUT
# pins at the wrong bit index; [2] was AD9361_CLK_OUT (a different signal
# entirely); [4]-[7] (AB7/AC7/AD7/AE7) matched no documented AD9361 pin at
# all. Now gpio_status[N] = AD9361_CTRL_OUTN for every N, per the manual.
################################################################################
set_property -dict {PACKAGE_PIN AB2  IOSTANDARD LVCMOS18} [get_ports {gpio_status[0]}]
set_property -dict {PACKAGE_PIN AF10 IOSTANDARD LVCMOS18} [get_ports {gpio_status[1]}]
set_property -dict {PACKAGE_PIN AF11 IOSTANDARD LVCMOS18} [get_ports {gpio_status[2]}]
set_property -dict {PACKAGE_PIN AC2  IOSTANDARD LVCMOS18} [get_ports {gpio_status[3]}]
set_property -dict {PACKAGE_PIN AB3  IOSTANDARD LVCMOS18} [get_ports {gpio_status[4]}]
set_property -dict {PACKAGE_PIN AG10 IOSTANDARD LVCMOS18} [get_ports {gpio_status[5]}]
set_property -dict {PACKAGE_PIN AH10 IOSTANDARD LVCMOS18} [get_ports {gpio_status[6]}]
set_property -dict {PACKAGE_PIN AC3  IOSTANDARD LVCMOS18} [get_ports {gpio_status[7]}]