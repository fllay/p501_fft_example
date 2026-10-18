#!/usr/bin/env python3
"""Plot the soft symbols that the FPGA receiver stored in its capture RAM (/tmp/p501_link_soft.npy on the board, copied to the PC): one panel per file.

    python3 plot_soft.py out.png soft1.npy:"label 1" soft2.npy:"label 2" ...        """
import sys
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
out = sys.argv[1]; items = [a.split(":", 1) for a in sys.argv[2:]]
fig, axs = plt.subplots(1, len(items), figsize=(3.6 * len(items), 3.9), squeeze=False)
for ax, (f, label) in zip(axs[0], items):
    zn = np.load(f) / 8192.0                                           # the AGC reference 16384 = amplitude 2.0 (the symbols sit at +-1.4 +-1.4j)
    ang = np.angle(zn * np.exp(-1j * np.pi / 4)); ang = (ang + np.pi / 4) % (np.pi / 2) - np.pi / 4          # angle to the nearest of the four ideal directions
    ax.plot(zn.real, zn.imag, ".", ms=3, alpha=.6); ax.set_aspect("equal"); ax.set_xlim(-2.5, 2.5); ax.set_ylim(-2.5, 2.5); ax.grid(alpha=.3)
    ax.set_title("%s\nangular spread %.1f deg" % (label, np.degrees(np.std(ang))), fontsize=9)
    print("%-28s angular spread %.1f deg, mean |z| %.2f" % (label, np.degrees(np.std(ang)), np.abs(zn).mean()))
fig.suptitle("1024 soft symbols after the Costas loop, read from the FPGA receiver's capture RAM", fontsize=9); fig.tight_layout(); fig.savefig(out, dpi=110)
