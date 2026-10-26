#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: B210 receiver: 16-QAM frames of the P501's FPGA transmitter, decoded with GNU Radio
# Author: p501_fft_example
# Description: The B210 receives the 16-QAM frames of the P501's FPGA transmitter at 915 MHz and decodes them (Zadoff-Chu frame sync, PLL, PRBS-15 check): constellation, symbol error rate, EVM.
# GNU Radio version: 3.10.12.0

from PyQt5 import Qt
from gnuradio import qtgui
from PyQt5 import QtCore
from PyQt5.QtCore import QObject, pyqtSlot
from gnuradio import analog
from gnuradio import blocks
from gnuradio import digital
from gnuradio import gr
from gnuradio.filter import firdes
from gnuradio.fft import window
import sys
import signal
from PyQt5 import Qt
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import uhd
import time
import qam16_b210_frame_rx_epy_block_0 as epy_block_0  # embedded python block
import sip
import threading



class qam16_b210_frame_rx(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "B210 receiver: 16-QAM frames of the P501's FPGA transmitter, decoded with GNU Radio", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("B210 receiver: 16-QAM frames of the P501's FPGA transmitter, decoded with GNU Radio")
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

        self.settings = Qt.QSettings("gnuradio/flowgraphs", "qam16_b210_frame_rx")

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
        self.sps = sps = 4
        self.nfilts = nfilts = 32
        self.excess_bw = excess_bw = 0.35
        self.samp_rate = samp_rate = 3840000
        self.rx_gain = rx_gain = 45
        self.rrc_taps = rrc_taps = firdes.root_raised_cosine(nfilts, nfilts*sps, 1.0, excess_bw, 11*int(sps*nfilts))
        self.freq = freq = 915e6
        self.fll_on = fll_on = 1
        self.fll_div = fll_div = 1600
        self.const_dqpsk = const_dqpsk = digital.constellation_dqpsk().base()
        self.bw_div = bw_div = 400

        ##################################################
        # Blocks
        ##################################################

        self._rx_gain_range = qtgui.Range(0, 76, 1, 45, 200)
        self._rx_gain_win = qtgui.RangeWidget(self._rx_gain_range, self.set_rx_gain, "B210 RX gain (dB)", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._rx_gain_win, 0, 0, 1, 4)
        for r in range(0, 1):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        # Create the options list
        self._fll_on_options = [0, 1]
        # Create the labels list
        self._fll_on_labels = ['OFF', 'ON']
        # Create the combo box
        # Create the radio buttons
        self._fll_on_group_box = Qt.QGroupBox("FLL band-edge" + ": ")
        self._fll_on_box = Qt.QVBoxLayout()
        class variable_chooser_button_group(Qt.QButtonGroup):
            def __init__(self, parent=None):
                Qt.QButtonGroup.__init__(self, parent)
            @pyqtSlot(int)
            def updateButtonChecked(self, button_id):
                self.button(button_id).setChecked(True)
        self._fll_on_button_group = variable_chooser_button_group()
        self._fll_on_group_box.setLayout(self._fll_on_box)
        for i, _label in enumerate(self._fll_on_labels):
            radio_button = Qt.QRadioButton(_label)
            self._fll_on_box.addWidget(radio_button)
            self._fll_on_button_group.addButton(radio_button, i)
        self._fll_on_callback = lambda i: Qt.QMetaObject.invokeMethod(self._fll_on_button_group, "updateButtonChecked", Qt.Q_ARG("int", self._fll_on_options.index(i)))
        self._fll_on_callback(self.fll_on)
        self._fll_on_button_group.buttonClicked[int].connect(
            lambda i: self.set_fll_on(self._fll_on_options[i]))
        self.top_grid_layout.addWidget(self._fll_on_group_box, 2, 0, 1, 1)
        for r in range(2, 3):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 1):
            self.top_grid_layout.setColumnStretch(c, 1)
        self._fll_div_range = qtgui.Range(100, 6400, 100, 1600, 200)
        self._fll_div_win = qtgui.RangeWidget(self._fll_div_range, self.set_fll_div, "FLL bandwidth: 2 pi / N", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._fll_div_win, 1, 2, 1, 2)
        for r in range(1, 2):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(2, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        self._bw_div_range = qtgui.Range(100, 1600, 50, 400, 200)
        self._bw_div_win = qtgui.RangeWidget(self._bw_div_range, self.set_bw_div, "Timing loop bandwidth: 2 pi / N", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._bw_div_win, 1, 0, 1, 2)
        for r in range(1, 2):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 2):
            self.top_grid_layout.setColumnStretch(c, 1)
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
        self.qtgui_number_sink_4 = qtgui.number_sink(
            gr.sizeof_float,
            0.0,
            qtgui.NUM_GRAPH_NONE,
            1,
            None # parent
        )
        self.qtgui_number_sink_4.set_update_time(0.25)
        self.qtgui_number_sink_4.set_title("carrier offset left for the PLL (Hz)")

        labels = ['offset', '', '', '', '',
            '', '', '', '', '']
        units = ['', '', '', '', '',
            '', '', '', '', '']
        colors = [("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"),
            ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black")]
        factor = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]

        for i in range(1):
            self.qtgui_number_sink_4.set_min(i, -20000)
            self.qtgui_number_sink_4.set_max(i, 20000)
            self.qtgui_number_sink_4.set_color(i, colors[i][0], colors[i][1])
            if len(labels[i]) == 0:
                self.qtgui_number_sink_4.set_label(i, "Data {0}".format(i))
            else:
                self.qtgui_number_sink_4.set_label(i, labels[i])
            self.qtgui_number_sink_4.set_unit(i, units[i])
            self.qtgui_number_sink_4.set_factor(i, factor[i])

        self.qtgui_number_sink_4.enable_autoscale(False)
        self._qtgui_number_sink_4_win = sip.wrapinstance(self.qtgui_number_sink_4.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_number_sink_4_win, 3, 4, 1, 2)
        for r in range(3, 4):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(4, 6):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.qtgui_number_sink_3 = qtgui.number_sink(
            gr.sizeof_float,
            0.0,
            qtgui.NUM_GRAPH_NONE,
            1,
            None # parent
        )
        self.qtgui_number_sink_3.set_update_time(0.25)
        self.qtgui_number_sink_3.set_title("frames decoded")

        labels = ['frames', '', '', '', '',
            '', '', '', '', '']
        units = ['', '', '', '', '',
            '', '', '', '', '']
        colors = [("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"),
            ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black")]
        factor = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]

        for i in range(1):
            self.qtgui_number_sink_3.set_min(i, 0)
            self.qtgui_number_sink_3.set_max(i, 100000000)
            self.qtgui_number_sink_3.set_color(i, colors[i][0], colors[i][1])
            if len(labels[i]) == 0:
                self.qtgui_number_sink_3.set_label(i, "Data {0}".format(i))
            else:
                self.qtgui_number_sink_3.set_label(i, labels[i])
            self.qtgui_number_sink_3.set_unit(i, units[i])
            self.qtgui_number_sink_3.set_factor(i, factor[i])

        self.qtgui_number_sink_3.enable_autoscale(True)
        self._qtgui_number_sink_3_win = sip.wrapinstance(self.qtgui_number_sink_3.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_number_sink_3_win, 2, 4, 1, 2)
        for r in range(2, 3):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(4, 6):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.qtgui_number_sink_2 = qtgui.number_sink(
            gr.sizeof_float,
            0.0,
            qtgui.NUM_GRAPH_NONE,
            1,
            None # parent
        )
        self.qtgui_number_sink_2.set_update_time(0.25)
        self.qtgui_number_sink_2.set_title("lock (1 = locked on the frames)")

        labels = ['lock', '', '', '', '',
            '', '', '', '', '']
        units = ['', '', '', '', '',
            '', '', '', '', '']
        colors = [("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"),
            ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black")]
        factor = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]

        for i in range(1):
            self.qtgui_number_sink_2.set_min(i, 0)
            self.qtgui_number_sink_2.set_max(i, 1)
            self.qtgui_number_sink_2.set_color(i, colors[i][0], colors[i][1])
            if len(labels[i]) == 0:
                self.qtgui_number_sink_2.set_label(i, "Data {0}".format(i))
            else:
                self.qtgui_number_sink_2.set_label(i, labels[i])
            self.qtgui_number_sink_2.set_unit(i, units[i])
            self.qtgui_number_sink_2.set_factor(i, factor[i])

        self.qtgui_number_sink_2.enable_autoscale(False)
        self._qtgui_number_sink_2_win = sip.wrapinstance(self.qtgui_number_sink_2.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_number_sink_2_win, 2, 2, 1, 2)
        for r in range(2, 3):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(2, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.qtgui_number_sink_1 = qtgui.number_sink(
            gr.sizeof_float,
            0.0,
            qtgui.NUM_GRAPH_NONE,
            1,
            None # parent
        )
        self.qtgui_number_sink_1.set_update_time(0.25)
        self.qtgui_number_sink_1.set_title("EVM of the last frame (dB)")

        labels = ['EVM', '', '', '', '',
            '', '', '', '', '']
        units = ['', '', '', '', '',
            '', '', '', '', '']
        colors = [("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"),
            ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black")]
        factor = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]

        for i in range(1):
            self.qtgui_number_sink_1.set_min(i, -40)
            self.qtgui_number_sink_1.set_max(i, 0)
            self.qtgui_number_sink_1.set_color(i, colors[i][0], colors[i][1])
            if len(labels[i]) == 0:
                self.qtgui_number_sink_1.set_label(i, "Data {0}".format(i))
            else:
                self.qtgui_number_sink_1.set_label(i, labels[i])
            self.qtgui_number_sink_1.set_unit(i, units[i])
            self.qtgui_number_sink_1.set_factor(i, factor[i])

        self.qtgui_number_sink_1.enable_autoscale(False)
        self._qtgui_number_sink_1_win = sip.wrapinstance(self.qtgui_number_sink_1.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_number_sink_1_win, 3, 2, 1, 2)
        for r in range(3, 4):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(2, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.qtgui_number_sink_0 = qtgui.number_sink(
            gr.sizeof_float,
            0.0,
            qtgui.NUM_GRAPH_NONE,
            1,
            None # parent
        )
        self.qtgui_number_sink_0.set_update_time(0.25)
        self.qtgui_number_sink_0.set_title("symbol error rate")

        labels = ['SER', '', '', '', '',
            '', '', '', '', '']
        units = ['', '', '', '', '',
            '', '', '', '', '']
        colors = [("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"),
            ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black")]
        factor = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]

        for i in range(1):
            self.qtgui_number_sink_0.set_min(i, 0)
            self.qtgui_number_sink_0.set_max(i, 1)
            self.qtgui_number_sink_0.set_color(i, colors[i][0], colors[i][1])
            if len(labels[i]) == 0:
                self.qtgui_number_sink_0.set_label(i, "Data {0}".format(i))
            else:
                self.qtgui_number_sink_0.set_label(i, labels[i])
            self.qtgui_number_sink_0.set_unit(i, units[i])
            self.qtgui_number_sink_0.set_factor(i, factor[i])

        self.qtgui_number_sink_0.enable_autoscale(False)
        self._qtgui_number_sink_0_win = sip.wrapinstance(self.qtgui_number_sink_0.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_number_sink_0_win, 3, 0, 1, 2)
        for r in range(3, 4):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 2):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.qtgui_freq_sink_x_0 = qtgui.freq_sink_c(
            2048, #size
            window.WIN_BLACKMAN_hARRIS, #wintype
            0, #fc
            samp_rate, #bw
            "received spectrum", #name
            1,
            None # parent
        )
        self.qtgui_freq_sink_x_0.set_update_time(0.1)
        self.qtgui_freq_sink_x_0.set_y_axis((-120), 0)
        self.qtgui_freq_sink_x_0.set_y_label('Relative Gain', 'dB')
        self.qtgui_freq_sink_x_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
        self.qtgui_freq_sink_x_0.enable_autoscale(False)
        self.qtgui_freq_sink_x_0.enable_grid(True)
        self.qtgui_freq_sink_x_0.set_fft_average(0.2)
        self.qtgui_freq_sink_x_0.enable_axis_labels(True)
        self.qtgui_freq_sink_x_0.enable_control_panel(False)
        self.qtgui_freq_sink_x_0.set_fft_window_normalized(False)

        self.qtgui_freq_sink_x_0.disable_legend()


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
                self.qtgui_freq_sink_x_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_freq_sink_x_0.set_line_label(i, labels[i])
            self.qtgui_freq_sink_x_0.set_line_width(i, widths[i])
            self.qtgui_freq_sink_x_0.set_line_color(i, colors[i])
            self.qtgui_freq_sink_x_0.set_line_alpha(i, alphas[i])

        self._qtgui_freq_sink_x_0_win = sip.wrapinstance(self.qtgui_freq_sink_x_0.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_freq_sink_x_0_win, 8, 0, 4, 6)
        for r in range(8, 12):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 6):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.qtgui_const_sink_x_0 = qtgui.const_sink_c(
            2048, #size
            "data symbols after the PLL", #name
            1, #number of inputs
            None # parent
        )
        self.qtgui_const_sink_x_0.set_update_time(0.1)
        self.qtgui_const_sink_x_0.set_y_axis((-1.6), 1.6)
        self.qtgui_const_sink_x_0.set_x_axis((-1.6), 1.6)
        self.qtgui_const_sink_x_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, "")
        self.qtgui_const_sink_x_0.enable_autoscale(False)
        self.qtgui_const_sink_x_0.enable_grid(True)
        self.qtgui_const_sink_x_0.enable_axis_labels(True)

        self.qtgui_const_sink_x_0.disable_legend()

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
                self.qtgui_const_sink_x_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_const_sink_x_0.set_line_label(i, labels[i])
            self.qtgui_const_sink_x_0.set_line_width(i, widths[i])
            self.qtgui_const_sink_x_0.set_line_color(i, colors[i])
            self.qtgui_const_sink_x_0.set_line_style(i, styles[i])
            self.qtgui_const_sink_x_0.set_line_marker(i, markers[i])
            self.qtgui_const_sink_x_0.set_line_alpha(i, alphas[i])

        self._qtgui_const_sink_x_0_win = sip.wrapinstance(self.qtgui_const_sink_x_0.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_const_sink_x_0_win, 4, 0, 4, 2)
        for r in range(4, 8):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 2):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.epy_block_0 = epy_block_0.blk(loop_bw=0.02, thr_search=0.6, thr_lock=0.45, pilot_weight=3.0, aided=True, symbol_rate=samp_rate/sps)
        self.digital_pfb_clock_sync_xxx_0 = digital.pfb_clock_sync_ccf(sps, (2*3.14159265/bw_div), rrc_taps, nfilts, (nfilts//2), 0.05, 1)
        self.digital_fll_band_edge_cc_0 = digital.fll_band_edge_cc(sps, excess_bw, 55, (2*3.14159265/fll_div*fll_on))
        self.blocks_null_sink_5 = blocks.null_sink(gr.sizeof_float*1)
        self.blocks_null_sink_4 = blocks.null_sink(gr.sizeof_float*1)
        self.blocks_null_sink_3 = blocks.null_sink(gr.sizeof_float*1)
        self.blocks_null_sink_2 = blocks.null_sink(gr.sizeof_float*1)
        self.blocks_null_sink_1 = blocks.null_sink(gr.sizeof_float*1)
        self.blocks_null_sink_0 = blocks.null_sink(gr.sizeof_float*1)
        self.blocks_float_to_complex_0 = blocks.float_to_complex(1)
        self.blocks_complex_to_float_0 = blocks.complex_to_float(1)
        self.analog_rail_ff_1 = analog.rail_ff((-3), 3)
        self.analog_rail_ff_0 = analog.rail_ff((-3), 3)
        self.analog_agc2_xx_0 = analog.agc2_cc(0.06, (1e-3), 0.947, 1, 200)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.analog_agc2_xx_0, 0), (self.blocks_complex_to_float_0, 0))
        self.connect((self.analog_rail_ff_0, 0), (self.blocks_float_to_complex_0, 0))
        self.connect((self.analog_rail_ff_1, 0), (self.blocks_float_to_complex_0, 1))
        self.connect((self.blocks_complex_to_float_0, 0), (self.analog_rail_ff_0, 0))
        self.connect((self.blocks_complex_to_float_0, 1), (self.analog_rail_ff_1, 0))
        self.connect((self.blocks_float_to_complex_0, 0), (self.digital_fll_band_edge_cc_0, 0))
        self.connect((self.digital_fll_band_edge_cc_0, 1), (self.blocks_null_sink_0, 0))
        self.connect((self.digital_fll_band_edge_cc_0, 2), (self.blocks_null_sink_1, 0))
        self.connect((self.digital_fll_band_edge_cc_0, 3), (self.blocks_null_sink_2, 0))
        self.connect((self.digital_fll_band_edge_cc_0, 0), (self.digital_pfb_clock_sync_xxx_0, 0))
        self.connect((self.digital_pfb_clock_sync_xxx_0, 1), (self.blocks_null_sink_3, 0))
        self.connect((self.digital_pfb_clock_sync_xxx_0, 2), (self.blocks_null_sink_4, 0))
        self.connect((self.digital_pfb_clock_sync_xxx_0, 3), (self.blocks_null_sink_5, 0))
        self.connect((self.digital_pfb_clock_sync_xxx_0, 0), (self.epy_block_0, 0))
        self.connect((self.epy_block_0, 0), (self.qtgui_const_sink_x_0, 0))
        self.connect((self.epy_block_0, 1), (self.qtgui_number_sink_0, 0))
        self.connect((self.epy_block_0, 2), (self.qtgui_number_sink_1, 0))
        self.connect((self.epy_block_0, 3), (self.qtgui_number_sink_2, 0))
        self.connect((self.epy_block_0, 4), (self.qtgui_number_sink_3, 0))
        self.connect((self.epy_block_0, 5), (self.qtgui_number_sink_4, 0))
        self.connect((self.uhd_usrp_source_0, 0), (self.analog_agc2_xx_0, 0))
        self.connect((self.uhd_usrp_source_0, 0), (self.qtgui_freq_sink_x_0, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "qam16_b210_frame_rx")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_sps(self):
        return self.sps

    def set_sps(self, sps):
        self.sps = sps
        self.set_rrc_taps(firdes.root_raised_cosine(self.nfilts, self.nfilts*self.sps, 1.0, self.excess_bw, 11*int(self.sps*self.nfilts)))

    def get_nfilts(self):
        return self.nfilts

    def set_nfilts(self, nfilts):
        self.nfilts = nfilts
        self.set_rrc_taps(firdes.root_raised_cosine(self.nfilts, self.nfilts*self.sps, 1.0, self.excess_bw, 11*int(self.sps*self.nfilts)))

    def get_excess_bw(self):
        return self.excess_bw

    def set_excess_bw(self, excess_bw):
        self.excess_bw = excess_bw
        self.set_rrc_taps(firdes.root_raised_cosine(self.nfilts, self.nfilts*self.sps, 1.0, self.excess_bw, 11*int(self.sps*self.nfilts)))

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.qtgui_freq_sink_x_0.set_frequency_range(0, self.samp_rate)
        self.uhd_usrp_source_0.set_samp_rate(self.samp_rate)

    def get_rx_gain(self):
        return self.rx_gain

    def set_rx_gain(self, rx_gain):
        self.rx_gain = rx_gain
        self.uhd_usrp_source_0.set_gain(self.rx_gain, 0)

    def get_rrc_taps(self):
        return self.rrc_taps

    def set_rrc_taps(self, rrc_taps):
        self.rrc_taps = rrc_taps
        self.digital_pfb_clock_sync_xxx_0.update_taps(self.rrc_taps)

    def get_freq(self):
        return self.freq

    def set_freq(self, freq):
        self.freq = freq
        self.uhd_usrp_source_0.set_center_freq(self.freq, 0)

    def get_fll_on(self):
        return self.fll_on

    def set_fll_on(self, fll_on):
        self.fll_on = fll_on
        self._fll_on_callback(self.fll_on)
        self.digital_fll_band_edge_cc_0.set_loop_bandwidth((2*3.14159265/self.fll_div*self.fll_on))

    def get_fll_div(self):
        return self.fll_div

    def set_fll_div(self, fll_div):
        self.fll_div = fll_div
        self.digital_fll_band_edge_cc_0.set_loop_bandwidth((2*3.14159265/self.fll_div*self.fll_on))

    def get_const_dqpsk(self):
        return self.const_dqpsk

    def set_const_dqpsk(self, const_dqpsk):
        self.const_dqpsk = const_dqpsk

    def get_bw_div(self):
        return self.bw_div

    def set_bw_div(self, bw_div):
        self.bw_div = bw_div
        self.digital_pfb_clock_sync_xxx_0.set_loop_bandwidth((2*3.14159265/self.bw_div))




def main(top_block_cls=qam16_b210_frame_rx, options=None):

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
