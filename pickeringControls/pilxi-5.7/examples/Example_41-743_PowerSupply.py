"""Example program for using the Pickering 41-743 Power Supply card with the Python pi743 ClientBridge wrapper."""

import pilxi
import pi743lx

if __name__ == "__main__":
    print("pi743lx wrapper version: {}".format(pi743lx.__version__))

    # IP address of the LXI
    IP_Address = "192.168.2.106"

    try:
        # Open a session with the LXI unit and get the session ID
        session = pilxi.Pi_Session(IP_Address)
        sessionID = session.GetSessionID()

    except pilxi.Error as ex:
        print("Error opening session with LXI: ", ex.message)
        exit()

    try:
        # Open the pi743lx library using the LXI session
        pi743Base = pi743lx.Base(sessionID)

        # List 41-743 cards present in LXI (as VISA-style resource strings)
        cards = pi743Base.findInstrumentsRsrc()

        for card in cards:
            print("Found 41-743 card at: ", card)

    except pi743lx.Error as ex:
        print("Error opening pi743lx library/listing cards:", ex.message)
        exit()

    try:
        # Open a card. With no arguments, pi743Base.openCard() will open the first card found
        # in the LXI chassis. Useful if there is only one present. Otherwise, a resource string
        # can be passed as an optional parameter:

        card = pi743Base.openCard()

        # Alternatively:
        #card = pi743Base.openCard(resource="myResource")

        # idQuery and reset can also be passed optionally:
        #card = pi743Base.openCard(resource="myResource", idQuery=True, reset=True)

    except pi743lx.Error as ex:
        print("Error opening 41-743 card: ", ex.message)
        exit()

    try:
        # Set connection status to disconnectedion
        connectionStatus = pi743Base.ConnectionStatus["CON_DISCONNECT"]
        card.setOutputConnection(connectionStatus)

        # Set a voltage (takes a float value in volts), and a current limit
        # (float value current in amps)
        voltage = 5.0
        current = 1.0

        card.setOutputCurrentLimit(current)
        card.setOutputVoltage(voltage)

        # Enable the DC-DC converter (enables output)
        card.setPowerSupplyStatus(True)

        connectionStatus = pi743Base.ConnectionStatus["CON_2WIRE_INTERNAL"]     # 2 wire internal sense
        #connectionStatus = pi743Base.ConnectionStatus["CON_4WIRE_EXTERNAL"]    # 4 wire external sense
        card.setOutputConnection(connectionStatus)

    except pi743lx.Error as ex:
        print("Error operating 41-743 card: ", ex.message)
        exit()

    card.close()
    session.Close()

