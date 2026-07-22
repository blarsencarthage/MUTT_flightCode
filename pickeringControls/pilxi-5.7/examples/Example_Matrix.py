from __future__ import print_function
import pilxi

if __name__ == "__main__": 
    
    # Connect to a chassis using an IP address.
    # The ClientBridge driver can also connect to local PXI chassis by passing
    # 'PXI' in place of the IP.

    IP_Address = "192.168.7.75"
    
    # In this example we'll directly connect to the card using bus and device numbers:
    bus = 4
    device = 15
    
    print("pilxi wrapper version: {}".format(pilxi.__version__))
    # Open a session with LXI device
    session = pilxi.Pi_Session(IP_Address)

    print("Sample program for Pickering LXI/PXI Matrix cards using PILXI ClientBridge Python Wrapper")
    print("Connecting to chassis at ", IP_Address)
    
    try:
        # Open the card
        card = session.OpenCard(bus, device)

    except pilxi.Error as ex:
        print("Error opening card: {}".format(ex.message))
        exit()

    # Get the card ID and an error code
    cardId = card.CardId()

    print("Successfully connected to card at bus", bus, "device", device)
    print("Card ID: ", cardId)

    # Use the 1st subunit
    subunit = 1

    print("Clearing subunit", subunit)
    # card.ClearSub() de-energises all outputs on a specified subunit
    card.ClearSub(subunit)

    # Now we can set some crosspoints on the matrix card subunit

    row = 1
    column = 1
    state = True
    card.OpCrosspoint(subunit, row, column, state)

    row = 1
    column = 2
    state = True
    card.OpCrosspoint(subunit, row, column, state)

    # Close the card
    card.Close()

    # Close the LXI session
    session.Close()
