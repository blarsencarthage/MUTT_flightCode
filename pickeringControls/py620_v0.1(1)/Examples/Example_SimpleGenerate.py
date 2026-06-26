""" Sample program for Pickering 41-620 Function Generator cards using the Py620 Python Wrapper"""

from __future__ import print_function
import py620

if __name__ == "__main__":

    # Py620 base class contains functions for card discovery:
    base = py620.Pi_Base()

    # Pi_Base.findCards() returns a list of VISA resource strings
    # representing 41-620 devices:
    devices = base.findCards()

    device = devices[0]
    print("Opening device at", device)

    # Open a card. Optional parameters include resource, idQuery and reset.
    # If no arguments are given, the openCard() method will open the first 41-620 card found.
    try:
        card = base.openCard(resource=device, idQuery=False, reset=True)
    except py620.Error as ex:
        print("Exception occurred:", ex.message)

    # Set active channel to use
    channel = 1
    card.setActiveChannel(channel)

    # Switch off channel output before configuring it
    card.outputOff()

    # Set trigger mode to continuous (no trigger)
    card.setTriggerMode(card.triggerSources["FRONT"], card.triggerModes["CONT"])

    # Set DC offset to generated waveform (float value from -5 to 5 volts)
    # The first argument specifies the desired offset voltage;
    # the second enables or disables DC offset.
    offsetVoltage = 1.0
    enableDCOffset = True
    card.setOutputOffsetVoltage(offsetVoltage, enableDCOffset)

    # Set attenuation to signal amplitude (float value in dB)
    attenuation = 3
    card.setAttenuation(attenuation)

    # Generate a signal
    # Signal shape can be defined using constants available with the Pi620_Card class:
    shape = card.signalShapes["SINE"]
    # shape = card.signalShapes["SQUARE"]
    # shape = card.signalShapes["TRIANGLE"]

    # Frequency of signal in kHz:
    frequency = 1
    # Symmetry of signal (0 - 100):
    symmetry = 20

    try:
        # Start generating a signal. By default, this method will start generating immediately without
        # first calling card.outputOn().
        # card.generateSignal(frequency, shape, symmetry)

        # The card.generateSignal() method can also be used with optional parameters to specify
        # a start phase offset and to enable/disable immediate signal generation.
        # For example, the following call will set the same signal as above, but with a
        # 90 degree phase offset and will disable signal output until card.outputOn() is called:
        card.generateSignal(frequency, shape, symmetry, startPhaseOffset=90, generate=False)

        # Set output on
        card.outputOn()

    except py620.Error as error:
        print("Exception occurred:", error.message)

    # Close card. This will not stop the card generating a signal.
    card.close()
