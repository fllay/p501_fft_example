#!/usr/bin/env python3
"""Make a Vivado-exported P501 hardware handoff (.hwh) loadable by PYNQ.

PYNQ's metadata parser (pynqmetadata) rejects two things that Vivado emits for
this design. Neither affects the real hardware; they only confuse PYNQ's
Python-side connectivity model:

 1. Orphan connections: the VCC_1 constant net lists the tie-offs
    sys_ps8/saxigp{0,1}_a{r,w}user, which sys_ps8 never declares as ports
    -> MetadataObjectNotFound.
 2. MDIO between sys_ps8 (emio_enet1_mdio_{i,o}) and gmii_to_rgmii_0
    (mdio_gem_{i,o}): both ends look like drivers to the polarity check
    -> WrongPolarityConnection. (Ethernet MDIO is handled by the Linux MAC
    driver, not by PYNQ, so dropping it from the model is harmless.)

usage: fix_hwh.py in.hwh [out.hwh]      (in place if out is omitted; idempotent)
"""
import re
import sys

ORPHANS = re.compile(r'<CONNECTION INSTANCE="sys_ps8" PORT="saxigp[01]_a[rw]user"\s*/>')
# cross-module MDIO connections, removed only inside the *other* module's section
# (the top-level external-port connections to sys_ps8 must stay)
MDIO_IN_GMII = re.compile(r'<CONNECTION INSTANCE="sys_ps8" PORT="emio_enet1_mdio_[io]"\s*/>')
MDIO_IN_PS8 = re.compile(r'<CONNECTION INSTANCE="gmii_to_rgmii_0" PORT="mdio_gem_[io]"\s*/>')
MODULE = re.compile(r'<MODULE\b[^>]*\bINSTANCE="([^"]+)"')


def main():
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else src
    out, n_orphan, n_mdio, inst = [], 0, 0, None
    for line in open(src, encoding="utf-8"):
        m = MODULE.search(line)
        if m:
            inst = m.group(1)
        elif "</MODULE>" in line:
            inst = None
        if ORPHANS.search(line):
            n_orphan += 1
        elif (inst == "gmii_to_rgmii_0" and MDIO_IN_GMII.search(line)) or \
             (inst == "sys_ps8" and MDIO_IN_PS8.search(line)):
            n_mdio += 1
        else:
            out.append(line)
    open(dst, "w", encoding="utf-8").writelines(out)
    print(f"{dst}: removed {n_orphan} orphan sys_ps8 tie-offs, {n_mdio} MDIO cross connections")


if __name__ == "__main__":
    main()
