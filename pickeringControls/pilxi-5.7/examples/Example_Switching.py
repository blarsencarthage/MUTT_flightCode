from __future__ import print_function
import pilxi

"""Example program for operating Pickering Switch cards using the Python-Pilxi wrapper"""

if __name__ == "__main__":
    print("pilxi wrapper version: {}".format(pilxi.__version__))
    # IP Address to use.
    # To use local PXI cards, place 'PXI' as the IP address.
    IP_Address = "10.0.0.27"

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
        bus = 0
        device = 4

        card = session.OpenCard(bus, device)
        print("Opened card at bus {} device {}".format(bus, device))

    except pilxi.Error as ex:
        print("Error ocurred opening card:", ex.message)
        exit()

    # Perform switching operations
    try:
        subunit = 1
        bitNumber = 1
        state = 1

        card.OpBit(subunit, bitNumber, state)
        print("Switched subunit: {} bit: {} state: {}".format(subunit, bitNumber, state))

    except pilxi.Error as ex:
        print("Error switching:", ex.message)
        exit()

    # Close the card and close the session with the LXI unit.

    card.Close()
    session.Close()





