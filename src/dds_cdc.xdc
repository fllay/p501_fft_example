# DDS parameter hand-over (rtl/dds_regs.v): the AXI-clock registers are only read by the sample-clock
# side after a synchronised toggle, i.e. long after they stopped changing -> not a timed path.
# Add this file only to a design that contains dds_regs (tutorial/dds_steps/step4_constraints.tcl).
set_false_path -from [get_cells -hier -filter {NAME =~ *dds_regs*/ctrl_a_reg* || NAME =~ *dds_regs*/ftw_a_reg* || NAME =~ *dds_regs*/amp_a_reg*}] \
               -to   [get_cells -hier -filter {NAME =~ *dds_regs*/ftw_reg* || NAME =~ *dds_regs*/amp_reg* || NAME =~ *dds_regs*/enable_reg*}]
# the two toggle synchronisers (first flop of each 2-flop chain)
set_false_path -to [get_cells -hier -filter {NAME =~ *dds_regs*/commit_sync_reg[0] || NAME =~ *dds_regs*/ack_sync_reg[0]}]
