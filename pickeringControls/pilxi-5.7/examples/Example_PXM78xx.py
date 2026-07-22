from __future__ import print_function
import pilxi
from LXIpxm78xx import __version__
from LXIpxm78xx import *

# IP address of the Pickering LXI chassis containing the PXM78xx instrument
LXI_IP = "192.168.10.228"

def example_DMM(instrument):

    ### Example: Operating instrument as DMM ###

    try:

        # Reset the instrument
        instrument.reset()

        # Initialise DMM
        instrument.DMM_init()

        # Configure DMM to DC voltage, range DC 4V
        instrument.DMM_configMeasurement(PXM78xx_FUNC.DMM_DCV, PXM78xx_RANGE.DCV_4V)

        # Configure filter
        instrument.DMM_configFilter(PXM78xx_FILTER.FILTER_1kHz)

        # Measure
        aperture = 0.1
        value, sbResult = instrument.DMM_meanMeasure(aperture)

        # Print results

        print("Result = ", value)
        print("Min = ", sbResult.min)
        print("Max = ", sbResult.max)

    except PXM78xx_Error as ex:

        print("Error operating instrument: ", ex.message)
        print("Error code ", hex(ex.errorCode))

def example_WFD(instrument):
    pre_samples = 1
    post_samples = 50
    total_samples = pre_samples + post_samples
    ### Example: Operating instrument as waveform digitiser ###

    try:

        # Reset the instrument
        print("Reseting instrument . . . ", end='')
        instrument.reset()
        print("OK")

        # Prepare waveform digitiser mode
        print("WFD_init() . . . ", end='')
        instrument.WFD_init(PXM78xx_CHANNEL.ADC16BIT)
        print("OK")

        # Configure measurement function and range
        print("WFD_configMeasurement() . . . ", end='')
        instrument.WFD_configMeasurement(PXM78xx_FUNC.WFD_DCV, PXM78xx_RANGE.DCV_8V)
        print("OK")

        sampleCfg = WFD_SAMPLECFG()

        # Configure sampling (level trigger)
        sampleCfg.interval = 500e-5
        sampleCfg.postTrigger = pre_samples
        sampleCfg.preTrigger = post_samples
        sampleCfg.triggerDelay = 0.0
        sampleCfg.triggerHysteresis = 0.1
        sampleCfg.triggerLevel = 0.1
        sampleCfg.triggerSource = PXM78xx_WFD_TRIGGER.RISING
        sampleCfg.continueWithNext = 0
        sampleCfg.noWaitForTrigger = 1

        print("WFD_configSampling() . . . ", end='')
        instrument.WFD_configSampling(sampleCfg)
        print("OK")

        # Configure averaging
        print("WFD_configMeanCount() . . . ", end='')
        instrument.WFD_configMeanCount(1)
        print("OK")

        # Start sampling
        print("WFD_startSampling() . . . ", end='')
        instrument.WFD_startSampling()
        print("OK")

        # Configure number of samples
        sampleCount = total_samples

        print("WFD_querySampleData() . . . ", end='')
        xData, yData = instrument.WFD_querySampleData(sampleCount)
        print("OK")

        print("Sampled Data (level trigger):")

        for i in range(len(xData)):
            print((xData[i] * 1e6), " us ", yData[i], "V")

    except PXM78xx_Error as ex:
        print("Error operating instrument: ", ex.message)
        print("Error code ", hex(ex.errorCode))
        exit(1)

def main():

    ### Example: Connecting to LXI and opening instrument(s) ###

    try:
        print("LXIpxm78xx wrapper version: {}".format(__version__))
        # Open a session with the LXI and get a session ID to use with
        # the PXM78xx wrapper
        
        print("Connecting to " + LXI_IP + " . . . ", end = '')
        session = pilxi.Pi_Session(LXI_IP)
        print("OK")
        sessionID = session.GetSessionID()

        # PXM78xx base class is used to discover and open instruments
        base = PXM78xx_Base(sessionID)



        libvers = base.QueryLibraryVersions()
        print("Library versions: ")
        print(libvers)

        # Discover free instruments in LXI
        print("Searching for instruments . . . ", end='')
        instruments = base.findFreeInstruments()
        print("OK")

        print("Found ", len(instruments), " Instruments:")
        for instr in instruments:
            print("Instrument at: ", instr)
        print()

        # Auto connect to first instrument found
        # Instrument opening functions return an instrument object
        # all methods operating the instrument belong to this object
        print("Connecting to first instrument . . . ", end='')
        instrument = base.autoConnectToFirst()
        print("OK")

    except PXM78xx_Error as ex:

        print("Error occurred opening instrument: ", ex.message)
        print("Error code", hex(ex.errorCode))
        exit(1)

    # Query some information about the instrument
    print("Instrument name: ", instrument.queryProductName())
    print("Instrument serial number: ", instrument.querySerialNumber())
    print("Instrument status: ", instrument.queryStatusMessage())
    print()

    # Example for operating the instrument as a DMM;
    example_DMM(instrument)
    
    # Example for operating the instrument as a waveform digitiser
    example_WFD(instrument)


if __name__ == "__main__":
    main()
