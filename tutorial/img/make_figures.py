#!/usr/bin/env python3
"""Regenerates the figures of the tutorials: python3 make_figures.py (needs rsvg-convert for the PNGs)."""
import subprocess

G = dict(fill="#F1EFE8", stroke="#5F5E5A", t1="#2C2C2A", t2="#444441")     # existing in the base design
T = dict(fill="#E1F5EE", stroke="#0F6E56", t1="#04342C", t2="#085041")     # added by the tutorials


class Fig:
    def __init__(self, w, h):
        self.w, self.h, self.o = w, h, []

    def box(self, x, y, w, h, title, sub, c, dash=False):
        d = ' stroke-dasharray="5 4"' if dash else ''
        self.o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{c["fill"]}" stroke="{c["stroke"]}" stroke-width="1.2"{d}/>')
        self.txt(x + w / 2, y + h / 2 - 9, title, 14, 600, "middle", c["t1"])
        self.txt(x + w / 2, y + h / 2 + 11, sub, 12, 400, "middle", c["t2"])

    def frame(self, x, y, w, h, label, dash=True, lx=None):
        d = ' stroke-dasharray="6 4"' if dash else ''
        self.o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="none" stroke="#B4B2A9" stroke-width="1.2"{d}/>')
        self.txt(x + 12 if lx is None else lx, y + 16, label, 13, 600)

    def arr(self, d):
        self.o.append(f'<path d="{d}" fill="none" stroke="#5F5E5A" stroke-width="1.4" marker-end="url(#a)"/>')

    def txt(self, x, y, s, size=13, weight=600, anchor="start", fill="#2C2C2A"):
        self.o.append(f'<text x="{x}" y="{y}" text-anchor="{anchor}" dominant-baseline="central" font-size="{size}" font-weight="{weight}" fill="{fill}">{s}</text>')

    def legend(self, y, items):
        for x, c, label, dash in items:
            d = ' stroke-dasharray="3 2"' if dash else ''
            self.o.append(f'<rect x="{x}" y="{y - 7}" width="14" height="14" rx="3" fill="{c["fill"]}" stroke="{c["stroke"]}" stroke-width="1"{d}/>')
            self.txt(x + 20, y, label, 12, 400)

    def save(self, name):
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}" '
               f'font-family="Helvetica, Arial, sans-serif">\n<defs><marker id="a" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" '
               f'orient="auto-start-reverse"><path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></marker></defs>\n'
               f'<rect width="{self.w}" height="{self.h}" fill="#FFFFFF"/>\n' + "\n".join(self.o) + "\n</svg>")
        open(name + ".svg", "w").write(svg)
        subprocess.run(["rsvg-convert", "-w", str(self.w * 2), name + ".svg", "-o", name + ".png"], check=True)


def data_paths():
    f = Fig(680, 590)
    W, H = 110, 56
    f.o.append('<rect x="20" y="60" width="110" height="470" rx="8" fill="#FFFFFF" stroke="#5F5E5A" stroke-width="1.2"/>')
    f.txt(75, 285, "PS + DDR", 14, 600, "middle"); f.txt(75, 305, "PYNQ, Python", 12, 400, "middle", "#444441")
    f.o.append('<rect x="548" y="60" width="112" height="470" rx="8" fill="#FFFFFF" stroke="#5F5E5A" stroke-width="1.2"/>')
    f.txt(604, 285, "axi_ad9361", 14, 600, "middle"); f.txt(604, 305, "AD9361 core", 12, 400, "middle", "#444441")
    f.txt(148, 40, "TX: DAC path (TX1 source: DMA in the base overlay, DDS in the DDS overlay)")
    f.box(148, 70, W, H, "dac_dma", "DDR to stream", G); f.box(276, 70, W, H, "upack + fifo", "to l_clk", G)
    for d in ("M130 98 L146 98", "M258 98 L274 98", "M386 98 L546 98"): f.arr(d)
    f.txt(466, 84, "base overlay", 12, 400, "middle", "#444441")
    f.box(148, 150, W, H, "dds_regs", "freq, amp, enable", T); f.box(276, 150, W, H, "DDS Compiler", "sin / cos", T)
    f.box(404, 150, W, H, "dds_out", "scale, enable", T)
    for d in ("M130 178 L146 178", "M258 178 L274 178", "M386 178 L402 178", "M514 178 L546 178"): f.arr(d)
    f.txt(466, 224, "DDS overlay", 12, 400, "middle", "#444441")
    f.o.append('<line x1="148" y1="266" x2="530" y2="266" stroke="#B4B2A9" stroke-width="1" stroke-dasharray="4 4"/>')
    f.txt(148, 298, "RX: ADC path")
    f.box(404, 330, W, H, "adc fifo", "to DMA clock", G); f.box(276, 330, W, H, "cpack", "channel pack", G)
    f.box(148, 330, W, H, "adc_dma", "raw to DDR", G)
    for d in ("M546 358 L516 358", "M402 358 L388 358", "M274 358 L260 358", "M146 358 L132 358"): f.arr(d)
    f.box(404, 410, W, H, "FIR / decim", "next step", T, True); f.box(276, 410, W, H, "FFT chain", "FFT tutorial", T)
    f.box(148, 410, W, H, "fft_dma", "power to DDR", T)
    for d in ("M546 438 L516 438", "M402 438 L388 438", "M274 438 L260 438", "M146 438 L132 438"): f.arr(d)
    f.legend(553, [(148, G, "in the base design", False), (322, T, "added in the tutorials", False), (490, T, "next step", True)])
    f.save("data_paths")


def fft_chain():
    f = Fig(680, 330)
    W, H = 116, 56
    xs = [30 + i * 128 for i in range(5)]
    f.frame(16, 28, 648, 108, "base design (already there)")
    names = [("axi_ad9361", "AD9361 core"), ("adc fifo", "clock crossing"), ("cpack", "channel pack"), ("adc_dma", "raw to DDR")]
    for i, (a, b) in enumerate(names):
        f.box(xs[i], 56, W, H, a, b, G)
        if i: f.arr(f"M{xs[i-1]+W} 84 L{xs[i]-2} 84")
    f.frame(16, 168, 648, 130, "what you add (l_clk domain until the DMA)", dash=False, lx=140)
    chain = [("fft_framer", "TLAST every N"), ("fft_core", "Xilinx FFT"), ("fft_power", "|X|^2, frame gate"),
             ("fft_fifo", "2 frames"), ("fft_dma", "AXI-S to DDR")]
    for i, (a, b) in enumerate(chain):
        f.box(xs[i], 204, W, H, a, b, T)
        if i: f.arr(f"M{xs[i-1]+W} 232 L{xs[i]-2} 232")
    # tap from axi_ad9361 down to fft_framer
    f.arr(f"M{xs[0]+W/2} 112 L{xs[0]+W/2} 202")
    f.txt(xs[0] + W / 2 + 10, 160, "adc_data_i0/q0, valid, l_clk", 11, 400, "start", "#444441")
    f.txt(xs[4] + W / 2, 276, "to DDR (HPC0)", 11, 400, "middle", "#444441")
    f.legend(318, [(30, G, "in the base design", False), (200, T, "added in this tutorial", False)])
    f.save("fft_chain")


def dds_fft():
    f = Fig(800, 340)
    W, H = 108, 56
    f.o.append('<rect x="20" y="50" width="90" height="250" rx="8" fill="#F1EFE8" stroke="#5F5E5A" stroke-width="1.2"/>')
    f.txt(65, 175, "PS", 14, 600, "middle"); f.txt(65, 195, "Python", 12, 400, "middle", "#444441")
    f.o.append('<rect x="626" y="50" width="110" height="250" rx="8" fill="#F1EFE8" stroke="#5F5E5A" stroke-width="1.2"/>')
    f.txt(681, 160, "axi_ad9361", 14, 600, "middle"); f.txt(681, 180, "AD9361 core", 12, 400, "middle", "#444441")
    f.txt(642, 98, "TX1", 12, 600, "start", "#444441"); f.txt(642, 228, "RX1", 12, 600, "start", "#444441")
    f.txt(128, 40, "TX: DDS tutorial"); f.txt(128, 170, "RX: FFT tutorial")
    f.box(128, 70, W, H, "dds_regs", "freq, amp, enable", T); f.box(252, 70, W, H, "DDS Compiler", "sin / cos", T); f.box(376, 70, W, H, "dds_out", "scale, enable", T)
    for d in ("M110 98 L126 98", "M236 98 L250 98", "M360 98 L374 98", "M484 98 L624 98"): f.arr(d)
    f.box(500, 200, W, H, "fft_framer", "TLAST every N", T); f.box(376, 200, W, H, "fft_core", "Xilinx FFT", T)
    f.box(252, 200, W, H, "fft_power", "|X|^2, frame gate", T); f.box(128, 200, W, H, "fft_fifo + dma", "spectra to DDR", T)
    for d in ("M624 228 L610 228", "M498 228 L486 228", "M374 228 L362 228", "M250 228 L238 228", "M126 228 L112 228"): f.arr(d)
    f.arr("M736 98 L772 98 L772 228 L738 228")
    f.txt(754, 163, "air or", 11, 400, "middle", "#444441"); f.txt(754, 177, "cable", 11, 400, "middle", "#444441")
    f.txt(128, 284, "No sample passes through Python: it sets the frequency and reads the spectra.", 12, 400, "start", "#444441")
    f.legend(324, [(128, T, "blocks you add (tutorials 1 and 2)", False), (420, G, "base design", False)])
    f.save("dds_fft")


if __name__ == "__main__":
    data_paths()
    fft_chain()
    dds_fft()
