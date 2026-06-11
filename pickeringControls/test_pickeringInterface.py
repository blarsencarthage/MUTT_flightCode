"""
Unit tests for pickeringInterface.py — no physical hardware required.

Strategy: inject a fake `pilpxi` module into sys.modules *before* importing
pickeringInterface, so the real ctypes DLL is never touched.

Run from the project root:
    python -m pytest pickeringControls/test_pickeringInterface.py -v
  or directly:
    python pickeringControls/test_pickeringInterface.py
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, call
from types import ModuleType

# ── Fake pilpxi module ────────────────────────────────────────────────────────
# Must be injected into sys.modules before pickeringInterface is imported.

class _FakePilpxiError(Exception):
    """Mirrors pilpxi.Error so `except pilpxi.Error` clauses work correctly."""
    def __init__(self, message, errorCode=None):
        self.message = message
        self.errorCode = errorCode
    def __str__(self):
        return self.message

_fake_pilpxi = ModuleType("pilpxi")
_fake_pilpxi.Error = _FakePilpxiError

_fake_wf_types = MagicMock()
_fake_wf_types.PILFG_WAVEFORM_SINE = 0x0
_fake_pilpxi.FG_WfTypes = _fake_wf_types

# Placeholder callables; replaced per-test in setUp
_fake_pilpxi.Base = MagicMock()
_fake_pilpxi.Pi_Card = MagicMock()

sys.modules.pop("pilpxi", None)
sys.modules["pilpxi"] = _fake_pilpxi

# ── Import module under test ──────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
sys.modules.pop("pickeringInterface", None)
import pickeringInterface as pi


# ── Helper ────────────────────────────────────────────────────────────────────

def _make_card():
    return MagicMock()


# ── initPXIE tests ────────────────────────────────────────────────────────────

class TestInitPXIE(unittest.TestCase):

    def setUp(self):
        _fake_pilpxi.Base = MagicMock()
        _fake_pilpxi.Pi_Card = MagicMock()

    # -- no hardware present --------------------------------------------------

    def test_no_free_cards_returns_empty_list_and_none(self):
        mock_base = MagicMock()
        mock_base.FindFreeCards.return_value = []
        _fake_pilpxi.Base.return_value = mock_base

        valid_devices, card = pi.initPXIE()

        self.assertEqual(valid_devices, [])
        self.assertIsNone(card)

    # -- card ID mismatch -----------------------------------------------------

    def test_wrong_card_id_excluded_from_valid_devices(self):
        mock_base = MagicMock()
        mock_base.FindFreeCards.return_value = [(1, 2)]
        _fake_pilpxi.Base.return_value = mock_base

        probe = MagicMock()
        probe.CardId.return_value = "41-999,SN123,A"
        _fake_pilpxi.Pi_Card.return_value = probe

        valid_devices, card = pi.initPXIE()

        probe.Close.assert_called_once()
        self.assertEqual(valid_devices, [])
        self.assertIsNone(card)

    # -- happy path -----------------------------------------------------------

    def test_valid_card_returned_and_cleared(self):
        mock_base = MagicMock()
        mock_base.FindFreeCards.return_value = [(1, 2)]
        _fake_pilpxi.Base.return_value = mock_base

        probe = MagicMock()
        probe.CardId.return_value = "41-620,SN456,B"
        real_card = MagicMock()
        _fake_pilpxi.Pi_Card.side_effect = [probe, real_card]

        valid_devices, card = pi.initPXIE()

        self.assertEqual(valid_devices, [(1, 2)])
        self.assertIs(card, real_card)
        real_card.ClearCard.assert_called_once()
        probe.Close.assert_called_once()

    def test_only_first_valid_device_is_opened_as_card(self):
        mock_base = MagicMock()
        mock_base.FindFreeCards.return_value = [(1, 1), (2, 2)]
        _fake_pilpxi.Base.return_value = mock_base

        probe1, probe2 = MagicMock(), MagicMock()
        probe1.CardId.return_value = "41-620,SN1,A"
        probe2.CardId.return_value = "41-620,SN2,B"
        real_card = MagicMock()
        _fake_pilpxi.Pi_Card.side_effect = [probe1, probe2, real_card]

        valid_devices, card = pi.initPXIE()

        self.assertEqual(valid_devices, [(1, 1), (2, 2)])
        self.assertIs(card, real_card)
        # The final Pi_Card call must target the first valid device
        self.assertEqual(_fake_pilpxi.Pi_Card.call_args_list[-1], call(1, 1))

    # -- exception handling ---------------------------------------------------

    def test_pilpxi_error_on_probe_open_skips_device(self):
        mock_base = MagicMock()
        mock_base.FindFreeCards.return_value = [(1, 2)]
        _fake_pilpxi.Base.return_value = mock_base

        _fake_pilpxi.Pi_Card.side_effect = _FakePilpxiError("open failed")

        valid_devices, card = pi.initPXIE()

        self.assertEqual(valid_devices, [])
        self.assertIsNone(card)

    def test_pilpxi_error_on_real_card_open_returns_none_card(self):
        mock_base = MagicMock()
        mock_base.FindFreeCards.return_value = [(3, 4)]
        _fake_pilpxi.Base.return_value = mock_base

        probe = MagicMock()
        probe.CardId.return_value = "41-620,SN789,C"
        _fake_pilpxi.Pi_Card.side_effect = [probe, _FakePilpxiError("card open failed")]

        valid_devices, card = pi.initPXIE()

        # Device was found valid during probing, but card open failed
        self.assertEqual(valid_devices, [(3, 4)])
        self.assertIsNone(card)


# ── updateWaveform tests ──────────────────────────────────────────────────────

class TestUpdateWaveform(unittest.TestCase):

    # -- guard: card is None --------------------------------------------------

    def test_none_card_returns_without_calling_hardware(self):
        # Should not raise; just prints and returns early
        pi.updateWaveform(None, 1, 100.0, 1.0, 0.0)

    # -- normal operation -----------------------------------------------------

    def test_valid_call_invokes_all_five_methods_in_order(self):
        card = _make_card()
        mgr = MagicMock()
        card.attach_mock(card.PILFG_AbortGeneration,  "PILFG_AbortGeneration")
        card.attach_mock(card.PILFG_SetWaveform,      "PILFG_SetWaveform")
        card.attach_mock(card.PILFG_SetAmplitude,     "PILFG_SetAmplitude")
        card.attach_mock(card.PILFG_SetFrequency,     "PILFG_SetFrequency")
        card.attach_mock(card.PILFG_SetDcOffset,      "PILFG_SetDcOffset")
        card.attach_mock(card.PILFG_InitiateGeneration, "PILFG_InitiateGeneration")

        pi.updateWaveform(card, 1, 1000.0, 2.5, 1.0)

        card.PILFG_AbortGeneration.assert_called_once_with(1)
        card.PILFG_SetWaveform.assert_called_once_with(1, _fake_pilpxi.FG_WfTypes.PILFG_WAVEFORM_SINE)
        card.PILFG_SetAmplitude.assert_called_once_with(1, 2.5)
        card.PILFG_SetFrequency.assert_called_once_with(1, 1000.0)
        card.PILFG_SetDcOffset.assert_called_once_with(1, 1.0)
        card.PILFG_InitiateGeneration.assert_called_once_with(1)

    # -- offset boundary checks -----------------------------------------------

    def test_offset_below_minus5_sets_dc_offset_to_zero(self):
        card = _make_card()
        pi.updateWaveform(card, 2, 500.0, 1.0, -5.1)
        card.PILFG_SetDcOffset.assert_called_once_with(2, 0)

    def test_offset_above_plus5_sets_dc_offset_to_zero(self):
        card = _make_card()
        pi.updateWaveform(card, 2, 500.0, 1.0, 5.1)
        card.PILFG_SetDcOffset.assert_called_once_with(2, 0)

    def test_offset_at_exactly_minus5_is_accepted(self):
        card = _make_card()
        pi.updateWaveform(card, 1, 100.0, 1.0, -5.0)
        card.PILFG_SetDcOffset.assert_called_once_with(1, -5.0)

    def test_offset_at_exactly_plus5_is_accepted(self):
        card = _make_card()
        pi.updateWaveform(card, 1, 100.0, 1.0, 5.0)
        card.PILFG_SetDcOffset.assert_called_once_with(1, 5.0)

    def test_offset_zero_is_accepted(self):
        card = _make_card()
        pi.updateWaveform(card, 1, 100.0, 1.0, 0.0)
        card.PILFG_SetDcOffset.assert_called_once_with(1, 0.0)

    # -- exception handling ---------------------------------------------------

    def test_pilpxi_error_during_generation_is_caught(self):
        card = _make_card()
        card.PILFG_AbortGeneration.side_effect = _FakePilpxiError("hardware fault")

        # Must not propagate the exception
        pi.updateWaveform(card, 1, 100.0, 1.0, 0.0)

        # Nothing after the failing call should have been reached
        card.PILFG_SetWaveform.assert_not_called()

    def test_pilpxi_error_on_initiate_is_caught(self):
        card = _make_card()
        card.PILFG_InitiateGeneration.side_effect = _FakePilpxiError("initiate failed")

        pi.updateWaveform(card, 1, 100.0, 1.0, 0.0)

        # Everything before InitiateGeneration should still have been called
        card.PILFG_AbortGeneration.assert_called_once()
        card.PILFG_SetWaveform.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
