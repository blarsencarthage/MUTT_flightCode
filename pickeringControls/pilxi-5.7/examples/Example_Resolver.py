"""Example program for using Pickering PXI resolver cards in LXI units using the Python ClientBridge wrapper"""

import pilxi

DM_Mode = pilxi.DM_Mode

if __name__ == "__main__":
    print("pilxi wrapper version: {}".format(pilxi.__version__))
    # Connect to a chassis using an IP address.
    # The ClientBridge driver can also connect to local PXI chassis by passing
    # 'PXI' in place of the IP.

    IP_Address = "192.168.0.238"

    # In this example we'll directly connect to the card using bus and device numbers:
    bus = 1
    device = 14

    try:
        # Open a session with LXI device
        session = pilxi.Pi_Session(IP_Address)

        # Open a card using bus and device numbers
        card = session.OpenCard(bus, device)

    except pilxi.Error as ex:
        print("Error occurred: {}".format(ex.message))
        exit()

    # This function returns information about the card,
    # Model name, Serial number and Firmware revision
    cardId = card.CardId()

    print("Successfully connected to specified card.")
    print("Card ID: ", cardId)

    # Switch Sub-unit
    switchSub = 5
    bankOffset = 11

    # LVDT Bank (Sub-Unit) number
    bank = 2

    #Input Switches
    try:
        card.OpBit(switchSub, ((bank - 1) * bankOffset) + 1, True)
        card.OpBit(switchSub, ((bank - 1) * bankOffset) + 2, True)
        card.OpBit(switchSub, ((bank - 1) * bankOffset) + 3, True)

    except pilxi.Error as ex:
        print("Error occurred switching: {}".format(ex.message))
        exit()

    #Output Switches
    try:
        card.OpBit(switchSub, ((bank - 1) * bankOffset) + 5, True)
        card.OpBit(switchSub, ((bank - 1) * bankOffset) + 6, True)
        card.OpBit(switchSub, ((bank - 1) * bankOffset) + 8, True)
        card.OpBit(switchSub, ((bank - 1) * bankOffset) + 9, True)

    except pilxi.Error as ex:
        print("Error occurred switching: {}".format(ex.message))
        exit()

    try:
        mode = DM_Mode.RESOLVER  # Setting Resolver Mode
        card.VDTSetMode(bank, mode)

    except pilxi.Error as ex:
        print("Error occurred setting VDT mode: {}".format(ex.message))
        exit()

    # Set position
    try:
        position = -156.25 # Between -180.00 to 180.00
        card.ResolverSetPosition(bank, position)

    except pilxi.Error as ex:
        print("Error occurred setting position: {}".format(ex.message))
        exit()

    # Set Speed
    try:
        speed = 50.00 # Set speed between 1.00 - 655.35 RPM
        card.ResolverSetRotateSpeed(bank, speed)

    except pilxi.Error as ex:
        print("Error occurred setting speed: {}".format(ex.message))
        exit()

    # Set Number of Turns
    try:
        turns = 20 # Set number of turns between 1- 65535
        card.ResolverSetNumOfTurns(bank, turns)

    except pilxi.Error as ex:
        print("Error occurred setting number of turns: {}".format(ex.message))
        exit()

    # Start/Stop (Start = True, Stop = False)
    try:
        card.ResolverSetStartStopRotate(bank, True)

    except pilxi.Error as ex:
        print("Error occurred stopping/starting: {}".format(ex.message))
        exit()

    input("Press Enter to Stop...")
    card.ResolverSetStartStopRotate(bank, False)



