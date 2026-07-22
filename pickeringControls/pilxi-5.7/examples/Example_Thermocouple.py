from __future__ import print_function
import pilxi


""" Sample program for Pickering LXI/PXI Thermocouple Simulator cards using the PILXI ClientBridge Python Wrapper """

if __name__ == "__main__":

    # Connect to a chassis using an IP address.
    # The ClientBridge driver can also connect to local PXI chassis by passing
    # 'PXI' in place of the IP.
    print("pilxi wrapper version: {}".format(pilxi.__version__))

    IP_Address = input("Please enter the IP address: ")

    # Default port and timeout settings in mS
    port = 1024
    timeout = 1000

    # In this example we'll directly connect to the card using bus and device numbers:
    bus = 1
    device = 12

    # Use the first subunit
    subunit = 1

    print("Sample program for Pickering LXI/PXI Thermocouple Simulator cards using the PILXI ClientBridge Python Wrapper")

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

    # Thermocouple specific functions:

    # Set subunit voltage range to auto
    print("Setting range to auto...")

    range = card.TS_RANGE["AUTO"]
    card.VsourceSetRange(subunit, range)

    # Get voltage range of a subunit
    range = card.VsourceGetRange(subunit)

    if range == card.TS_RANGE["AUTO"]:
        print("Set subunit", subunit, "range to auto.")

    # Set voltage to 19.5 mV on the subunit
    mvolts = 19.5

    print("Setting voltage to", mvolts, "mV...")

    card.VsourceSetVoltage(subunit, mvolts)

    # Read the voltage of a subunit
    mvolts = card.VsourceGetVoltage(subunit)

    print("Voltage set to", mvolts, " mV.")

    # 41-760-001 Example; Setting channel isolation switches
    # Please refer to your thermocouple manual to find the subunit for
    # your specific isolation switch subunit.
    isolation_subunit = 33

    if cardId.startswith("41-760-001"):
        # Turn Vo1 on
        card.OpBit(isolation_subunit, 1, 1)

        # Turn Vcold1 on
        card.OpBit(isolation_subunit, 2, 1)

        # Turn Vo1 off
        card.OpBit(isolation_subunit, 1, 0)

        # Turn Vcold1 off
        card.OpBit(isolation_subunit, 2, 0)

    # Get compensation block temperatures

    temperatures = card.VsourceGetTemperature(card.ATTR["TS_TEMPERATURES_C"])

    index = 0
    for index, temperature in enumerate(temperatures):
        print("Compensation block temperature", index, ":", temperature, "C")

