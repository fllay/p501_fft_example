import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = "/tmp/claude-0/-home-claude/164b9041-6620-56fd-b7f7-17496c21d4ff/scratchpad/fft4_fll_block_diagram.png"
fig, ax = plt.subplots(figsize=(12, 9))
ax.set_xlim(0, 1200); ax.set_ylim(900, 0); ax.axis("off")
FS = 12


def box(x, y, w, h, text, fc, ec, fs=FS):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=14", fc=fc, ec=ec, lw=1.8))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color="#1e1e1e", linespacing=1.35)


def arrow(pts, color="#1e1e1e", start_dot=False):
    xs, ys = zip(*pts)
    if len(pts) > 2:
        ax.plot(xs[:-1], ys[:-1], color=color, lw=1.8, solid_capstyle="butt")
    ax.annotate("", xy=pts[-1], xytext=pts[-2], arrowprops=dict(arrowstyle="-|>", color=color, lw=1.8, shrinkA=0, shrinkB=0, mutation_scale=16))
    if len(pts) == 2:
        ax.plot(xs, ys, color=color, lw=1.8, solid_capstyle="butt", zorder=1)
    if start_dot:
        ax.plot([pts[0][0]], [pts[0][1]], "o", color=color, ms=6)


# zone
ax.add_patch(FancyBboxPatch((20, 100), 1160, 780, boxstyle="round,pad=0,rounding_size=18", fc="#e5dbff", ec="#8b5cf6", lw=1.2, alpha=0.35))
ax.text(40, 112, "FFT-of-4th-power FLL", fontsize=16, color="#5b21b6", va="top", fontweight="bold")
ax.text(40, 146, "one embedded Python block", fontsize=FS, color="#5b21b6", va="top", linespacing=1.3)

# top path
box(560, 10, 250, 70, "pfb_clock_sync_ccf\n1 sps, before Costas", "#a5d8ff", "#4a9eed")
arrow([(685, 80), (685, 200)])
box(550, 200, 270, 80, "Derotate\ny = x * e^(-j*theta)", "#d0bfff", "#8b5cf6")
box(40, 205, 260, 70, "NCO state\nphi, omega", "#c3fae8", "#06b6d4")
arrow([(300, 240), (550, 240)])
ax.text(312, 212, "theta = phi + omega*k", fontsize=FS, color="#374151", va="top")
box(880, 10, 250, 70, "costas_loop_cc", "#b2f2bb", "#22c55e")
arrow([(820, 240), (1005, 240), (1005, 80)])
ax.text(838, 212, "y, 1 sps", fontsize=FS, color="#374151", va="top")
arrow([(900, 240), (900, 430)], start_dot=True)

# estimator chain
box(800, 430, 200, 100, "Collect N symbols\nz = y^4", "#ffd8a8", "#f59e0b")
arrow([(800, 480), (760, 480)])
box(560, 430, 200, 100, "FFT, 4N points\n(zero-padded)\n|S| = abs", "#ffd8a8", "#f59e0b")
arrow([(560, 480), (520, 480)])
box(320, 430, 200, 100, "Peak search +\nparabolic\ninterpolation", "#ffd8a8", "#f59e0b")
arrow([(320, 480), (280, 480)])
box(80, 430, 200, 100, "Gate:\npeak/mean >\nmin_pmr ?", "#fff3bf", "#f59e0b")
arrow([(180, 530), (180, 600)])
ax.text(196, 553, "pass", fontsize=FS, color="#15803d", va="top")
box(80, 600, 200, 100, "f_res = f4 / 4\nomega += mu*2pi*\nf_res / Rs", "#d0bfff", "#8b5cf6", fs=11)
arrow([(80, 650), (50, 650), (50, 275)])
arrow([(280, 650), (360, 650)])
box(360, 600, 260, 100, "f_est [Hz]\n2nd output", "#b2f2bb", "#22c55e")

# notes
notes = [
    ("Per update (every N = 1024 symbols):", "#1e1e1e"),
    ("1. Derotate the block with the current phi, omega; the result y also goes to the Costas loop.", "#374151"),
    ("2. Residual offset on the derotated block: y^4 -> FFT -> peak -> f_res = f4 / 4.", "#374151"),
    ("3. If peak/mean > min_pmr: omega += mu*2*pi*f_res/Rs   (mu = 1 full correction, mu < 1 averages).", "#374151"),
    ("4. If the gate rejects the estimate, omega is unchanged. The next block uses the new omega.", "#374151"),
]
for i, (t, c) in enumerate(notes):
    ax.text(40, 728 + 30 * i, t, fontsize=FS, color=c, va="top")

fig.savefig(OUT, dpi=150, bbox_inches="tight", facecolor="white")
print(OUT)
