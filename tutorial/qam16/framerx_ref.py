"""Loads the handoff's floating-point golden model FrameRx (ref/gnuradio/rx_block.py) without GNU Radio (a stub `gr` is used when gnuradio is not installed).
    from framerx_ref import R          # R.FrameRx, R.tone_freq, ...
"""
import importlib.util, os, sys, types

HERE = os.path.dirname(os.path.abspath(__file__))
try:
    import gnuradio  # noqa: F401
except ImportError:
    gr = types.ModuleType("gnuradio.gr"); gr.basic_block = type("basic_block", (), {"__init__": lambda self, **k: None}); gr.sync_block = gr.basic_block
    pkg = types.ModuleType("gnuradio"); pkg.gr = gr
    sys.modules["gnuradio"] = pkg; sys.modules["gnuradio.gr"] = gr
_spec = importlib.util.spec_from_file_location("rx_block_ref", os.path.join(HERE, "ref", "gnuradio", "rx_block.py"))
R = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(R)
