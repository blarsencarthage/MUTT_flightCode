
#Author: Braedon Larsen 
#Created: 6.11.26
#Updated: 6.17.26
#NOTE: This is a copy of pickeringInterface.py for testing

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

def updateWaveform(self, channel, frequency=None, amplitude=None, offset=None, phase=None):
    if channel not in self.channel_state:
        self.channel_state[channel] = {
            'frequency': self.card.PILFG_GetFrequency(channel),
            'amplitude': self.card.PILFG_GetAmplitude(channel),
            'offset':    self.card.PILFG_GetDcOffset(channel),
            'phase':     self.card.PILFG_GetStartPhase(channel),
        }

    state = self.channel_state[channel]
    if frequency is not None:
        state['frequency'] = frequency
    if amplitude is not None:
        state['amplitude'] = amplitude
    if offset is not None:
        state['offset'] = offset
    if phase is not None:
        state['phase'] = phase

    try:
        self.card.PILFG_SetWaveform(channel, pilpxi.FG_WfTypes.PILFG_WAVEFORM_SINE)
        self.card.PILFG_SetAmplitude(channel, state['amplitude'])
        self.card.PILFG_SetFrequency(channel, state['frequency'])
        if state['offset'] < 0 or state['offset'] > 5:
            print("Offset voltage must be between 0 and 5 volts.")
            self.card.PILFG_SetDcOffset(channel, 0)
        else:
            self.card.PILFG_SetDcOffset(channel, state['offset'])
        self.card.PILFG_SetStartPhase(channel, state['phase'] % 360.0)
        self.card.PILFG_InitiateGeneration(channel)
    except pilpxi.Error as error:
        print("Exception occurred:", error.message)

    

