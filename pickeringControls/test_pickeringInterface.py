"""
Unit tests for pickeringInterface.py — no physical hardware required.

Strategy: inject fake `pilxi` and `pi620lx` modules into sys.modules *before*
importing pickeringInterface, so no ctypes DLLs are touched. pilxi is only
used for the LXI session (Pi_Session/GetSessionID); all card discovery and
control goes through the fake pi620lx.Base/Card.

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

# ── Fake pilxi module (session only — no OpenCard/FindFreeCards anymore) ──────

class _FakePilxiError(Exception):
    def __init__(self, message, errorCode=None):
        self.message = message
        self.errorCode = errorCode
    def __str__(self):
        return self.message

_fake_pilxi = ModuleType("pilxi")
_fake_pilxi.Error = _FakePilxiError
_fake_pilxi.Pi_Session = MagicMock()

sys.modules.pop("pilxi", None)
sys.modules["pilxi"] = _fake_pilxi

# ── Fake pi620lx module ───────────────────────────────────────────────────────

class _FakePi620Error(Exception):
    def __init__(self, message, errorCode=None):
        self.message = message
        self.errorCode = errorCode
    def __str__(self):
        return self.message

_fake_pi620lx = ModuleType("pi620lx")
_fake_pi620lx.Error = _FakePi620Error
_fake_pi620lx.Base = MagicMock()

sys.modules.pop("pi620lx", None)
sys.modules["pi620lx"] = _fake_pi620lx

# ── Import module under test ──────────────────────────────────────────────────

sys.path.insert(0, os.path.dirname(__file__))
sys.modules.pop("pickeringInterface", None)
import pickeringInterface as pi


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_card():
    card = MagicMock()
    card.triggerSources = {"FRONT": 0}
    card.triggerModes = {"CONT": 6}
    return card

def _make_wave(channel=1, frequency=1000.0, amplitude=1.0, offset=0.5, phase=0.0):
    return pi.waveAtributes(channel=channel, frequency=frequency,
                            amplitude=amplitude, offset=offset, phase=phase)


# ── amplitude volts<->dB conversion tests ─────────────────────────────────────

class TestAmplitudeVolts(unittest.TestCase):
    def test_full_scale_volts_is_zero_db(self):
        wave = _make_wave()
        wave.setAmplitudeVolts(20.0)
        self.assertAlmostEqual(wave.getAmplitude(), 0.0)
        self.assertAlmostEqual(wave.getAmplitudeVolts(), 20.0)

    def test_half_scale_volts_is_six_db(self):
        wave = _make_wave()
        wave.setAmplitudeVolts(10.0)
        self.assertAlmostEqual(wave.getAmplitude(), 20 * 0.30103, places=3)
        self.assertAlmostEqual(wave.getAmplitudeVolts(), 10.0, places=3)

    def test_volts_above_full_scale_clamps_to_zero_db(self):
        wave = _make_wave()
        wave.setAmplitudeVolts(50.0)
        self.assertAlmostEqual(wave.getAmplitude(), 0.0)

    def test_zero_or_negative_volts_clamps_to_max_attenuation(self):
        wave = _make_wave()
        wave.setAmplitudeVolts(0.0)
        self.assertAlmostEqual(wave.getAmplitude(), 40.0)


# ── initPXIE tests ────────────────────────────────────────────────────────────

class TestInitPXIE(unittest.TestCase):

    def setUp(self):
        self.mock_session = MagicMock()
        self.mock_session.GetSessionID.return_value = 1
        _fake_pilxi.Pi_Session.return_value = self.mock_session

        self.mock_base = MagicMock()
        self.mock_base.findCards.return_value = []
        _fake_pi620lx.Base.return_value = self.mock_base

    def test_no_cards_returns_empty_list(self):
        session, result = pi.initPXIE()
        self.assertEqual(result, [])

    def test_returns_the_session_used_to_open_cards(self):
        session, result = pi.initPXIE()
        self.assertIs(session, self.mock_session)

    def test_one_card_returns_three_wave_attributes(self):
        card = _make_card()
        self.mock_base.findCards.return_value = [(1, 2)]
        self.mock_base.openCard.return_value = card

        session, result = pi.initPXIE()

        self.assertEqual(len(result), 3)
        for wave in result:
            self.assertIsInstance(wave, pi.waveAtributes)
            self.assertIs(wave._card, card)

    def test_two_cards_return_six_wave_attributes(self):
        card1, card2 = _make_card(), _make_card()
        self.mock_base.findCards.return_value = [(1, 1), (2, 2)]
        self.mock_base.openCard.side_effect = [card1, card2]

        session, result = pi.initPXIE()

        self.assertEqual(len(result), 6)

    def test_card_channels_are_numbered_1_to_3(self):
        card = _make_card()
        self.mock_base.findCards.return_value = [(1, 1)]
        self.mock_base.openCard.return_value = card

        session, result = pi.initPXIE()

        self.assertEqual([w.getChannel() for w in result], [1, 2, 3])

    def test_card_is_stamped_with_bus_and_device(self):
        card = _make_card()
        self.mock_base.findCards.return_value = [(3, 4)]
        self.mock_base.openCard.return_value = card

        pi.initPXIE()

        self.assertEqual(card._bus, 3)
        self.assertEqual(card._device, 4)

    def test_open_card_error_skips_card(self):
        self.mock_base.findCards.return_value = [(1, 2)]
        self.mock_base.openCard.side_effect = _FakePi620Error("open failed")

        session, result = pi.initPXIE()

        self.assertEqual(result, [])

    def test_first_card_error_still_opens_second(self):
        card2 = _make_card()
        self.mock_base.findCards.return_value = [(1, 1), (2, 2)]
        self.mock_base.openCard.side_effect = [_FakePi620Error("fail"), card2]

        session, result = pi.initPXIE()

        self.assertEqual(len(result), 3)
        for wave in result:
            self.assertIs(wave._card, card2)

    def test_get_session_id_error_returns_session_and_empty_list(self):
        self.mock_session.GetSessionID.side_effect = _FakePilxiError("no session")

        session, result = pi.initPXIE()

        self.assertIs(session, self.mock_session)
        self.assertEqual(result, [])

    def test_find_cards_error_returns_session_and_empty_list(self):
        self.mock_base.findCards.side_effect = _FakePi620Error("find failed")

        session, result = pi.initPXIE()

        self.assertIs(session, self.mock_session)
        self.assertEqual(result, [])


# ── updateWaveform tests ──────────────────────────────────────────────────────

class TestUpdateWaveform(unittest.TestCase):

    def test_none_card_returns_without_calling_hardware(self):
        wave = _make_wave()
        pi.updateWaveform(None, wave)  # must not raise

    def test_valid_call_invokes_expected_pi620lx_methods(self):
        card = _make_card()
        wave = _make_wave(channel=1, frequency=1000.0, amplitude=2.5,
                          offset=1.0, phase=45.0)
        pi.updateWaveform(card, wave)

        card.setActiveChannel.assert_called_once_with(1)
        card.outputOff.assert_called_once()
        card.setTriggerMode.assert_called_once_with(0, 6)
        card.setOutputOffsetVoltage.assert_called_once_with(1.0, True)
        card.setAttenuation.assert_called_once_with(2.5)
        # frequency is Hz on waveAtributes, converted to kHz for generateSignal()
        card.generateSignal.assert_called_once_with(
            1.0, pi._WAVEFORM_TYPE_SINE, 50.0, startPhaseOffset=45.0, generate=False)
        card.outputOn.assert_called_once()

    def test_offset_below_negative_five_is_clamped_to_zero(self):
        card = _make_card()
        wave = _make_wave(channel=2, offset=-5.1)
        pi.updateWaveform(card, wave)
        card.setOutputOffsetVoltage.assert_called_once_with(0.0, True)

    def test_offset_above_five_is_clamped_to_zero(self):
        card = _make_card()
        wave = _make_wave(channel=2, offset=5.1)
        pi.updateWaveform(card, wave)
        card.setOutputOffsetVoltage.assert_called_once_with(0.0, True)

    def test_offset_at_negative_five_is_accepted(self):
        card = _make_card()
        wave = _make_wave(offset=-5.0)
        pi.updateWaveform(card, wave)
        card.setOutputOffsetVoltage.assert_called_once_with(-5.0, True)

    def test_offset_at_five_is_accepted(self):
        card = _make_card()
        wave = _make_wave(offset=5.0)
        pi.updateWaveform(card, wave)
        card.setOutputOffsetVoltage.assert_called_once_with(5.0, True)

    def test_pi620lx_error_is_caught_and_does_not_propagate(self):
        card = _make_card()
        card.setActiveChannel.side_effect = _FakePi620Error("hardware fault")
        wave = _make_wave()
        pi.updateWaveform(card, wave)  # must not raise
        card.outputOff.assert_not_called()

    def test_pi620lx_error_on_output_on_is_caught(self):
        card = _make_card()
        card.outputOn.side_effect = _FakePi620Error("output failed")
        wave = _make_wave()
        pi.updateWaveform(card, wave)  # must not raise
        card.generateSignal.assert_called_once()


# ── abortGeneration tests ─────────────────────────────────────────────────────

class TestAbortGeneration(unittest.TestCase):

    def test_none_card_returns_without_calling_hardware(self):
        pi.abortGeneration(None, 1)  # must not raise

    def test_selects_channel_then_turns_output_off(self):
        card = _make_card()
        pi.abortGeneration(card, 2)
        card.setActiveChannel.assert_called_once_with(2)
        card.outputOff.assert_called_once()

    def test_pi620lx_error_is_caught_and_does_not_propagate(self):
        card = _make_card()
        card.outputOff.side_effect = _FakePi620Error("fault")
        pi.abortGeneration(card, 1)  # must not raise


if __name__ == "__main__":
    unittest.main(verbosity=2)
