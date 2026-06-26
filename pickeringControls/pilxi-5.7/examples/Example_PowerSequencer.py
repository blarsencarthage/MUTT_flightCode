"""Example program for using Pickering LXI Remote AC Management Switch (power sequencer) with the Python Clientbridge wrapper."""

import pipslx
import pilxi

if __name__ == "__main__":
    print("pilxi wrapper version: {}".format(pilxi.__version__))
    # IP address of the LXI Power Management Switch
    IP_Address = "192.168.0.244"

    # Open a session with the LXI unit and get the session ID
    session = pilxi.Pi_Session(IP_Address)
    sessionID = session.GetSessionID()

    # Open the pipslx library using the LXI session
    powerSequencer = pipslx.Pipslx(sessionID)

    # Start sequence
    powerSequencer.sequence(pipslx.SEQUENCE_START)

    # Get the state of a specified channel
    channel = 2
    state = powerSequencer.get_chan_state(channel)

    # Set the state of a specified channel
    state = 1
    powerSequencer.set_chan_state(channel, state)

    emergency = False

    if emergency:
        # In an emergency, call shutdown method to immediately disconnect
        # all channels. No sequence times applied
        powerSequencer.shutdown()
    else:
        # Otherwise, begin the regular shutdown sequence
        powerSequencer.sequence(pipslx.SEQUENCE_STOP)

    # Close pipslx
    powerSequencer.close()

    # Close LXI session
    session.Close()
