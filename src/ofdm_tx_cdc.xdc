# Clock crossings of rtl/ofdm_tx.v (enable and the two handshake toggles). Add only to a design that contains ofdm_tx.
# Each crosses through a 2-flop synchroniser (first flop = reg[0]); the data of the symbol buffer (a dual-clock RAM) is read only after the synchronised `rdy` event, which comes after the last write.
set_false_path -to [get_cells -hier -filter {NAME =~ *qpsk_tx*/en_s_reg[0] || NAME =~ *qpsk_tx*/rd_s_reg[0] || NAME =~ *qpsk_tx*/fr_s_reg[0] || NAME =~ *ofdm_tx*/en_s_reg[0] || NAME =~ *ofdm_tx*/rd_s_reg[0] || NAME =~ *ofdm_tx*/fr_s_reg[0]}]
