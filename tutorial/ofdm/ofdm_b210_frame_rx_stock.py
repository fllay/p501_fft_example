#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: B210 receiver: OFDM frames with the stock GNU Radio OFDM blocks
# Author: p501_fft_example
# Description: The B210 receives the OFDM frames of the P501 (or of ofdm_b210_frame_tx.grc) at 850 MHz, 3.84 MS/s and decodes them with the stock gr-digital OFDM blocks: Schmidl and Cox synchroniser, header/payload demux, FFT, channel estimator, frame equalizer, serializer, constellation decoder. One small Python block stands in for the packet header, one counts the errors.
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
import ofdm_b210_frame_rx_stock_counter as counter  # embedded python block
import ofdm_b210_frame_rx_stock_hdr as hdr  # embedded python block
import ofdm_b210_frame_rx_stock_soft as soft  # embedded python block
import sip
import threading



class ofdm_b210_frame_rx_stock(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "B210 receiver: OFDM frames with the stock GNU Radio OFDM blocks", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("B210 receiver: OFDM frames with the stock GNU Radio OFDM blocks")
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

        self.settings = Qt.QSettings("gnuradio/flowgraphs", "ofdm_b210_frame_rx_stock")

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
        self.pilot_symbols = pilot_symbols = tuple(tuple(p * v for v in ((0.707106781187+0.707106781187j), (0.707106781187-0.707106781187j), (-0.707106781187+0.707106781187j), (-0.707106781187-0.707106781187j))) for p in pilot_polarity)
        self.pilot_carriers = pilot_carriers = ([-11, -4, 4, 11],)
        self.payload_mod = payload_mod = digital.constellation_calcdist([((-3, -1, 3, 1)[i >> 2] + 1j * (-3, -1, 3, 1)[i & 3]) / 10 ** 0.5 for i in range(16)], list(range(16)), 4, 1)
        self.occupied_carriers = occupied_carriers = ([-14, -13, -12, -10, -9, -8, -7, -6, -5, -3, -2, -1, 1, 2, 3, 5, 6, 7, 8, 9, 10, 12, 13, 14],)
        self.fft_len = fft_len = 64
        self.eq_alpha = eq_alpha = 0.6
        self.threshold = threshold = 0.8
        self.sync_word2 = sync_word2 = [0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, (0.707106781187-0.707106781187j), (-0.707106781187-0.707106781187j), (0.707106781187-0.707106781187j), (0.707106781187-0.707106781187j), (-0.707106781187+0.707106781187j), (-0.707106781187-0.707106781187j), (0.707106781187-0.707106781187j), (0.707106781187+0.707106781187j), (0.707106781187-0.707106781187j), (-0.707106781187+0.707106781187j), (0.707106781187+0.707106781187j), (-0.707106781187-0.707106781187j), (0.707106781187-0.707106781187j), (0.707106781187+0.707106781187j), 0j, (0.707106781187-0.707106781187j), (-0.707106781187+0.707106781187j), (0.707106781187+0.707106781187j), (-0.707106781187-0.707106781187j), (0.707106781187-0.707106781187j), (0.707106781187-0.707106781187j), (0.707106781187+0.707106781187j), (0.707106781187+0.707106781187j), (0.707106781187+0.707106781187j), (0.707106781187-0.707106781187j), (-0.707106781187+0.707106781187j), (-0.707106781187-0.707106781187j), (-0.707106781187+0.707106781187j), (-0.707106781187-0.707106781187j), 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j]
        self.sync_word1 = sync_word1 = [0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, (-1-1j), 0j, (-1+1j), 0j, (-1-1j), 0j, (-1-1j), 0j, (1+1j), 0j, (-1-1j), 0j, (-1-1j), 0j, 0j, 0j, (1+1j), 0j, (1+1j), 0j, (1-1j), 0j, (-1-1j), 0j, (-1+1j), 0j, (-1-1j), 0j, (-1+1j), 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j, 0j]
        self.soft_n = soft_n = 8
        self.samp_rate = samp_rate = 3840000
        self.rx_gain = rx_gain = 45
        self.payload_equalizer = payload_equalizer = digital.ofdm_equalizer_simpledfe(fft_len, payload_mod.base(), occupied_carriers, pilot_carriers, pilot_symbols, 0, eq_alpha)
        self.length_tag_key = length_tag_key = "frame_length"
        self.freq = freq = 850e6
        self.dither_level = dither_level = 0.12
        self.cp_len = cp_len = 16
        self.cfo_frames = cfo_frames = 13
        self.capture_file = capture_file = "ofdm_b210_capture.c64"

        ##################################################
        # Blocks
        ##################################################

        self._threshold_range = qtgui.Range(0.3, 0.99, 0.01, 0.8, 200)
        self._threshold_win = qtgui.RangeWidget(self._threshold_range, self.set_threshold, "S&C detection threshold (stock block)", "counter_slider", float, QtCore.Qt.Horizontal)
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
        self.tabs.addTab(self.tabs_widget_1, '2 Frame detection (stock S&C)')
        self.tabs_widget_2 = Qt.QWidget()
        self.tabs_layout_2 = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom, self.tabs_widget_2)
        self.tabs_grid_layout_2 = Qt.QGridLayout()
        self.tabs_layout_2.addLayout(self.tabs_grid_layout_2)
        self.tabs.addTab(self.tabs_widget_2, '3 Carrier offset')
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
        self._dither_level_range = qtgui.Range(0, 0.4, 0.01, 0.12, 200)
        self._dither_level_win = qtgui.RangeWidget(self._dither_level_range, self.set_dither_level, "detector dither (fraction of the signal level)", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._dither_level_win, 1, 3, 1, 3)
        for r in range(1, 2):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(3, 6):
            self.top_grid_layout.setColumnStretch(c, 1)
        self._cfo_frames_range = qtgui.Range(1, 60, 1, 13, 200)
        self._cfo_frames_win = qtgui.RangeWidget(self._cfo_frames_range, self.set_cfo_frames, "carrier offset averaging (frames)", "counter_slider", int, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._cfo_frames_win, 1, 0, 1, 3)
        for r in range(1, 2):
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
        self.time_sink_det = qtgui.time_sink_f(
            8192, #size
            samp_rate, #samp_rate
            "|x| and the detect pulses of the stock S&C block (two frames of 3840 samples = 1 ms each)", #name
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

        labels = ['|x| (x 5)', 'detect', 'Signal 3', 'Signal 4', 'Signal 5',
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
            "carrier offset (Hz): the value of the S&C block for every frame (blue) and the average that is applied (red)", #name
            2, #number of inputs
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

        labels = ['S&C block', 'averaged', 'Signal 3', 'Signal 4', 'Signal 5',
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
        self.sync = digital.ofdm_sync_sc_cfb(fft_len, cp_len, True, threshold)
        self.sym_delay = blocks.delay(gr.sizeof_gr_complex*1, (fft_len + cp_len))
        self.soft_v2s = blocks.vector_to_stream(gr.sizeof_gr_complex*1, 64)
        self.soft_s2v = blocks.stream_to_vector(gr.sizeof_gr_complex*1, 64)
        self.soft_keep = blocks.keep_m_in_n(gr.sizeof_gr_complex, (44 * 64), (44 * 64 * soft_n), 0)
        self.soft = soft.blk(smooth=5)
        self.ser = digital.ofdm_serializer_vcc(fft_len, occupied_carriers, length_tag_key, "", 0, "", True)
        self.rx_in = blocks.copy(gr.sizeof_gr_complex*1)
        self.rx_in.set_enabled(True)
        self.rot = blocks.multiply_vcc(1)
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
        self.number_recent.set_title("symbol error rate, last 2000 frames (about 2 s)")

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
        self.number_frames.set_title("frames decoded")

        labels = ['frames', '', '', '', '',
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
        self.keep_ser = blocks.keep_one_in_n(gr.sizeof_float*1, 1056)
        self.keep_recent = blocks.keep_one_in_n(gr.sizeof_float*1, 1056)
        self.keep_frames = blocks.keep_one_in_n(gr.sizeof_float*1, 1056)
        self.keep_evm = blocks.keep_one_in_n(gr.sizeof_float*1, 1056)
        self.keep_err = blocks.keep_one_in_n(gr.sizeof_float*1, 1056)
        self.keep29 = blocks.keep_m_in_n(gr.sizeof_gr_complex, 29, 64, 18)
        self.hpd = digital.header_payload_demux(
            3,
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
        self.eq = digital.ofdm_frame_equalizer_vcvc(payload_equalizer.base(), cp_len, length_tag_key, False, 0)
        self.dith_noise = analog.noise_source_c(analog.GR_GAUSSIAN, 1, 7)
        self.dith_mult = blocks.multiply_vcc(1)
        self.dith_mag = blocks.complex_to_mag(1)
        self.dith_lvl = filter.single_pole_iir_filter_ff((2.4e-4), 1)
        self.dith_k = blocks.multiply_const_cc(dither_level)
        self.dith_f2c = blocks.float_to_complex(1)
        self.dith_add = blocks.add_vcc(1)
        self.detect_f = blocks.char_to_float(1, 1)
        self.dec = digital.constellation_decoder_cb(payload_mod.base())
        self.dc_sub = blocks.sub_cc(1)
        self.dc_iir = filter.single_pole_iir_filter_cc((1e-4), 1)
        self.counter = counter.blk()
        self.const_soft = qtgui.const_sink_c(
            2048, #size
            "the received data symbols after the soft equalizer: the spread of the clusters is the noise (the channel is divided out, the pilots remove the phase and gain)", #name
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
            "the decided symbols (the stock equalizer outputs its decisions, so this is always clean: the error counters tell the quality)", #name
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
        self.chanest = digital.ofdm_chanest_vcvc(sync_word1, sync_word2, 1, 0, (-1), False)
        self.cfo_hz_raw = blocks.multiply_const_ff((samp_rate / (3.141592653589793 * fft_len)))
        self.cfo_hz_avg = blocks.multiply_const_ff((samp_rate / (3.141592653589793 * fft_len)))
        self.cfo_avg = filter.single_pole_iir_filter_ff((1.0 / (cfo_frames * 3840)), 1)


        ##################################################
        # Connections
        ##################################################
        self.msg_connect((self.hdr, 'header_data'), (self.hpd, 'header_data'))
        self.connect((self.cfo_avg, 0), (self.cfo_hz_avg, 0))
        self.connect((self.cfo_avg, 0), (self.osc, 0))
        self.connect((self.cfo_hz_avg, 0), (self.time_sink_cfo, 1))
        self.connect((self.cfo_hz_raw, 0), (self.time_sink_cfo, 0))
        self.connect((self.chanest, 0), (self.hdr, 0))
        self.connect((self.counter, 1), (self.keep_err, 0))
        self.connect((self.counter, 2), (self.keep_frames, 0))
        self.connect((self.counter, 3), (self.keep_recent, 0))
        self.connect((self.counter, 0), (self.keep_ser, 0))
        self.connect((self.dc_iir, 0), (self.dc_sub, 1))
        self.connect((self.dc_sub, 0), (self.dith_add, 0))
        self.connect((self.dc_sub, 0), (self.dith_mag, 0))
        self.connect((self.dc_sub, 0), (self.sym_delay, 0))
        self.connect((self.dc_sub, 0), (self.x_mag, 0))
        self.connect((self.dc_sub, 0), (self.x_mag2, 0))
        self.connect((self.dec, 0), (self.counter, 0))
        self.connect((self.detect_f, 0), (self.time_sink_det, 1))
        self.connect((self.dith_add, 0), (self.sync, 0))
        self.connect((self.dith_f2c, 0), (self.dith_mult, 0))
        self.connect((self.dith_k, 0), (self.dith_add, 1))
        self.connect((self.dith_lvl, 0), (self.dith_f2c, 0))
        self.connect((self.dith_mag, 0), (self.dith_lvl, 0))
        self.connect((self.dith_mult, 0), (self.dith_k, 0))
        self.connect((self.dith_noise, 0), (self.dith_mult, 1))
        self.connect((self.eq, 0), (self.ser, 0))
        self.connect((self.fft_avg, 0), (self.vec_fft, 0))
        self.connect((self.fft_hdr, 0), (self.chanest, 0))
        self.connect((self.fft_mag, 0), (self.fft_avg, 0))
        self.connect((self.fft_pay, 0), (self.eq, 0))
        self.connect((self.fft_pay, 0), (self.fft_scale, 0))
        self.connect((self.fft_pay, 0), (self.soft_v2s, 0))
        self.connect((self.fft_scale, 0), (self.fft_mag, 0))
        self.connect((self.fft_scale, 0), (self.v2s64, 0))
        self.connect((self.h_arg, 0), (self.vec_harg, 0))
        self.connect((self.h_mag, 0), (self.vec_hmag, 0))
        self.connect((self.hdr, 0), (self.h_arg, 0))
        self.connect((self.hdr, 0), (self.h_mag, 0))
        self.connect((self.hpd, 0), (self.fft_hdr, 0))
        self.connect((self.hpd, 1), (self.fft_pay, 0))
        self.connect((self.keep29, 0), (self.const_raw, 0))
        self.connect((self.keep_err, 0), (self.number_err, 0))
        self.connect((self.keep_evm, 0), (self.number_evm, 0))
        self.connect((self.keep_frames, 0), (self.number_frames, 0))
        self.connect((self.keep_recent, 0), (self.number_recent, 0))
        self.connect((self.keep_ser, 0), (self.number_ser, 0))
        self.connect((self.keep_soft, 0), (self.const_soft, 0))
        self.connect((self.osc, 0), (self.rot, 1))
        self.connect((self.rot, 0), (self.hpd, 0))
        self.connect((self.rx_in, 0), (self.dc_iir, 0))
        self.connect((self.rx_in, 0), (self.dc_sub, 0))
        self.connect((self.rx_in, 0), (self.freq_sink_rx, 0))
        self.connect((self.ser, 0), (self.const_eq, 0))
        self.connect((self.ser, 0), (self.dec, 0))
        self.connect((self.soft, 1), (self.keep_evm, 0))
        self.connect((self.soft, 0), (self.v2s_soft, 0))
        self.connect((self.soft_keep, 0), (self.soft_s2v, 0))
        self.connect((self.soft_s2v, 0), (self.soft, 0))
        self.connect((self.soft_v2s, 0), (self.soft_keep, 0))
        self.connect((self.sym_delay, 0), (self.rot, 0))
        self.connect((self.sync, 0), (self.cfo_avg, 0))
        self.connect((self.sync, 0), (self.cfo_hz_raw, 0))
        self.connect((self.sync, 1), (self.detect_f, 0))
        self.connect((self.sync, 1), (self.hpd, 1))
        self.connect((self.uhd_usrp_source_0, 0), (self.rx_in, 0))
        self.connect((self.v2s64, 0), (self.keep29, 0))
        self.connect((self.v2s_soft, 0), (self.keep_soft, 0))
        self.connect((self.x_mag, 0), (self.time_sink_rx, 0))
        self.connect((self.x_mag2, 0), (self.x_scale, 0))
        self.connect((self.x_scale, 0), (self.time_sink_det, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "ofdm_b210_frame_rx_stock")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_pilot_polarity(self):
        return self.pilot_polarity

    def set_pilot_polarity(self, pilot_polarity):
        self.pilot_polarity = pilot_polarity
        self.set_pilot_symbols(tuple(tuple(p * v for v in ((0.707106781187+0.707106781187j), (0.707106781187-0.707106781187j), (-0.707106781187+0.707106781187j), (-0.707106781187-0.707106781187j))) for p in self.pilot_polarity))

    def get_pilot_symbols(self):
        return self.pilot_symbols

    def set_pilot_symbols(self, pilot_symbols):
        self.pilot_symbols = pilot_symbols
        self.set_payload_equalizer(digital.ofdm_equalizer_simpledfe(self.fft_len, payload_mod.base(), self.occupied_carriers, self.pilot_carriers, self.pilot_symbols, 0, self.eq_alpha))

    def get_pilot_carriers(self):
        return self.pilot_carriers

    def set_pilot_carriers(self, pilot_carriers):
        self.pilot_carriers = pilot_carriers
        self.set_payload_equalizer(digital.ofdm_equalizer_simpledfe(self.fft_len, payload_mod.base(), self.occupied_carriers, self.pilot_carriers, self.pilot_symbols, 0, self.eq_alpha))

    def get_payload_mod(self):
        return self.payload_mod

    def set_payload_mod(self, payload_mod):
        self.payload_mod = payload_mod

    def get_occupied_carriers(self):
        return self.occupied_carriers

    def set_occupied_carriers(self, occupied_carriers):
        self.occupied_carriers = occupied_carriers
        self.set_payload_equalizer(digital.ofdm_equalizer_simpledfe(self.fft_len, payload_mod.base(), self.occupied_carriers, self.pilot_carriers, self.pilot_symbols, 0, self.eq_alpha))

    def get_fft_len(self):
        return self.fft_len

    def set_fft_len(self, fft_len):
        self.fft_len = fft_len
        self.set_payload_equalizer(digital.ofdm_equalizer_simpledfe(self.fft_len, payload_mod.base(), self.occupied_carriers, self.pilot_carriers, self.pilot_symbols, 0, self.eq_alpha))
        self.cfo_hz_raw.set_k((self.samp_rate / (3.141592653589793 * self.fft_len)))
        self.cfo_hz_avg.set_k((self.samp_rate / (3.141592653589793 * self.fft_len)))
        self.osc.set_sensitivity((-2.0 / self.fft_len))
        self.sym_delay.set_dly(int((self.fft_len + self.cp_len)))

    def get_eq_alpha(self):
        return self.eq_alpha

    def set_eq_alpha(self, eq_alpha):
        self.eq_alpha = eq_alpha
        self.set_payload_equalizer(digital.ofdm_equalizer_simpledfe(self.fft_len, payload_mod.base(), self.occupied_carriers, self.pilot_carriers, self.pilot_symbols, 0, self.eq_alpha))

    def get_threshold(self):
        return self.threshold

    def set_threshold(self, threshold):
        self.threshold = threshold
        self.sync.set_threshold(self.threshold)

    def get_sync_word2(self):
        return self.sync_word2

    def set_sync_word2(self, sync_word2):
        self.sync_word2 = sync_word2

    def get_sync_word1(self):
        return self.sync_word1

    def set_sync_word1(self, sync_word1):
        self.sync_word1 = sync_word1

    def get_soft_n(self):
        return self.soft_n

    def set_soft_n(self, soft_n):
        self.soft_n = soft_n
        self.soft_keep.set_n((44 * 64 * self.soft_n))

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.uhd_usrp_source_0.set_samp_rate(self.samp_rate)
        self.freq_sink_rx.set_frequency_range(0, self.samp_rate)
        self.time_sink_rx.set_samp_rate(self.samp_rate)
        self.time_sink_det.set_samp_rate(self.samp_rate)
        self.cfo_hz_raw.set_k((self.samp_rate / (3.141592653589793 * self.fft_len)))
        self.cfo_hz_avg.set_k((self.samp_rate / (3.141592653589793 * self.fft_len)))
        self.time_sink_cfo.set_samp_rate(self.samp_rate)

    def get_rx_gain(self):
        return self.rx_gain

    def set_rx_gain(self, rx_gain):
        self.rx_gain = rx_gain
        self.uhd_usrp_source_0.set_gain(self.rx_gain, 0)

    def get_payload_equalizer(self):
        return self.payload_equalizer

    def set_payload_equalizer(self, payload_equalizer):
        self.payload_equalizer = payload_equalizer

    def get_length_tag_key(self):
        return self.length_tag_key

    def set_length_tag_key(self, length_tag_key):
        self.length_tag_key = length_tag_key

    def get_freq(self):
        return self.freq

    def set_freq(self, freq):
        self.freq = freq
        self.uhd_usrp_source_0.set_center_freq(self.freq, 0)

    def get_dither_level(self):
        return self.dither_level

    def set_dither_level(self, dither_level):
        self.dither_level = dither_level
        self.dith_k.set_k(self.dither_level)

    def get_cp_len(self):
        return self.cp_len

    def set_cp_len(self, cp_len):
        self.cp_len = cp_len
        self.sym_delay.set_dly(int((self.fft_len + self.cp_len)))

    def get_cfo_frames(self):
        return self.cfo_frames

    def set_cfo_frames(self, cfo_frames):
        self.cfo_frames = cfo_frames
        self.cfo_avg.set_taps((1.0 / (self.cfo_frames * 3840)))

    def get_capture_file(self):
        return self.capture_file

    def set_capture_file(self, capture_file):
        self.capture_file = capture_file




def main(top_block_cls=ofdm_b210_frame_rx_stock, options=None):

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
