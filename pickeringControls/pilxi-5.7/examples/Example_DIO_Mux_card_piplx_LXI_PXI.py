from __future__ import print_function

import math

import pilxi

"""Example Program for Pickering LXI-PXI-PCI DIO Mux type cards, using Clientbridge (piplx and picmlx) driverr"""

if __name__ == "__main__":
    print("pilxi wrapper version: {}".format(pilxi.__version__))

    # IP Address to use.
    # To use local PXI cards, place 'PXI' as the IP address.
    IP_Address = "192.168.2.236"

    # Open a session with an LXI device.
    # If any errors occur, an exception will be raised.
    try:
        session = pilxi.Pi_Session(IP_Address)
        print("Opened session with LXI at", IP_Address)

    except pilxi.Error as ex:
        print("Error ocurred opening session:", ex.message)
        exit()

    # Open a card by bus and device numbers.
    try:
        bus = 3
        device = 14

        card = session.OpenCard(bus, device)
        print("Opened card at bus {} device {}".format(bus, device))
        print(card.CardId())
    except pilxi.Error as ex:
        print("Error ocurred opening card:", ex.message)
        exit()

    # Perform switching operations
    try:
        #subunit 3: 12 bit threshold value
        subunit = 3
        voltage = 0.5
        threshold = 4095 * (voltage / 50.0)
        threshold = math.trunc(threshold)
        #print formatting
        binaryThreshold = bin(threshold)
        #writeSub data type cast
        threshold = [threshold]

        card.ClearSub(subunit)
        print("\nSetting threshold 1 to", str(voltage) + "V with bit pattern", binaryThreshold.replace('0b', ''))
        card.WriteSub(subunit, threshold)

        #subunit 4: 12 bit threshold value
        subunit = 4
        voltage = 10
        threshold = 4095 * (voltage / 50.0)
        threshold = math.trunc(threshold)
        #print formatting
        binaryThreshold = bin(threshold)
        #writeSub data type cast
        threshold = [threshold]

        card.ClearSub(subunit)
        print("Setting threshold 2 to", str(voltage) + "V with bit pattern", binaryThreshold.replace('0b', ''))
        card.WriteSub(subunit, threshold)

        #subunit 5: specifies channel control (MUX) //40-412-001 only
        subunit = 5
        channel = 5
        state = 1
        card.OpBit(subunit, channel, state)
        print("\nSwitched subunit: {} bit: {} new_state: {}".format(subunit, channel, state))

        #read the input subunit 1: specific channel threshold readings
        subunit = 1
        print("\nFor channel", channel, "Input threshold states are:", int(card.ReadBit(subunit, 2)), int(card.ReadBit(subunit, 1)))

    except pilxi.Error as ex:
        print("Error:", ex.message)
        exit()

    # Close the card and close the session with the LXI unit.

    card.Close()
    session.Close()
