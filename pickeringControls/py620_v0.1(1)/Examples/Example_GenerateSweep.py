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
    # The idQuery parameter will check we are opening a 41-620 compliant card.
    # The reset parameter will specify whether to reset the card on initialisation.
    # If no arguments are given, the base.openCard() method will open the first 41-620 card found.
    try:
        card = base.openCard(resource=device, idQuery=True, reset=True)
    except py620.Error as ex:
        print("Exception occurred:", ex.message)

    # Set active channel to use
    channel = 1
    card.setActiveChannel(channel)

    # Switch off channel output before configuring it
    card.outputOff()

    # Set trigger mode to continuous (no trigger)
    card.setTriggerMode(card.triggerSources["FRONT"], card.triggerModes["CONT"])

    # Set attenuation to signal amplitude (float value in dB)
    attenuation = 0
    card.setAttenuation(attenuation)

    # Set DC offset to generated waveform (float value from -5 to 5 volts)
    # The first argument specifies the desired offset voltage;
    # the second enables or disables DC offset.
    offsetVoltage = 1.0
    enableDCOffset = 0
    card.setOutputOffsetVoltage(offsetVoltage, enableDCOffset)

    # Generate a sweep using the values defined below.
    # Frequency values are floats in kHz.
    symmetry = 0
    # With mode set to 0, card.generateSweep() will generate a sweeping signal from start to end frequency
    # repeatedly.
    # With mode 1 it will generate a sweeping signal from start to end frequency with the FSK pin set high, or from
    # end to start frequency with the FSK pin set low.
    mode = 0
    startFrequency = 0.5
    endFrequency = 5
    freqStepSize = 0.01
    freqStepTime = 5

    try:
        card.generateSweep(card.signalShapes["SINE"],
                           symmetry,
                           mode,
                           startFrequency,
                           endFrequency,
                           freqStepSize,
                           freqStepTime)
    except py620.Error as error:
        print("Exception occurred:", error.message)

    # Close the card. This will not stop signal generation.
    card.close()