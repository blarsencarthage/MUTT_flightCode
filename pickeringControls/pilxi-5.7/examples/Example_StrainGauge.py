from __future__ import print_function
import pilxi

# Sample program for Pickering LXI/PXI Strain Gauge Simulator cards (ex: 40-265-016) using the PILXI ClientBridge Python Wrapper
# This example is written for the Pickering 40-265-016 6-channel Strain Gauge simulator card. Modification to the source code
# may be required for other cards. Please refer to your product manual for information on how to operate your specific card. 

if __name__ == "__main__":
    print("pilxi wrapper version: {}".format(pilxi.__version__))
    # Connect to a chassis using an IP address.
    # The ClientBridge driver can also connect to local PXI chassis by passing
    # 'PXI' in place of the IP.

    IP_Address = "192.168.0.12"

    # Default port and timeout settings in mS
    port = 1024
    timeout = 1000

    # In this example we'll directly connect to the card using bus and device numbers:
    bus = 13
    device = 13

    # The Pickering 40-265-016 6-channel Strain Gauge simulator card uses a set of Precision Resistor subunits
    # numbered 1 - 6, followed by a set of Bridge Control (switch) subunits.
    # Bridge Control subunits on the 6-channel card are numbered n + 6, where n is the number of the
    # corresponding Precision Resistor subunit. 4-channel cards will have Bridge Control subunits at n + 4, and so on.
    # Please refer to your product manual for more information on your specific card.

    # In this example we'll use the first resistor subunit and its corresponding Bridge Control switch subunit:
    subunit = 1
    switchSubunit = subunit + 6

    try:

        # Open a session with the LXI unit
        session = pilxi.Pi_Session(IP_Address)

        # Open a card by bus and device numbers
        card = session.OpenCard(bus, device)

        # Get the card ID
        cardId = card.CardId()

    # On any errors, print a description of the error and exit
    except pilxi.Error as ex:
        print("Error occurred: ", ex.message)
        exit()

    print("Connected to chassis at", IP_Address)
    print("Successfully connected to card at bus", bus, "device", device)
    print("Card ID: ", cardId)

    # Controlling the 40-265-016 6-channel Strain Gauge simulator
    # Bridge control subunit bits for this card are as follows:
    # Bit 1 - Internal Excitation
    # Bit 2 - External Excitation
    # Bit 3 - Output Enable
    # Bit 4 - Bridge Switches
    BIT_INTERNAL_EXCITATION = 1
    BIT_EXTERNAL_EXCITATION = 2
    BIT_OUTPUT_ENABLE       = 3
    BIT_BRIDGE_SWITCHES     = 4

    # Please refer to your product manual for specific information about your card.

    # Switch Bridge Control subunit excitation source to external excitation:
    card.OpBit(switchSubunit, BIT_EXTERNAL_EXCITATION, 1)

    # Set resistor output to a specified value in Ohms:
    resistance = 350.503
    card.ResSetResistance(subunit, resistance)

    # Get resistance
    resistance = card.ResGetResistance(subunit)
    print("Resistance set to", resistance)

    # Set output enable switch
    card.OpBit(switchSubunit, BIT_OUTPUT_ENABLE, 1)

    # It is recommended to close open cards after using them
    card.Close()