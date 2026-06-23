
#Author: Braedon Larsen 
#Created: 6.11.26
#Updated 6.17.26 
import os
import sys

_pkg_dir = os.path.join(os.path.dirname(__file__), "python_pilpxi_v1.7")
if _pkg_dir not in sys.path:
    sys.path.insert(0, _pkg_dir)

import pilpxi

def initPXIE():
    #Initalizes PXI interface and returns a Base object, contains valid cards found, IP address, etc.
    base = pilpxi.Base()
    if base is None:
        print("Failed to initialize PXI interface.")
        return None
    else:
        print("PXI interface initialized successfully.")
    #Returns array of free cards, each element is a tuple of bus and device
    freeCards = base.FindFreeCards()

    if not freeCards:
        print("No devices found.")
    else:  
        print(f"Found {len(freeCards)} free devices.")

    validDevices = []
    for bus, device in freeCards:
        try:
            checkCard = pilpxi.Pi_Card(bus, device)
            if "41-620" in checkCard.CardId(): #This check is to only allow the func gen through, may be the wrong typing 
                validDevices.append((bus, device))
            else:
                print(f"Device at bus={bus}, device={device} is not a 41-620 compliant card.")
            checkCard.Close()
        except pilpxi.Error as ex:
            print("Exception checking device:", ex.message)

    cards = []
    for bus, device in validDevices:
        try:
            card = pilpxi.Pi_Card(bus, device)
            card.ClearCard()
            cards.append(card)
        except pilpxi.Error as ex:
            print("Exception occurred:", ex.message)
    print(f"Found {len(cards)} valid 41-620 compliant cards.")
    return cards


def updateWaveform(card, channel, frequency, amplitude, offset, phase=0.0):
    if card is None:
        print("No card available.")
        return
    try:
        print(f"Updating waveform on card {card.CardId()}, channel {channel}: frequency={frequency}, amplitude={amplitude}, offset={offset}, phase={phase}")
        card.outputOff(channel)
        card.PILFG_SetWaveform(channel, pilpxi.FG_WfTypes.PILFG_WAVEFORM_SINE)
        card.PILFG_SetAmplitude(channel, amplitude)
        card.PILFG_SetFrequency(channel, frequency)
        if offset < 0 or offset > 5:
            print("Offset voltage must be between 0 and 5 volts.")
            card.PILFG_SetDcOffset(channel, 0)
        else:
            card.PILFG_SetDcOffset(channel, offset)
        card.PILFG_SetStartPhase(channel, phase % 360.0)
        card.PILFG_InitiateGeneration(channel)
    except pilpxi.Error as error:
        print("Exception occurred:", error.message)

