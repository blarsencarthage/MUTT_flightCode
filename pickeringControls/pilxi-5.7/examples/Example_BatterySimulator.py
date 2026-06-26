""" Sample program for Pickering LXI/PXI Battery Simulator cards using the PILXI ClientBridge Python Wrapper """

import pilxi

if __name__ == "__main__":
    print("pilxi wrapper version: {}".format(pilxi.__version__))
    # Connect to a chassis using an IP address.
    # The ClientBridge driver can also connect to local PXI chassis by passing
    # 'PXI' in place of the IP.

    IP_Address = "192.168.2.80"

    # Default port and timeout settings in mS
    port = 1024
    timeout = 1000

    # In this example we'll directly connect to the card using bus and device numbers:
    bus = 4
    device = 13

    # Use the first subunit
    subunit = 1

    print("Sample program for Pickering LXI/PXI Battery Simulator cards using the PILXI ClientBridge Python Wrapper")

    # Open a session with LXI
    try:
        session = pilxi.Pi_Session(IP_Address, port, timeout)
    except pilxi.Error as ex:
        print("Opening LXI session failed: {}".format(ex.message))
        exit()

    # Open the card
    try:
        card = session.OpenCard(bus, device)
    except pilxi.Error as ex:
        print("Opening card failed: {}".format(ex.message))
        exit()

    # Get the card ID
    cardId = card.CardId()

    print("Connected to chassis at", IP_Address)
    print("Successfully connected to card at bus:", bus, "device:", device)
    print("Card ID: ", cardId)

    # Functions to control Battery Simulator:

    volts = 3.3
    current = 0.03

    try:
        print("Setting voltage to", volts)
        # Set Voltage
        card.BattSetVoltage(subunit, volts)

        print("Setting current to", current)
        # Set Current
        card.BattSetCurrent(subunit, current)

        print("Enabling Battery Simulator output")

        # Enable Output
        card.BattSetEnable(subunit, 1)

        # Get Interlock State
        interlockState = card.BattReadInterlockState(subunit)
        if interlockState:
            print("Interlock is 'up' (enabled)")
        else:
            print("Interlock is 'down' (disabled)")

        # Get Voltage
        volts = card.BattGetVoltage(subunit)
        print("Voltage is set to ", volts)

        # Set Current
        current = card.BattGetCurrent(subunit)
        print("Current is set to", current)

        # Get Output state
        state = card.BattGetEnable(subunit)
        if state:
            print("Output state is enabled")

    except pilxi.Error as ex:
        print("Error occurred operating Battery Simulator: {}".format(ex.message))
        print("Error code: {}".format(ex.errorCode))

    try:
        # Measure channel voltage and current on supported battery simulator cards
        # e.g. 41-752A-01x models. Please consult your product manual for your
        # card's specific capabilities.

        # 41-752A-01x: Enable set-measure-set mode.
        card.BattSetMeasureSet(subunit, True)

        # 41-752A-01x: Change measurement device accuracy.
        card.BattSetMeasureConfig(subunit,                              # Subunit to configure
                                  pilxi.BattNumSamples.SAMPLES_128,     # Average values after 128 samples
                                  pilxi.BattConversionTime.T_1052us,    # 1052 us voltage sample time
                                  pilxi.BattConversionTime.T_540us,     # 540 us current sample time
                                  pilxi.BattOperationMode.CONTINUOUS)   # Measure continuously (no wait for trigger)

        # The battery simulator (41-752A-01x) has the capability to take into consideration the load
        # at which the voltage must be provided. Calculated data for voltage at different loads are
        # used to provide this functionality.
        load = 100  # units: mA
        card.BattSetLoad(subunit, load)

        volts = card.BattMeasureVoltage(subunit)
        print("Measured voltage: ", volts)

        current = card.BattMeasureCurrentmA(subunit)
        print("Measured ", current, " mA")

        current = card.BattMeasureCurrentA(subunit)
        print("Measured ", current, " A")

    except pilxi.Error as ex:
        print("Error operating special battery simulator functionality: {}".format(ex.message))
        print("Error code: {}".format(ex.errorCode))
        exit()

    # Close the card. It is recommended to close any open cards
    print("Closing card and exiting.")

    card.Close()
