"""Example program for using the Pickering 41-620 Function Generator card with the Python pi620lx ClientBridge wrapper."""
import os
import sys
_pkg_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_pkg_dir, "pilxi-5.7"))
import pilxi
import pi620lx

if __name__ == "__main__":

    print("pi620lx wrapper version: {}".format(pi620lx.__version__))
    
    # IP address of the LXI
    IP_Address = "169.254.112.5"

    # Open a session with the LXI unit and get the session ID
    session = pilxi.Pi_Session(IP_Address)
    sessionID = session.GetSessionID()

    # Open the pi620lx library using the LXI session
    pi620Base = pi620lx.Base(sessionID)

    # Discover and list 41-620 cards present in LXI
    cards = pi620Base.findCards()

    for card in cards:
        bus, device = card
        print("Found 41-620 card at bus {} device {}".format(bus, device))

    # Open a 41-620 card. With no parameters, the openCard() method will open the first 41-620 found.
    # This is useful if your LXI has only one 41-620 function generator card present.
    # Otherwise, the method can be called as below:
    # card = pi620Base.openCard(bus, device)
    # using bus and device numbers obtained from the Base.findCards() method
    card = pi620Base.openCard()

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
    offsetVoltage = 4.0
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
    frequency = 10
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
        import time 
        time.sleep(5)
        # Set output on
        card.outputOn()

    except pi620lx.Error as error:
        print("Exception occurred:", error.message)

    # Close card. This will not stop the card generating a signal.
    card.close()

