"""
Unit tests for pickeringInterface.py — no physical hardware required.

Strategy: inject fake `pilxi` and `pi620lx` modules into sys.modules *before*
importing pickeringInterface, so no ctypes DLLs are touched.

Run from the project root:
    python -m pytest pickeringControls/test_pickeringInterface.py -v
  or directly:
    python pickeringControls/test_pickeringInterface.py
"""

import sys
import os
import unittest
from unittest.mock import MagicMock
from types import ModuleType

# ── Fake pilxi module ─────────────────────────────────────────────────────────

class _FakePilxiError(Exception):
    def __init__(self, message, errorCode=None):
        self.message = message
        self.errorCode = errorCode
    def __str__(self):
        return self.message

_fake_pilxi = ModuleType("pilxi")
_fake_pilxi.Error = _FakePilxiError

_fake_wf_types = MagicMock()
_fake_wf_types.PIFGLX_WAVEFORM_SINE = 0x0
_fake_pilxi.WaveformTypes = _fake_wf_types

_fake_pilxi.Pi_Session = MagicMock()

sys.modules.pop("pilxi", None)
sys.modules["pilxi"] = _fake_pilxi

# ── Fake pi620lx module ───────────────────────────────────────────────────────

_fake_pi620lx = ModuleType("pi620lx")
sys.modules.pop("pi620lx", None)
sys.modules["pi620lx"] = _fake_pi620lx

# ── Import module under test ──────────────────────────────────────────────────

sys.path.insert(0, os.path.dirname(__file__))
sys.modules.pop("pickeringInterface", None)
import pickeringInterface as pi


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_card():
    return MagicMock()

def _make_wave(channel=1, frequency=1000.0, amplitude=1.0, offset=0.5, phase=0.0):
    return pi.waveAtributes(channel=channel, frequency=frequency,
                            amplitude=amplitude, offset=offset, phase=phase)


# ── initPXIE tests ────────────────────────────────────────────────────────────

class TestInitPXIE(unittest.TestCase):

    def setUp(self):
        self.mock_session = MagicMock()
        self.mock_session.FindFreeCards.return_value = []
        _fake_pilxi.Pi_Session.return_value = self.mock_session

    def test_no_free_cards_returns_empty_list(self):
        result = pi.initPXIE()
        self.assertEqual(result, [])

    def test_one_card_returns_three_wave_attributes(self):
        card = _make_card()
        self.mock_session.FindFreeCards.return_value = [(1, 2)]
        self.mock_session.OpenCard.return_value = card

        result = pi.initPXIE()

        self.assertEqual(len(result), 3)
        for wave in result:
            self.assertIsInstance(wave, pi.waveAtributes)
            self.assertIs(wave._card, card)

    def test_two_cards_return_six_wave_attributes(self):
        card1, card2 = _make_card(), _make_card()
        self.mock_session.FindFreeCards.return_value = [(1, 1), (2, 2)]
        self.mock_session.OpenCard.side_effect = [card1, card2]

        result = pi.initPXIE()

        self.assertEqual(len(result), 6)

    def test_card_channels_are_numbered_1_to_3(self):
        card = _make_card()
        self.mock_session.FindFreeCards.return_value = [(1, 1)]
        self.mock_session.OpenCard.return_value = card

        result = pi.initPXIE()

        self.assertEqual([w.getChannel() for w in result], [1, 2, 3])

    def test_card_is_cleared_on_open(self):
        card = _make_card()
        self.mock_session.FindFreeCards.return_value = [(1, 1)]
        self.mock_session.OpenCard.return_value = card

        pi.initPXIE()

        card.ClearCard.assert_called_once()

    def test_open_card_error_skips_card(self):
        self.mock_session.FindFreeCards.return_value = [(1, 2)]
        self.mock_session.OpenCard.side_effect = _FakePilxiError("open failed")

        result = pi.initPXIE()

        self.assertEqual(result, [])

    def test_first_card_error_still_opens_second(self):
        card2 = _make_card()
        self.mock_session.FindFreeCards.return_value = [(1, 1), (2, 2)]
        self.mock_session.OpenCard.side_effect = [_FakePilxiError("fail"), card2]

        result = pi.initPXIE()

        self.assertEqual(len(result), 3)
        for wave in result:
            self.assertIs(wave._card, card2)


# ── updateWaveform tests ──────────────────────────────────────────────────────

class TestUpdateWaveform(unittest.TestCase):

    def test_none_card_returns_without_calling_hardware(self):
        wave = _make_wave()
        pi.updateWaveform(None, wave)  # must not raise

    def test_valid_call_invokes_all_pifglx_methods(self):
        card = _make_card()
        wave = _make_wave(channel=1, frequency=1000.0, amplitude=2.5,
                          offset=1.0, phase=45.0)
        pi.updateWaveform(card, wave)

        card.PIFGLX_AbortGeneration.assert_called_once_with(1)
        card.PIFGLX_SetWaveform.assert_called_once()
        card.PIFGLX_SetAmplitude.assert_called_once_with(1, 2.5)
        card.PIFGLX_SetFrequency.assert_called_once_with(1, 1000.0)
        card.PIFGLX_SetDcOffset.assert_called_once_with(1, 1.0)
        card.PIFGLX_SetStartPhase.assert_called_once_with(1, 45.0)
        card.PIFGLX_InitiateGeneration.assert_called_once_with(1)

    def test_offset_below_zero_sets_dc_offset_to_zero(self):
        card = _make_card()
        wave = _make_wave(channel=2, offset=-0.1)
        pi.updateWaveform(card, wave)
        card.PIFGLX_SetDcOffset.assert_called_once_with(2, 0)

    def test_offset_above_five_sets_dc_offset_to_zero(self):
        card = _make_card()
        wave = _make_wave(channel=2, offset=5.1)
        pi.updateWaveform(card, wave)
        card.PIFGLX_SetDcOffset.assert_called_once_with(2, 0)

    def test_offset_at_zero_is_accepted(self):
        card = _make_card()
        wave = _make_wave(offset=0.0)
        pi.updateWaveform(card, wave)
        card.PIFGLX_SetDcOffset.assert_called_once_with(1, 0.0)

    def test_offset_at_five_is_accepted(self):
        card = _make_card()
        wave = _make_wave(offset=5.0)
        pi.updateWaveform(card, wave)
        card.PIFGLX_SetDcOffset.assert_called_once_with(1, 5.0)

    def test_pilxi_error_is_caught_and_does_not_propagate(self):
        card = _make_card()
        card.PIFGLX_AbortGeneration.side_effect = _FakePilxiError("hardware fault")
        wave = _make_wave()
        pi.updateWaveform(card, wave)  # must not raise
        card.PIFGLX_SetWaveform.assert_not_called()

    def test_pilxi_error_on_initiate_is_caught(self):
        card = _make_card()
        card.PIFGLX_InitiateGeneration.side_effect = _FakePilxiError("initiate failed")
        wave = _make_wave()
        pi.updateWaveform(card, wave)  # must not raise
        card.PIFGLX_AbortGeneration.assert_called_once()
        card.PIFGLX_SetWaveform.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
