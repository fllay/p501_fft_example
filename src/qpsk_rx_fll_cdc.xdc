# Clock crossings of rtl/qpsk_rx_fll.v (l_clk -> the 100 MHz engine clock). Add only to a design that contains qpsk_rx_fll.
# 1. the Gray-coded sample counter: one bit changes per count, the two-flop synchroniser takes care of the rest
set_false_path -to [get_cells -hier -filter {NAME =~ *qpsk_rx*/g_s1_reg[*]}]
# 2. the raw sample RAM: written on l_clk, read on the engine clock (by the FLL stage) only for samples that the (synchronised) counter says are complete
set_false_path -from [get_cells -hier -filter {NAME =~ *qpsk_rx*/sram_reg*}] -to [get_cells -hier -filter {NAME =~ *qpsk_rx*/raw_word_reg[*]}]
