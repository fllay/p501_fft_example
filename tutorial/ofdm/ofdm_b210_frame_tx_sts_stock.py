#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: B210 transmitter: OFDM frames with the 128-sample STS preamble, the data from the stock GNU Radio OFDM blocks
# Author: p501_fft_example
# Description: The B210 transmits the frame of the P501 receiver with the 128-sample STS (overlay p501_ofdm_rx_sts; 850 MHz, 3.84 MS/s): the preamble from a vector source, the 44 data symbols from the stock gr-digital blocks (chunks to symbols, OFDM carrier allocator, IFFT, cyclic prefixer), the idle slot of 32 samples, joined by a tagged stream mux.
# GNU Radio version: 3.10.12.0

from PyQt5 import Qt
from gnuradio import qtgui
from PyQt5 import QtCore
from PyQt5.QtCore import QObject, pyqtSlot
from gnuradio import analog
from gnuradio import blocks
from gnuradio import digital
from gnuradio import fft
from gnuradio.fft import window
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
import sip
import threading



class ofdm_b210_frame_tx_sts_stock(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "B210 transmitter: OFDM frames with the 128-sample STS preamble, the data from the stock GNU Radio OFDM blocks", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("B210 transmitter: OFDM frames with the 128-sample STS preamble, the data from the stock GNU Radio OFDM blocks")
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

        self.settings = Qt.QSettings("gnuradio/flowgraphs", "ofdm_b210_frame_tx_sts_stock")

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
        self.tx_amp = tx_amp = 0.25
        self.pilot_polarity = pilot_polarity = [-1, -1, -1, -1, -1, -1, -1, 1, 1, 1, 1, 1, 1, -1, 1, 1, 1, 1, 1, -1, -1, 1, 1, 1, 1, -1, 1, -1, 1, 1, 1, -1, -1, -1, -1, 1, 1, -1, 1, 1, 1, -1, 1, -1]
        self.tx_scale = tx_scale = tx_amp / (8 * 0.668721)
        self.tx_on = tx_on = 0
        self.tx_gain = tx_gain = 60
        self.samp_rate = samp_rate = 3840000
        self.preamble_samples = preamble_samples = [3.055050463j, 0j, (-0+1.265443336j), (-0+3.662737783j), 3.055050463j, 0j, -1.265443336j, 1.013731006j, 3.055050463j, 0j, -7.375544262j, -12.303725381j, -9.16515139j, 0j, (-0+7.375544262j), (-0+7.627256592j), 3.055050463j, 0j, (-0+1.265443336j), (-0+3.662737783j), 3.055050463j, 0j, -1.265443336j, 1.013731006j, 3.055050463j, 0j, -7.375544262j, -12.303725381j, -9.16515139j, 0j, (-0+7.375544262j), (-0+7.627256592j), 3.055050463j, 0j, (-0+1.265443336j), (-0+3.662737783j), 3.055050463j, 0j, -1.265443336j, 1.013731006j, 3.055050463j, 0j, -7.375544262j, -12.303725381j, -9.16515139j, 0j, (-0+7.375544262j), (-0+7.627256592j), 3.055050463j, 0j, (-0+1.265443336j), (-0+3.662737783j), 3.055050463j, 0j, -1.265443336j, 1.013731006j, 3.055050463j, 0j, -7.375544262j, -12.303725381j, -9.16515139j, 0j, (-0+7.375544262j), (-0+7.627256592j), 3.055050463j, 0j, (-0+1.265443336j), (-0+3.662737783j), 3.055050463j, 0j, -1.265443336j, 1.013731006j, 3.055050463j, 0j, -7.375544262j, -12.303725381j, -9.16515139j, 0j, (-0+7.375544262j), (-0+7.627256592j), 3.055050463j, 0j, (-0+1.265443336j), (-0+3.662737783j), 3.055050463j, 0j, -1.265443336j, 1.013731006j, 3.055050463j, 0j, -7.375544262j, -12.303725381j, -9.16515139j, 0j, (-0+7.375544262j), (-0+7.627256592j), 3.055050463j, 0j, (-0+1.265443336j), (-0+3.662737783j), 3.055050463j, 0j, -1.265443336j, 1.013731006j, 3.055050463j, 0j, -7.375544262j, -12.303725381j, -9.16515139j, 0j, (-0+7.375544262j), (-0+7.627256592j), 3.055050463j, 0j, (-0+1.265443336j), (-0+3.662737783j), 3.055050463j, 0j, -1.265443336j, 1.013731006j, 3.055050463j, 0j, -7.375544262j, -12.303725381j, -9.16515139j, 0j, (-0+7.375544262j), (-0+7.627256592j), (1.414213562-5.656854249j), (3.82596343-6.344152676j), (0.736064958-2.459096554j), (-4.352851698-0.370352313j), (-6.15432203-3.07192983j), (-3.594217809-5.900513181j), (-0.041880602-3.732032249j), (1.31705065+1.057343847j), (0.414213562+1.828427125j), (-1.318335704-2.647894806j), (-3.368322263-6.239551035j), (-5.613930276-3.766319299j), (-6.665723819+2.471347365j), (-4.923052165+6.336819696j), (-1.479470678+5.297618727j), (-0.072137357+1.710711654j), (-2.828427125-1.414213562j), (-7.01343444-2.805014404j), (-7.632302381-1.924802493j), (-3.169400875+0.979475894j), (2.775829235+3.388955165j), (6.002152583+2.221216839j), (6.304684422-1.57915577j), (6.242577601-2.877714446j), (6.414213562+1j), (4.395436322+5.680987331j), (-0.946227068+5.005221894j), (-6.108506294-0.379194642j), (-6.065141355-3.685055759j), (-0.38665805-1.505089947j), (5.711388008+1.644360676j), (7.123780937+0.511896432j), (4.242640687-2.828427125j), (1.408132422-2.311434862j), (1.048633847+2.438171812j), (1.394587711+4.908093235j), (0.15432203+1.07192983j), (-1.692566848-4.518238804j), (-1.438336333-4.88109368j), (0.991261859+0.024108815j), (2.414213562+3.828427125j), (0.604643647+2.429444514j), (-2.542497062-1.764611155j), (-3.350946859-4.435622199j), (-0.99113043-4.471347365j), (1.842133835-2.983988665j), (2.756239332-0.380010927j), (2.437946399+2.831836995j), (2.828427125+4.242640687j), (3.944122989+1.904781282j), (4.190749327-2.054272766j), (3.353916722-3.352432416j), (3.224170765-1.388955165j), (4.510883933-0.090184171j), (4.832386762-1.8077183j), (1.61389429-3.429990076j), (-3.585786438-1j), (-5.846528665+4.093283622j), (-2.799807857+6.998940296j), (1.84713157+6.41635174j), (2.408287105+5.685055759j), (-1.75867548+6.439978235j), (-5.331302412+5.438031525j), (-3.654374379+0.171806778j), (1.414213562-5.656854249j), (3.82596343-6.344152676j), (0.736064958-2.459096554j), (-4.352851698-0.370352313j), (-6.15432203-3.07192983j), (-3.594217809-5.900513181j), (-0.041880602-3.732032249j), (1.31705065+1.057343847j), (0.414213562+1.828427125j), (-1.318335704-2.647894806j), (-3.368322263-6.239551035j), (-5.613930276-3.766319299j), (-6.665723819+2.471347365j), (-4.923052165+6.336819696j), (-1.479470678+5.297618727j), (-0.072137357+1.710711654j), (-2.828427125-1.414213562j), (-7.01343444-2.805014404j), (-7.632302381-1.924802493j), (-3.169400875+0.979475894j), (2.775829235+3.388955165j), (6.002152583+2.221216839j), (6.304684422-1.57915577j), (6.242577601-2.877714446j), (6.414213562+1j), (4.395436322+5.680987331j), (-0.946227068+5.005221894j), (-6.108506294-0.379194642j), (-6.065141355-3.685055759j), (-0.38665805-1.505089947j), (5.711388008+1.644360676j), (7.123780937+0.511896432j), (4.242640687-2.828427125j), (1.408132422-2.311434862j), (1.048633847+2.438171812j), (1.394587711+4.908093235j), (0.15432203+1.07192983j), (-1.692566848-4.518238804j), (-1.438336333-4.88109368j), (0.991261859+0.024108815j), (2.414213562+3.828427125j), (0.604643647+2.429444514j), (-2.542497062-1.764611155j), (-3.350946859-4.435622199j), (-0.99113043-4.471347365j), (1.842133835-2.983988665j), (2.756239332-0.380010927j), (2.437946399+2.831836995j), (2.828427125+4.242640687j), (3.944122989+1.904781282j), (4.190749327-2.054272766j), (3.353916722-3.352432416j), (3.224170765-1.388955165j), (4.510883933-0.090184171j), (4.832386762-1.8077183j), (1.61389429-3.429990076j), (-3.585786438-1j), (-5.846528665+4.093283622j), (-2.799807857+6.998940296j), (1.84713157+6.41635174j), (2.408287105+5.685055759j), (-1.75867548+6.439978235j), (-5.331302412+5.438031525j), (-3.654374379+0.171806778j), (1.414213562-5.656854249j), (3.82596343-6.344152676j), (0.736064958-2.459096554j), (-4.352851698-0.370352313j), (-6.15432203-3.07192983j), (-3.594217809-5.900513181j), (-0.041880602-3.732032249j), (1.31705065+1.057343847j), (0.414213562+1.828427125j), (-1.318335704-2.647894806j), (-3.368322263-6.239551035j), (-5.613930276-3.766319299j), (-6.665723819+2.471347365j), (-4.923052165+6.336819696j), (-1.479470678+5.297618727j), (-0.072137357+1.710711654j), (-2.828427125-1.414213562j), (-7.01343444-2.805014404j), (-7.632302381-1.924802493j), (-3.169400875+0.979475894j), (2.775829235+3.388955165j), (6.002152583+2.221216839j), (6.304684422-1.57915577j), (6.242577601-2.877714446j), (6.414213562+1j), (4.395436322+5.680987331j), (-0.946227068+5.005221894j), (-6.108506294-0.379194642j), (-6.065141355-3.685055759j), (-0.38665805-1.505089947j), (5.711388008+1.644360676j), (7.123780937+0.511896432j)]
        self.pilot_symbols = pilot_symbols = tuple(tuple(p * v for v in ((0.707106781187+0.707106781187j), (0.707106781187-0.707106781187j), (-0.707106781187+0.707106781187j), (-0.707106781187-0.707106781187j))) for p in pilot_polarity)
        self.pilot_carriers = pilot_carriers = ([-11, -4, 4, 11],)
        self.payload_points = payload_points = [((-3, -1, 3, 1)[i >> 2] + 1j * (-3, -1, 3, 1)[i & 3]) / 10 ** 0.5 for i in range(16)]
        self.payload_nibbles = payload_nibbles = [15, 15, 15, 14, 0, 0, 0, 4, 0, 0, 1, 8, 0, 0, 5, 0, 0, 1, 14, 0, 0, 4, 4, 0, 1, 9, 8, 0, 5, 5, 0, 1, 15, 14, 0, 4, 0, 4, 1, 8, 1, 8, 5, 0, 5, 1, 14, 1, 14, 4, 4, 4, 5, 9, 9, 9, 13, 5, 5, 4, 15, 15, 15, 10, 0, 0, 1, 12, 0, 0, 4, 8, 0, 1, 11, 0, 0, 5, 10, 0, 1, 13, 12, 0, 4, 12, 8, 1, 10, 11, 0, 5, 15, 10, 1, 12, 1, 12, 4, 8, 4, 9, 11, 1, 11, 5, 10, 5, 11, 13, 13, 13, 8, 12, 12, 13, 2, 10, 10, 14, 15, 15, 14, 6, 0, 0, 5, 4, 0, 1, 15, 8, 0, 4, 1, 0, 1, 8, 6, 0, 5, 1, 4, 1, 14, 7, 8, 4, 5, 1, 1, 9, 14, 6, 5, 4, 5, 5, 15, 9, 15, 12, 1, 4, 0, 8, 7, 8, 3, 1, 1, 0, 10, 6, 6, 3, 13, 5, 4, 8, 15, 15, 11, 2, 0, 1, 10, 12, 0, 5, 14, 8, 1, 12, 7, 0, 4, 9, 2, 1, 11, 6, 12, 5, 11, 6, 9, 13, 11, 7, 4, 13, 11, 3, 10, 13, 10, 9, 14, 13, 15, 4, 6, 12, 3, 9, 6, 8, 9, 7, 7, 3, 7, 3, 2, 11, 2, 10, 15, 10, 15, 14, 1, 14, 0, 4, 4, 4, 1, 9, 9, 8, 5, 5, 5, 1, 15, 15, 14, 4, 0, 0, 5, 8, 0, 1, 13, 0, 0, 4, 14, 0, 1, 10, 4, 0, 5, 13, 8, 1, 12, 13, 0, 4, 10, 14, 1, 11, 14, 4, 5, 8, 5, 9, 13, 1, 13, 4, 14, 4, 15, 10, 5, 10, 1, 13, 13, 12, 4, 12, 12, 9, 10, 10, 11, 5, 15, 15, 11, 12, 0, 1, 8, 8, 0, 5, 3, 0, 1, 14, 10, 0, 4, 7, 12, 1, 9, 0, 8, 5, 6, 3, 1, 15, 4, 10, 4, 3, 11, 13, 8, 9, 8, 13, 3, 5, 2, 14, 11, 14, 14, 7, 8, 6, 5, 1, 1, 5, 14, 6, 7, 12, 5, 5, 0, 9, 15, 14, 3, 4, 0, 4, 11, 8, 1, 11, 9, 0, 5, 9, 6, 1, 13, 7, 4, 4, 15, 3, 9, 10, 2, 9, 5, 12, 15, 7, 12, 10, 3, 0, 11, 12, 10, 3, 8, 11, 12, 9, 3, 8, 11, 6, 9, 3, 11, 7, 6, 9, 11, 3, 7, 5, 10, 11, 3, 13, 15, 10, 8, 12, 1, 15, 2, 8, 4, 2, 15, 1, 8, 14, 2, 5, 2, 4, 13, 14, 13, 10, 12, 6, 13, 14, 9, 6, 12, 7, 7, 6, 9, 3, 3, 7, 6, 10, 11, 3, 7, 15, 10, 11, 0, 1, 15, 10, 0, 4, 1, 12, 1, 8, 4, 8, 5, 1, 11, 1, 14, 5, 10, 4, 5, 13, 13, 9, 12, 12, 13, 4, 10, 10, 15, 11, 15, 14, 1, 8, 0, 4, 5, 0, 1, 9, 14, 0, 5, 4, 4, 1, 15, 9, 8, 4, 1, 5, 1, 8, 7, 14, 5, 1, 0, 5, 14, 6, 1, 12, 5, 4, 4, 9, 15, 9, 11, 4, 1, 5, 11, 8, 7, 13, 9, 1, 0, 13, 6, 6, 2, 15, 5, 4, 14, 3, 15, 10, 4, 8, 1, 13, 11, 0, 4, 13, 10, 1, 10, 13, 12, 5, 14, 12, 9, 12, 6, 11, 4, 9, 7, 11, 11, 7, 1, 9, 11, 2, 5, 5, 10, 13, 15, 13, 14, 12, 0, 12, 6, 8, 2, 9, 7, 0, 15, 7, 2, 2, 3, 2, 12, 12, 10, 14, 10, 11, 14, 7, 15, 8, 5, 0, 1, 1, 14, 0, 6, 4, 4, 1, 5, 9, 8, 7, 13, 5, 1, 0, 15, 14, 6, 2, 0, 5, 4, 12, 1, 15, 10, 8, 4, 1, 15, 1, 8, 4, 2, 5, 1, 8, 13, 14, 5, 2, 12, 5, 14, 14, 9, 12, 6, 7, 4, 9, 5, 3, 11, 7, 14, 9, 11, 0, 7, 5, 10, 1, 3, 13, 12, 6, 8, 12, 9, 7, 2, 11, 7, 2, 15, 11, 2, 14, 1, 10, 14, 4, 5, 14, 5, 9, 12, 5, 13, 4, 9, 12, 15, 11, 4, 10, 1, 11, 11, 12, 5, 9, 8, 9, 13, 5, 3, 4, 15, 14, 11, 10, 0, 7, 9, 12, 1, 1, 4, 8, 6, 7, 11, 1, 5, 1, 10, 7, 14, 5, 13, 0, 5, 12, 14, 1, 12, 10, 4, 4, 11, 13, 9, 11, 8, 13, 5, 9, 2, 15, 13, 6, 14, 0, 15, 6, 4, 2, 3, 5, 8, 12, 11, 13, 2, 11, 8, 14, 15, 9, 2, 6, 1, 6, 13, 4, 7, 6, 15, 9, 3, 6, 1, 6, 11, 4, 7, 7, 11, 9, 3, 1, 9, 6, 10, 5, 7, 7, 13, 15, 3, 0, 12, 2, 10, 2, 8, 15, 12, 15, 2, 0, 10, 2, 12, 3, 12, 14, 8, 8, 10, 7, 3, 3, 13, 2, 10, 8, 14, 15, 15, 2, 6, 0, 2, 13, 4, 0, 14, 15, 8, 2, 6, 1, 0, 13, 4, 6, 2, 15, 9, 4, 14, 1, 7, 10, 4, 7, 1, 13, 9, 2, 4, 13, 6, 13, 10, 15, 6, 13, 14, 3, 6, 12, 4, 11, 6, 9, 11, 11, 7, 5, 9, 11, 3, 13, 5, 10, 8, 15, 13, 15, 2, 0, 12, 2, 12, 2, 8, 14, 8, 15, 2, 7, 2, 2, 13, 2, 12, 14, 14, 14, 10, 6, 6, 7, 13, 5, 5, 0, 15, 15, 14, 2, 0, 0, 4, 12, 0, 1, 10, 8, 0, 5, 15, 0, 1, 12, 2, 0, 4, 8, 12, 1, 11, 2, 8, 5, 10, 15, 1, 13, 14, 2, 4, 12, 4, 13, 10, 9, 10, 13, 15, 5, 14, 12, 3, 12, 6, 8, 8, 9, 7, 3, 3, 7, 2, 10, 11, 2, 15, 15, 10, 14, 0, 1, 14, 4, 0, 4, 5, 8, 1, 9, 13, 0, 5, 4, 14, 1, 15, 10, 4, 4, 1, 13, 9, 8, 4, 13, 5, 1, 10, 15, 14, 5]
        self.occupied_carriers = occupied_carriers = ([-14, -13, -12, -10, -9, -8, -7, -6, -5, -3, -2, -1, 1, 2, 3, 5, 6, 7, 8, 9, 10, 12, 13, 14],)
        self.length_tag_key = length_tag_key = "packet_len"
        self.freq = freq = 850e6
        self.fft_len = fft_len = 64
        self.cp_len = cp_len = 16

        ##################################################
        # Blocks
        ##################################################

        # Create the options list
        self._tx_on_options = [0, 1]
        # Create the labels list
        self._tx_on_labels = ['OFF', 'ON']
        # Create the combo box
        # Create the radio buttons
        self._tx_on_group_box = Qt.QGroupBox("Transmit (B210 TX/RX port)" + ": ")
        self._tx_on_box = Qt.QVBoxLayout()
        class variable_chooser_button_group(Qt.QButtonGroup):
            def __init__(self, parent=None):
                Qt.QButtonGroup.__init__(self, parent)
            @pyqtSlot(int)
            def updateButtonChecked(self, button_id):
                self.button(button_id).setChecked(True)
        self._tx_on_button_group = variable_chooser_button_group()
        self._tx_on_group_box.setLayout(self._tx_on_box)
        for i, _label in enumerate(self._tx_on_labels):
            radio_button = Qt.QRadioButton(_label)
            self._tx_on_box.addWidget(radio_button)
            self._tx_on_button_group.addButton(radio_button, i)
        self._tx_on_callback = lambda i: Qt.QMetaObject.invokeMethod(self._tx_on_button_group, "updateButtonChecked", Qt.Q_ARG("int", self._tx_on_options.index(i)))
        self._tx_on_callback(self.tx_on)
        self._tx_on_button_group.buttonClicked[int].connect(
            lambda i: self.set_tx_on(self._tx_on_options[i]))
        self.top_grid_layout.addWidget(self._tx_on_group_box, 0, 0, 1, 1)
        for r in range(0, 1):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 1):
            self.top_grid_layout.setColumnStretch(c, 1)
        self._tx_gain_range = qtgui.Range(0, 86, 1, 60, 200)
        self._tx_gain_win = qtgui.RangeWidget(self._tx_gain_range, self.set_tx_gain, "B210 TX gain (dB)", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._tx_gain_win, 0, 1, 1, 3)
        for r in range(0, 1):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(1, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.tabs = Qt.QTabWidget()
        self.tabs_widget_0 = Qt.QWidget()
        self.tabs_layout_0 = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom, self.tabs_widget_0)
        self.tabs_grid_layout_0 = Qt.QGridLayout()
        self.tabs_layout_0.addLayout(self.tabs_grid_layout_0)
        self.tabs.addTab(self.tabs_widget_0, '1 Data symbols')
        self.tabs_widget_1 = Qt.QWidget()
        self.tabs_layout_1 = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom, self.tabs_widget_1)
        self.tabs_grid_layout_1 = Qt.QGridLayout()
        self.tabs_layout_1.addLayout(self.tabs_grid_layout_1)
        self.tabs.addTab(self.tabs_widget_1, '2 Subcarriers')
        self.tabs_widget_2 = Qt.QWidget()
        self.tabs_layout_2 = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom, self.tabs_widget_2)
        self.tabs_grid_layout_2 = Qt.QGridLayout()
        self.tabs_layout_2.addLayout(self.tabs_grid_layout_2)
        self.tabs.addTab(self.tabs_widget_2, '3 Frame in time')
        self.tabs_widget_3 = Qt.QWidget()
        self.tabs_layout_3 = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom, self.tabs_widget_3)
        self.tabs_grid_layout_3 = Qt.QGridLayout()
        self.tabs_layout_3.addLayout(self.tabs_grid_layout_3)
        self.tabs.addTab(self.tabs_widget_3, '4 Spectrum')
        self.top_grid_layout.addWidget(self.tabs, 2, 0, 1, 4)
        for r in range(2, 3):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.x_mag = blocks.complex_to_mag(1)
        self.vec_sub = qtgui.vector_sink_f(
            64,
            (-32),
            1,
            "subcarrier k",
            "|X[k]|",
            "|X[k]| per subcarrier before the IFFT (mean of the 44 data symbols of a frame): 24 data subcarriers and the 4 pilots",
            1, # Number of inputs
            None # parent
        )
        self.vec_sub.set_update_time(0.1)
        self.vec_sub.set_y_axis(0, 2)
        self.vec_sub.enable_autoscale(False)
        self.vec_sub.enable_grid(True)
        self.vec_sub.set_x_axis_units("")
        self.vec_sub.set_y_axis_units("")
        self.vec_sub.set_ref_level(0)


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
                self.vec_sub.set_line_label(i, "Data {0}".format(i))
            else:
                self.vec_sub.set_line_label(i, labels[i])
            self.vec_sub.set_line_width(i, widths[i])
            self.vec_sub.set_line_color(i, colors[i])
            self.vec_sub.set_line_alpha(i, alphas[i])

        self._vec_sub_win = sip.wrapinstance(self.vec_sub.qwidget(), Qt.QWidget)
        self.tabs_grid_layout_1.addWidget(self._vec_sub_win, 0, 0, 1, 1)
        for r in range(0, 1):
            self.tabs_grid_layout_1.setRowStretch(r, 1)
        for c in range(0, 1):
            self.tabs_grid_layout_1.setColumnStretch(c, 1)
        self.v_mag = blocks.complex_to_mag(64)
        self.v_avg = blocks.moving_average_ff(44, (1.0 / 44), 4000, 64)
        self.uhd_usrp_sink_0 = uhd.usrp_sink(
            ",".join(('', 'num_send_frames=128,num_recv_frames=128,send_frame_size=16360,recv_frame_size=16360')),
            uhd.stream_args(
                cpu_format="fc32",
                args='',
                channels=list(range(0,1)),
            ),
            "",
        )
        self.uhd_usrp_sink_0.set_samp_rate(samp_rate)
        self.uhd_usrp_sink_0.set_time_unknown_pps(uhd.time_spec(0))

        self.uhd_usrp_sink_0.set_center_freq(freq, 0)
        self.uhd_usrp_sink_0.set_antenna('TX/RX', 0)
        self.uhd_usrp_sink_0.set_gain(tx_gain, 0)
        self._tx_amp_range = qtgui.Range(0, 0.29, 0.01, 0.25, 200)
        self._tx_amp_win = qtgui.RangeWidget(self._tx_amp_range, self.set_tx_amp, "TX digital amplitude (RMS of the active part)", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._tx_amp_win, 1, 0, 1, 4)
        for r in range(1, 2):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.to_frame = blocks.stream_to_tagged_stream(gr.sizeof_char, 1, len(payload_nibbles), length_tag_key)
        self.time_sink = qtgui.time_sink_f(
            8192, #size
            samp_rate, #samp_rate
            "the frame as the B210 sends it: |x| (two frames of 3840 samples = 1 ms each: the STS, the training symbols, the 44 data symbols, a gap of 32 samples)", #name
            1, #number of inputs
            None # parent
        )
        self.time_sink.set_update_time(0.1)
        self.time_sink.set_y_axis(0, 1.0)

        self.time_sink.set_y_label('Amplitude', "")

        self.time_sink.enable_tags(False)
        self.time_sink.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.time_sink.enable_autoscale(True)
        self.time_sink.enable_grid(True)
        self.time_sink.enable_axis_labels(True)
        self.time_sink.enable_control_panel(False)
        self.time_sink.enable_stem_plot(False)

        self.time_sink.disable_legend()

        labels = ["|x|", 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
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
                self.time_sink.set_line_label(i, "Data {0}".format(i))
            else:
                self.time_sink.set_line_label(i, labels[i])
            self.time_sink.set_line_width(i, widths[i])
            self.time_sink.set_line_color(i, colors[i])
            self.time_sink.set_line_style(i, styles[i])
            self.time_sink.set_line_marker(i, markers[i])
            self.time_sink.set_line_alpha(i, alphas[i])

        self._time_sink_win = sip.wrapinstance(self.time_sink.qwidget(), Qt.QWidget)
        self.tabs_grid_layout_2.addWidget(self._time_sink_win, 0, 0, 1, 1)
        for r in range(0, 1):
            self.tabs_grid_layout_2.setRowStretch(r, 1)
        for c in range(0, 1):
            self.tabs_grid_layout_2.setColumnStretch(c, 1)
        self.scale = blocks.multiply_const_cc(tx_scale * tx_on)
        self.pre_tag = blocks.stream_to_tagged_stream(gr.sizeof_gr_complex, 1, len(preamble_samples), length_tag_key)
        self.pre_src = blocks.vector_source_c(preamble_samples, True, 1, [])
        self.payload_src = blocks.vector_source_b(payload_nibbles, True, 1, [])
        self.mux = blocks.tagged_stream_mux(gr.sizeof_gr_complex*1, length_tag_key, 0)
        self.mux.set_min_output_buffer(32768)
        self.mapper = digital.chunks_to_symbols_bc(payload_points, 1)
        self.ifft = fft.fft_vcc(fft_len, False, (), True, 1)
        self.idle_tag = blocks.stream_to_tagged_stream(gr.sizeof_gr_complex, 1, 32, length_tag_key)
        self.idle_src = analog.sig_source_c(0, analog.GR_CONST_WAVE, 0, 0, 0)
        self.gate = blocks.tag_gate(gr.sizeof_gr_complex * 1, False)
        self.gate.set_single_key("")
        self.freq_sink = qtgui.freq_sink_c(
            2048, #size
            window.WIN_BLACKMAN_hARRIS, #wintype
            0, #fc
            samp_rate, #bw
            "spectrum sent to the B210: 28 subcarriers of 60 kHz = 1.7 MHz", #name
            1,
            None # parent
        )
        self.freq_sink.set_update_time(0.1)
        self.freq_sink.set_y_axis((-100), 20)
        self.freq_sink.set_y_label('Relative Gain', 'dB')
        self.freq_sink.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
        self.freq_sink.enable_autoscale(False)
        self.freq_sink.enable_grid(True)
        self.freq_sink.set_fft_average(0.2)
        self.freq_sink.enable_axis_labels(True)
        self.freq_sink.enable_control_panel(False)
        self.freq_sink.set_fft_window_normalized(False)

        self.freq_sink.disable_legend()


        labels = ['TX', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.freq_sink.set_line_label(i, "Data {0}".format(i))
            else:
                self.freq_sink.set_line_label(i, labels[i])
            self.freq_sink.set_line_width(i, widths[i])
            self.freq_sink.set_line_color(i, colors[i])
            self.freq_sink.set_line_alpha(i, alphas[i])

        self._freq_sink_win = sip.wrapinstance(self.freq_sink.qwidget(), Qt.QWidget)
        self.tabs_grid_layout_3.addWidget(self._freq_sink_win, 0, 0, 1, 1)
        for r in range(0, 1):
            self.tabs_grid_layout_3.setRowStretch(r, 1)
        for c in range(0, 1):
            self.tabs_grid_layout_3.setColumnStretch(c, 1)
        self.cp = digital.ofdm_cyclic_prefixer(
            fft_len,
            fft_len + cp_len,
            0,
            length_tag_key)
        self.cp.set_min_output_buffer(32768)
        self.const_data = qtgui.const_sink_c(
            1056, #size
            "the 16-QAM symbols of the payload (24 per OFDM symbol)", #name
            1, #number of inputs
            None # parent
        )
        self.const_data.set_update_time(0.1)
        self.const_data.set_y_axis((-1.6), 1.6)
        self.const_data.set_x_axis((-1.6), 1.6)
        self.const_data.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, "")
        self.const_data.enable_autoscale(False)
        self.const_data.enable_grid(True)
        self.const_data.enable_axis_labels(True)

        self.const_data.disable_legend()

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
                self.const_data.set_line_label(i, "Data {0}".format(i))
            else:
                self.const_data.set_line_label(i, labels[i])
            self.const_data.set_line_width(i, widths[i])
            self.const_data.set_line_color(i, colors[i])
            self.const_data.set_line_style(i, styles[i])
            self.const_data.set_line_marker(i, markers[i])
            self.const_data.set_line_alpha(i, alphas[i])

        self._const_data_win = sip.wrapinstance(self.const_data.qwidget(), Qt.QWidget)
        self.tabs_grid_layout_0.addWidget(self._const_data_win, 0, 0, 1, 1)
        for r in range(0, 1):
            self.tabs_grid_layout_0.setRowStretch(r, 1)
        for c in range(0, 1):
            self.tabs_grid_layout_0.setColumnStretch(c, 1)
        self.alloc = digital.ofdm_carrier_allocator_cvc( fft_len, occupied_carriers, pilot_carriers, pilot_symbols, (), length_tag_key, True)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.alloc, 0), (self.ifft, 0))
        self.connect((self.alloc, 0), (self.v_mag, 0))
        self.connect((self.cp, 0), (self.mux, 1))
        self.connect((self.gate, 0), (self.uhd_usrp_sink_0, 0))
        self.connect((self.idle_src, 0), (self.idle_tag, 0))
        self.connect((self.idle_tag, 0), (self.mux, 2))
        self.connect((self.ifft, 0), (self.cp, 0))
        self.connect((self.mapper, 0), (self.alloc, 0))
        self.connect((self.mapper, 0), (self.const_data, 0))
        self.connect((self.mux, 0), (self.scale, 0))
        self.connect((self.payload_src, 0), (self.to_frame, 0))
        self.connect((self.pre_src, 0), (self.pre_tag, 0))
        self.connect((self.pre_tag, 0), (self.mux, 0))
        self.connect((self.scale, 0), (self.freq_sink, 0))
        self.connect((self.scale, 0), (self.gate, 0))
        self.connect((self.scale, 0), (self.x_mag, 0))
        self.connect((self.to_frame, 0), (self.mapper, 0))
        self.connect((self.v_avg, 0), (self.vec_sub, 0))
        self.connect((self.v_mag, 0), (self.v_avg, 0))
        self.connect((self.x_mag, 0), (self.time_sink, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "ofdm_b210_frame_tx_sts_stock")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_tx_amp(self):
        return self.tx_amp

    def set_tx_amp(self, tx_amp):
        self.tx_amp = tx_amp
        self.set_tx_scale(self.tx_amp / (8 * 0.668721))

    def get_pilot_polarity(self):
        return self.pilot_polarity

    def set_pilot_polarity(self, pilot_polarity):
        self.pilot_polarity = pilot_polarity
        self.set_pilot_symbols(tuple(tuple(p * v for v in ((0.707106781187+0.707106781187j), (0.707106781187-0.707106781187j), (-0.707106781187+0.707106781187j), (-0.707106781187-0.707106781187j))) for p in self.pilot_polarity))

    def get_tx_scale(self):
        return self.tx_scale

    def set_tx_scale(self, tx_scale):
        self.tx_scale = tx_scale
        self.scale.set_k(self.tx_scale * self.tx_on)

    def get_tx_on(self):
        return self.tx_on

    def set_tx_on(self, tx_on):
        self.tx_on = tx_on
        self._tx_on_callback(self.tx_on)
        self.scale.set_k(self.tx_scale * self.tx_on)

    def get_tx_gain(self):
        return self.tx_gain

    def set_tx_gain(self, tx_gain):
        self.tx_gain = tx_gain
        self.uhd_usrp_sink_0.set_gain(self.tx_gain, 0)

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.uhd_usrp_sink_0.set_samp_rate(self.samp_rate)
        self.time_sink.set_samp_rate(self.samp_rate)
        self.freq_sink.set_frequency_range(0, self.samp_rate)

    def get_preamble_samples(self):
        return self.preamble_samples

    def set_preamble_samples(self, preamble_samples):
        self.preamble_samples = preamble_samples
        self.pre_src.set_data(self.preamble_samples, [])
        self.pre_tag.set_packet_len(len(self.preamble_samples))
        self.pre_tag.set_packet_len_pmt(len(self.preamble_samples))

    def get_pilot_symbols(self):
        return self.pilot_symbols

    def set_pilot_symbols(self, pilot_symbols):
        self.pilot_symbols = pilot_symbols

    def get_pilot_carriers(self):
        return self.pilot_carriers

    def set_pilot_carriers(self, pilot_carriers):
        self.pilot_carriers = pilot_carriers

    def get_payload_points(self):
        return self.payload_points

    def set_payload_points(self, payload_points):
        self.payload_points = payload_points
        self.mapper.set_symbol_table(self.payload_points)

    def get_payload_nibbles(self):
        return self.payload_nibbles

    def set_payload_nibbles(self, payload_nibbles):
        self.payload_nibbles = payload_nibbles
        self.payload_src.set_data(self.payload_nibbles, [])
        self.to_frame.set_packet_len(len(self.payload_nibbles))
        self.to_frame.set_packet_len_pmt(len(self.payload_nibbles))

    def get_occupied_carriers(self):
        return self.occupied_carriers

    def set_occupied_carriers(self, occupied_carriers):
        self.occupied_carriers = occupied_carriers

    def get_length_tag_key(self):
        return self.length_tag_key

    def set_length_tag_key(self, length_tag_key):
        self.length_tag_key = length_tag_key

    def get_freq(self):
        return self.freq

    def set_freq(self, freq):
        self.freq = freq
        self.uhd_usrp_sink_0.set_center_freq(self.freq, 0)

    def get_fft_len(self):
        return self.fft_len

    def set_fft_len(self, fft_len):
        self.fft_len = fft_len

    def get_cp_len(self):
        return self.cp_len

    def set_cp_len(self, cp_len):
        self.cp_len = cp_len




def main(top_block_cls=ofdm_b210_frame_tx_sts_stock, options=None):

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
