#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: B210 receiver: OFDM frames (Schmidl-Cox sync, 16-QAM data), block by block
# Author: p501_fft_example
# Description: The B210 receives the OFDM frames of the P501 (or of ofdm_b210_frame_tx.grc) at 850 MHz, 3.84 MS/s and decodes them with separate blocks: S&C metric, frame detector, carrier corrections, FFT, channel estimate, equalizer, slicer, error counter; one plot tab per stage.
# GNU Radio version: 3.10.12.0

from PyQt5 import Qt
from gnuradio import qtgui
from PyQt5 import QtCore
from gnuradio import analog
from gnuradio import blocks
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
import ofdm_b210_frame_rx_coarse as coarse  # embedded python block
import ofdm_b210_frame_rx_counter as counter  # embedded python block
import ofdm_b210_frame_rx_det as det  # embedded python block
import ofdm_b210_frame_rx_eq as eq  # embedded python block
import ofdm_b210_frame_rx_est as est  # embedded python block
import ofdm_b210_frame_rx_fine as fine  # embedded python block
import ofdm_b210_frame_rx_slicer as slicer  # embedded python block
import sip
import threading



class ofdm_b210_frame_rx(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "B210 receiver: OFDM frames (Schmidl-Cox sync, 16-QAM data), block by block", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("B210 receiver: OFDM frames (Schmidl-Cox sync, 16-QAM data), block by block")
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

        self.settings = Qt.QSettings("gnuradio/flowgraphs", "ofdm_b210_frame_rx")

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
        self.threshold = threshold = 0.65
        self.smooth = smooth = 5
        self.samp_rate = samp_rate = 3840000
        self.rx_gain = rx_gain = 45
        self.guard_level = guard_level = 0.1
        self.freq = freq = 850e6
        self.decode_n = decode_n = 8
        self.capture_file = capture_file = "ofdm_b210_capture.c64"

        ##################################################
        # Blocks
        ##################################################

        self._threshold_range = qtgui.Range(0.3, 0.95, 0.01, 0.65, 200)
        self._threshold_win = qtgui.RangeWidget(self._threshold_range, self.set_threshold, "S&C detection threshold (metric M)", "counter_slider", float, QtCore.Qt.Horizontal)
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
        self.tabs.addTab(self.tabs_widget_1, '2 Frame detection (Schmidl-Cox)')
        self.tabs_widget_2 = Qt.QWidget()
        self.tabs_layout_2 = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom, self.tabs_widget_2)
        self.tabs_grid_layout_2 = Qt.QGridLayout()
        self.tabs_layout_2.addLayout(self.tabs_grid_layout_2)
        self.tabs.addTab(self.tabs_widget_2, '3 Frame and carrier correction')
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
        self._smooth_range = qtgui.Range(1, 9, 2, 5, 200)
        self._smooth_win = qtgui.RangeWidget(self._smooth_range, self.set_smooth, "pilot smoothing (symbols)", "counter_slider", int, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._smooth_win, 1, 3, 1, 3)
        for r in range(1, 2):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(3, 6):
            self.top_grid_layout.setColumnStretch(c, 1)
        self._rx_gain_range = qtgui.Range(0, 76, 1, 45, 200)
        self._rx_gain_win = qtgui.RangeWidget(self._rx_gain_range, self.set_rx_gain, "B210 RX gain (dB)", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._rx_gain_win, 0, 0, 1, 3)
        for r in range(0, 1):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 3):
            self.top_grid_layout.setColumnStretch(c, 1)
        self._decode_n_range = qtgui.Range(1, 40, 1, 8, 200)
        self._decode_n_win = qtgui.RangeWidget(self._decode_n_range, self.set_decode_n, "decode 1 frame in N", "counter_slider", int, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._decode_n_win, 1, 0, 1, 3)
        for r in range(1, 2):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 3):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.x_mag = blocks.complex_to_mag(1)
        self.vec_hmag = qtgui.vector_sink_f(
            29,
            (-14),
            1,
            "subcarrier k",
            "|H|",
            "channel |H[k]| (k = 0, the DC, is not used)",
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
            29,
            (-14),
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
        self.v2s64 = blocks.vector_to_stream(gr.sizeof_gr_complex*1, 64)
        self.v2s24 = blocks.vector_to_stream(gr.sizeof_gr_complex*1, 24)
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
        self.time_sink_pilot = qtgui.time_sink_f(
            440, #size
            samp_rate / 80, #samp_rate
            "pilot tracking per symbol: arg g (rad, the common phase error) and |g| (gain)", #name
            2, #number of inputs
            None # parent
        )
        self.time_sink_pilot.set_update_time(0.1)
        self.time_sink_pilot.set_y_axis(-3.5, 3.5)

        self.time_sink_pilot.set_y_label('', "")

        self.time_sink_pilot.enable_tags(False)
        self.time_sink_pilot.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.time_sink_pilot.enable_autoscale(True)
        self.time_sink_pilot.enable_grid(True)
        self.time_sink_pilot.enable_axis_labels(True)
        self.time_sink_pilot.enable_control_panel(False)
        self.time_sink_pilot.enable_stem_plot(False)

        self.time_sink_pilot.disable_legend()

        labels = ['arg g', '|g|', 'Signal 3', 'Signal 4', 'Signal 5',
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
                self.time_sink_pilot.set_line_label(i, "Data {0}".format(i))
            else:
                self.time_sink_pilot.set_line_label(i, labels[i])
            self.time_sink_pilot.set_line_width(i, widths[i])
            self.time_sink_pilot.set_line_color(i, colors[i])
            self.time_sink_pilot.set_line_style(i, styles[i])
            self.time_sink_pilot.set_line_marker(i, markers[i])
            self.time_sink_pilot.set_line_alpha(i, alphas[i])

        self._time_sink_pilot_win = sip.wrapinstance(self.time_sink_pilot.qwidget(), Qt.QWidget)
        self.tabs_grid_layout_5.addWidget(self._time_sink_pilot_win, 0, 1, 1, 2)
        for r in range(0, 1):
            self.tabs_grid_layout_5.setRowStretch(r, 1)
        for c in range(1, 3):
            self.tabs_grid_layout_5.setColumnStretch(c, 1)
        self.time_sink_m = qtgui.time_sink_f(
            8192, #size
            samp_rate, #samp_rate
            "Schmidl-Cox metric M and the threshold (two frames)", #name
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
        self.tabs_grid_layout_1.addWidget(self._time_sink_m_win, 0, 0, 1, 1)
        for r in range(0, 1):
            self.tabs_grid_layout_1.setRowStretch(r, 1)
        for c in range(0, 1):
            self.tabs_grid_layout_1.setColumnStretch(c, 1)
        self.time_sink_frame = qtgui.time_sink_f(
            3760, #size
            samp_rate, #samp_rate
            "the frame after the carrier corrections: S&C | T1 | T2 | 44 data symbols (47 x 80 samples)", #name
            1, #number of inputs
            None # parent
        )
        self.time_sink_frame.set_update_time(0.1)
        self.time_sink_frame.set_y_axis(0, 4)

        self.time_sink_frame.set_y_label('Amplitude', "")

        self.time_sink_frame.enable_tags(False)
        self.time_sink_frame.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.time_sink_frame.enable_autoscale(True)
        self.time_sink_frame.enable_grid(True)
        self.time_sink_frame.enable_axis_labels(True)
        self.time_sink_frame.enable_control_panel(False)
        self.time_sink_frame.enable_stem_plot(False)

        self.time_sink_frame.disable_legend()

        labels = ['|frame|', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
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
                self.time_sink_frame.set_line_label(i, "Data {0}".format(i))
            else:
                self.time_sink_frame.set_line_label(i, labels[i])
            self.time_sink_frame.set_line_width(i, widths[i])
            self.time_sink_frame.set_line_color(i, colors[i])
            self.time_sink_frame.set_line_style(i, styles[i])
            self.time_sink_frame.set_line_marker(i, markers[i])
            self.time_sink_frame.set_line_alpha(i, alphas[i])

        self._time_sink_frame_win = sip.wrapinstance(self.time_sink_frame.qwidget(), Qt.QWidget)
        self.tabs_grid_layout_2.addWidget(self._time_sink_frame_win, 0, 0, 1, 3)
        for r in range(0, 1):
            self.tabs_grid_layout_2.setRowStretch(r, 1)
        for c in range(0, 3):
            self.tabs_grid_layout_2.setColumnStretch(c, 1)
        self.thr_src = analog.sig_source_f(0, analog.GR_CONST_WAVE, 0, 0, threshold)
        self.slicer = slicer.blk()
        self.sc_mult = blocks.multiply_vcc(1)
        self.sc_mag2 = blocks.complex_to_mag_squared(1)
        self.sc_div = blocks.divide_ff(1)
        self.sc_delay = blocks.delay(gr.sizeof_gr_complex*1, 32)
        self.sc_conj = blocks.conjugate_cc()
        self.sc_avg = blocks.moving_average_cc(32, 1, 4000, 1)
        self.s2v64 = blocks.stream_to_vector(gr.sizeof_gr_complex*1, 64)
        self.s2v29 = blocks.stream_to_vector(gr.sizeof_gr_complex*1, 29)
        self.rx_in = blocks.copy(gr.sizeof_gr_complex*1)
        self.rx_in.set_enabled(True)
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
        self.tabs_grid_layout_5.addWidget(self._number_ser_win, 1, 1, 1, 1)
        for r in range(1, 2):
            self.tabs_grid_layout_5.setRowStretch(r, 1)
        for c in range(1, 2):
            self.tabs_grid_layout_5.setColumnStretch(c, 1)
        self.number_ok = qtgui.number_sink(
            gr.sizeof_float,
            0.0,
            qtgui.NUM_GRAPH_NONE,
            1,
            None # parent
        )
        self.number_ok.set_update_time(0.25)
        self.number_ok.set_title("frame accepted by the T1/T2 check (1) or thrown away (0)")

        labels = ['accepted', '', '', '', '',
            '', '', '', '', '']
        units = ['', '', '', '', '',
            '', '', '', '', '']
        colors = [("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"),
            ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black")]
        factor = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]

        for i in range(1):
            self.number_ok.set_min(i, 0)
            self.number_ok.set_max(i, 1)
            self.number_ok.set_color(i, colors[i][0], colors[i][1])
            if len(labels[i]) == 0:
                self.number_ok.set_label(i, "Data {0}".format(i))
            else:
                self.number_ok.set_label(i, labels[i])
            self.number_ok.set_unit(i, units[i])
            self.number_ok.set_factor(i, factor[i])

        self.number_ok.enable_autoscale(False)
        self._number_ok_win = sip.wrapinstance(self.number_ok.qwidget(), Qt.QWidget)
        self.tabs_grid_layout_2.addWidget(self._number_ok_win, 1, 1, 1, 1)
        for r in range(1, 2):
            self.tabs_grid_layout_2.setRowStretch(r, 1)
        for c in range(1, 2):
            self.tabs_grid_layout_2.setColumnStretch(c, 1)
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
        self.tabs_grid_layout_5.addWidget(self._number_frames_win, 1, 3, 1, 1)
        for r in range(1, 2):
            self.tabs_grid_layout_5.setRowStretch(r, 1)
        for c in range(3, 4):
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
        self.tabs_grid_layout_5.addWidget(self._number_err_win, 1, 2, 1, 1)
        for r in range(1, 2):
            self.tabs_grid_layout_5.setRowStretch(r, 1)
        for c in range(2, 3):
            self.tabs_grid_layout_5.setColumnStretch(c, 1)
        self.number_cfo = qtgui.number_sink(
            gr.sizeof_float,
            0.0,
            qtgui.NUM_GRAPH_NONE,
            1,
            None # parent
        )
        self.number_cfo.set_update_time(0.25)
        self.number_cfo.set_title("carrier offset (Hz): coarse + fine")

        labels = ['carrier offset', '', '', '', '',
            '', '', '', '', '']
        units = ['Hz', '', '', '', '',
            '', '', '', '', '']
        colors = [("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"),
            ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black")]
        factor = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]

        for i in range(1):
            self.number_cfo.set_min(i, 0)
            self.number_cfo.set_max(i, 1)
            self.number_cfo.set_color(i, colors[i][0], colors[i][1])
            if len(labels[i]) == 0:
                self.number_cfo.set_label(i, "Data {0}".format(i))
            else:
                self.number_cfo.set_label(i, labels[i])
            self.number_cfo.set_unit(i, units[i])
            self.number_cfo.set_factor(i, factor[i])

        self.number_cfo.enable_autoscale(False)
        self._number_cfo_win = sip.wrapinstance(self.number_cfo.qwidget(), Qt.QWidget)
        self.tabs_grid_layout_2.addWidget(self._number_cfo_win, 1, 0, 1, 1)
        for r in range(1, 2):
            self.tabs_grid_layout_2.setRowStretch(r, 1)
        for c in range(0, 1):
            self.tabs_grid_layout_2.setColumnStretch(c, 1)
        self.keep64 = blocks.keep_m_in_n(gr.sizeof_gr_complex, 64, 80, 16)
        self.keep29 = blocks.keep_m_in_n(gr.sizeof_gr_complex, 29, 64, 18)
        self.h_mag = blocks.complex_to_mag(29)
        self.h_arg = blocks.complex_to_arg(29)
        self.guard_sq = blocks.multiply_vff(1)
        self.guard_k = blocks.multiply_const_ff(((guard_level * 32) ** 2))
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
        self.frame_mag = blocks.complex_to_mag(1)
        self.fine = fine.blk(back=6, check=True)
        self.fft_scale = blocks.multiply_const_vcc([1.0 / 8.0] * 64)
        self.fft_mag = blocks.complex_to_mag(64)
        self.fft_avg = blocks.moving_average_ff(64, (1.0 / 64), 4000, 64)
        self.fft64 = fft.fft_vcc(64, True, [], True, 1)
        self.est = est.blk()
        self.eq = eq.blk(smooth=smooth, slope=True)
        self.en_mult = blocks.multiply_vff(1)
        self.en_mag2 = blocks.complex_to_mag_squared(1)
        self.en_eps = blocks.add_const_ff((1e-12))
        self.en_delay = blocks.delay(gr.sizeof_float*1, 32)
        self.en_avg = blocks.moving_average_ff(32, 1, 4000, 1)
        self.det = det.blk(threshold=threshold, back=6, skip=decode_n - 1)
        self.dc_sub = blocks.sub_cc(1)
        self.dc_iir = filter.single_pole_iir_filter_cc((1e-4), 1)
        self.counter = counter.blk()
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
            "data symbols after the equalizer (24 subcarriers x 44 symbols per frame)", #name
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
        self.tabs_grid_layout_5.addWidget(self._const_eq_win, 0, 0, 2, 1)
        for r in range(0, 2):
            self.tabs_grid_layout_5.setRowStretch(r, 1)
        for c in range(0, 1):
            self.tabs_grid_layout_5.setColumnStretch(c, 1)
        self.coarse = coarse.blk(back=6)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.coarse, 0), (self.fine, 0))
        self.connect((self.counter, 1), (self.number_err, 0))
        self.connect((self.counter, 2), (self.number_frames, 0))
        self.connect((self.counter, 0), (self.number_ser, 0))
        self.connect((self.dc_iir, 0), (self.dc_sub, 1))
        self.connect((self.dc_sub, 0), (self.det, 0))
        self.connect((self.dc_sub, 0), (self.en_mag2, 0))
        self.connect((self.dc_sub, 0), (self.sc_delay, 0))
        self.connect((self.dc_sub, 0), (self.sc_mult, 0))
        self.connect((self.dc_sub, 0), (self.x_mag, 0))
        self.connect((self.det, 0), (self.coarse, 0))
        self.connect((self.en_avg, 0), (self.en_delay, 0))
        self.connect((self.en_avg, 0), (self.en_mult, 1))
        self.connect((self.en_delay, 0), (self.en_mult, 0))
        self.connect((self.en_eps, 0), (self.sc_div, 1))
        self.connect((self.en_mag2, 0), (self.en_avg, 0))
        self.connect((self.en_mag2, 0), (self.guard_avg, 0))
        self.connect((self.en_mult, 0), (self.guard_add, 0))
        self.connect((self.eq, 1), (self.time_sink_pilot, 0))
        self.connect((self.eq, 2), (self.time_sink_pilot, 1))
        self.connect((self.eq, 0), (self.v2s24, 0))
        self.connect((self.est, 1), (self.eq, 1))
        self.connect((self.est, 0), (self.eq, 0))
        self.connect((self.est, 1), (self.h_arg, 0))
        self.connect((self.est, 1), (self.h_mag, 0))
        self.connect((self.fft64, 0), (self.fft_scale, 0))
        self.connect((self.fft_avg, 0), (self.vec_fft, 0))
        self.connect((self.fft_mag, 0), (self.fft_avg, 0))
        self.connect((self.fft_scale, 0), (self.fft_mag, 0))
        self.connect((self.fft_scale, 0), (self.v2s64, 0))
        self.connect((self.fine, 0), (self.frame_mag, 0))
        self.connect((self.fine, 0), (self.keep64, 0))
        self.connect((self.fine, 1), (self.number_cfo, 0))
        self.connect((self.fine, 2), (self.number_ok, 0))
        self.connect((self.frame_mag, 0), (self.time_sink_frame, 0))
        self.connect((self.guard_add, 0), (self.en_eps, 0))
        self.connect((self.guard_avg, 0), (self.guard_sq, 0))
        self.connect((self.guard_avg, 0), (self.guard_sq, 1))
        self.connect((self.guard_k, 0), (self.guard_add, 1))
        self.connect((self.guard_sq, 0), (self.guard_k, 0))
        self.connect((self.h_arg, 0), (self.vec_harg, 0))
        self.connect((self.h_mag, 0), (self.vec_hmag, 0))
        self.connect((self.keep29, 0), (self.const_raw, 0))
        self.connect((self.keep29, 0), (self.s2v29, 0))
        self.connect((self.keep64, 0), (self.s2v64, 0))
        self.connect((self.rx_in, 0), (self.dc_iir, 0))
        self.connect((self.rx_in, 0), (self.dc_sub, 0))
        self.connect((self.rx_in, 0), (self.freq_sink_rx, 0))
        self.connect((self.s2v29, 0), (self.est, 0))
        self.connect((self.s2v64, 0), (self.fft64, 0))
        self.connect((self.sc_avg, 0), (self.det, 2))
        self.connect((self.sc_avg, 0), (self.sc_mag2, 0))
        self.connect((self.sc_conj, 0), (self.sc_mult, 1))
        self.connect((self.sc_delay, 0), (self.sc_conj, 0))
        self.connect((self.sc_div, 0), (self.det, 1))
        self.connect((self.sc_div, 0), (self.time_sink_m, 0))
        self.connect((self.sc_mag2, 0), (self.sc_div, 0))
        self.connect((self.sc_mult, 0), (self.sc_avg, 0))
        self.connect((self.slicer, 0), (self.counter, 0))
        self.connect((self.thr_src, 0), (self.time_sink_m, 1))
        self.connect((self.uhd_usrp_source_0, 0), (self.rx_in, 0))
        self.connect((self.v2s24, 0), (self.const_eq, 0))
        self.connect((self.v2s24, 0), (self.slicer, 0))
        self.connect((self.v2s64, 0), (self.keep29, 0))
        self.connect((self.x_mag, 0), (self.time_sink_rx, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "ofdm_b210_frame_rx")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_threshold(self):
        return self.threshold

    def set_threshold(self, threshold):
        self.threshold = threshold
        self.thr_src.set_offset(self.threshold)
        self.det.threshold = self.threshold

    def get_smooth(self):
        return self.smooth

    def set_smooth(self, smooth):
        self.smooth = smooth
        self.eq.smooth = self.smooth

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.uhd_usrp_source_0.set_samp_rate(self.samp_rate)
        self.freq_sink_rx.set_frequency_range(0, self.samp_rate)
        self.time_sink_rx.set_samp_rate(self.samp_rate)
        self.time_sink_m.set_samp_rate(self.samp_rate)
        self.time_sink_frame.set_samp_rate(self.samp_rate)
        self.time_sink_pilot.set_samp_rate(self.samp_rate / 80)

    def get_rx_gain(self):
        return self.rx_gain

    def set_rx_gain(self, rx_gain):
        self.rx_gain = rx_gain
        self.uhd_usrp_source_0.set_gain(self.rx_gain, 0)

    def get_guard_level(self):
        return self.guard_level

    def set_guard_level(self, guard_level):
        self.guard_level = guard_level
        self.guard_k.set_k(((self.guard_level * 32) ** 2))

    def get_freq(self):
        return self.freq

    def set_freq(self, freq):
        self.freq = freq
        self.uhd_usrp_source_0.set_center_freq(self.freq, 0)

    def get_decode_n(self):
        return self.decode_n

    def set_decode_n(self, decode_n):
        self.decode_n = decode_n
        self.det.skip = self.decode_n - 1

    def get_capture_file(self):
        return self.capture_file

    def set_capture_file(self, capture_file):
        self.capture_file = capture_file




def main(top_block_cls=ofdm_b210_frame_rx, options=None):

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
