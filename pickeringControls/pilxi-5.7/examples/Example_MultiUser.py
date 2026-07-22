# Example for multiuser LXI access using the Pickering pilxi Python Clientbridge wrapper
# Two instances of this script can be run, demonstrating multithreaded/multiuser access
# to an LXI switch card.

import pilxi

if __name__ == "__main__":

    print("Python Clientbridge multiuser access demonstration program")
    print("pilxi wrapper version: {}".format(pilxi.__version__))

    IP_Address = "192.168.2.83"

    try:
        # Connect to LXI and get a session object
        session = pilxi.Pi_Session(IP_Address)

    except pilxi.Error as ex:
        print(f"Error getting session: {ex.message}")
        print("Please check your connection and IP address.")
        exit()

    # Get a list of usable cards
    cardsList = session.GetUsableCards(0)

    print(f"Found {len(cardsList)} usable card(s):")

    # Open the first card for multiuser access
    try:
        card = session.OpenCardByID(cardsList[0], accessType=pilxi.AccessTypes.MULTIUSER)

    except pilxi.Error as ex:
        print(f"Error opening card: {ex.message}")
        exit()

    subunitType = card.SubType(1)

    print(f"Card Type: {subunitType}")
    print()

    print("Card switch state will be repeatedly inverted on user input.")
    print("Press any key to invert state, q to exit:")

    subunit = 1
    bit = 1

    while True:

        userInput = input("Press to invert...")

        if(userInput):
            break

        # Get switch state
        bitState = card.ViewBit(subunit, bit)

        # Invert it
        bitState = not bitState

        # Set switch state
        card.OpBit(subunit, bit, bitState)

