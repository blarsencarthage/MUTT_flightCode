from __future__ import print_function
import pilxi

if __name__ == "__main__":

    # Connect to a chassis using an IP address.
    # The ClientBridge driver can also connect to local PXI chassis by passing
    # 'PXI' in place of the IP.

    print("pilxi wrapper version: {}".format(pilxi.__version__))    
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

    print("Sample program for manipulating subunit states on Pickering Matrix Cards using the PILXI Python Wrapper")
    print()

    # This function returns information about the card,
    # Model name, Serial number and Firmware revision
    cardId = card.CardId()

    print("Successfully connected to specified card.")
    print("Card ID: ", cardId)

    # Use the 1st subunit
    subunit = 1

    # This function returns the number of rows and columns of the specified card subunit
    typeNum, rows, columns = card.SubInfo(subunit, True)
    subType = card.SubType(subunit, 1)
    print("Rows: {}\nColumns: {}".format(rows, columns))
    print("Card subunit type: {}".format(subType))
    print()

    # This function clears (de-energises) all outputs of a subunit
    card.ClearSub(subunit)

    # Get the subunit state object
    subState = card.GetSubState(subunit)

    # If we're using a matrix subunit:
    if subType.startswith("MATRIX"):

        # Switch crosspoints on the matrix
        row = 1
        column = 1
        subState.PreSetCrosspoint(row, column, True)

        row = 1
        column = 2
        subState.PreSetCrosspoint(row, column, True)

    # If we're using a switch subunit
    elif subType.startswith("SWITCH"):

        # Pre-set a range of bits
        for bit in range(1, 5):
            subState.PreSetBit(bit, 1)

    input("Press Enter to continue...")
    print()

    try:
        # Write the changed state back to the card
        card.WriteSubState(subunit, subState)
        print("Wrote modified state to subunit", subunit)

    except pilxi.Error as ex:
        print("Error occurred writing subunit state: {}".format(ex.message))
        exit()

    # Close the card
    card.Close()

    # Close the LXI session
    session.Close()
