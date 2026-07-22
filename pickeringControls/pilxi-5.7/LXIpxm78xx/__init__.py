from sys import version_info
import ctypes as c
import platform
import warnings
from enum import IntEnum

__version__ = "1.1.0"

# region Structs

class Complex_t(c.Structure):
    _fields_ = [
        ("magnitude", c.c_double),
        ("phase", c.c_double),
        ("realPart", c.c_double),
        ("imaginaryPart", c.c_double)
    ]


class DMM_SBRESULT(c.Structure):
    _fields_ = [
        ("frequency", c.c_double),
        ("dcOffset", c.c_double),
        ("acRms", c.c_double),
        ("acdcRms", c.c_double),
        ("sampleCount", c.c_uint32),
        ("nPeriods", c.c_uint32),
        ("sampleInterval", c.c_double),
        ("min", c.c_double),
        ("max", c.c_double),
        ("uncertainty", c.c_double),
        ("serialResistance", c.c_double),
        ("impedance", Complex_t),
        ("zValue", c.c_double),
        ("zPhase", c.c_double),
        ("uValue", c.c_double),
        ("uPhase", c.c_double),
        ("iValue", c.c_double),
        ("iPhase", c.c_double),
        ("nPerPeriod", c.c_double),
        ("dPhi", c.c_double),
        ("triggerDelay", c.c_double),
        ("meanCount", c.c_uint32)
    ]


class WFD_SAMPLECFG(c.Structure):
    _fields_ = [
        ("interval", c.c_double),
        ("preTrigger", c.c_uint32),
        ("postTrigger", c.c_uint32),
        ("triggerLevel", c.c_double),
        ("triggerHysteresis", c.c_double),
        ("triggerDelay", c.c_double),
        ("triggerSource", c.c_int),
        ("continueWithNext", c.c_uint16),
        ("noWaitForTrigger", c.c_uint16)
    ]


class WFD_SEGMENTCFG(c.Structure):
    _fields_ = [
        ("interval", c.c_uint32),              # sample rate devider
        ("preTrigger", c.c_uint32),            # number of samples before trigger event
        ("postTrigger", c.c_uint32),           # number of samples after trigger event
        ("triggerLevel", c.c_uint32),          # level of trigger comparator
        ("triggerHysteresis", c.c_uint32),     # hysteresis of trigger comparator
        ("triggerDelay", c.c_uint32),          # delay between trigger event and start of aquisition
        ("startAddr", c.c_uint32),             # start address of sampling data in instrument memory
        ("ctrlReg", c.c_uint32)                # control register (bit 7..0 -> Trigger source selector", c_uint32), bit 8 -> Continue / Stop)
    ]

# Trigger Matrix

class TM_INPUT_TAB(c.Structure):
    _fields_ = [
        ("inputMask", c.c_ulonglong),          # One entry of \ref PXM78xx_TM_CHANNEL_t in each element of the array. This value can be passed to any function expecting a TriggerMatrix channel as parameter.
        ("inputName", c.c_char * 64)           # Human readable description of the channel.
    ]

class TM_CHANNEL_TAB(c.Structure):
    _fields_ = [
        ("chanelIdx", c.c_int),                # One entry of \ref public_tm_input in each element of the array. This value can be passed to PXM78xx_TM_ConfigInputMask().
        ("channelName", c.c_char * 64)         # Human readable description of the input.
    ]

# endregion

# region Enums

class PXM78xx_STATUS(IntEnum):
    OK = 0,  # Instrument is operable
    STFAIL = 1,  # SelfTest failed
    CALINVALID = 2,  # calibration data invalid
    TEMPLOW = 3,  # Temperature too low
    TEMPHIGH = 4,  # Temperature too high
    AF_FAIL = 5,  # AnalogFrontend failure
    POWER_FAIL = 6,  # AnalogFrontend Power Supply failure
    DCDC_FAIL = 7,  # DCDC Converter failure
    PLL_FAIL = 8,  # PLL failure
    SDM_TIMEOUT = 9,  # SerDes Timeout
    DATA_MIGRATED = 10  # Functional limitation due to device data migration


class PXM78xx_ERRORCODES(IntEnum):
    FUNC_NOT_LOADED = -0x6000,  # Desired function not loaded from 'PXM78xx.dll' library.
    SW = -8000,  # unknown software error
    HW = -8001,  # unknown hardware error
    INV_PARAMETER = -8002,  # invalid parameter
    INV_HANDLE = -8003,  # invalid intrument handle
    NULLPOINTER = -8004,  # nullpointer exception
    INV_ADR = -8005,  # address out of range
    INV_VALUE = -8006,  # invalid input value
    INV_SAMPLERATE = -8007,  # invalid sample rate
    INV_CHANNEL = -8008,  # invalid channel
    INV_MODE = -8009,  # invalid mode
    INV_IMAGE = -8010,  # invalid update image
    INV_APERTURE = -8011,  # invalid aperture
    INV_HWCFG = -8012,  # invalid hardware configuration
    ID_QUERY = -8013,  # identification query failed
    I2C_ACCESS = -8014,  # I2C access failed
    I2C_NACK = -8015,  # no acknowlage from I2C slave
    TIMEOUT = -8016,  # communication timeout
    OPTION = -8017,  # option not available
    MEMORY = -8018,  # could not allocate memory
    FILE = -8019,  # opening or reading file failed
    CRC = -8020,  # invalid checksum
    VERIFY = -8021,  # verification of written data failed
    INV_CAL = -8023,  # calibration invalid
    NOT_INIT = -8024,  # instrument not initialized
    DATAID = -8025,  # incompatible calibration data
    NO_CAL_VAL = -8026,  # no calibration available
    NO_RANGE = -8027,  # no suitable range available
    NO_FILTER = -8028,  # no suitable filter available
    WAITTRG = -8029,  # waiting for trigger
    SEGMENT_INACTIVE = -8030,  # segment is inactive
    ANALOG_BOARD = -8031,  # analog board not available
    NOT_SUPPORTED = -8032,  # feature or function not supported
    INV_FUNC = -8033,  # invalid measurement function
    INV_ADJVAL = -8034,  # adjustment value is not acceptable
    INV_FIRMWARE = -8035,  # instrument firmware is not compatible
    RSC_INACTIVE = -8036,  # resource is inactive
    TRIGGER_FAILURE = -8037,  # general trigger failure
    INV_VERSION = -8038,  # a given version is not compatible
    INV_BUF_SIZE = -8039,  # a given buffer size is not sufficient
    # Warnings
    WARN_CORRUPT_DATA = 5000,  # data in NV-memory is corrupt
    WARN_INC_APERTURE = 5001,  # increase aperture
    WARN_DEC_APERTURE = 5002,  # decrease aperture
    WARN_NO_SIGNAL = 5003,  # no input signal
    WARN_IRNORED = 5004,  # setting is ignored in current condition.
    WARN_OVRNG = 5005,  # input signal is out of acceptable range.


class PXM78xx_RANGE:
    DCV_10mV = 0.010  # 10mV  DC voltage range
    DCV_100mV = 0.100  # 1000mV DC voltage range
    DCV_125mV = 0.125  # 250mV DC voltage range
    DCV_250mV = 0.25  # 250mV DC voltage range
    DCV_500mV = 0.50  # 500mV DC voltage range
    DCV_1V = 1.00  # 1V    DC voltage range
    DCV_2V = 2.00  # 2V    DC voltage range
    DCV_4V = 4.00  # 4V    DC voltage range
    DCV_8V = 8.00  # 8V    DC voltage range
    DCV_16V = 16.00  # 16V   DC voltage range
    DCV_32V = 32.00  # 32V   DC voltage range
    DCV_64V = 64.00  # 64V   DC voltage range
    DCV_128V = 128.00  # 128V  DC voltage range
    DCV_256V = 256.00  # 256V  DC voltage range

    ACV_5mV = 0.005  # 5mV   AC voltage range
    ACV_50mV = 0.050  # 50mV  AC voltage range
    ACV_125mV = 0.125  # 125mV AC voltage range
    ACV_250mV = 0.25  # 250mV AC voltage range
    ACV_500mV = 0.50  # 500mV AC voltage range
    ACV_1V = 1.00  # 1V    AC voltage range
    ACV_2V = 2.00  # 2V    AC voltage range
    ACV_4V = 4.00  # 4V    AC voltage range
    ACV_8V = 8.00  # 8V    AC voltage range
    ACV_16V = 16.00  # 16V   AC voltage range
    ACV_32V = 32.00  # 32V   AC voltage range
    ACV_64V = 64.00  # 64V   AC voltage range
    ACV_128V = 128.00  # 128V  AC voltage range

    DCA_10mA = 0.010  # 10mA  DC current range
    DCA_100mA = 0.100  # 100mA DC current range
    DCA_1A = 1.000  # 1A    DC current range

    ACA_10mA = 0.010  # 10mA  AC current range
    ACA_100mA = 0.100  # 100mA AC current range
    ACA_1A = 1.000  # 1A    AC current range

    L_10uH = 1.00e-5  # 10uH  inductance range
    L_100uH = 1.00e-4  # 100uH inductance range
    L_1mH = 1.00e-3  # 1mH   inductance range
    L_10mH = 1.00e-2  # 10mH  inductance range
    L_100mH = 1.00e-1  # 100mH inductance range
    L_1H = 1.00e-0  # 1H    inductance range

    C_1nF = 1.00e-9  # 1nF   capacitance range
    C_10nF = 1.00e-8  # 10nF  capacitance range
    C_100nF = 1.00e-7  # 100nF capacitance range
    C_1uF = 1.00e-6  # 1uF   capacitance range
    C_10uF = 1.00e-5  # 10uF  capacitance range
    C_100uF = 1.00e-4  # 100uF capacitance range
    C_1mF = 1.00e-3  # 1mF   capacitance range
    C_10mF = 1.00e-2  # 10mF  capacitance range

    R_100OHM = 1.00e+2  # 100Ohm  resistance range
    R_1kOHM = 1.00e+3  # 1kOhm   resistance range
    R_10kOHM = 1.00e+4  # 10kOhm  resistance range
    R_100kOHM = 1.00e+5  # 100kOhm resistance range
    R_1MOHM = 1.00e+6  # 1MOhm   resistance range
    R_10MOHM = 1.00e+7  # 10MOhm  resistance range


class PXM78xx_FUNC(IntEnum):
    DMM_DCV = 0,  # DC voltage measurement
    DMM_ACV = 1,  # AC voltage measurement with AC coupling
    DMM_ACDCV = 2,  # AC+DC voltage measurement with DC coupling. Result is RMS of applied signal (AC+DC part).
    DMM_DCC = 3,  # DC current measurement
    DMM_ACC = 4,  # AC current measurement
    DMM_L2W = 5,  # inductance measurement 2 wire (not available on all models)
    DMM_L4W = 6,  # inductance measurement 4 wire (not available on all models)
    DMM_C2W = 7,  # capacitance measurement 2 wire (not available on all models)
    DMM_C4W = 8,  # capacitance measurement 4 wire (not available on all models)
    DMM_R2W = 9,  # resistance measurement 2 wire
    DMM_R4W = 10,  # resistance measurement 4 wire
    DMM_DIODE = 11,  # diode measurement
    WFD_DCV = 12,  # waveform digitizer voltage
    WFD_DCC = 13,  # waveform digitizer current
    DMM_ACV_DC_COUPLED = 14,  # AC voltage measurement with DC Coupling. Result is RMS of AC part.


class PXM78xx_FILTER(IntEnum):
    FILTER_100Hz = 100,  # 100 Hz filter.
    FILTER_1kHz = 1000,  # 1 kHz filter.
    FILTER_10kHz = 10000,  # 10 kHz filter.
    FILTER_100kHz = 100000,  # 100 kHz filter.
    FILTER_1MHz = 1000000,  # 1 MHz filter.
    FILTER_NONE = 9999999,  # no filter for maximum analog bandwidth.
    FILTER_INVALID = -1  # invalid filter setting.


class PXM78xx_CHANNEL(IntEnum):
    ADC16BIT = 0,  # 16 Bit 20 MSps ADC
    ADC24BIT = 1  # 24 Bit 1 MSps ADC (not available on all models)


class PXM78xx_TM_EDGE(IntEnum):
    FALLING = 0,  # trigger on falling edge of the input signal.
    RISING = 1  # trigger on rising edge of the input signal.


class PXM78xx_CABLECOMPENSATION_MODE(IntEnum):
    R2W = 0,  # compensate to zero, using R2W measurement only.
    R4W = 1  # compensate to R4W result, using R2W and R4W measurment.


class PXM78xx_WFD_STATUS(IntEnum):
    PXM78xx_WFD_STATUS_IDLE = 0,  # Sample Engine is stopped. Call \ref PXM78xx_WFD_StartSampling to start the Sampling Engine.
    PXM78xx_WFD_STATUS_WAITING = 1,  # Pre-trigger samples have been acquired and the Sample Engine is waiting for a trigger event to start acquisition of post-trigger samples.
    PXM78xx_WFD_STATUS_TRIGGERED = 2,  # Sampling Engine is triggered an will begin with data acquisition in the next clock cycle.
    PXM78xx_WFD_STATUS_FINISHED = 3,  # Acquisition is finished. Data can be fetched.
    PXM78xx_WFD_STATUS_ERROR = 4,  # FIFO has run full. If this happens something went fundamentally wrong.
    PXM78xx_WFD_STATUS_RUNNING = 5,  # Data acquisition in progress


class PXM78xx_COUPLING(IntEnum):
    PXM78xx_COUPLING_DC = 0,
    PXM78xx_COUPLING_AC = 1


class PXM78xx_WFD_TRIGGER(IntEnum):
    EXTERN  = (1<<7),               # input from trigger matrix
    RISING  = (1<<7)|(1<<0),        # measurement signal rising edge
    FALLING = (1<<7)|(1<<1),        # measurement signal falling edge
    BOTH    = (1<<7)|(1<<0)|(1<<1)  # measurement signal rising or falling edge

# Trigger Matrix definitions

class PXM78xx_TM_INPUT(IntEnum):
    SOFTWARE        = (0x0000000000000800 <<  0)  # PXI trigger line 0
    PXI_TRIG0       = (0x0000000000001000 <<  0)  # PXI trigger line 0
    PXI_TRIG1       = (0x0000000000001000 <<  1)  # PXI trigger line 1
    PXI_TRIG2       = (0x0000000000001000 <<  2)  # PXI trigger line 2
    PXI_TRIG3       = (0x0000000000001000 <<  3)  # PXI trigger line 3
    PXI_TRIG4       = (0x0000000000001000 <<  4)  # PXI trigger line 4
    PXI_TRIG5       = (0x0000000000001000 <<  5)  # PXI trigger line 5
    PXI_TRIG6       = (0x0000000000001000 <<  6)  # PXI trigger line 6
    PXI_TRIG7       = (0x0000000000001000 <<  7)  # PXI trigger line 7
    PXI_STARTRIG    = (0x0000000000001000 <<  9)  # PXI star trigger

    ADC16_CMP1_RISE = (0x0000000000001000 << 11)  # 16Bit ADC Comparator 1 Rising Edge
    ADC16_CMP1_FALL = (0x0000000000001000 << 12)  # 16Bit ADC Comparator 1 Falling Edge
    ADC16_CMP2_RISE = (0x0000000000001000 << 13)  # 16Bit ADC Comparator 2 Rising Edge
    ADC16_CMP2_FALL = (0x0000000000001000 << 14)  # 16Bit ADC Comparator 2 Falling Edge
    ADC16_CMP3_RISE = (0x0000000000001000 << 15)  # 16Bit ADC Comparator 3 Rising Edge
    ADC16_CMP3_FALL = (0x0000000000001000 << 23)  # 16Bit ADC Comparator 3 Falling Edge
    ADC16_SMPL      = (0x0000000000001000 << 24)  # 16Bit ADC Sampling Trigger

    ADC24_CMP1_RISE = (0x0000000000001000 << 16)  # 24Bit ADC Comparator 1 Rising Edge
    ADC24_CMP1_FALL = (0x0000000000001000 << 17)  # 24Bit ADC Comparator 1 Falling Edge
    ADC24_CMP2_RISE = (0x0000000000001000 << 18)  # 24Bit ADC Comparator 2 Rising Edge
    ADC24_CMP2_FALL = (0x0000000000001000 << 19)  # 24Bit ADC Comparator 2 Falling Edge
    ADC24_SMPL      = (0x0000000000001000 << 20)  # 24Bit ADC Sampling Trigger

    FRONT2          = (0x0000000000001000 << 21)  # external front panel input connector
    FRONT1          = (0x0000000000001000 << 22)  # external front panel input connector
    FLOAT           = (0x0000000000001000 <<  0)  # trigger line from floating FPGA
    
class PXM78xx_TM_CHANNEL(IntEnum):
    PXI0     = 0,  # PXI trigger line 0
    PXI1     = 1,  # PXI trigger line 1
    PXI2     = 2,  # PXI trigger line 2
    PXI3     = 3,  # PXI trigger line 3
    PXI4     = 4,  # PXI trigger line 4
    PXI5     = 5,  # PXI trigger line 5
    PXI6     = 6,  # PXI trigger line 6
    PXI7     = 7,  # PXI trigger line 7
    WFD16    = 8,  # 16Bit ADC Sample Engine external trigger
    WFD24    = 13, # 24Bit ADC Sample Engine external trigger
    ADC16    = 9,  # 16Bit ADC trigger
    ADC24    = 10, # 24Bit ADC trigger
    FRONT1   = 15, # Front Trigger 1
    FRONT2   = 14, # Front Trigger 2
    TC1_0    = 11, # Timer/Counter Channel 1 Input 0
    TC1_1    = 12, # Timer/Counter Channel 1 Input 1
    TC2_0    = 16, # Timer/Counter Channel 2 Input 0
    TC2_1    = 17  # Timer/Counter Channel 2 Input 1

class PXM78xx_TM_INPUT_FUNC(IntEnum):
    OR  = 0,     # require one of the specified trigger inputs (logical OR)
    AND = 1      # require all of the specified trigger inputs (logical AND)

class PXM78xx_TM_EDGE(IntEnum):
    FALLING = 0, # trigger on falling edge of the input signal.
    RISING  = 1  # trigger on rising edge of the input signal.

class PXM78xx_TM_MODE(IntEnum):
    ASYNC        = 0, # Asynchronous trigger routing optimized for minimal trigger latency.
    SYNC_LEVEL   = 1, # Synchronous trigger routing. Input signals are synchonized to the TriggerMatrix Clock. This Mode is prefered for external trigger signals (PXI Backplane or Front) which are routed to an internal trigger reciever (Timer/Counter, Waveform Digitizer, ...).
    SYNC_SLOPE   = 2  # Synchronous trigger routung with slope generation. This mode features edge detection, single shot, configurable pulse width and delay.

# Timer/Counter definitions

# Timer/Counter Channel
class PXM78xx_TC_CHANNEL(IntEnum):
    TC1 = 0,                      # TimerCounter Channel 1
    TC2 = 1                       # TimerCounter Channel 2

# Timer/Counter Status
class PXM78xx_TC_STATUS(IntEnum):
    BUSY      = 0x0,              # Timer/Counter is busy doing very important shit and things
    FINISHED  = 0x1,              # Timer/Counter has finished and measurement result is ready
    WAITTRG   = 0x2,              # Timer/Counter is waiting for a trigger event
    IDLE      = 0x4               # Timer/Counter is ready to start

class PXM78xx_TC_MODE(IntEnum):
    TIMER_AA          = 0x01,     # measure time between two events on Trigger A.
    TIMER_AB          = 0x02,     # measure time between an event on Trigger A and Trigger B.
    COUNTER_GATE      = 0x04,     # count events of TriggerA during GateTime
    COUNTER_B         = 0x08,     # count events of TriggerA while Trigger B is HIGH
    TIMER_ABA         = 0x10      # measure time between an event of Trigger A and Trigger B (result1) and two events on Trigger A (result2). This mode is useful for PulseWidthRatio measurement if Trigger A is rising edge and Trigger B is falling edge of one signal.


# Timer/Counter Trigger Input
# These values can combined with an bitwise OR (|) if necessary.
# PXM78xx_TC_ConfigTriggerInput()

class PXM78xx_TC_TRGINPUT(IntEnum):
    NONE          = 0x00,         # leave the Timer/Counter trigger unconnected
    IN0_RISING    = 0x01,         # connect the Timer/Counter trigger to input 0 of the TriggerMatrix with detection of the rising edge. 
    IN0_FALLING   = 0x02,         # connect the Timer/Counter trigger to input 0 of the TriggerMatrix with detection of the falling edge.
    IN0_LEVEL     = 0x04,         # connect the Timer/Counter trigger to input 0 of the TriggerMatrix without edge detection.
    IN1_RISING    = 0x08,         # connect the Timer/Counter trigger to input 1 of the TriggerMatrix with detection of the rising edge.
    IN1_FALLING   = 0x10,         # connect the Timer/Counter trigger to input 1 of the TriggerMatrix with detection of the falling edge.
    IN1_LEVEL     = 0x20,         # connect the Timer/Counter trigger to input 1 of the TriggerMatrix without edge detection.
    MASK          = 0xFF

# endregion


class PXM78xx_Error(Exception):
    def __init__(self, message, errorCode=None):
        self.message = message
        self.errorCode = errorCode

    def __str__(self):
        return self.message


class PXM78xx_Base:

    def __init__(self, session):
        self.session = session
        self.vi = 0

        if platform.system() == "Windows":
            arch = platform.architecture()
            if "64bit" in arch:
                self._handle = c.windll.LoadLibrary("LXI_PXM78xx_w64")

            else:
                self._handle = c.windll.LoadLibrary("LXI_PXM78xx_w32")

        self.pythonMajorVersion = version_info[0]

    #region Private methods for error handling and Python 2/3 string issues

    def _stringToStr(self, inputString):
        """Take a string passed to a function in Python 2 or Python 3 and convert to
           a ctypes-friendly ASCII string"""

        # Check for Python 2 or 3
        if self.pythonMajorVersion < 3:
            if type(inputString) is str:
                return inputString
            if type(inputString) is unicode:
                return inputString.encode()
        else:
            if type(inputString) is bytes:
                return inputString
            elif type(inputString) is str:
                return inputString.encode()

    def _pythonString(self, inputString):
        """Ensure returned strings are native in Python 2 and Python 3"""

        # Check for Python 2 or 3
        if self.pythonMajorVersion < 3:
            try:
                return inputString.value
            except AttributeError:
                return inputString
        else:
            try:
                return inputString.value.decode()
            except AttributeError:
                return inputString.decode()

    def _handleError(self, error):

        if error:
            errorString = c.create_string_buffer(256)
            self._handle.LXI_PXM78xx_error_message(self.session, 0, int(error), c.byref(errorString), 256)
            errorString = self._pythonString(errorString.value)
            raise PXM78xx_Error(errorString, errorCode=error)
        return

    #endregion

    #region Discovery and connection functions

    def getVersion(self):

        bufferSize = 256
        rev = c.create_string_buffer(bufferSize)

        err = self._handle.LXI_PXM78xx_GetVersion(rev, bufferSize)
        self._handleError(err)

        return self._pythonString(rev.value)

    def QueryLibraryVersions(self):

        bufferSize = 256
        rev = c.create_string_buffer(bufferSize)

        err = self._handle.LXI_PXM78xx_QueryLibraryVersions(self.session, rev, bufferSize)
        self._handleError(err)

        return "PyWrap_LXI_PXM78xx: " + __version__ + "\n" + self._pythonString(rev.value)

    def findFreeInstruments(self):

        bufferSize = 256
        resourceNames = ((c.c_char * bufferSize) * 10)()
        resourceCount = c.c_uint32(10)
        buslist = (c.c_uint32 * bufferSize)()
        slotlist = (c.c_uint32 * bufferSize)()

        err = self._handle.LXI_PXM78xx_FindFreeInstruments(self.session, resourceNames, c.byref(resourceCount), buslist, slotlist)
        self._handleError(err)

        resources = [self._pythonString(name.value) for name in resourceNames if self._pythonString(name.value) != ""]

        return resources

    def autoConnectToFirst(self):

        instrHandle = c.c_uint32()

        err = self._handle.LXI_PXM78xx_autoConnectToFirst(self.session, c.byref(instrHandle))
        self._handleError(err)

        instrument = _PXM78xx_Card(self.session, instrHandle)

        return instrument

    def autoConnectToAll(self):

        instrArrayLength = c.c_uint16(16)
        instrArray = (c.c_uint32 * instrArrayLength.value)()
        numConnected = c.c_uint32(0)

        err = self._handle.LXI_PXM78xx_autoConnectToAll(self.session,
                                                        instrArray,
                                                        instrArrayLength,
                                                        c.byref(numConnected))
        self._handleError(err)

        instruments = []

        for i in range(numConnected.value):
            instruments.append(_PXM78xx_Card(self.session, instrArray[i]))

        return instruments


    #endregion

class _PXM78xx_Card(PXM78xx_Base):

    #region Constructor, error and destructor methods

    def __init__(self, session, vi):

        PXM78xx_Base.__init__(self, session)

        self.vi = vi
        self.session = session
        self.disposed = False

    def _close(self):
        if not self.disposed:
            self._handle.LXI_PXM78xx_close(self.session, self.vi)
            self.disposed = True
        return

    def __del__(self):
        if not self.disposed:
            self._close()
        return

    def _handleError(self, error):

        if error:
            errorString = c.create_string_buffer(256)
            self._handle.LXI_PXM78xx_error_message(self.session, self.vi, int(error), c.byref(errorString), 256)
            errorString = self._pythonString(errorString.value)

            # If the error code is a warning (between 5000 and 5005)
            if 5000 <= error <= 5005:
                warnings.warn(errorString)

            # Else it's just a regular error
            else:
                raise PXM78xx_Error(errorString, errorCode=error)
        return

    #endregion

    #region Self test, reset, and instrument identification methods

    def reset(self):

        err = self._handle.LXI_PXM78xx_reset(self.session, self.vi)
        self._handleError(err)

        return

    def selfTest(self):

        testResult = c.c_uint16()
        messageBufferLength = c.c_uint32(256)
        testMessage = c.create_string_buffer(messageBufferLength.value)

        err = self._handle.LXI_PXM78xx_self_test(self.session,
                                                 self.vi,
                                                 c.byref(testResult),
                                                 testMessage,
                                                 messageBufferLength)
        self._handleError(err)

        return testResult.value, self._pythonString(testMessage.value)

    def resetFuse(self):

        err = self._handle.LXI_PXM78xx_AF_ResetFuse(self.session, self.vi)
        self._handleError(err)

        return

    def queryStatus(self):

        status = c.c_int()

        err = self._handle.LXI_PXM78xx_QueryStatus(self.session, self.vi, c.byref(status))
        self._handleError(err)

        return status.value

    def queryStatusMessage(self):

        message = c.create_string_buffer(64)
        messageLen = c.c_uint32(64)

        err = self._handle.LXI_PXM78xx_QueryStatusMessage(self.session, self.vi, message, messageLen)
        self._handleError(err)

        return self._pythonString(message)

    def queryTemperature(self):

        tempShunt = c.c_double(0)
        tempFPGA  = c.c_double(0)

        err = self._handle.LXI_PXM78xx_QueryTemperature(self.session, self.vi, c.byref(tempFPGA), c.byref(tempShunt))
        self._handleError(err)

        return tempFPGA.value, tempShunt.value

    def querySlotNumber(self):

        slot = c.c_int16(0)

        err = self._handle.LXI_PXM78xx_QuerySlotNumber(self.session, self.vi, c.byref(slot))
        self._handleError(err)

        return slot.value

    def queryInstrumentLocation(self):

        bus = c.c_uint32(0)
        device = c.c_uint32(0)

        err = self._handle.LXI_PXM78xx_QueryInstrumentLocation(self.session, self.vi, c.byref(bus), c.byref(device))
        self._handleError(err)

        return bus.value, device.value

    def querySerialNumber(self):

        serialNumber = c.create_string_buffer(10)
        serialNumberLen = c.c_uint32(10)

        err = self._handle.LXI_PXM78xx_QuerySerialNumber(self.session, self.vi, serialNumber, serialNumberLen)
        self._handleError(err)

        return self._pythonString(serialNumber)

    def queryProductName(self):

        productName = c.create_string_buffer(128)
        productNameLen = c.c_uint32(128)

        err = self._handle.LXI_PXM78xx_QueryProductName(self.session, self.vi, productName, productNameLen)
        self._handleError(err)

        return self._pythonString(productName)

    #endregion

    #region DMM methods

    def DMM_configFunction(self, function):

        function = c.c_int(function)

        err = self._handle.LXI_PXM78xx_DMM_ConfigFunction(self.session, self.vi, function)
        self._handleError(err)

        return

    def DMM_configRange(self, measureRange):

        measureRange = c.c_double(measureRange)

        err = self._handle.LXI_PXM78xx_DMM_ConfigRange(self.session, self.vi, measureRange)
        self._handleError(err)

        return

    def DMM_configMeasurement(self, function, measureRange):

        function = c.c_int(function)
        measureRange = c.c_double(measureRange)

        err = self._handle.LXI_PXM78xx_DMM_ConfigMeasurement(self.session, self.vi, function, measureRange)
        self._handleError(err)

        return

    def DMM_queryMeasurement(self):

        function = c.c_int(0)
        measureRange = c.c_double(0.0)

        err = self._handle.LXI_PXM78xx_DMM_QueryMeasurement(self.session,
                                                            self.vi,
                                                            c.byref(function),
                                                            c.byref(measureRange))
        self._handleError(err)

        return function.value, measureRange.value

    def DMM_configFilter(self, bwFilter):

        bwFilter = c.c_int(bwFilter)

        err = self._handle.LXI_PXM78xx_DMM_ConfigFilter(self.session, self.vi, bwFilter)
        self._handleError(err)

        return

    def DMM_queryFilter(self):

        bwFilter = c.c_int(0)

        err = self._handle.LXI_PXM78xx_DMM_QueryFilter(self.session, self.vi, c.byref(bwFilter))
        self._handleError(err)

        return bwFilter.value

    def DMM_forceTrigger(self):

        err = self._handle.LXI_PXM78xx_DMM_ForceTrigger(self.session. self.vi)
        self._handleError(err)

        return

    def DMM_singleMeasure(self):

        result = c.c_double()

        err = self._handle.LXI_PXM78xx_DMM_SingleMeasure(self.session, self.vi, c.byref(result))
        self._handleError(err)

        return result.value

    def DMM_meanMeasure(self, aperture):

        aperture = c.c_double(aperture)
        result = c.c_double()
        sbResult = DMM_SBRESULT()

        err = self._handle.LXI_PXM78xx_DMM_MeanMeasure(self.session, self.vi, aperture, c.byref(result), c.byref(sbResult))
        self._handleError(err)

        return result.value, sbResult

    def DMM_fetchSingleResult(self):

        result = c.c_double()

        err = self._handle.LXI_PXM78xx_DMM_FetchSingleResult(self.session, self.vi, c.byref(result))
        self._handleError(err)

        return result.value

    def DMM_fetchMeanResult(self):

        result = c.c_double()
        sbResult = DMM_SBRESULT()

        err = self._handle.LXI_PXM78xx_DMM_FetchMeanResult(self.session, self.vi, c.byref(result), c.byref(sbResult))
        self._handleError(err)

        return result.value, sbResult

    def DMM_queryAccuracy(self, signalFrequency, result):

        result = c.c_double(result)
        signalFrequency = c.c_double(signalFrequency)
        uncertainty = c.c_double()

        err = self._handle.LXI_PXM78xx_DMM_QueryAccuracy(self.session,
                                                         self.vi,
                                                         signalFrequency,
                                                         result,
                                                         c.byref(uncertainty))
        self._handleError(err)

        return uncertainty.value

    def DMM_configAperture(self, aperture):

        aperture = c.c_double(aperture)
        sbResult = DMM_SBRESULT()

        err = self._handle.LXI_PXM78xx_DMM_ConfigAperture(self.session, self.vi, aperture, c.byref(sbResult))
        self._handleError(err)

        return sbResult

    def DMM_queryAperture(self):

        aperture = c.c_double()

        err = self._handle.LXI_PXM78xx_DMM_QueryAperture(self.session, self.vi, c.byref(aperture))
        self._handleError(err)

        return aperture.value

    def DMM_init(self):

        err = self._handle.LXI_PXM78xx_DMM_Init(self.session, self.vi)
        self._handleError(err)

        return

    def DMM_queryFilterList(self):

        filterValuesLen = c.c_uint32(5)
        filterValues = (c.c_uint32 * filterValuesLen.value)()
        filterLabelsLen = c.c_uint32(40)
        filterLabels = c.create_string_buffer(filterLabelsLen.value)

        err = self._handle.LXI_PXM78xx_DMM_QueryFilterList(self.session,
                                                           self.vi,
                                                           c.byref(filterValues),
                                                           c.byref(filterValuesLen),
                                                           c.byref(filterLabels),
                                                           filterLabelsLen)
        self._handleError(err)

        filterValuesList = []
        for i in range(filterValuesLen.value):
            filterValuesList.append(filterValues[i])

        filterLabelsList = self._pythonString(filterLabels.value).split(";")

        filtersDict = {filterLabelsList[i]: filterValuesList[i] for i in range(len(filterValuesList))}

        return filtersDict

    def DMM_queryChannel(self):

        channel = c.c_int()

        err = self._handle.LXI_PXM78xx_DMM_QueryChannel(self.session, self.vi, c.byref(channel))
        self._handleError(err)

        return channel.value

    def DMM_queryChannelByFunction(self, function, measureRange):

        function = c.c_int(function)
        measureRange = c.c_double(measureRange)
        channel = c.c_int()

        err = self._handle.LXI_PXM78xx_DMM_QueryChannelByFunction(self.session,
                                                                  self.vi,
                                                                  c.byref(channel),
                                                                  function,
                                                                  measureRange)
        self._handleError(err)

        return function.value

    def DMM_queryTriggerChannel(self):

        tmChannel = c.c_int()

        err = self._handle.LXI_PXM78xx_DMM_QueryTriggerChannel(self.session, self.vi, c.byref(tmChannel))
        self._handleError(err)

        return tmChannel.value

    def DMM_configTrigger(self, triggerSource, triggerDelay, holdOff, edge):

        triggerSource = c.c_uint64(triggerSource)
        triggerDelay = c.c_double(triggerDelay)
        holdOff = c.c_double(holdOff)
        edge = c.c_int(edge)

        err = self._handle.LXI_PXM78xx_DMM_ConfigTrigger(self.session,
                                                         self.vi,
                                                         triggerSource,
                                                         triggerDelay,
                                                         holdOff,
                                                         edge)
        self._handleError(err)

        return

    def DMM_queryTrigger(self):

        triggerSource = c.c_uint64()
        triggerDelay = c.c_double()
        holdOff = c.c_double()
        edge = c.c_int()

        err = self._handle.LXI_PXM78xx_DMM_QueryTrigger(self.session,
                                                        self.vi,
                                                        c.byref(triggerSource),
                                                        c.byref(triggerDelay),
                                                        c.byref(holdOff),
                                                        c.byref(edge))
        self._handleError(err)

        return triggerSource.value, triggerDelay.value, holdOff.value, edge.value

    def DMM_calculateElementsFromImpedance(self, parallel):

        parallel = c.c_uint32(parallel)
        sbResult = DMM_SBRESULT()
        resistance = c.c_double()
        capacitance = c.c_double()
        inductance = c.c_double()

        err = self._handle.LXI_PXM78xx_DMM_CalculateElementsFromImpedance(self.session,
                                                                          self.vi,
                                                                          parallel,
                                                                          c.byref(sbResult),
                                                                          c.byref(resistance),
                                                                          c.byref(capacitance),
                                                                          c.byref(inductance))
        self._handleError(err)

        return sbResult, resistance.value, capacitance.value, inductance.value

    def DMM_waitUntilReadyForTrigger(self):

        err = self._handle.LXI_PXM78xx_DMM_WaitUntilReadyForTrigger(self.session, self.vi)
        self._handleError(err)

        return

    def DMM_waitUntilFinished(self):

        err = self._handle.LXI_PXM78xx_DMM_WaitUntilFinished(self.session, self.vi)
        self._handleError(err)

        return

    def DMM_isOverRange(self, value):

        value = c.c_double(value)

        err = self._handle.LXI_PXM78xx_DMM_IsOverRange(self.session, value)

        if err == PXM78xx_ERRORCODES.WARN_OVRNG:
            return True
        else:
            return False

    def DMM_configACFrequencyMin(self, value):

        value = c.c_double(value)

        err = self._handle.LXI_PXM78xx_DMM_ConfigACFrequencyMin(self.session, self.vi, value)
        self._handleError(err)

        return

    def DMM_configACFrequencyMax(self, value):

        value = c.c_double(value)

        err = self._handle.LXI_PXM78xx_DMM_ConfigACFrequencyMax(self.session, self.vi, value)
        self._handleError(err)

        return

    def DMM_queryACFrequencyMin(self):

        value = c.c_double()

        err = self._handle.LXI_PXM78xx_DMM_QueryACFrequencyMin(self.session, self.vi, c.byref(value))
        self._handleError(err)

        return value.value

    def DMM_queryACFrequencyMax(self):

        value = c.c_double()

        err = self._handle.LXI_PXM78xx_DMM_QueryACFrequencyMax(self.session, self.vi, c.byref(value))
        self._handleError(err)

        return value.value

    def DMM_R2W_cableCompensation(self, mode, measureRange):

        mode = c.c_int(mode)
        measureRange = c.c_double(measureRange)

        err = self._handle.LXI_PXM78xx_DMM_R2W_CableCompensation(self.session,
                                                                 self.vi,
                                                                 mode,
                                                                 measureRange)
        self._handleError(err)

        return

    #endregion

    #region Waveform Digitiser methods

    def WFD_configSampling(self, sampleCfg):

        err = self._handle.LXI_PXM78xx_WFD_ConfigSampling(self.session, self.vi, c.byref(sampleCfg))
        self._handleError(err)

        return

    def WFD_querySampling(self):

        sampleCfg = WFD_SAMPLECFG()

        err = self._handle.LXI_PXM78xx_WFD_QuerySampling(self.session, self.vi, c.byref(sampleCfg))
        self._handleError(err)

        return sampleCfg

    def WFD_queryStatus(self):

        status = c.c_int()

        # last parameter reserved for future use
        err = self._handle.LXI_PXM78xx_WFD_QueryStatus(self.session, self.vi, c.byref(status), c.c_uint32(0))
        self._handleError(err)

        return status.value

    def WFD_queryStatusMessage(self):

        messageLen = c.c_uint32(64)
        message = c.create_string_buffer(messageLen.value)

        err = self._handle.LXI_PXM78xx_WFD_QueryStatusMessage(self.session, self.vi, c.byref(message), messageLen)
        self._handleError(err)

        return self._pythonString(message.value)

    def WFD_querySampleData(self, sampleCount):

        yData = (c.c_double * sampleCount)()
        xData = (c.c_double * sampleCount)()
        sampleCount = c.c_uint32(sampleCount)

        err = self._handle.LXI_PXM78xx_WFD_QuerySampleData(self.session,
                                                           self.vi,
                                                           c.byref(yData),
                                                           c.byref(xData),
                                                           c.byref(sampleCount))
        self._handleError(err)

        x = []
        y = []

        for i in range(sampleCount.value):
            y.append(yData[i])
            x.append(xData[i])

        return x, y

    def WFD_startSampling(self):

        err = self._handle.LXI_PXM78xx_WFD_StartSampling(self.session, self.vi)
        self._handleError(err)

        return

    def WFD_stopSampling(self):

        err = self._handle.LXI_PXM78xx_WFD_StopSampling(self.session, self.vi)
        self._handleError(err)

        return

    def WFD_init(self, channel):

        channel = c.c_int(channel)

        err = self._handle.LXI_PXM78xx_WFD_Init(self.session, self.vi, channel)
        self._handleError(err)

        return

    def WFD_queryTriggerChannel(self):

        channel = c.c_int()

        err = self._handle.LXI_PXM78xx_WFD_QueryTriggerChannel(self.session, self.vi, c.byref(channel))
        self._handleError(err)

        return channel.value

    def WFD_configMeasurement(self, function, measureRange):

        function = c.c_int(function)
        measureRange = c.c_double(measureRange)

        err = self._handle.LXI_PXM78xx_WFD_ConfigMeasurement(self.session, self.vi, function, measureRange)
        self._handleError(err)

        return

    def WFD_queryMeasurement(self):

        function = c.c_int()
        measureRange = c.c_double()

        err = self._handle.LXI_PXM78xx_WFD_ConfigMeasurement(self.session,
                                                             self.vi,
                                                             c.byref(function),
                                                             c.byref(measureRange))
        self._handleError(err)

        return function.value, measureRange.value

    def WFD_configSegment(self, segment, sampleCfg):

        segment = c.c_uint32(segment)

        err = self._handle.LXI_PXM78xx_WFD_ConfigSegment(self.session,
                                                         self.vi,
                                                         segment,
                                                         c.byref(sampleCfg))
        self._handleError(err)

        return

    def WFD_querySegment(self, segment):

        segment = c.c_uint32(segment)
        sampleCfg = WFD_SAMPLECFG()
        startAddr = c.c_uint32()

        err = self._handle.LXI_PXM78xx_WFD_QuerySegment(self.session,
                                                        self.vi,
                                                        segment,
                                                        c.byref(sampleCfg),
                                                        c.byref(startAddr))
        self._handleError(err)

        return sampleCfg, startAddr.value

    def WFD_querySegmentData(self, segment, sampleCount):

        xData = (c.c_double * sampleCount)()
        yData = (c.c_double * sampleCount)()
        sampleCount = c.c_uint32(sampleCount)
        segment = c.c_uint32(segment)
        segmentGap = c.c_double()

        err = self._handle.LXI_PXM78xx_WFD_QuerySegmentData(self.session,
                                                            self.vi,
                                                            segment,
                                                            c.byref(yData),
                                                            c.byref(xData),
                                                            c.byref(sampleCount),
                                                            c.byref(segmentGap))
        self._handleError(err)

        x = []
        y = []

        for i in range(sampleCount.value):
            y.append(yData[i])
            x.append(xData[i])

        return x, y, segmentGap.value

    def WFD_configComparator(self, compChannel, comparatorLevel, comparatorHysteresis):

        compChannel = c.c_uint32(compChannel)
        comparatorLevel = c.c_double(comparatorLevel)
        comparatorHysteresis = c.c_double(comparatorHysteresis)

        err = self._handle.LXI_PXM78xx_WFD_ConfigComparator(self.session,
                                                            self.vi,
                                                            compChannel,
                                                            comparatorLevel,
                                                            comparatorHysteresis)
        self._handleError(err)

        return

    def WFD_queryComparator(self, compChannel):

        compChannel = c.c_uint32(compChannel)
        comparatorLevel = c.c_double()
        comparatorHysteresis = c.c_double()

        err = self._handle.LXI_PXM78xx_WFD_QueryComparator(self.session,
                                                           self.vi,
                                                           compChannel,
                                                           c.byref(comparatorLevel),
                                                           c.byref(comparatorHysteresis))
        self._handleError(err)

        return comparatorLevel.value, comparatorHysteresis.value

    def WFD_queryMeanCount(self):

        meanCount = c.c_uint32()

        err = self._handle.LXI_PXM78xx_WFD_QueryMeanCount(self.session, self.vi, c.byref(meanCount))
        self._handleError(err)

        return meanCount.value

    def WFD_configMeanCount(self, meanCount):

        meanCount = c.c_uint32(meanCount)

        err = self._handle.LXI_PXM78xx_WFD_ConfigMeanCount(self.session, self.vi, meanCount)
        self._handleError(err)

        return

    def WFD_reset(self):

        err = self._handle.LXI_PXM78xx_WFD_Reset(self.session, self.vi)
        self._handleError(err)

        return

    def WFD_queryMaxSampleRate(self):

        fMax = c.c_uint32()

        err = self._handle.LXI_PXM78xx_WFD_QueryMaxSampleRate(self.session, self.vi, c.byref(fMax))
        self._handleError(err)

        return fMax.value

    def WFD_forceTrigger(self):

        err = self._handle.LXI_PXM78xx_WFD_ForceTrigger(self.session, self.vi)
        self._handleError(err)

        return

    def WFD_configChannel(self, channel):

        channel = c.c_int(channel)

        err = self._handle.LXI_PXM78xx_WFD_ConfigChannel(self.session, self.vi, channel)
        self._handleError(err)

        return

    def WFD_queryChannel(self):

        channel = c.c_int()

        err = self._handle.LXI_PXM78xx_WFD_QueryChannel(self.session, self.vi, c.byref(channel))
        self._handleError(err)

        return channel.value

    def WFD_configFilter(self, bwFilter):

        bwFilter = c.c_int(bwFilter)

        err = self._handle.LXI_PXM78xx_WFD_ConfigFilter(self.session, self.vi, bwFilter)
        self._handleError(err)

        return

    def WFD_queryFilter(self):

        bwFilter = c.c_int()

        err = self._handle.LXI_PXM78xx_WFD_QueryFilter(self.session, self.vi, c.byref(bwFilter))
        self._handleError(err)

        return bwFilter.value

    def WFD_configInputCoupling(self, coupling):

        coupling = c.c_int(coupling)

        err = self._handle.LXI_PXM78xx_WFD_ConfigInputCoupling(self.session, self.vi, coupling)
        self._handleError(err)

        return

    def WFD_queryInputCoupling(self):

        coupling = c.c_int()

        err = self._handle.LXI_PXM78xx_WFD_QueryInputCoupling(self.session, self.vi, c.byref(coupling))
        self._handleError(err)

        return coupling.value

    def WFD_queryFilterList(self):

        filterValuesLen = c.c_uint32(5)
        filterValues = (c.c_uint32 * filterValuesLen.value)()
        filterLabelsLen = c.c_uint32(40)
        filterLabels = c.create_string_buffer(filterLabelsLen.value)

        err = self._handle.LXI_PXM78xx_WFD_QueryFilterList(self.session,
                                                           self.vi,
                                                           c.byref(filterValues),
                                                           c.byref(filterValuesLen),
                                                           c.byref(filterLabels),
                                                           filterLabelsLen)
        self._handleError(err)

        filterValuesList = []
        for i in range(filterValuesLen.value):
            filterValuesList.append(filterValues[i])

        filterLabelsList = self._pythonString(filterLabels.value).split(";")

        filtersDict = {filterLabelsList[i]: filterValuesList[i] for i in range(len(filterValuesList))}

        return filtersDict

    def WFD_configTrigger(self, triggerSource, triggerDelay, holdOff, edge):

        triggerSource = c.c_uint64(triggerSource)
        triggerDelay = c.c_double(triggerDelay)
        holdOff = c.c_double(holdOff)
        edge = c.c_int(edge)

        err = self._handle.LXI_PXM78xx_WFD_ConfigTrigger(self.session,
                                                         self.vi,
                                                         triggerSource,
                                                         triggerDelay,
                                                         holdOff,
                                                         edge)
        self._handleError(err)

        return

    def WFD_queryTrigger(self):

        triggerSource = c.c_uint64()
        triggerDelay = c.c_double()
        holdOff = c.c_double()
        edge = c.c_int()

        err = self._handle.LXI_PXM78xx_WFD_QueryTrigger(self.session,
                                                        self.vi,
                                                        c.byref(triggerSource),
                                                        c.byref(triggerDelay),
                                                        c.byref(holdOff),
                                                        c.byref(edge))
        self._handleError(err)

        return triggerSource.value, triggerDelay.value, holdOff.value, edge.value

    def WFD_waitUntilReadyForTrigger(self, segment):

        segment = c.c_uint32(segment)

        err = self._handle.LXI_PXM78xx_WFD_WaitUntilReadyForTrigger(self.session, self.vi, segment)
        self._handleError(err)

        return

    def WFD_waitUntilFinished(self, timeout):

        timeout = c.c_double(timeout)

        err = self._handle.LXI_PXM78xx_WFD_WaitUntilFinished(self.session, self.vi, timeout)
        self._handleError(err)

        return

    def WFD_ConfigFetchTimeout(self, timeout):

        timeout = c.c_double(timeout)

        err = self._handle.LXI_PXM78xx_WFD_ConfigFetchTimeout(self.session, self.vi, timeout)
        self._handleError(err)

        return

    #endregion
    
    #region Trigger Matrix

    def TM_ConfigInputMask(self, channel, inputMask):

        channel = c.c_int(channel)
        inputMask = c.c_uint64(inputMask)

        err = self._handle.LXI_PXM78xx_TM_ConfigInputMask(self.session, self.vi, channel, inputMask)
        self._handleError(err)

        return

    def TM_QueryInputMask(self, channel):

        channel = c.c_int(channel)
        inputMask = c.c_uint32()

        err = self._handle.LXI_PXM78xx_TM_QueryInputMask(self.session, self.vi, channel, c.byref(inputMask))
        self._handleError(err)

        return inputMask.value

    def TM_ConfigInputFunction(self, channel, inputFunction):

        channel = c.c_int(channel)
        inputFunction = c.c_int(inputFunction)

        err = self._handle.LXI_PXM78xx_TM_ConfigInputFunction(self.session, self.vi, channel, inputFunction)
        self._handleError(err)

        return
        
        
    def TM_QueryInputFunction(self, channel):

        channel = c.c_int(channel)
        inputFunction = c.c_int()

        err = self._handle.LXI_PXM78xx_TM_QueryInputFunction(self.session, self.vi, channel, c.byref(inputFunction))
        self._handleError(err)

        return inputFunction.value

    def TM_ConfigInversion(self, channel, invert):

        channel = c.c_int(channel)
        invert = c.c_bool(invert)

        err = self._handle.LXI_PXM78xx_TM_ConfigInversion(self.session, self.vi, channel, invert)
        self._handleError(err)

        return

    def TM_QueryInversion(self, channel):

        channel = c.c_int(channel)
        invert = c.c_bool()

        err = self._handle.LXI_PXM78xx_TM_QueryInversion(self.session, self.vi, channel, c.byref(invert))
        self._handleError(err)

        return invert.value

    def TM_ConfigDelay(self, channel, trigDelay):

        channel = c.c_int(channel)
        trigDelay = c.c_double(trigDelay)

        err = self._handle.LXI_PXM78xx_TM_ConfigDelay(self.session, self.vi, channel, trigDelay)
        self._handleError(err)

        return
    
    def TM_QueryDelay(self, channel):

        channel = c.c_int(channel)
        trigDelay = c.c_double()

        err = self._handle.LXI_PXM78xx_TM_QueryDelay(self.session, self.vi, channel, c.byref(trigDelay))
        self._handleError(err)

        return trigDelay.value


    def TM_ConfigPulseWidth(self, channel, pulseWidth):

        channel = c.c_int(channel)
        pulseWidth = c.c_double(pulseWidth)

        err = self._handle.LXI_PXM78xx_TM_ConfigPulseWidth(self.session, self.vi, channel, pulseWidth)
        self._handleError(err)

        return

    def TM_QueryPulseWidth(self, channel):

        channel = c.c_int(channel)
        pulseWidth = c.c_double()

        err = self._handle.LXI_PXM78xx_TM_QueryPulseWidth(self.session, self.vi, channel, c.byref(pulseWidth))
        self._handleError(err)

        return pulseWidth.value


    def TM_ForceTrigger(self, affectedChannels):

        affectedChannels = c.c_uint32(affectedChannels)

        err = self._handle.LXI_PXM78xx_TM_ForceTrigger(self.session, self.vi, affectedChannels)
        self._handleError(err)

        return
    
    def TM_QueryEvent(self):

        affectedChannels = c.c_uint32()

        err = self._handle.LXI_PXM78xx_TM_QueryEvent(self.session, self.vi, c.byref(affectedChannels))
        self._handleError(err)

        return affectedChannels.value
    

    def TM_ConfigArming(self, channel, arm):

        channel = c.c_int(channel)
        arm = c.c_bool(arm)

        err = self._handle.LXI_PXM78xx_TM_ConfigArming(self.session, self.vi, channel, arm)
        self._handleError(err)

        return

    
    def TM_QueryArming(self, channel):

        channel = c.c_int(channel)
        arm = c.c_bool()

        err = self._handle.LXI_PXM78xx_TM_QueryArming(self.session, self.vi, channel, c.byref(arm))
        self._handleError(err)

        return arm.value


    def TM_ConfigSingleShot (self, channel, singleShot):
        channel = c.c_int(channel)
        singleShot = c.c_bool(singleShot)

        err = self._handle.LXI_PXM78xx_TM_ConfigSingleShot(self.session, self.vi, channel, singleShot)
        self._handleError(err)

        return

    def TM_QuerySingleShot(self, channel):

        channel = c.c_int(channel)
        singleShot = c.c_bool()

        err = self._handle.LXI_PXM78xx_TM_QuerySingleShot(self.session, self.vi, channel, c.byref(singleShot))
        self._handleError(err)

        return singleShot.value

    def TM_ConfigEdge(self, channel, edge):

        channel = c.c_int(channel)
        edge = c.c_int(edge)

        err = self._handle.LXI_PXM78xx_TM_ConfigEdge(self.session, self.vi, channel, edge)
        self._handleError(err)

        return

    def TM_QueryEdge(self, channel):

        channel = c.c_int(channel)
        edge = c.c_int()

        err = self._handle.LXI_PXM78xx_TM_QueryEdge(self.session, self.vi, channel, c.byref(edge))
        self._handleError(err)

        return edge.value
    
    def TM_ConfigMode(self, channel, mode):

        channel = c.c_int(channel)
        mode = c.c_int(mode)

        err = self._handle.LXI_PXM78xx_TM_ConfigMode(self.session, self.vi, channel, mode)
        self._handleError(err)

        return

    def TM_QueryMode(self, channel):

        channel = c.c_int(channel)
        mode = c.c_int()

        err = self._handle.LXI_PXM78xx_TM_QueryMode(self.session, self.vi, channel, c.byref(mode))
        self._handleError(err)

        return mode.value
    

    def TM_ConfigOutputEnable(self, channel, enable):

        channel = c.c_int(channel)
        enable = c.c_bool(enable)

        err = self._handle.LXI_PXM78xx_TM_ConfigOutputEnable(self.session, self.vi, channel, enable)
        self._handleError(err)

        return

    def TM_QueryOutputEnable(self, channel):

        channel = c.c_int(channel)
        enable = c.c_bool()

        err = self._handle.LXI_PXM78xx_TM_QueryOutputEnable(self.session, self.vi, channel, c.byref(enable))
        self._handleError(err)

        return enable.value

    def TM_QueryInputsAndChannels(self, inCnt, outCnt):

        inCnt = c.c_uint32(inCnt)
        outCnt = c.c_uint32(outCnt)
        inTab = (TM_INPUT_TAB * inCnt.value)()
        outTab = (TM_CHANNEL_TAB * outCnt.value)()
        
        err = self._handle.LXI_PXM78xx_TM_QueryInputsAndChannels(self.session, self.vi, c.byref(inTab), c.byref(inCnt), c.byref(outTab), c.byref(outCnt))

        self._handleError(err)

        return inTab, inCnt.value, outTab, outCnt.value
    
    def TM_Reset(self, ch):

        ch = c.c_int(ch)

        err = self._handle.LXI_PXM78xx_TM_Reset(self.session, self.vi, ch)

        self._handleError(err)

        return

    def TM_ConfigInputFilter(self, inputMask, minPulseWidth):

        inputMask = c.c_uint64(inputMask)
        minPulseWidth = c.c_double(minPulseWidth)

        err = self._handle.LXI_PXM78xx_TM_ConfigInputFilter(self.session, self.vi, inputMask, minPulseWidth)
        self._handleError(err)

        return
    
    def TM_QueryInputFilter(self, inputMask):

        inputMask = c.c_uint64(inputMask)
        minPulseWidth = c.c_double()

        err = self._handle.LXI_PXM78xx_TM_QueryInputFilter(self.session, self.vi, inputMask, c.byref(minPulseWidth))
        self._handleError(err)

        return minPulseWidth.value

    def TM_ConfigInputInversion(self, inputMask, invert):

        inputMask = c.c_uint64(inputMask)
        invert = c.c_bool(invert)

        err = self._handle.LXI_PXM78xx_TM_ConfigInputInversion(self.session, self.vi, inputMask, invert)
        self._handleError(err)

        return

    def TM_QueryInputInversion(self, inputMask):

        inputMask = c.c_uint64(inputMask)
        invert = c.c_bool()

        err = self._handle.LXI_PXM78xx_TM_QueryInputInversion(self.session, self.vi, inputMask, c.byref(invert))
        self._handleError(err)

        return invert.value

    def TM_ResetInput(self, inputMask):

        inputMask = c.c_uint64(inputMask)

        err = self._handle.LXI_PXM78xx_TM_ResetInput(self.session, self.vi, inputMask)
        self._handleError(err)

        return

    #endregion
    
    #region Timer/Counter

    
    def TC_ConfigEnable(self, ch, enable):

        ch = c.c_int(ch)
        enable = c.c_bool(enable)

        err = self._handle.LXI_PXM78xx_TC_ConfigEnable(self.session, self.vi, ch, enable)
        self._handleError(err)

        return

    def TC_QueryEnable(self, ch):

        ch = c.c_int(ch)
        enable = c.c_bool()

        err = self._handle.LXI_PXM78xx_TC_QueryEnable(self.session, self.vi, ch, c.byref(enable))
        self._handleError(err)

        return enable.value


    def TC_QueryStatus(self, ch):

        ch = c.c_int(ch)
        status = c.c_int()

        err = self._handle.LXI_PXM78xx_TC_QueryStatus(self.session, self.vi, ch, c.byref(status))
        self._handleError(err)

        return status.value

    def TC_QueryStatusMessage(self, ch):

        ch = c.c_int(ch)
        status = c.create_string_buffer(64)
        statusLen = c.c_uint32(64)

        err = self._handle.LXI_PXM78xx_TC_QueryStatusMessage(self.session, self.vi, ch, status, statusLen)
        self._handleError(err)

        return self._pythonString(status)
        

    def TC_ConfigMode(self, ch, mode):

        ch = c.c_int(ch)
        mode = c.c_int(mode)

        err = self._handle.LXI_PXM78xx_TC_ConfigMode(self.session, self.vi, ch, mode)
        self._handleError(err)

        return

    def TC_QueryMode(self, ch):

        ch = c.c_int(ch)
        mode = c.c_int()

        err = self._handle.LXI_PXM78xx_TC_QueryMode(self.session, self.vi, ch, c.byref(mode))
        self._handleError(err)

        return mode.value


    def TC_ConfigTriggerInput(self, ch, trgA, trgB):

        ch = c.c_int(ch)
        trgA = c.c_int(trgA)
        trgB = c.c_int(trgB)

        err = self._handle.LXI_PXM78xx_TC_ConfigTriggerInput(self.session, self.vi, ch, trgA, trgB)
        self._handleError(err)

        return
    
    def TC_QueryTriggerInput(self, ch):

        ch = c.c_int(ch)
        trgA = c.c_int()
        trgB = c.c_int()

        err = self._handle.LXI_PXM78xx_TC_QueryTriggerInput(self.session, self.vi, ch, c.byref(trgA), c.byref(trgB))
        self._handleError(err)

        return trgA.value, trgB.value

    def TC_ConfigGateTime(self, ch, time):

        ch = c.c_int(ch)
        time = c.c_double(time)

        err = self._handle.LXI_PXM78xx_TC_ConfigGateTime(self.session, self.vi, ch, time)
        self._handleError(err)

        return
    
    def TC_QueryGateTime(self, ch):

        ch = c.c_int(ch)
        time = c.c_double()

        err = self._handle.LXI_PXM78xx_TC_QueryGateTime(self.session, self.vi, ch, c.byref(time))
        self._handleError(err)

        return time.value


    def TC_FetchResult(self, ch, maxWaitTime):

        ch = c.c_int(ch)
        maxWaitTime = c.c_double(maxWaitTime)
        result1 = c.c_double()
        result2 = c.c_double()

        err = self._handle.LXI_PXM78xx_TC_FetchResult(self.session, self.vi, ch, c.byref(result1), c.byref(result2))
        self._handleError(err)

        return result1.value, result2.value

    def TC_Reset(self, ch):

        ch = c.c_int(ch)

        err = self._handle.LXI_PXM78xx_TC_Reset(self.session, self.vi, ch)
        self._handleError(err)

        return

    #endregion









