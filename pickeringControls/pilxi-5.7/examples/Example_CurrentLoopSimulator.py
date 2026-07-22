# Example program for Pickering 41-765-001 PXI Current Loop simulator
# Using the python-pilxi Python ClientBridge wrapper

import pilxi

if __name__ == "__main__":
    print("pilxi wrapper version: {}".format(pilxi.__version__))
    # Connect to a chassis using an IP address.
    # The ClientBridge driver can also connect to local PXI chassis by passing
    # 'PXI' in place of the IP.
    IP_Address = "192.168.1.200"

    # Open a session with LXI device
    session = pilxi.Pi_Session(IP_Address)

    # Bus and device numbering for the 41-765-001
    bus = 4
    device = 14

    try:
        # Open the card
        card = session.OpenCard(bus, device)

    except pilxi.Error as ex:
        print("Error opening card: {}".format(ex.message))
        exit()

    # Get the card's ID string
    cardId = card.CardId()

    print("Successfully connected to card at bus", bus, "device", device)
    print("Card ID: ", cardId)

    try:
        # Sets 0 - 24 mA mode on subunit (channel) 1
        mode = card.CL_MODE["0_24_MA"]
        subunit = 1
        card.CLSetMode(subunit, mode)

        # Set current value to 6.55 mA on output
        current = 6.55
        card.CLSetCurrent(subunit, current)

        # Set 0 - 5V mode on subunit (channel) 1
        mode = card.CL_MODE["0_5_V"]
        card.CLSetMode(subunit, mode)

        # Sets voltage value to 2.25V on output
        voltage = 2.25
        card.CLSetVoltage(subunit, voltage)

    except pilxi.Error as ex:
        print("Error occurred: {}".format(ex.message))
        exit()

    # 40-765-001 specific example; setting isolation switches
    # Isolation switches are organised as subunit 17
    # Please refer to your product manual as this may vary between models.

    try:
        isolationSubunit = 17
        isolationSwitch = 1
        state = 1

        # Close Channel 1 isolation switch
        card.OpBit(isolationSubunit, isolationSwitch, state)

    except pilxi.Error as ex:
        print("Error operating isolation switches: {}".format(ex.message))
        exit()

    # Close the card and session
    card.Close()
    session.Close()

