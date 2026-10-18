# QPSK step 3 - the transmitter replaces the DAC DMA path for TX1 (I0/Q0), as the DDS does in tutorial 2 (the two cannot be in one design).
current_bd_design system

delete_bd_objs [get_bd_nets -of_objects [get_bd_pins axi_ad9361/dac_data_i0]] \
               [get_bd_nets -of_objects [get_bd_pins axi_ad9361/dac_data_q0]]
connect_bd_net [get_bd_pins qpsk_tx/dac_i] [get_bd_pins axi_ad9361/dac_data_i0]
connect_bd_net [get_bd_pins qpsk_tx/dac_q] [get_bd_pins axi_ad9361/dac_data_q0]
