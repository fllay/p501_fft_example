# Clock crossings of rtl/ofdm_rx.v (l_clk -> the 100 MHz engine clock). Add only to a design that contains ofdm_rx.
# 1. the Gray-coded sample counter: one bit changes per count, the two-flop synchroniser takes care of the rest
set_false_path -to [get_cells -hier -filter {NAME =~ *ofdm_rx*/g_s1_reg[*]}]
# 2. the two sample RAMs: written on l_clk, read on the engine clock only for samples that the (synchronised) counter says are complete
set_false_path -from [get_cells -hier -filter {NAME =~ *ofdm_rx*/sram_s_reg*}] -to [get_cells -hier -filter {NAME =~ *ofdm_rx*/ss_q_reg[*]}]
set_false_path -from [get_cells -hier -filter {NAME =~ *ofdm_rx*/sram_w_reg*}] -to [get_cells -hier -filter {NAME =~ *ofdm_rx*/sw_q_reg[*]}]
