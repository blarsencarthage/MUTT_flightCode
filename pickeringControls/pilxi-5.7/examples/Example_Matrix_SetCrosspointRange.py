from __future__ import print_function
import pilxi
import sys

""" Sample program for Pickering LXI/PXI 40-584-001 2x128 Matrix cards using PILXI ClientBridge Python Wrapper """

if __name__ == "__main__":
    print("pilxi wrapper version: {}".format(pilxi.__version__))
    # Connect to a chassis using an IP address.
    # The ClientBridge driver can also connect to local PXI chassis by passing
    # 'PXI' in place of the IP.
    
    IP_Address = "PXI"

    # Default port and timeout settings in mS
    port = 1024
    timeout = 1000

    # In this example we'll directly connect to the card using bus and device numbers:
    bus = 21
    device = 0

    # Use the first subunit
    subunit = 1

    print("Sample program for Pickering LXI/PXI 40-584-001 2x128 Matrix cards using PILXI ClientBridge Python Wrapper")
    print("Connecting to chassis at ", IP_Address)

    # Open a session with LXI device
    session = pilxi.Pi_Session(IP_Address, port, timeout)

    try:
        # Open the card
        card = session.OpenCard(bus, device)

    except pilxi.Error as ex:
        print("Error occurred: {}".format(ex.message))
        exit()

    # Get the card ID and an error code
    cardId = card.CardId()

    print("Successfully connected to card at bus", bus, "device", device)
    print("Card ID: ", cardId)

    print("Clearing subunit", subunit)
    # card.ClearSub() de-energises all outputs on a specified subunit
    card.ClearSub(subunit)

    # SetCrosspointRange sets a range of crosspoints in a given row   
    # Accepting the Row from user.
    if (sys.version_info > (3, 0, 0)):
        input_var = input("Please enter the Row (Y): ")
    else:
        input_var = raw_input("Please enter the Row (Y): ")
    row = int(input_var)

    # Accepting the starting value of the column range from user.
    if (sys.version_info > (3, 0, 0)):
        input_var = input("Please enter the START value of column range to be controlled (X): ")
    else:
        input_var = raw_input("Please enter the START value of column range to be controlled (X): ")
    start_column = int(input_var)
    
    # Accepting the ending value of the column range from user.
    if (sys.version_info > (3, 0, 0)):
        input_var = int(input("Please enter the END value of column range to be controlled (X): "))
    else:
        input_var = raw_input("Please enter the END value of column range to be controlled (X): ")
    end_column = int(input_var)

    print("Switching range", start_column, "-", end_column, "on row", row)

    state = 1 # to energize the crosspoints
    #state = 0 # to de energize the crosspoints
    card.SetCrosspointRange(subunit, row, start_column, end_column, state)

    if (sys.version_info > (3, 0, 0)):
        input_var = input("Press Enter to continue ")
    else:
        input_var = raw_input("Please Enter to continue ")

    print("Clearing outputs and closing card...")
    card.ClearSub(subunit)

    # Close the card before exiting the program
    card.Close()

    # Close the LXI session
    session.Close()
