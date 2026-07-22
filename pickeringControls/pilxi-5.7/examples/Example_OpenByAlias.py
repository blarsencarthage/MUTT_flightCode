"""Example program for opening cards using aliases defined in Resource Manager"""

import pilxi

if __name__ == "__main__":
    print("pilxi wrapper version: {}".format(pilxi.__version__))
    # Alias of the device we want to use as defined in the Resource Manager
    alias = "MyAlias"

    # Subunit we want to use
    subunit = 1

    try:
        # Open card by alias; this also establishes a session with the LXI device
        card = pilxi.Pi_Card_ByAlias(alias)

        subtype = card.SubType(subunit)

        print("Opened card subunit of type:", subtype)

        # Close the card. Closing a card object of class Pi_Card_ByAlias will also
        # close the LXI session.
        card.Close()

    # On error, print error message and exit
    except pilxi.Error as ex:
        print("Error occurred:", ex.message)
        exit()