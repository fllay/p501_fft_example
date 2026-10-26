#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: B210 receiver: OFDM frames with the 128-sample STS preamble, stock blocks and a pilot equalizer of our own
# Author: p501_fft_example
# Description: Like ofdm_b210_frame_rx_sts_stock.grc, but the stock Frame Equalizer (decision directed channel update, 4.7e-4 symbol errors on a recording of the B210 receiving the P501) is replaced by a block of our own (pilot_eq.py): the channel from the training symbol, the common phase and gain of every symbol from the 4 pilots, no feedback from the decisions.
# GNU Radio version: 3.10.12.0

from PyQt5 import Qt
from gnuradio import qtgui
from PyQt5 import QtCore
from gnuradio import analog
from gnuradio import blocks
from gnuradio import digital
from gnuradio import fft
from gnuradio.fft import window
from gnuradio import filter
from gnuradio import gr
from gnuradio.filter import firdes
import sys
import signal
from PyQt5 import Qt
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import uhd
import time
import ofdm_b210_frame_rx_sts_pilot_counter as counter  # embedded python block
import ofdm_b210_frame_rx_sts_pilot_hdr as hdr  # embedded python block
import ofdm_b210_frame_rx_sts_pilot_pilot_eq as pilot_eq  # embedded python block
import ofdm_b210_frame_rx_sts_pilot_sts_sync as sts_sync  # embedded python block
import sip
import threading



class ofdm_b210_frame_rx_sts_pilot(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "B210 receiver: OFDM frames with the 128-sample STS preamble, stock blocks and a pilot equalizer of our own", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("B210 receiver: OFDM frames with the 128-sample STS preamble, stock blocks and a pilot equalizer of our own")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except BaseException as exc:
            print(f"Qt GUI: Could not set Icon: {str(exc)}", file=sys.stderr)
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("gnuradio/flowgraphs", "ofdm_b210_frame_rx_sts_pilot")

        try:
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except BaseException as exc:
            print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Variables
        ##################################################
        self.pilot_polarity = pilot_polarity = [-1, -1, -1, -1, -1, -1, -1, 1, 1, 1, 1, 1, 1, -1, 1, 1, 1, 1, 1, -1, -1, 1, 1, 1, 1, -1, 1, -1, 1, 1, 1, -1, -1, -1, -1, 1, 1, -1, 1, 1, 1, -1, 1, -1]
        self.threshold = threshold = 0.65
        self.sync_word = sync_word = [0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, (-0.707106781187+0.707106781187j), (0.707106781187-0.707106781187j), (0.707106781187-0.707106781187j), (-0.707106781187-0.707106781187j), (0.707106781187-0.707106781187j), (0.707106781187-0.707106781187j), (0.707106781187-0.707106781187j), (0.707106781187-0.707106781187j), (-0.707106781187+0.707106781187j), (-0.707106781187-0.707106781187j), (0.707106781187+0.707106781187j), (-0.707106781187+0.707106781187j), (-0.707106781187+0.707106781187j), (-0.707106781187+0.707106781187j), 0j, (-0.707106781187-0.707106781187j), (0.707106781187-0.707106781187j), (-0.707106781187+0.707106781187j), (-0.707106781187-0.707106781187j), (-0.707106781187-0.707106781187j), (-0.707106781187+0.707106781187j), (-0.707106781187+0.707106781187j), (0.707106781187+0.707106781187j), (0.707106781187-0.707106781187j), (-0.707106781187+0.707106781187j), (-0.707106781187-0.707106781187j), (-0.707106781187-0.707106781187j), (0.707106781187+0.707106781187j), (0.707106781187+0.707106781187j), 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j]
        self.sync_delay = sync_delay = 384
        self.samp_rate = samp_rate = 3840000
        self.rx_gain = rx_gain = 45
        self.pilot_symbols = pilot_symbols = tuple(tuple(p * v for v in ((0.707106781187+0.707106781187j), (0.707106781187-0.707106781187j), (-0.707106781187+0.707106781187j), (-0.707106781187-0.707106781187j))) for p in pilot_polarity)
        self.pilot_carriers = pilot_carriers = ([-11, -4, 4, 11],)
        self.payload_mod = payload_mod = digital.constellation_calcdist([((-3, -1, 3, 1)[i >> 2] + 1j * (-3, -1, 3, 1)[i & 3]) / 10 ** 0.5 for i in range(16)], list(range(16)), 4, 1)
        self.occupied_carriers = occupied_carriers = ([-14, -13, -12, -10, -9, -8, -7, -6, -5, -3, -2, -1, 1, 2, 3, 5, 6, 7, 8, 9, 10, 12, 13, 14],)
        self.length_tag_key = length_tag_key = "frame_length"
        self.guard_level = guard_level = 0.1
        self.freq = freq = 850e6
        self.fft_len = fft_len = 64
        self.cp_len = cp_len = 16
        self.check_n = check_n = 8
        self.capture_file = capture_file = "ofdm_b210_capture_sts.c64"

        ##################################################
        # Blocks
        ##################################################

        self._threshold_range = qtgui.Range(0.3, 0.95, 0.01, 0.65, 200)
        self._threshold_win = qtgui.RangeWidget(self._threshold_range, self.set_threshold, "STS detection threshold (metric M)", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._threshold_win, 0, 3, 1, 3)
        for r in range(0, 1):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(3, 6):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.tabs = Qt.QTabWidget()
        self.tabs_widget_0 = Qt.QWidget()
        self.tabs_layout_0 = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom, self.tabs_widget_0)
        self.tabs_grid_layout_0 = Qt.QGridLayout()
        self.tabs_layout_0.addLayout(self.tabs_grid_layout_0)
        self.tabs.addTab(self.tabs_widget_0, '1 Received signal')
        self.tabs_widget_1 = Qt.QWidget()
        self.tabs_layout_1 = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom, self.tabs_widget_1)
        self.tabs_grid_layout_1 = Qt.QGridLayout()
        self.tabs_layout_1.addLayout(self.tabs_grid_layout_1)
        self.tabs.addTab(self.tabs_widget_1, "2 Frame detection (STS)")
        self.tabs_widget_2 = Qt.QWidget()
        self.tabs_layout_2 = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom, self.tabs_widget_2)
        self.tabs_grid_layout_2 = Qt.QGridLayout()
        self.tabs_layout_2.addLayout(self.tabs_grid_layout_2)
        self.tabs.addTab(self.tabs_widget_2, "3 Carrier offset")
        self.tabs_widget_3 = Qt.QWidget()
        self.tabs_layout_3 = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom, self.tabs_widget_3)
        self.tabs_grid_layout_3 = Qt.QGridLayout()
        self.tabs_layout_3.addLayout(self.tabs_grid_layout_3)
        self.tabs.addTab(self.tabs_widget_3, '4 FFT')
        self.tabs_widget_4 = Qt.QWidget()
        self.tabs_layout_4 = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom, self.tabs_widget_4)
        self.tabs_grid_layout_4 = Qt.QGridLayout()
        self.tabs_layout_4.addLayout(self.tabs_grid_layout_4)
        self.tabs.addTab(self.tabs_widget_4, '5 Channel estimate')
        self.tabs_widget_5 = Qt.QWidget()
        self.tabs_layout_5 = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom, self.tabs_widget_5)
        self.tabs_grid_layout_5 = Qt.QGridLayout()
        self.tabs_layout_5.addLayout(self.tabs_grid_layout_5)
        self.tabs.addTab(self.tabs_widget_5, '6 Equalizer and decisions')
        self.top_grid_layout.addWidget(self.tabs, 2, 0, 1, 6)
        for r in range(2, 3):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 6):
            self.top_grid_layout.setColumnStretch(c, 1)
        self._rx_gain_range = qtgui.Range(0, 76, 1, 45, 200)
        self._rx_gain_win = qtgui.RangeWidget(self._rx_gain_range, self.set_rx_gain, "B210 RX gain (dB)", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._rx_gain_win, 0, 0, 1, 3)
        for r in range(0, 1):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 3):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.x_scale = blocks.multiply_const_ff(5)
        self.x_mag2 = blocks.complex_to_mag(1)
        self.x_mag = blocks.complex_to_mag(1)
        self.vec_hmag = qtgui.vector_sink_f(
            64,
            (-32),
            1,
            "subcarrier k",
            "|H|",
            "channel |H[k]| (the unused subcarriers are 0)",
            1, # Number of inputs
            None # parent
        )
        self.vec_hmag.set_update_time(0.1)
        self.vec_hmag.set_y_axis(0, 2)
        self.vec_hmag.enable_autoscale(True)
        self.vec_hmag.enable_grid(True)
        self.vec_hmag.set_x_axis_units("")
        self.vec_hmag.set_y_axis_units("")
        self.vec_hmag.set_ref_level(0)


        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.vec_hmag.set_line_label(i, "Data {0}".format(i))
            else:
                self.vec_hmag.set_line_label(i, labels[i])
            self.vec_hmag.set_line_width(i, widths[i])
            self.vec_hmag.set_line_color(i, colors[i])
            self.vec_hmag.set_line_alpha(i, alphas[i])

        self._vec_hmag_win = sip.wrapinstance(self.vec_hmag.qwidget(), Qt.QWidget)
        self.tabs_grid_layout_4.addWidget(self._vec_hmag_win, 0, 0, 1, 1)
        for r in range(0, 1):
            self.tabs_grid_layout_4.setRowStretch(r, 1)
        for c in range(0, 1):
            self.tabs_grid_layout_4.setColumnStretch(c, 1)
        self.vec_harg = qtgui.vector_sink_f(
            64,
            (-32),
            1,
            "subcarrier k",
            "rad",
            "channel phase arg H[k] (rad): a straight line = a delay (the timing offset and the early FFT window)",
            1, # Number of inputs
            None # parent
        )
        self.vec_harg.set_update_time(0.1)
        self.vec_harg.set_y_axis((-3.2), 3.2)
        self.vec_harg.enable_autoscale(False)
        self.vec_harg.enable_grid(True)
        self.vec_harg.set_x_axis_units("")
        self.vec_harg.set_y_axis_units("")
        self.vec_harg.set_ref_level(0)


        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.vec_harg.set_line_label(i, "Data {0}".format(i))
            else:
                self.vec_harg.set_line_label(i, labels[i])
            self.vec_harg.set_line_width(i, widths[i])
            self.vec_harg.set_line_color(i, colors[i])
            self.vec_harg.set_line_alpha(i, alphas[i])

        self._vec_harg_win = sip.wrapinstance(self.vec_harg.qwidget(), Qt.QWidget)
        self.tabs_grid_layout_4.addWidget(self._vec_harg_win, 1, 0, 1, 1)
        for r in range(1, 2):
            self.tabs_grid_layout_4.setRowStretch(r, 1)
        for c in range(0, 1):
            self.tabs_grid_layout_4.setColumnStretch(c, 1)
        self.vec_fft = qtgui.vector_sink_f(
            64,
            (-32),
            1,
            "subcarrier k",
            "|X[k]|",
            "|FFT| of the OFDM symbols (mean of 64 symbols): subcarrier k = bin - 32",
            1, # Number of inputs
            None # parent
        )
        self.vec_fft.set_update_time(0.1)
        self.vec_fft.set_y_axis(0, 3)
        self.vec_fft.enable_autoscale(False)
        self.vec_fft.enable_grid(True)
        self.vec_fft.set_x_axis_units("")
        self.vec_fft.set_y_axis_units("")
        self.vec_fft.set_ref_level(0)


        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.vec_fft.set_line_label(i, "Data {0}".format(i))
            else:
                self.vec_fft.set_line_label(i, labels[i])
            self.vec_fft.set_line_width(i, widths[i])
            self.vec_fft.set_line_color(i, colors[i])
            self.vec_fft.set_line_alpha(i, alphas[i])

        self._vec_fft_win = sip.wrapinstance(self.vec_fft.qwidget(), Qt.QWidget)
        self.tabs_grid_layout_3.addWidget(self._vec_fft_win, 0, 0, 1, 1)
        for r in range(0, 1):
            self.tabs_grid_layout_3.setRowStretch(r, 1)
        for c in range(0, 1):
            self.tabs_grid_layout_3.setColumnStretch(c, 1)
        self.v2s_soft = blocks.vector_to_stream(gr.sizeof_gr_complex*1, 24)
        self.v2s_dec = blocks.vector_to_stream(gr.sizeof_gr_complex*1, 24)
        self.v2s64 = blocks.vector_to_stream(gr.sizeof_gr_complex*1, 64)
        self.uhd_usrp_source_0 = uhd.usrp_source(
            ",".join(('', 'num_send_frames=128,num_recv_frames=128,send_frame_size=16360,recv_frame_size=16360')),
            uhd.stream_args(
                cpu_format="fc32",
                args='',
                channels=list(range(0,1)),
            ),
        )
        self.uhd_usrp_source_0.set_samp_rate(samp_rate)
        self.uhd_usrp_source_0.set_time_unknown_pps(uhd.time_spec(0))

        self.uhd_usrp_source_0.set_center_freq(freq, 0)
        self.uhd_usrp_source_0.set_antenna('RX2', 0)
        self.uhd_usrp_source_0.set_gain(rx_gain, 0)
        self.trg_sum = blocks.integrate_ff(3840, 1)
        self.time_sink_rx = qtgui.time_sink_f(
            8192, #size
            samp_rate, #samp_rate
            "received signal |x| (two frames of 3840 samples = 1 ms each)", #name
            1, #number of inputs
            None # parent
        )
        self.time_sink_rx.set_update_time(0.1)
        self.time_sink_rx.set_y_axis(0, 1)

        self.time_sink_rx.set_y_label('Amplitude', "")

        self.time_sink_rx.enable_tags(False)
        self.time_sink_rx.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.time_sink_rx.enable_autoscale(True)
        self.time_sink_rx.enable_grid(True)
        self.time_sink_rx.enable_axis_labels(True)
        self.time_sink_rx.enable_control_panel(False)
        self.time_sink_rx.enable_stem_plot(False)

        self.time_sink_rx.disable_legend()

        labels = ['|x|', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'red', 'green', 'black', 'cyan',
            'magenta', 'yellow', 'dark red', 'dark green', 'dark blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(1):
            if len(labels[i]) == 0:
                self.time_sink_rx.set_line_label(i, "Data {0}".format(i))
            else:
                self.time_sink_rx.set_line_label(i, labels[i])
            self.time_sink_rx.set_line_width(i, widths[i])
            self.time_sink_rx.set_line_color(i, colors[i])
            self.time_sink_rx.set_line_style(i, styles[i])
            self.time_sink_rx.set_line_marker(i, markers[i])
            self.time_sink_rx.set_line_alpha(i, alphas[i])

        self._time_sink_rx_win = sip.wrapinstance(self.time_sink_rx.qwidget(), Qt.QWidget)
        self.tabs_grid_layout_0.addWidget(self._time_sink_rx_win, 1, 0, 1, 1)
        for r in range(1, 2):
            self.tabs_grid_layout_0.setRowStretch(r, 1)
        for c in range(0, 1):
            self.tabs_grid_layout_0.setColumnStretch(c, 1)
        self.time_sink_m = qtgui.time_sink_f(
            8192, #size
            samp_rate, #samp_rate
            "STS metric M and the threshold (two frames)", #name
            2, #number of inputs
            None # parent
        )
        self.time_sink_m.set_update_time(0.1)
        self.time_sink_m.set_y_axis(-0.1, 1.1)

        self.time_sink_m.set_y_label('M', "")

        self.time_sink_m.enable_tags(False)
        self.time_sink_m.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.time_sink_m.enable_autoscale(False)
        self.time_sink_m.enable_grid(True)
        self.time_sink_m.enable_axis_labels(True)
        self.time_sink_m.enable_control_panel(False)
        self.time_sink_m.enable_stem_plot(False)

        self.time_sink_m.disable_legend()

        labels = ['M', 'threshold', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'red', 'green', 'black', 'cyan',
            'magenta', 'yellow', 'dark red', 'dark green', 'dark blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(2):
            if len(labels[i]) == 0:
                self.time_sink_m.set_line_label(i, "Data {0}".format(i))
            else:
                self.time_sink_m.set_line_label(i, labels[i])
            self.time_sink_m.set_line_width(i, widths[i])
            self.time_sink_m.set_line_color(i, colors[i])
            self.time_sink_m.set_line_style(i, styles[i])
            self.time_sink_m.set_line_marker(i, markers[i])
            self.time_sink_m.set_line_alpha(i, alphas[i])

        self._time_sink_m_win = sip.wrapinstance(self.time_sink_m.qwidget(), Qt.QWidget)
        self.tabs_grid_layout_1.addWidget(self._time_sink_m_win, 1, 0, 1, 1)
        for r in range(1, 2):
            self.tabs_grid_layout_1.setRowStretch(r, 1)
        for c in range(0, 1):
            self.tabs_grid_layout_1.setColumnStretch(c, 1)
        self.time_sink_det = qtgui.time_sink_f(
            8192, #size
            samp_rate, #samp_rate
            "|x| and the trigger of the STS synchroniser (two frames of 3840 samples = 1 ms each)", #name
            2, #number of inputs
            None # parent
        )
        self.time_sink_det.set_update_time(0.1)
        self.time_sink_det.set_y_axis(-0.1, 1.2)

        self.time_sink_det.set_y_label('', "")

        self.time_sink_det.enable_tags(False)
        self.time_sink_det.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.time_sink_det.enable_autoscale(False)
        self.time_sink_det.enable_grid(True)
        self.time_sink_det.enable_axis_labels(True)
        self.time_sink_det.enable_control_panel(False)
        self.time_sink_det.enable_stem_plot(False)

        self.time_sink_det.disable_legend()

        labels = ['|x| (x 5)', "trigger", 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'red', 'green', 'black', 'cyan',
            'magenta', 'yellow', 'dark red', 'dark green', 'dark blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(2):
            if len(labels[i]) == 0:
                self.time_sink_det.set_line_label(i, "Data {0}".format(i))
            else:
                self.time_sink_det.set_line_label(i, labels[i])
            self.time_sink_det.set_line_width(i, widths[i])
            self.time_sink_det.set_line_color(i, colors[i])
            self.time_sink_det.set_line_style(i, styles[i])
            self.time_sink_det.set_line_marker(i, markers[i])
            self.time_sink_det.set_line_alpha(i, alphas[i])

        self._time_sink_det_win = sip.wrapinstance(self.time_sink_det.qwidget(), Qt.QWidget)
        self.tabs_grid_layout_1.addWidget(self._time_sink_det_win, 0, 0, 1, 1)
        for r in range(0, 1):
            self.tabs_grid_layout_1.setRowStretch(r, 1)
        for c in range(0, 1):
            self.tabs_grid_layout_1.setColumnStretch(c, 1)
        self.time_sink_cfo = qtgui.time_sink_f(
            32768, #size
            samp_rate, #samp_rate
            "carrier offset (Hz) measured for every frame: coarse from the STS, fine from the two training symbols", #name
            1, #number of inputs
            None # parent
        )
        self.time_sink_cfo.set_update_time(0.1)
        self.time_sink_cfo.set_y_axis(-20000, 20000)

        self.time_sink_cfo.set_y_label('Hz', "")

        self.time_sink_cfo.enable_tags(False)
        self.time_sink_cfo.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.time_sink_cfo.enable_autoscale(False)
        self.time_sink_cfo.enable_grid(True)
        self.time_sink_cfo.enable_axis_labels(True)
        self.time_sink_cfo.enable_control_panel(False)
        self.time_sink_cfo.enable_stem_plot(False)

        self.time_sink_cfo.disable_legend()

        labels = ["measured", 'averaged', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'red', 'green', 'black', 'cyan',
            'magenta', 'yellow', 'dark red', 'dark green', 'dark blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(1):
            if len(labels[i]) == 0:
                self.time_sink_cfo.set_line_label(i, "Data {0}".format(i))
            else:
                self.time_sink_cfo.set_line_label(i, labels[i])
            self.time_sink_cfo.set_line_width(i, widths[i])
            self.time_sink_cfo.set_line_color(i, colors[i])
            self.time_sink_cfo.set_line_style(i, styles[i])
            self.time_sink_cfo.set_line_marker(i, markers[i])
            self.time_sink_cfo.set_line_alpha(i, alphas[i])

        self._time_sink_cfo_win = sip.wrapinstance(self.time_sink_cfo.qwidget(), Qt.QWidget)
        self.tabs_grid_layout_2.addWidget(self._time_sink_cfo_win, 0, 0, 1, 1)
        for r in range(0, 1):
            self.tabs_grid_layout_2.setRowStretch(r, 1)
        for c in range(0, 1):
            self.tabs_grid_layout_2.setColumnStretch(c, 1)
        self.thr_src = analog.sig_source_f(0, analog.GR_CONST_WAVE, 0, 0, threshold)
        self.sym_delay = blocks.delay(gr.sizeof_gr_complex*1, sync_delay)
        self.sts_sync = sts_sync.blk(threshold=threshold, delay=sync_delay)
        self.sts_sync.set_min_output_buffer(262144)
        self.sc_mult = blocks.multiply_vcc(1)
        self.sc_mag2 = blocks.complex_to_mag_squared(1)
        self.sc_div = blocks.divide_ff(1)
        self.sc_div.set_min_output_buffer(262144)
        self.sc_delay = blocks.delay(gr.sizeof_gr_complex*1, 16)
        self.sc_conj = blocks.conjugate_cc()
        self.sc_avg = blocks.moving_average_cc(48, 1, 4000, 1)
        self.sc_avg.set_min_output_buffer(262144)
        self.rx_in = blocks.copy(gr.sizeof_gr_complex*1)
        self.rx_in.set_enabled(True)
        self.rot = blocks.multiply_vcc(1)
        self.pilot_eq = pilot_eq.blk(smooth=1, slope=0, frames=16, evm_every=8)
        self.osc = analog.frequency_modulator_fc((-2.0 / fft_len))
        self.number_ser = qtgui.number_sink(
            gr.sizeof_float,
            0.0,
            qtgui.NUM_GRAPH_NONE,
            1,
            None # parent
        )
        self.number_ser.set_update_time(0.25)
        self.number_ser.set_title("symbol error rate (since the start)")

        labels = ['SER', '', '', '', '',
            '', '', '', '', '']
        units = ['', '', '', '', '',
            '', '', '', '', '']
        colors = [("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"),
            ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black")]
        factor = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]

        for i in range(1):
            self.number_ser.set_min(i, 0)
            self.number_ser.set_max(i, 1)
            self.number_ser.set_color(i, colors[i][0], colors[i][1])
            if len(labels[i]) == 0:
                self.number_ser.set_label(i, "Data {0}".format(i))
            else:
                self.number_ser.set_label(i, labels[i])
            self.number_ser.set_unit(i, units[i])
            self.number_ser.set_factor(i, factor[i])

        self.number_ser.enable_autoscale(False)
        self._number_ser_win = sip.wrapinstance(self.number_ser.qwidget(), Qt.QWidget)
        self.tabs_grid_layout_5.addWidget(self._number_ser_win, 2, 0, 1, 1)
        for r in range(2, 3):
            self.tabs_grid_layout_5.setRowStretch(r, 1)
        for c in range(0, 1):
            self.tabs_grid_layout_5.setColumnStretch(c, 1)
        self.number_recent = qtgui.number_sink(
            gr.sizeof_float,
            0.0,
            qtgui.NUM_GRAPH_NONE,
            1,
            None # parent
        )
        self.number_recent.set_update_time(0.25)
        self.number_recent.set_title("symbol error rate, last 2000 checked frames (about 16 s)")

        labels = ['SER now', '', '', '', '',
            '', '', '', '', '']
        units = ['', '', '', '', '',
            '', '', '', '', '']
        colors = [("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"),
            ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black")]
        factor = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]

        for i in range(1):
            self.number_recent.set_min(i, 0)
            self.number_recent.set_max(i, 1)
            self.number_recent.set_color(i, colors[i][0], colors[i][1])
            if len(labels[i]) == 0:
                self.number_recent.set_label(i, "Data {0}".format(i))
            else:
                self.number_recent.set_label(i, labels[i])
            self.number_recent.set_unit(i, units[i])
            self.number_recent.set_factor(i, factor[i])

        self.number_recent.enable_autoscale(False)
        self._number_recent_win = sip.wrapinstance(self.number_recent.qwidget(), Qt.QWidget)
        self.tabs_grid_layout_5.addWidget(self._number_recent_win, 2, 3, 1, 1)
        for r in range(2, 3):
            self.tabs_grid_layout_5.setRowStretch(r, 1)
        for c in range(3, 4):
            self.tabs_grid_layout_5.setColumnStretch(c, 1)
        self.number_frames = qtgui.number_sink(
            gr.sizeof_float,
            0.0,
            qtgui.NUM_GRAPH_NONE,
            1,
            None # parent
        )
        self.number_frames.set_update_time(0.25)
        self.number_frames.set_title("frames checked (1 in check_n)")

        labels = ["frames", '', '', '', '',
            '', '', '', '', '']
        units = ['', '', '', '', '',
            '', '', '', '', '']
        colors = [("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"),
            ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black")]
        factor = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]

        for i in range(1):
            self.number_frames.set_min(i, 0)
            self.number_frames.set_max(i, 1)
            self.number_frames.set_color(i, colors[i][0], colors[i][1])
            if len(labels[i]) == 0:
                self.number_frames.set_label(i, "Data {0}".format(i))
            else:
                self.number_frames.set_label(i, labels[i])
            self.number_frames.set_unit(i, units[i])
            self.number_frames.set_factor(i, factor[i])

        self.number_frames.enable_autoscale(False)
        self._number_frames_win = sip.wrapinstance(self.number_frames.qwidget(), Qt.QWidget)
        self.tabs_grid_layout_5.addWidget(self._number_frames_win, 2, 2, 1, 1)
        for r in range(2, 3):
            self.tabs_grid_layout_5.setRowStretch(r, 1)
        for c in range(2, 3):
            self.tabs_grid_layout_5.setColumnStretch(c, 1)
        self.number_fnd = qtgui.number_sink(
            gr.sizeof_float,
            0.0,
            qtgui.NUM_GRAPH_NONE,
            1,
            None # parent
        )
        self.number_fnd.set_update_time(0.25)
        self.number_fnd.set_title("frames found per frame period (1 = every frame is found)")

        labels = ["found", '', '', '', '',
            '', '', '', '', '']
        units = ['', '', '', '', '',
            '', '', '', '', '']
        colors = [("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"),
            ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black")]
        factor = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]

        for i in range(1):
            self.number_fnd.set_min(i, 0)
            self.number_fnd.set_max(i, 1)
            self.number_fnd.set_color(i, colors[i][0], colors[i][1])
            if len(labels[i]) == 0:
                self.number_fnd.set_label(i, "Data {0}".format(i))
            else:
                self.number_fnd.set_label(i, labels[i])
            self.number_fnd.set_unit(i, units[i])
            self.number_fnd.set_factor(i, factor[i])

        self.number_fnd.enable_autoscale(False)
        self._number_fnd_win = sip.wrapinstance(self.number_fnd.qwidget(), Qt.QWidget)
        self.tabs_grid_layout_2.addWidget(self._number_fnd_win, 1, 0, 1, 1)
        for r in range(1, 2):
            self.tabs_grid_layout_2.setRowStretch(r, 1)
        for c in range(0, 1):
            self.tabs_grid_layout_2.setColumnStretch(c, 1)
        self.number_evm = qtgui.number_sink(
            gr.sizeof_float,
            0.0,
            qtgui.NUM_GRAPH_NONE,
            1,
            None # parent
        )
        self.number_evm.set_update_time(0.25)
        self.number_evm.set_title("EVM against the known payload (dB)")

        labels = ['EVM', '', '', '', '',
            '', '', '', '', '']
        units = ['dB', '', '', '', '',
            '', '', '', '', '']
        colors = [("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"),
            ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black")]
        factor = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]

        for i in range(1):
            self.number_evm.set_min(i, 0)
            self.number_evm.set_max(i, 1)
            self.number_evm.set_color(i, colors[i][0], colors[i][1])
            if len(labels[i]) == 0:
                self.number_evm.set_label(i, "Data {0}".format(i))
            else:
                self.number_evm.set_label(i, labels[i])
            self.number_evm.set_unit(i, units[i])
            self.number_evm.set_factor(i, factor[i])

        self.number_evm.enable_autoscale(False)
        self._number_evm_win = sip.wrapinstance(self.number_evm.qwidget(), Qt.QWidget)
        self.tabs_grid_layout_5.addWidget(self._number_evm_win, 2, 4, 1, 1)
        for r in range(2, 3):
            self.tabs_grid_layout_5.setRowStretch(r, 1)
        for c in range(4, 5):
            self.tabs_grid_layout_5.setColumnStretch(c, 1)
        self.number_err = qtgui.number_sink(
            gr.sizeof_float,
            0.0,
            qtgui.NUM_GRAPH_NONE,
            1,
            None # parent
        )
        self.number_err.set_update_time(0.25)
        self.number_err.set_title("symbol errors")

        labels = ['errors', '', '', '', '',
            '', '', '', '', '']
        units = ['', '', '', '', '',
            '', '', '', '', '']
        colors = [("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"),
            ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black")]
        factor = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]

        for i in range(1):
            self.number_err.set_min(i, 0)
            self.number_err.set_max(i, 1)
            self.number_err.set_color(i, colors[i][0], colors[i][1])
            if len(labels[i]) == 0:
                self.number_err.set_label(i, "Data {0}".format(i))
            else:
                self.number_err.set_label(i, labels[i])
            self.number_err.set_unit(i, units[i])
            self.number_err.set_factor(i, factor[i])

        self.number_err.enable_autoscale(False)
        self._number_err_win = sip.wrapinstance(self.number_err.qwidget(), Qt.QWidget)
        self.tabs_grid_layout_5.addWidget(self._number_err_win, 2, 1, 1, 1)
        for r in range(2, 3):
            self.tabs_grid_layout_5.setRowStretch(r, 1)
        for c in range(1, 2):
            self.tabs_grid_layout_5.setColumnStretch(c, 1)
        self.keep_soft = blocks.keep_one_in_n(gr.sizeof_gr_complex*1, 8)
        self.keep_evm = blocks.keep_one_in_n(gr.sizeof_float*1, 1056)
        self.keep_chk = blocks.keep_m_in_n(gr.sizeof_char, 1056, (1056 * check_n), 0)
        self.keep29 = blocks.keep_m_in_n(gr.sizeof_gr_complex, 29, 64, 18)
        self.hpd = digital.header_payload_demux(
            2,
            fft_len,
            cp_len,
            length_tag_key,
            "",
            True,
            gr.sizeof_gr_complex,
            "",
            samp_rate,
            (),
            0)
        self.hdr = hdr.blk(nsym=44)
        self.h_mag = blocks.complex_to_mag(64)
        self.h_arg = blocks.complex_to_arg(64)
        self.guard_sq = blocks.multiply_vff(1)
        self.guard_k = blocks.multiply_const_ff(((guard_level * 48) ** 2))
        self.guard_avg = filter.single_pole_iir_filter_ff((2.4e-4), 1)
        self.guard_add = blocks.add_vff(1)
        self.freq_sink_rx = qtgui.freq_sink_c(
            2048, #size
            window.WIN_BLACKMAN_hARRIS, #wintype
            0, #fc
            samp_rate, #bw
            "received spectrum (raw): 28 subcarriers of 60 kHz = 1.7 MHz wide; the spike at 0 is the DC / LO leakage", #name
            1,
            None # parent
        )
        self.freq_sink_rx.set_update_time(0.1)
        self.freq_sink_rx.set_y_axis((-120), 0)
        self.freq_sink_rx.set_y_label('Relative Gain', 'dB')
        self.freq_sink_rx.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
        self.freq_sink_rx.enable_autoscale(False)
        self.freq_sink_rx.enable_grid(True)
        self.freq_sink_rx.set_fft_average(0.2)
        self.freq_sink_rx.enable_axis_labels(True)
        self.freq_sink_rx.enable_control_panel(False)
        self.freq_sink_rx.set_fft_window_normalized(False)

        self.freq_sink_rx.disable_legend()


        labels = ['B210 RX2', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.freq_sink_rx.set_line_label(i, "Data {0}".format(i))
            else:
                self.freq_sink_rx.set_line_label(i, labels[i])
            self.freq_sink_rx.set_line_width(i, widths[i])
            self.freq_sink_rx.set_line_color(i, colors[i])
            self.freq_sink_rx.set_line_alpha(i, alphas[i])

        self._freq_sink_rx_win = sip.wrapinstance(self.freq_sink_rx.qwidget(), Qt.QWidget)
        self.tabs_grid_layout_0.addWidget(self._freq_sink_rx_win, 0, 0, 1, 1)
        for r in range(0, 1):
            self.tabs_grid_layout_0.setRowStretch(r, 1)
        for c in range(0, 1):
            self.tabs_grid_layout_0.setColumnStretch(c, 1)
        self.fft_scale = blocks.multiply_const_vcc([1.0 / 8.0] * 64)
        self.fft_pay = fft.fft_vcc(fft_len, True, (), True, 1)
        self.fft_mag = blocks.complex_to_mag(64)
        self.fft_hdr = fft.fft_vcc(fft_len, True, (), True, 1)
        self.fft_avg = blocks.moving_average_ff(64, (1.0 / 64), 4000, 64)
        self.en_mult = blocks.multiply_vff(1)
        self.en_mag2 = blocks.complex_to_mag_squared(1)
        self.en_eps = blocks.add_const_ff((1e-12))
        self.en_delay = blocks.delay(gr.sizeof_float*1, 16)
        self.en_avg = blocks.moving_average_ff(48, 1, 4000, 1)
        self.detect_f = blocks.char_to_float(1, 1)
        self.dec = digital.constellation_decoder_cb(payload_mod.base())
        self.dc_sub = blocks.sub_cc(1)
        self.dc_sub.set_min_output_buffer(262144)
        self.dc_iir = filter.single_pole_iir_filter_cc((1e-4), 1)
        self.counter = counter.blk()
        self.const_soft = qtgui.const_sink_c(
            2048, #size
            "the received data symbols after the equalizer: the spread of the clusters is the noise (the channel is divided out, the pilots remove the phase and gain)", #name
            1, #number of inputs
            None # parent
        )
        self.const_soft.set_update_time(0.1)
        self.const_soft.set_y_axis((-1.6), 1.6)
        self.const_soft.set_x_axis((-1.6), 1.6)
        self.const_soft.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, "")
        self.const_soft.enable_autoscale(False)
        self.const_soft.enable_grid(True)
        self.const_soft.enable_axis_labels(True)

        self.const_soft.disable_legend()

        labels = ['symbols', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        styles = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        markers = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.const_soft.set_line_label(i, "Data {0}".format(i))
            else:
                self.const_soft.set_line_label(i, labels[i])
            self.const_soft.set_line_width(i, widths[i])
            self.const_soft.set_line_color(i, colors[i])
            self.const_soft.set_line_style(i, styles[i])
            self.const_soft.set_line_marker(i, markers[i])
            self.const_soft.set_line_alpha(i, alphas[i])

        self._const_soft_win = sip.wrapinstance(self.const_soft.qwidget(), Qt.QWidget)
        self.tabs_grid_layout_5.addWidget(self._const_soft_win, 0, 0, 2, 2)
        for r in range(0, 2):
            self.tabs_grid_layout_5.setRowStretch(r, 1)
        for c in range(0, 2):
            self.tabs_grid_layout_5.setColumnStretch(c, 1)
        self.const_raw = qtgui.const_sink_c(
            2048, #size
            "after the FFT, before the equalizer (used subcarriers: the channel and the carrier rotate and scale the points)", #name
            1, #number of inputs
            None # parent
        )
        self.const_raw.set_update_time(0.1)
        self.const_raw.set_y_axis((-1.6), 1.6)
        self.const_raw.set_x_axis((-1.6), 1.6)
        self.const_raw.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, "")
        self.const_raw.enable_autoscale(False)
        self.const_raw.enable_grid(True)
        self.const_raw.enable_axis_labels(True)

        self.const_raw.disable_legend()

        labels = ['symbols', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        styles = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        markers = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.const_raw.set_line_label(i, "Data {0}".format(i))
            else:
                self.const_raw.set_line_label(i, labels[i])
            self.const_raw.set_line_width(i, widths[i])
            self.const_raw.set_line_color(i, colors[i])
            self.const_raw.set_line_style(i, styles[i])
            self.const_raw.set_line_marker(i, markers[i])
            self.const_raw.set_line_alpha(i, alphas[i])

        self._const_raw_win = sip.wrapinstance(self.const_raw.qwidget(), Qt.QWidget)
        self.tabs_grid_layout_3.addWidget(self._const_raw_win, 1, 0, 1, 1)
        for r in range(1, 2):
            self.tabs_grid_layout_3.setRowStretch(r, 1)
        for c in range(0, 1):
            self.tabs_grid_layout_3.setColumnStretch(c, 1)
        self.const_eq = qtgui.const_sink_c(
            2048, #size
            "the decided points (the nearest of the 16: the error counters tell the quality)", #name
            1, #number of inputs
            None # parent
        )
        self.const_eq.set_update_time(0.1)
        self.const_eq.set_y_axis((-1.6), 1.6)
        self.const_eq.set_x_axis((-1.6), 1.6)
        self.const_eq.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, "")
        self.const_eq.enable_autoscale(False)
        self.const_eq.enable_grid(True)
        self.const_eq.enable_axis_labels(True)

        self.const_eq.disable_legend()

        labels = ['symbols', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        styles = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        markers = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.const_eq.set_line_label(i, "Data {0}".format(i))
            else:
                self.const_eq.set_line_label(i, labels[i])
            self.const_eq.set_line_width(i, widths[i])
            self.const_eq.set_line_color(i, colors[i])
            self.const_eq.set_line_style(i, styles[i])
            self.const_eq.set_line_marker(i, markers[i])
            self.const_eq.set_line_alpha(i, alphas[i])

        self._const_eq_win = sip.wrapinstance(self.const_eq.qwidget(), Qt.QWidget)
        self.tabs_grid_layout_5.addWidget(self._const_eq_win, 0, 2, 2, 2)
        for r in range(0, 2):
            self.tabs_grid_layout_5.setRowStretch(r, 1)
        for c in range(2, 4):
            self.tabs_grid_layout_5.setColumnStretch(c, 1)
        self.chanest = digital.ofdm_chanest_vcvc(sync_word, sync_word, 1, 0, (-1), True)
        self.cfo_hz_raw = blocks.multiply_const_ff((samp_rate / (3.141592653589793 * fft_len)))


        ##################################################
        # Connections
        ##################################################
        self.msg_connect((self.hdr, 'header_data'), (self.hpd, 'header_data'))
        self.connect((self.cfo_hz_raw, 0), (self.time_sink_cfo, 0))
        self.connect((self.chanest, 0), (self.hdr, 0))
        self.connect((self.counter, 1), (self.number_err, 0))
        self.connect((self.counter, 2), (self.number_frames, 0))
        self.connect((self.counter, 3), (self.number_recent, 0))
        self.connect((self.counter, 0), (self.number_ser, 0))
        self.connect((self.dc_iir, 0), (self.dc_sub, 1))
        self.connect((self.dc_sub, 0), (self.en_mag2, 0))
        self.connect((self.dc_sub, 0), (self.sc_delay, 0))
        self.connect((self.dc_sub, 0), (self.sc_mult, 0))
        self.connect((self.dc_sub, 0), (self.sts_sync, 0))
        self.connect((self.dc_sub, 0), (self.sym_delay, 0))
        self.connect((self.dc_sub, 0), (self.x_mag, 0))
        self.connect((self.dc_sub, 0), (self.x_mag2, 0))
        self.connect((self.dec, 0), (self.keep_chk, 0))
        self.connect((self.detect_f, 0), (self.time_sink_det, 1))
        self.connect((self.detect_f, 0), (self.trg_sum, 0))
        self.connect((self.en_avg, 0), (self.en_delay, 0))
        self.connect((self.en_avg, 0), (self.en_mult, 1))
        self.connect((self.en_delay, 0), (self.en_mult, 0))
        self.connect((self.en_eps, 0), (self.sc_div, 1))
        self.connect((self.en_mag2, 0), (self.en_avg, 0))
        self.connect((self.en_mag2, 0), (self.guard_avg, 0))
        self.connect((self.en_mult, 0), (self.guard_add, 0))
        self.connect((self.fft_avg, 0), (self.vec_fft, 0))
        self.connect((self.fft_hdr, 0), (self.chanest, 0))
        self.connect((self.fft_mag, 0), (self.fft_avg, 0))
        self.connect((self.fft_pay, 0), (self.fft_scale, 0))
        self.connect((self.fft_pay, 0), (self.pilot_eq, 0))
        self.connect((self.fft_scale, 0), (self.fft_mag, 0))
        self.connect((self.fft_scale, 0), (self.v2s64, 0))
        self.connect((self.guard_add, 0), (self.en_eps, 0))
        self.connect((self.guard_avg, 0), (self.guard_sq, 1))
        self.connect((self.guard_avg, 0), (self.guard_sq, 0))
        self.connect((self.guard_k, 0), (self.guard_add, 1))
        self.connect((self.guard_sq, 0), (self.guard_k, 0))
        self.connect((self.h_arg, 0), (self.vec_harg, 0))
        self.connect((self.h_mag, 0), (self.vec_hmag, 0))
        self.connect((self.hdr, 0), (self.h_arg, 0))
        self.connect((self.hdr, 0), (self.h_mag, 0))
        self.connect((self.hpd, 0), (self.fft_hdr, 0))
        self.connect((self.hpd, 1), (self.fft_pay, 0))
        self.connect((self.keep29, 0), (self.const_raw, 0))
        self.connect((self.keep_chk, 0), (self.counter, 0))
        self.connect((self.keep_evm, 0), (self.number_evm, 0))
        self.connect((self.keep_soft, 0), (self.const_soft, 0))
        self.connect((self.osc, 0), (self.rot, 1))
        self.connect((self.pilot_eq, 2), (self.keep_evm, 0))
        self.connect((self.pilot_eq, 0), (self.v2s_dec, 0))
        self.connect((self.pilot_eq, 1), (self.v2s_soft, 0))
        self.connect((self.rot, 0), (self.hpd, 0))
        self.connect((self.rx_in, 0), (self.dc_iir, 0))
        self.connect((self.rx_in, 0), (self.dc_sub, 0))
        self.connect((self.rx_in, 0), (self.freq_sink_rx, 0))
        self.connect((self.sc_avg, 0), (self.sc_mag2, 0))
        self.connect((self.sc_avg, 0), (self.sts_sync, 2))
        self.connect((self.sc_conj, 0), (self.sc_mult, 1))
        self.connect((self.sc_delay, 0), (self.sc_conj, 0))
        self.connect((self.sc_div, 0), (self.sts_sync, 1))
        self.connect((self.sc_div, 0), (self.time_sink_m, 0))
        self.connect((self.sc_mag2, 0), (self.sc_div, 0))
        self.connect((self.sc_mult, 0), (self.sc_avg, 0))
        self.connect((self.sts_sync, 0), (self.cfo_hz_raw, 0))
        self.connect((self.sts_sync, 1), (self.detect_f, 0))
        self.connect((self.sts_sync, 1), (self.hpd, 1))
        self.connect((self.sts_sync, 0), (self.osc, 0))
        self.connect((self.sym_delay, 0), (self.rot, 0))
        self.connect((self.thr_src, 0), (self.time_sink_m, 1))
        self.connect((self.trg_sum, 0), (self.number_fnd, 0))
        self.connect((self.uhd_usrp_source_0, 0), (self.rx_in, 0))
        self.connect((self.v2s64, 0), (self.keep29, 0))
        self.connect((self.v2s_dec, 0), (self.const_eq, 0))
        self.connect((self.v2s_dec, 0), (self.dec, 0))
        self.connect((self.v2s_soft, 0), (self.keep_soft, 0))
        self.connect((self.x_mag, 0), (self.time_sink_rx, 0))
        self.connect((self.x_mag2, 0), (self.x_scale, 0))
        self.connect((self.x_scale, 0), (self.time_sink_det, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "ofdm_b210_frame_rx_sts_pilot")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_pilot_polarity(self):
        return self.pilot_polarity

    def set_pilot_polarity(self, pilot_polarity):
        self.pilot_polarity = pilot_polarity
        self.set_pilot_symbols(tuple(tuple(p * v for v in ((0.707106781187+0.707106781187j), (0.707106781187-0.707106781187j), (-0.707106781187+0.707106781187j), (-0.707106781187-0.707106781187j))) for p in self.pilot_polarity))

    def get_threshold(self):
        return self.threshold

    def set_threshold(self, threshold):
        self.threshold = threshold
        self.thr_src.set_offset(self.threshold)
        self.sts_sync.threshold = self.threshold

    def get_sync_word(self):
        return self.sync_word

    def set_sync_word(self, sync_word):
        self.sync_word = sync_word

    def get_sync_delay(self):
        return self.sync_delay

    def set_sync_delay(self, sync_delay):
        self.sync_delay = sync_delay
        self.sym_delay.set_dly(int(self.sync_delay))
        self.sts_sync.delay = self.sync_delay

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.uhd_usrp_source_0.set_samp_rate(self.samp_rate)
        self.freq_sink_rx.set_frequency_range(0, self.samp_rate)
        self.time_sink_rx.set_samp_rate(self.samp_rate)
        self.time_sink_det.set_samp_rate(self.samp_rate)
        self.cfo_hz_raw.set_k((self.samp_rate / (3.141592653589793 * self.fft_len)))
        self.time_sink_cfo.set_samp_rate(self.samp_rate)
        self.time_sink_m.set_samp_rate(self.samp_rate)

    def get_rx_gain(self):
        return self.rx_gain

    def set_rx_gain(self, rx_gain):
        self.rx_gain = rx_gain
        self.uhd_usrp_source_0.set_gain(self.rx_gain, 0)

    def get_pilot_symbols(self):
        return self.pilot_symbols

    def set_pilot_symbols(self, pilot_symbols):
        self.pilot_symbols = pilot_symbols

    def get_pilot_carriers(self):
        return self.pilot_carriers

    def set_pilot_carriers(self, pilot_carriers):
        self.pilot_carriers = pilot_carriers

    def get_payload_mod(self):
        return self.payload_mod

    def set_payload_mod(self, payload_mod):
        self.payload_mod = payload_mod

    def get_occupied_carriers(self):
        return self.occupied_carriers

    def set_occupied_carriers(self, occupied_carriers):
        self.occupied_carriers = occupied_carriers

    def get_length_tag_key(self):
        return self.length_tag_key

    def set_length_tag_key(self, length_tag_key):
        self.length_tag_key = length_tag_key

    def get_guard_level(self):
        return self.guard_level

    def set_guard_level(self, guard_level):
        self.guard_level = guard_level
        self.guard_k.set_k(((self.guard_level * 48) ** 2))

    def get_freq(self):
        return self.freq

    def set_freq(self, freq):
        self.freq = freq
        self.uhd_usrp_source_0.set_center_freq(self.freq, 0)

    def get_fft_len(self):
        return self.fft_len

    def set_fft_len(self, fft_len):
        self.fft_len = fft_len
        self.cfo_hz_raw.set_k((self.samp_rate / (3.141592653589793 * self.fft_len)))
        self.osc.set_sensitivity((-2.0 / self.fft_len))

    def get_cp_len(self):
        return self.cp_len

    def set_cp_len(self, cp_len):
        self.cp_len = cp_len

    def get_check_n(self):
        return self.check_n

    def set_check_n(self, check_n):
        self.check_n = check_n
        self.keep_chk.set_n((1056 * self.check_n))

    def get_capture_file(self):
        return self.capture_file

    def set_capture_file(self, capture_file):
        self.capture_file = capture_file




def main(top_block_cls=ofdm_b210_frame_rx_sts_pilot, options=None):

    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls()

    tb.start()
    tb.flowgraph_started.set()

    tb.show()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    qapp.exec_()

if __name__ == '__main__':
    main()
