
#Author: Braedon Larsen 
#Created: 6.11.26

import os
import sys

_pkg_dir = os.path.join(os.path.dirname(__file__), "python_pilpxi_v1.7")
if _pkg_dir not in sys.path:
    sys.path.insert(0, _pkg_dir)

import pilpxi

def initPXIE():
    base = pilpxi.Base()
    free_cards = base.FindFreeCards()

    if not free_cards:
        print("No devices found.")

    valid_devices = []
    for bus, device in free_cards:
        try:
            probe = pilpxi.Pi_Card(bus, device)
            if "41-620" in probe.CardId():
                valid_devices.append((bus, device))
            else:
                print(f"Device at bus={bus}, device={device} is not a 41-620 compliant card.")
            probe.Close()
        except pilpxi.Error as ex:
            print("Exception checking device:", ex.message)

    cards = []
    for bus, device in valid_devices:
        try:
            card = pilpxi.Pi_Card(bus, device)
            card.ClearCard()
            cards.append(card)
        except pilpxi.Error as ex:
            print("Exception occurred:", ex.message)
    return cards


def updateWaveform(card,channel, frequency, amplitude, offset):
    if card is None:
        print("No card available.")
        return
    try:
        card.PILFG_AbortGeneration(channel)
        card.PILFG_SetWaveform(channel, pilpxi.FG_WfTypes.PILFG_WAVEFORM_SINE)
        card.PILFG_SetAmplitude(channel, amplitude)
        card.PILFG_SetFrequency(channel, frequency)
        if offset < -5 or offset > 5:
            print("Offset voltage must be between -5 and 5 volts.")
            card.PILFG_SetDcOffset(channel, 0)
        else:
            card.PILFG_SetDcOffset(channel, offset)
        card.PILFG_InitiateGeneration(channel)
    except pilpxi.Error as error:
        print("Exception occurred:", error.message)

