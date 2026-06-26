from __future__ import print_function
import pilxi
import sys

""" Sample program for Pickering LXI/PXI Attenuator cards using the PILXI ClientBridge Python Wrapper """

if __name__ == "__main__":
    print("pilxi wrapper version: {}".format(pilxi.__version__))
    # Connect to a chassis using an IP address.
    # The ClientBridge driver can also connect to local PXI chassis by passing
    # 'PXI' in place of the IP.
    IP_Address = "192.168.0.12"

    # In this example we'll directly connect to the card using bus and device numbers:
    bus = 13
    slot = 12

    # Use the first subunit
    subunit = 1

    print("Sample program for Pickering LXI/PXI Attenuator cards using the PILXI ClientBridge Python Wrapper")

    session = pilxi.Pi_Session(IP_Address)

    # Open a card at the given bus and device.
    try:
        card = session.OpenCard(bus, slot)

    # If an error occurs, an exception will be raised that will contain an error message
    # and the driver error code.
    except pilxi.Error as ex:
        print("Driver error {} occurred: {}".format(ex.errorCode, ex.message))
        exit()

    # Get the card ID and an error code
    cardId = card.CardId()

    print("Connected to chassis at", IP_Address)
    print("Successfully connected to card at bus", bus, "device", slot)
    print("Card ID: ", cardId)

    # Attenuation values are expressed in decibels (dB):
    attenuation = 3

    try:
        # This function sets attenuation value on the specified subunit
        card.SetAttenuation(subunit, attenuation)
        print("Set attenuation value to", attenuation, "dB...")

        # This function returns the current attenuation value:
        attenuation = card.GetAttenuation(subunit)
        print("Got attenuation value of ", attenuation, "dB.")

    except pilxi.Error as ex:
        print("Driver error {} occurred: {}".format(ex.errorCode, ex.message))
        exit()

    # Close the card. It is recommended to close any open cards
    card.Close()

    # Close the session with LXI device
    session.Close()
