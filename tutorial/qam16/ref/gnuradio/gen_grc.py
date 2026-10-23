import yaml, sys
from gnuradio.grc.core.utils import epy_block_io

TX_SRC = open('tx_block.py').read()
RX_SRC = open('rx_block.py').read()

def cache(src):
    return repr(tuple(epy_block_io.extract(src)))

class G:
    def __init__(self, gid, title, gui=True):
        self.id, self.title, self.blocks, self.conns, self.y = gid, title, [], [], {}
        self.gui = gui
    def add(self, bname, bid, xy, **params):
        io = params.pop('_io_cache', None)
        st = {'coordinate': list(xy), 'rotation': 0, 'state': 'enabled'}
        if io: st['_io_cache'] = io
        self.blocks.append({'name': bname, 'id': bid, 'parameters': {k: str(v) for k, v in params.items()}, 'states': st})
    def var(self, name, value, xy): self.add(name, 'variable', xy, comment='', value=value)
    def note(self, name, text, xy): self.add(name, 'note', xy, alias='', comment='', note=text)
    def conn(self, a, ap, b, bp): self.conns.append([a, str(ap), b, str(bp)])
    def save(self, path):
        d = {'options': {'parameters': {'author': '', 'category': 'Custom', 'cmake_opt': '', 'comment': '',
                'copyright': '', 'description': self.title, 'gen_cmake': 'On', 'gen_linking': 'dynamic',
                'generate_options': 'qt_gui' if self.gui else 'no_gui', 'hier_block_src_path': '.:',
                'id': self.id, 'max_nouts': '0', 'output_language': 'python', 'placement': '(0,0)',
                'qt_qss_theme': '', 'realtime_scheduling': '', 'run': 'True', 'run_command': '{python} -u {filename}',
                'run_options': 'prompt', 'sizing_mode': 'fixed', 'thread_safe_setters': '', 'title': self.title,
                'window_size': '(1200,900)'},
                'states': {'coordinate': [8, 8], 'rotation': 0, 'state': 'enabled'}},
             'blocks': self.blocks, 'connections': self.conns, 'metadata': {'file_format': 1, 'grc_version': '3.10.9.2'}}
        yaml.safe_dump(d, open(path, 'w'), default_flow_style=False, sort_keys=False, width=100)

COMMON_VARS = [('samp_rate', '1000000'), ('sps', '4'), ('symbol_rate', 'samp_rate/sps'), ('excess_bw', '0.35'), ('nfilts', '32'),
               ('freq', '2.4e9')]

def common(g):
    y = 80
    for n, v in COMMON_VARS:
        g.var(n, v, (8, y)); y += 64

def tx_chain(g, x0, y0, sink_kind):
    """frame source -> RRC interpolating filter -> amplitude -> sink"""
    g.add('tx_taps', 'variable_rrc_filter_taps', (200, 80), gain='sps', samp_rate='samp_rate', sym_rate='symbol_rate',
          alpha='excess_bw', ntaps='11*sps*1+1', comment='Transmit pulse shape (RRC, 4 sps, span 11 symbols)')
    g.add('tx_frames', 'epy_block', (x0, y0), _source_code=TX_SRC, seed='1', fixed_payload='True', _io_cache=cache(TX_SRC),
          comment='[CP 8 | ZC 63 | 14 x (63 x 16-QAM + 1 pilot)] = 967 symbols per frame, 1 sample/symbol')
    g.add('tx_rrc', 'interp_fir_filter_xxx', (x0 + 330, y0), type='ccf', interp='sps', taps='tx_taps', samp_delay='0',
          comment='pulse shaping, 1 sps -> 4 sps')
    g.add('tx_amp', 'blocks_multiply_const_vxx', (x0 + 600, y0), type='complex', const='0.3', vlen='1', comment='back-off / TX level')

def rx_chain(g, x0, y0, sink_hint=True):
    g.add('rx_taps', 'variable_rrc_filter_taps', (200, 144), gain='nfilts', samp_rate='nfilts*samp_rate', sym_rate='symbol_rate',
          alpha='excess_bw', ntaps='11*sps*nfilts', comment='Polyphase RRC bank for pfb_clock_sync (matched filter + timing)')
    g.add('rx_agc', 'analog_agc_xx', (x0, y0), type='complex', rate='1e-4', reference='0.5', gain='1.0', max_gain='65536',
          comment='1. AGC (slow: the 16-QAM envelope is not constant)')
    g.add('rx_fll', 'digital_fll_band_edge_cc', (x0 + 250, y0), type='cc', samps_per_sym='sps', rolloff='excess_bw', filter_size='2*sps+1' if False else '44',
          w='0.01', comment='2. Coarse CFO: band-edge FLL (leaves residual < Rs/(2*63) = 2 kHz for the sync word)')
    g.add('rx_timing', 'digital_pfb_clock_sync_xxx', (x0 + 500, y0), type='ccf', sps='sps', loop_bw='6.28/100.0', taps='rx_taps',
          filter_size='nfilts', init_phase='nfilts/2', max_dev='1.5', osps='1',
          comment='3. RRC matched filter + timing recovery, output 1 sps')
    g.add('rx_sync', 'epy_block', (x0 + 750, y0), _source_code=RX_SRC, symbol_rate='symbol_rate', loop_bw='0.02', thr_search='0.6',
          pilot_weight='3.0', check_payload='True', seed='1', print_every='100', _io_cache=cache(RX_SRC),
          comment='4. ZC frame sync (SEARCH->VERIFY->LOCKED) + carrier phase/gain from the sync word + pilot/decision-directed PLL. Output: 882 payload symbols per frame')
    g.conn('rx_agc', 0, 'rx_fll', 0); g.conn('rx_fll', 0, 'rx_timing', 0); g.conn('rx_timing', 0, 'rx_sync', 0)
    if sink_hint:
        g.add('rx_const', 'qtgui_const_sink_x', (x0 + 1050, y0), type='complex', name='"16-QAM after sync + PLL"', size='2048', grid='True',
              autoscale='False', ymin='-1.5', ymax='1.5', xmin='-1.5', xmax='1.5', nconnections='1', update_time='0.10',
              gui_hint='', tr_mode='qtgui.TRIG_MODE_FREE', tr_slope='qtgui.TRIG_SLOPE_POS', tr_level='0.0', tr_chan='0', tr_tag='""',
              legend='True', axislabels='True', label1='', width1='1', color1='"blue"', style1='0', marker1='0', alpha1='1.0')
        g.conn('rx_sync', 0, 'rx_const', 0)
        g.add('rx_const_pre', 'qtgui_const_sink_x', (x0 + 1050, y0 + 220), type='complex', name='"1 sps before sync (after timing)"', size='2048', grid='True',
              autoscale='False', ymin='-2', ymax='2', xmin='-2', xmax='2', nconnections='1', update_time='0.10',
              gui_hint='', tr_mode='qtgui.TRIG_MODE_FREE', tr_slope='qtgui.TRIG_SLOPE_POS', tr_level='0.0', tr_chan='0', tr_tag='""',
              legend='True', axislabels='True', label1='', width1='1', color1='"red"', style1='0', marker1='0', alpha1='1.0')
        g.conn('rx_timing', 0, 'rx_const_pre', 0)

def uhd_sink(g, xy):
    g.add('usrp_tx', 'uhd_usrp_sink', xy, type='fc32', otw='', stream_args='', stream_chans='[]', dev_addr='""', dev_args='""', sync='sync',
          start_time='-1.0', clock_rate='0.0', num_mboards='1', clock_source0='', time_source0='', sd_spec0='', nchan='1', samp_rate='samp_rate',
          center_freq0='freq', gain0='60', gain_type0='default', ant0='TX/RX', bw0='0', norm_gain0='False', lo_source0='internal', lo_export0='False',
          len_tag_name='', comment='B210 TX/RX port. Use an attenuator/cable for a wired test!')

def uhd_source(g, xy):
    g.add('usrp_rx', 'uhd_usrp_source', xy, type='fc32', otw='', stream_args='', stream_chans='[]', dev_addr='""', dev_args='""', sync='sync',
          start_time='-1.0', clock_rate='0.0', num_mboards='1', clock_source0='', time_source0='', sd_spec0='', nchan='1', samp_rate='samp_rate',
          center_freq0='freq', rx_agc0='Default', gain0='40', gain_type0='default', ant0='RX2', bw0='0', lo_source0='internal', lo_export0='False',
          dc_offs_enb0='default', dc_offs0='0j', iq_imbal_enb0='default', iq_imbal0='0j', norm_gain0='False', comment='B210 RX2 port')

# ---------------- TX ----------------
g = G('qam16_zc_tx', '16-QAM + Zadoff-Chu frame transmitter (USRP B210)')
common(g); tx_chain(g, 400, 200, 'uhd'); uhd_sink(g, (1250, 190))
g.conn('tx_frames', 0, 'tx_rrc', 0); g.conn('tx_rrc', 0, 'tx_amp', 0); g.conn('tx_amp', 0, 'usrp_tx', 0)
g.note('n1', 'Frame (967 symbols, 3.87 ms at 250 ksym/s): CP 8 | ZC 63 | 14 x (63 16-QAM + 1 pilot). Sync word and CP at average payload power.', (400, 330))
g.save('qam16_zc_tx.grc')

# ---------------- RX ----------------
g = G('qam16_zc_rx', '16-QAM + Zadoff-Chu frame receiver (USRP B210)')
common(g); uhd_source(g, (260, 220)); rx_chain(g, 600, 220)
g.conn('usrp_rx', 0, 'rx_agc', 0)
g.note('n1', 'Chain: AGC -> band-edge FLL -> RRC + polyphase timing -> ZC frame sync/PLL -> 16-QAM symbols. The status line (locked, frames, CFO, EVM, SER) is printed every 100 frames.', (600, 460))
g.save('qam16_zc_rx.grc')

# ---------------- loopback ----------------
g = G('qam16_zc_loopback', '16-QAM + Zadoff-Chu loopback (no hardware)')
common(g)
g.var('cfo_hz', '1500', (8, 400)); g.var('noise_v', '0.02', (8, 464)); g.var('clk_ppm', '10', (8, 528))
tx_chain(g, 260, 200, 'none')
g.add('chan', 'channels_channel_model', (1000, 190), noise_voltage='noise_v', freq_offset='cfo_hz/samp_rate', epsilon='1.0+clk_ppm*1e-6', taps='1.0',
      seed='0', block_tags='False', comment='AWGN + carrier offset + sample-clock offset')
g.add('thr', 'blocks_throttle', (1250, 190), type='complex', samples_per_second='samp_rate', vlen='1', ignoretag='True')
rx_chain(g, 260, 460)
g.conn('tx_frames', 0, 'tx_rrc', 0); g.conn('tx_rrc', 0, 'tx_amp', 0); g.conn('tx_amp', 0, 'chan', 0); g.conn('chan', 0, 'thr', 0); g.conn('thr', 0, 'rx_agc', 0)
g.save('qam16_zc_loopback.grc')
print('ok')
