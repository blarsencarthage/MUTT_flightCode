import ctypes
from ctypes import util
import platform
from math import floor
import sys
from enum import IntEnum

__version__ = "1.7"
"""Pilpxi python wrapper version"""

#region Enums


class BattConversionTime(IntEnum):
    T_50us      = 0x0
    T_84us      = 0x1
    T_150us     = 0x2
    T_280us     = 0x3
    T_540us     = 0x4
    T_1052us    = 0x5
    T_2074us    = 0x6
    T_4120us    = 0x7


class BattNumSamples(IntEnum):
    SAMPLES_1       = 0x0
    SAMPLES_4       = 0x1
    SAMPLES_16      = 0x2
    SAMPLES_64      = 0x3
    SAMPLES_128     = 0x4
    SAMPLES_256     = 0x5
    SAMPLES_512     = 0x6
    SAMPLES_1024    = 0x7


class BattOperationMode(IntEnum):
    CONTINUOUS = 0xB
    TRIGGERED  = 0x3


class ErrorCodes(IntEnum):

    NO_ERR				= 0,	# No error 
    NO_CARD				= 1,	# No card present with specified number 
    NO_INFO				= 2,	# Card information unobtainable - hardware problem 
    CARD_DISABLED		= 3,	# Card disabled - hardware problem 
    BAD_SUB				= 4,	# Card has no sub-unit with specified number 
    BAD_BIT				= 5,	# Sub-unit has no bit with specified number 
    NO_CAL_DATA			= 6,	# Sub-unit has no calibration data to write/read 
    BAD_ARRAY			= 7,	# Array type, size or shape is incorrect 
    MUX_ILLEGAL			= 8,	# Non-zero write data is illegal for MUX sub-unit 
    EXCESS_CLOSURE		= 9,	# Sub-unit closure limit exceeded 
    ILLEGAL_MASK		= 10,	# One or more of the specified channels cannot be masked 
    OUTPUT_MASKED		= 11,	# Cannot activate an output that is masked 
    BAD_LOCATION		= 12,	# Cannot open a Pickering card at the specified location 
    READ_FAIL			= 13,	# Failed read from hardware 
    WRITE_FAIL			= 14,	# Failed write to hardware 
    DRIVER_OP			= 15,	# Hardware driver failure 
    DRIVER_VERSION		= 16,	# Incompatible hardware driver version 
    SUB_TYPE			= 17,	# Function call incompatible with sub-unit type or capabilities 
    BAD_ROW				= 18,	# Matrix row value out of range 
    BAD_COLUMN			= 19,	# Matrix column value out of range 
    BAD_ATTEN			= 20,	# Attenuation value out of range 
    BAD_VOLTAGE			= 21,	# Voltage value out of range 
    BAD_CAL_INDEX		= 22,	# Calibration reference out of range 
    BAD_SEGMENT			= 23,	# Segment number out of range 
    BAD_FUNC_CODE		= 24,	# Function code value out of range 
    BAD_SUBSWITCH		= 25,	# Subswitch value out of range 
    BAD_ACTION			= 26,	# Action code out of range 
    STATE_CORRUPT		= 27,	# Cannot execute due to corrupt sub-unit state 
    BAD_ATTR_CODE		= 28,	# Unrecognised attribute code 
    EEPROM_WRITE_TMO	= 29,	# Timeout writing to EEPROM 
    ILLEGAL_OP			= 30,	# Operation is illegal in the sub-unit's current state 
    BAD_POT				= 31,	# Unrecognised pot number requested 
    MATRIXR_ILLEGAL		= 32,	# Invalid write pattern for MATRIXR sub-unit 
    MISSING_CHANNEL		= 33,	# Attempted operation on non-existent channel 
    CARD_INACCESSIBLE	= 34,	# Card cannot be accessed (failed/removed/unpowered) 
    BAD_FP_FORMAT		= 35,	# Unsupported internal floating-point format (internal error) 
    UNCALIBRATED		= 36,	# Sub-unit is not calibrated 
    BAD_RESISTANCE		= 37,	# Unobtainable resistance value 
    BAD_STORE			= 38,	# Invalid calibration store number 
    BAD_MODE			= 39,	# Invalid mode value 
    SETTINGS_CONFLICT	= 40,	# Conflicting device settings 
    CARD_TYPE			= 41,	# Function call incompatible with card type or capabilities 
    BAD_POLE			= 42,	# Switch pole value out of range 
    MISSING_CAPABILITY	= 43,	# Attempted to activate a non-existent capability 
    MISSING_HARDWARE	= 44,	# Action requires hardware that is not present 
    HARDWARE_FAULT		= 45,	# Faulty hardware 
    EXECUTION_FAIL		= 46,	# Failed to execute (e.g. blocked by a hardware condition) 
    BAD_CURRENT			= 47,	# Current value out of range 
    BAD_RANGE			= 48,	# Invalid range value 
    ATTR_UNSUPPORTED	= 49,	# Attribute not supported 
    BAD_REGISTER		= 50,	# Register number out of range 
    MATRIXP_ILLEGAL		= 51,	# Invalid channel closure or write pattern for MATRIXP sub-unit 
    BUFFER_UNDERSIZE	= 52,	# Data buffer too small 
    ACCESS_MODE			= 53,	# Inconsistent shared access mode 
    POOR_RESISTANCE		= 54,	# Resistance outside limits 
    BAD_ATTR_VALUE		= 55,	# Bad attribute value 
    INVALID_POINTER		= 56,	# Invalid pointer 
    ATTR_READ_ONLY		= 57,	# Attribute is read only 
    ATTR_DISABLED		= 58,	# Attribute is disabled 
    PSU_MAIN_OUTPUT_DISABLED	= 59,	# Main output is disabled, cannot enable the channel 
    OUT_OF_MEMORY_HEAP	= 60,	# Unable to allocate memory on Heap
    INVALID_PROCESSID	= 61,	# Invalid ProcessID 
    SHARED_MEMORY		= 62,	# Shared memory error 
    CARD_OPENED_OTHER_PROCESS	= 63, 	# Card is opened by a process in exclusive mode 
    DIO_PORT_DISABLED	= 64, 	# DIO card PORT is disabled due to Over-Current Scenario 
    DIO_INVALID_FILE	= 65,	# DIO Pattern File is invalid 
    DIO_DYNAMIC_ACTIVE	= 66,	# DIO Dynamic operation is active, action not permissible 
    DIO_FILE_ENTRY_ERR	= 67,	# DIO File Entry has error, check the file entries.
    HW_INT_NOT_SUPPORTED    = 69,	# Hardware Interlock feature not supported for the card 
    HW_INT_ERROR			= 70	# Hardware Interlock is not detected on the card, cannot use the function 

class Attributes(IntEnum):
    
    TYPE				= 0x400,	# Gets/Sets DWORD attribute value of Type of the Sub-unit (values: TYPE_MUXM, TYPE_MUXMS) 
    MODE				= 0x401,	# Gets/Sets DWORD attribute value of Mode of the Card 

        # Current monitoring attributes 
    CNFGREG_VAL			= 0x402,	# Gets/Sets WORD value of config register 
    SHVLREG_VAL			= 0x403,	# Gets WORD value of shuntvoltage register 
    CURRENT_VAL			= 0x404,	# Gets double current value in Amps 

    # Read-only Power Supply attributes 
    INTERLOCK_STATUS			= 0x405,	# Gets BOOL value of interlock status (Card Level Attibute) 
    OVERCURRENT_STATUS_MAIN	    = 0x406,	# Gets BOOL value of main overcurrent status 
    OVERCURRENT_STATUS_CH		= 0x407,	# Gets BOOL value of overcurrent status on specific channel 

    # Read/Write Power Supply attributes 
    OUTPUT_ENABLE_MAIN			= 0x408,	# Gets/Sets BOOL value. Enables/Disables main 
    OUTPUT_ENABLE_CH			= 0x409,	# Gets/Sets BOOL value. Enables/Disables specific channel 

    # Read/Write Thermocouple Simulator functions 
    TS_SET_RANGE				= 0x40A,		# Gets/Sets Auto range which toggles between based on the value 
    #Read-only function
    TS_LOW_RANGE_MIN			= 0x40B,        # Gets DOUBLE value for minimum of the low range on Themocouple
    TS_LOW_RANGE_MED			= 0x40C,        # Gets DOUBLE value for median of the low range on Themocouple
    TS_LOW_RANGE_MAX			= 0x40D,        # Gets DOUBLE value for maxmium of the low range on Themocouple
    TS_LOW_RANGE_MAX_DEV		= 0x40E,        # Gets DOUBLE value for maximum deviation on the low range on Themocouple
    TS_LOW_RANGE_PREC_PC		= 0x40F,        # Gets DOUBLE value for precision percentage on the low range on Themocouple
    TS_LOW_RANGE_PREC_DELTA	    = 0x410,        # Gets DOUBLE value for precision delta on the low range on Themocouple
    TS_MED_RANGE_MIN			= 0x411,        # Gets DOUBLE value for minimum of the mid range on Themocouple
    TS_MED_RANGE_MED			= 0x412,        # Gets DOUBLE value for median of the mid range on Themocouple
    TS_MED_RANGE_MAX			= 0x413,        # Gets DOUBLE value for maximum of the mid range on Themocouple
    TS_MED_RANGE_MAX_DEV		= 0x414,        # Gets DOUBLE value for maximum deviation on the mid range on Themocouple
    TS_MED_RANGE_PREC_PC		= 0x415,        # Gets DOUBLE value for precision percentage on the mid range on Themocouple
    TS_MED_RANGE_PREC_DELTA	    = 0x416,        # Gets DOUBLE value for precision delta on the mid range on Themocouple
    TS_HIGH_RANGE_MIN			= 0x417,        # Gets DOUBLE value for minimum of the high range on Themocouple
    TS_HIGH_RANGE_MED			= 0x418,        # Gets DOUBLE value for median of the high range on Themocouple
    TS_HIGH_RANGE_MAX			= 0x419,        # Gets DOUBLE value for maximum of the high range on Themocouple
    TS_HIGH_RANGE_MAX_DEV		= 0x41A,        # Gets DOUBLE value for maximum deviation on the high range on Themocouple
    TS_HIGH_RANGE_PREC_PC		= 0x41B,        # Gets DOUBLE value for precision percentage on the high range on Themocouple
    TS_HIGH_RANGE_PREC_DELTA	= 0x41C,        # Gets DOUBLE value for precision delta on the high range on Themocouple
    TS_POT_VAL					= 0x41D,        # Gets UCHAR value for the pot settings on Thermocouple
    #Write-only function
    TS_SET_POT					= 0x41E,        # Sets UCHAR value for the pot settings on Thermocouple 
    TS_SAVE_POT				    = 0x41F,        # Sets UCHAR value for the pot settings on Thermocouple
    TS_DATA_DUMP				= 0x420,
    MUXM_MBB					= 0x421,

    #Thermocouple Complentation function
    TS_TEMPERATURES_C = 0x42E, # Read 7 sensors on 1192r0 41-760 I2C Compensation Block in degrees Celsius
    TS_TEMPERATURES_F = 0x42F, # Read 7 sensors on 1192r0 41-760 I2C Compensation Block in degrees Farenheit

    TS_EEPROM = 0x430, # Read/write 34LC02 eeprom
    TS_EEPROM_OFFSET = 0x431,  # Supply offset to eeprom

    CARD_PCB_NUM = 0x43D, #Card PCB Number.
    CARD_PCB_REV_NUM = 0x43E, #Card PCB Revision Number.
    CARD_FW_REV_NUM = 0x43F, #Card FPGA Firmware Revision Number.

    CURRENT_MA = 0x440,  # Sets/Gets DOUBLE value of Current in mA
    CURRENT_A = 0X404    # Sets/gets double value of current in A
    VOLTAGE_V = 0x441,   # Sets/Gets DOUBLE value of Voltage in V (Current loop) 
                                # Gets DOUBLE value of Voltage in V (LVDT/RVDT/Resolver) 
    SLEW_RATE = 0x442,   # Sets/Gets BYTE value Upper nibble <StepSize> Lower nibble <Clock-Rate>  
    IS_SLEW = 0x443,	  # Gets BOOL value stating if Slew is ON or OFF  

    # Current monitoring attributes 
    VOLTAGE_VAL = 0x444,   # Gets DOUBLE value of Voltage in Volts 

    # VDT attributes   
    VDT_AUTO_INPUT_ATTEN					= 0x450,	# Sets/Gets DWORD (0-100) for input gain (Default = 100)
    VDT_ABS_POSITION                       = 0x451,	# Sets/Gets DWORD (0-32767) for Both Outputs on LVDT_5_6 WIRE & OutputA on LVDT_4_WIRE  
    VDT_ABS_POSITION_B                     = 0x452,	# Sets/Gets DWORD (0-32767)  for OutputB on LVDT_4_WIRE  
    VDT_PERCENT_POSITION                   = 0x453,	# Sets/Gets DOUBLE (-100.00% to 100.00%) for Both Out on LVDT_5_6 WIRE & OutA on LVDT_4_WIRE 
    VDT_PERCENT_POSITION_B                 = 0x454,	# Sets/Gets DOUBLE (-100.00% to 100.00%) for OutB on LVDT_4_WIRE 
    VDT_VOLTAGE_SUM                        = 0x455,   # Sets/Gets DOUBLE in Volts  for VSUM value  
    VDT_VOLTAGE_DIFF                       = 0x456,	# Sets/Gets DOUBLE in Volts  for VDIFF value (the limit is +/- VSUM)  
    VDT_OUT_GAIN                           = 0x457,	# Sets/Gets DWORD (1 or 2) for 1x or 2x output multiplier  #CALIBRATION ONLY
    VDT_MANUAL_INPUT_ATTEN                 = 0x458,	# Sets/Gets DWORD (0-255) Pot Value on LVDT  
    VDT_MODE                               = 0x459,	# Sets/Gets DWORD to set mode 1 = LVDT_5_6_WIRE, mode 2=  LVDT_4_WIRE.
    VDT_DELAY_A                            = 0x45A,	# Sets/Gets DWORD (0-6499) delay for OutputA   
    VDT_DELAY_B                            = 0x45B,	# Sets/Gets DWORD (0-6499) delay for OutputB   
    VDT_INPUT_LEVEL                        = 0x45C,	# Sets/Gets DWORD (0-65520) for Input Value  
    VDT_INPUT_FREQ                         = 0x45D,	# Sets/Gets DWORD (300-20000 Hz) for Input Frequency   
    VDT_OUT_LEVEL                          = 0x45E,	# Sets/Gets DWORD (0-4096)  output level  
                            

    # LVDT Mk2 Get only
    VDT_DSPIC_VERSION                      = 0x45F,	# Gets DWORD value of for dsPIC firmware version 104 = v0.01.04 

    # LVDT Mk2 Set/Get
    VDT_INVERT_A        					= 0x460,	# Sets/Gets DWORD (0 or 1)  for OutA 
    VDT_INVERT_B                            = 0x461,    # Sets/Gets DWORD (0 or 1)  for OutB  
    VDT_PHASE_TRACKING					    = 0x462,	# 'TP' Phase tracking mode on or off  -CALIBRATION ONLY
    VDT_SAMPLE_LOAD						    = 0x463,	# Sets DWORD comprises of Top 16 bits is GAIN (0-100) and lower 16 frequency (300-20000 Hz)
    VDT_INPUT_FREQ_HI_RES                  = 0x464,	# Gets DOUBLE value of frequency in Hz 
    VDT_LOS_THRESHOLD                      = 0x465,	# Sets/Gets DWORD (0 to 32768) for LOS Threshold (Default = 32768) 
    VDT_SMPL_BUFFER_SIZE                   = 0x466,	# Sets/Gets DWORD (1 to 500) for Sample buffer size (Default = 500) 
    VDT_NULL_OFFSET                        = 0x467,	# Sets/Gets WORD (0 to 100) for null offset (Default = 0)
    #LVDT Get Only
    VDT_STATUS                             = 0x468,    # Gets BYTE value (0x00 or 0x01) checking LOS status 
    VDT_MAX_OUT_VOLTAGE                    = 0x469,    #Gets DOUBLE value for maximum output voltage 
    VDT_MIN_OUT_VOLTAGE                    = 0x46A,    #Gets DOUBLE value for minimum output voltage 
    VDT_MAX_IN_VOLTAGE                     = 0x46B,    #Gets DOUBLE value for maximum input voltage 
    VDT_MIN_IN_VOLTAGE                     = 0x46C,    #Gets DOUBLE value for minimum input voltage 

    VDT_PHASE_DELAY_A						= 0x46D,	#Set/Gets DOUBLE in degrees for OutA
    VDT_PHASE_DELAY_B						= 0x46E,	#Set/Gets DOUBLE in degrees for OutB
    RESOLVER_START_STOP_ROTATE				= 0x470,	#Sets/Gets BOOL TRUE for Start, FALSE of Stop 
    RESOLVER_NUM_OF_TURNS					= 0x471,	# Sets/ Gets WORD Number of turns (1-65535)
    RESOLVER_ROTATE_SPEED					= 0x472,	#Sets/Gets DOUBLE rotating speed (RPM speed upto 655.35 RPM)
    RESOLVER_POSITION						= 0x473,	#Sets/Gets DOUBLE rotation between -180.00 to 180.00 Degrees 
    RESOLVER_POSITION_0_360				    = 0x474,	#Sets/Gets DOUBLE rotation between 0.00 to 360.00 Degrees 
    VDT_NO_WAIT							    = 0x475,	#Applicable to 4 wire mode, Sets OutA and OutB instantaneously
    RAMP_RESPONSE						    = 0x476,	#Sets/Gets DOUBLE response delay in seconds upto 1677 seconds 
    SETTLE_DELAY_ZERO						= 0x480,	#Sets/Gets BOOL, settling time set to zero for the ouput subunits 
                                                            # Use this attribute carefully. Settling delay wont be applied. 
                                                            # Handle the settling time needed for the relays appropriately, in the application.
    MEASURE_CONFIG							= 0x481,	# Set measurement configuration
    LOAD									= 0x482,	# Set/Get DWORD load 0-300 (0-300mA)
    # DIO card.
    DIO_PATTERN_MODE						= 0x490,	# Sets/Gets Pattern Mode (BOOL) 
    DIO_EXT_CLOCK_MODE						= 0x491,	# Sets/Gets External Clock Mode (DWORD) 
    DIO_PATTERN							    = 0x492,	# Sets/Gets each pattern for individual ports (BYTE) 
    DIO_PATTERN_OFFSET						= 0x493,	# Sets/Gets offset of the pattern to be read from individual ports (DWORD) 
    DIO_PATTERN_TOTAL_COUNT				    = 0x494,	# Gets pattern count for individual ports (DWORD) 
    DIO_EXT_CLK_IO_STATE					= 0x495,	# Sets/Gets port clk pin state when IO Mode is set (BOOL) 
    DIO_EXT_CLK_IO_DIR						= 0x496,	# Sets/Gets port clk pin direction when IO Mode is set (BOOL) 

                                                
    #	**************** Card level Attributes ****************
    #	C_ attributes are for card level operations.
    #	Attributes range should be handled in the SetAttribute/GetAttribute Functions.
    #	Range 0x1000 to 0x1999 is reserved for card level attributes.
    #	Subunit Parameter for SetAttribute() and GetAttribute() will be insignificant for these Attributes.

    #	Some Attributes are repurposed as card-level attributes
    #		INTERLOCK_STATUS

    # DIO card.
    C_DIO_INT_CLOCK_ENABLE					= 0x1000,	# Sets/Gets Internal Clock Enable/Disable (BOOL) 
    C_DIO_INT_CLOCK_FREQ					= 0x1001,	# Sets/Gets Internal Clock Frequency (DOUBLE) 
    C_DIO_START_POSITION					= 0x1002,	# Sets/Gets Start postion of pattern capture engine (DWORD) 
    C_DIO_END_POSITION						= 0x1003,	# Sets/Gets End postion of pattern capture engine (DWORD) 
    C_DIO_DYNAMIC_CONTINUOUS				= 0x1004,	# Sets/Gets continuous run status of pattern capture engine (BOOL) 
    C_DIO_DYNAMIC_ONELOOP					= 0x1005,	# Sets/Gets one loop execution status of pattern generation/acquisition engine (BOOL) 
    C_DIO_LOAD_PATTERN_FILE				    = 0x1007,	# Loads pattern file data to DIO card memory (CHAR*) 
    C_DIO_SOFTWARE_TRIGGER					= 0x1008,	# Send Software trigger for pattern mode operation (BOOL) 
    C_DIO_DYNAMIC_BUSY						= 0x1009,	# Check the status of the capture engine (BOOL) 
    C_DIO_ALL_PORT_DATA					    = 0x100A,	# Load/Retreive patterns for all ports for an address offset (DWORD*) 
                                                            # Make sure an array of DWORD with number of elements as number of ports 
                                                            #	of the card is passed as parameter for this attribute 
    C_DIO_ALL_PORT_DATA_OFFSET				= 0x100B,	# Used to get/set the offset to/from which data should be loaded/retrieved (DWORD) 
    C_DIO_FIFO_POS							= 0x100C,	# Gets FIFO postion or number of dynamic operations for the card (DWORD) 
    C_DIO_ABORT							    = 0x100D,	# Aborts the DIO Dynamic Operation (BOOL) 
    C_DIO_PATTERN_FILE_ERR					= 0x100E,	# Get the errors found in the Pattern File (CHAR*) 
    C_DIO_SAVE_PATTERN_FILE				    = 0x100F,	# Saves to pattern file from DIO card memory (CHAR*) 
    C_DIO_VERIFY_PATTERN_FILE				= 0x1010,	# Verify the pattern file to be loaded to DIO card memory (CHAR*) 
    C_DIO_GO_TO_START						= 0x1011,	# Clears any pending transactions and prepares the card to start DIO operation. (BOOL) 
    C_DIO_CLOCK_DELAY						= 0x1012,	# Sets/Gets the output clock delay in microseconds (min = 0.08 us, max = 163 us) (DOUBLE) 

    C_CAPABILITIES							= 0x1100,	# Retrieve capabilities of the card (DWORD) 
    C_SET_MEASURE_SET						= 0x1101,	# Set voltage/current, measure, set again (BOOL) 
    C_TEMP_SENSOR_COUNT					    = 0x1102,	# Get the number of Temperature sensors on-board (DWORD) 
    C_GA_SLOT_ADDRESS						= 0x1103	# Retrieve Global address slot address of a PXIe card (DWORD) 


class TS_Range(IntEnum):

    AUTO    = 0,
    LOW     = 1,
    MED     = 2,
    HIGH    = 3


class CL_Mode(IntEnum):
    MODE_4_20_MA        = 1, # 4-20mA Mode (Set by Default)
    MODE_0_24_MA        = 2, # 0-20mA Mode
    MODE_MINUS24_24_MA  = 3, # +/-24mA Mode
    MODE_0_5_V          = 4, # 0-5V Mode
    MODE_MINUS12_12_V   = 5, # +/-12V Mode
    MODE_MINUS5_5_V     = 6  # +/-5V


class DM_Mode(IntEnum):

    LVDT_5_6_WIRE = 1,
    LVDT_4_WIRE   = 2,
    RESOLVER      = 3


class RES_Mode(IntEnum):

    SET = 0,  # Legacy/Default mode to support existing break before make with settling delay
    MBB = 1,  # New mode to suport make before break with settling delay
    APPLY_PATTERN_IMMEDIATE = 2,  # Apply new pattern immediately and wait till settling delay
    NO_SETTLING_DELAY = 4,  # Disable settling delay,same as DriverMode NO_WAIT, but at sub-unit level
    DONT_SET = 999,  # Do the calculations but don't set the card
    END = 9999

class FG_WfTypes(IntEnum): # PILFG Waveform Types
    PILFG_WAVEFORM_SINE         = 0x0,
    PILFG_WAVEFORM_SQUARE		= 0x1,
    PILFG_WAVEFORM_TRIANGLE	    = 0x2,
    PILFG_WAVEFORM_RAMP_UP		= 0x3,
    PILFG_WAVEFORM_RAMP_DOWN	= 0x4,
    PILFG_WAVEFORM_DC			= 0x5,
    PILFG_WAVEFORM_PULSE		= 0x6,
    PILFG_WAVEFORM_PWM			= 0x7,
    PILFG_WAVEFORM_ARB			= 0x8

class FG_TriggerInputSource(IntEnum):
    PILFG_TRIG_IN_FRONT = 0x0

class FG_TriggerInputModes(IntEnum):
    PILFG_TRIG_IN_EDGE_RISING = 0x0,
    PILFG_TRIG_IN_EDGE_FALLING = 0x1

class FG_TriggerOutputModes(IntEnum):
    PILFG_TRIG_OUT_GEN_PULSE_POS = 0x0,
    PILFG_TRIG_OUT_GEN_PULSE_NEG = 0x1,
    PILFG_TRIG_OUT_SOFT_PULSE_POS = 0x2,
    PILFG_TRIG_OUT_SOFT_PULSE_NEG = 0x3

#endregion

class _CardInfo:
    def __init__(self, cardIdStr):
        cardIdData = str.split(cardIdStr, ',')

        self.typeCode = cardIdData[0]
        self.serialNumber = cardIdData[1]
        self.revision = cardIdData[2]


class Error(Exception):
    """Base error class provides error message and optional error code from driver."""

    def __init__(self, message, errorCode=None):
        self.message = message
        self.errorCode = errorCode

    def __str__(self):
        return self.message

class _SubState:
    def __init__(self, rows, columns, subunit, subInfo, stateData):
        self.stateData = stateData
        self.rows = rows
        self.columns = columns
        self.subunit = subunit
        self.subInfo = subInfo

    def _SetBit(self, bitNum, state):

        dwordNum = int(floor(bitNum / 32))
        dwordBit = int(bitNum % 32)

        if state:
            self.stateData[dwordNum] = self.stateData[dwordNum] | (1 << dwordBit)
        else:
            self.stateData[dwordNum] = self.stateData[dwordNum] & ~(1 << dwordBit)

        return

    def _PeekBit(self, bitNum):
        dwordNum = int(floor(bitNum / 32))
        dwordBit = int(bitNum % 32)

        state = bool(self.stateData[dwordNum] & (1 << dwordBit))
        return state

    def PreSetCrosspoint(self, row, column, state):

        if not 1 <= row <= self.rows:
            raise Error("Row value out of card subunit range")
        if not 1 <= column <= self.columns:
            raise Error("Column value out of card subunit range")

        switchNum = ((row - 1) * self.columns) + (column - 1)

        self._SetBit(switchNum, state)

        return

    def GetCrosspointState(self, row, column):

        if not 1 <= row <= self.rows:
            raise Error("Row value out of card subunit range")
        if not 1 <= column <= self.columns:
            raise Error("Column value out of card subunit range")

        switchNum = ((row - 1) * self.columns) + (column - 1)
        return self._PeekBit(switchNum)

    def PreClearSub(self):
        self.stateData = [0] * len(self.stateData)
        return

    def PreSetBit(self, bitNum, state):

        if not 1 <= bitNum <= self.columns:
            raise Error("Switch value out of card subunit range")

        bitNum -= 1
        self._SetBit(bitNum, state)
        return

    def GetBit(self, bitNum):

        if not 1 <= bitNum <= self.columns:
            raise Error("Switch value out of card subunit range")

        bitNum -= 1
        return self._PeekBit(bitNum)


class Base:
    def __init__(self):
        if platform.system() == "Windows":
            self.handle = ctypes.windll.LoadLibrary("pilpxi")
        elif platform.system() == "Linux":
            arch = platform.architecture()
            if "64bit" in arch:
                self.handle = ctypes.cdll.LoadLibrary("libpilpxi64.so")
            else:
                self.handle = ctypes.cdll.LoadLibrary("libpilpxi32.so")

        self.pythonMajorVersion = sys.version_info[0]

        #region Dict enums

        # Capabilities flags enum for ResInfo()
        self.RESCAP = {
            "RES_CAP_NONE": 0x00,
            "RES_CAP_PREC": 0x01,
            "RES_CAP_ZERO": 0x02,
            "RES_CAP_INF":  0x04,
            "RES_CAP_REF":  0x08
        }

        # Error Code Enum
        self.ERRORCODE = {
            "NO_ERR" : 0,                       # No error
            "ER_NO_CARD" : 1,                   # No card present with specified number
            "ER_NO_INFO" : 2,                   # Card information unobtainable - hardware problem
            "ER_CARD_DISABLED" : 3,             # Card disabled - hardware problem
            "ER_BAD_SUB" : 4,                   # Card has no sub-unit with specified number
            "ER_BAD_BIT" : 5,                   # Sub-unit has no bit with specified number
            "ER_NO_CAL_DATA" : 6,               # Sub-unit has no calibration data to write/read
            "ER_BAD_ARRAY" : 7,                 # Array type, size or shape is incorrect
            "ER_MUX_ILLEGAL" : 8,               # Non-zero write data is illegal for MUX sub-unit
            "ER_EXCESS_CLOSURE" : 9,            # Sub-unit closure limit exceeded
            "ER_ILLEGAL_MASK" : 10,             # One or more of the specified channels cannot be masked
            "ER_OUTPUT_MASKED" : 11,            # Cannot activate an output that is masked
            "ER_BAD_LOCATION" : 12,             # Cannot open a Pickering card at the specified location
            "ER_READ_FAIL" : 13,                # Failed read from hardware
            "ER_WRITE_FAIL" : 14,               # Failed write to hardware
            "ER_DRIVER_OP" : 15,                # Hardware driver failure
            "ER_DRIVER_VERSION" : 16,           # Incompatible hardware driver version
            "ER_SUB_TYPE" : 17,                 # Function call incompatible with sub-unit type or capabilities
            "ER_BAD_ROW" : 18,                  # Matrix row value out of range
            "ER_BAD_COLUMN" : 19,               # Matrix column value out of range
            "ER_BAD_ATTEN" : 20,                # Attenuation value out of range
            "ER_BAD_VOLTAGE" : 21,              # Voltage value out of range
            "ER_BAD_CAL_INDEX" : 22,            # Calibration reference out of range
            "ER_BAD_SEGMENT" : 23,              # Segment number out of range
            "ER_BAD_FUNC_CODE" : 24,            # Function code value out of range
            "ER_BAD_SUBSWITCH" : 25,            # Subswitch value out of range
            "ER_BAD_ACTION" : 26,               # Action code out of range
            "ER_STATE_CORRUPT" : 27,            # Cannot execute due to corrupt sub-unit state
            "ER_BAD_ATTR_CODE" : 28,            # Unrecognised attribute code
            "ER_EEPROM_WRITE_TMO" : 29,         # Timeout writing to EEPROM
            "ER_ILLEGAL_OP" : 30,               # Operation is illegal in the sub-unit's current state
            "ER_BAD_POT" : 31,                  # Unrecognised pot number requested
            "ER_MATRIXR_ILLEGAL" : 32,          # Invalid write pattern for MATRIXR sub-unit
            "ER_MISSING_CHANNEL" : 33,          # Attempted operation on non-existent channel
            "ER_CARD_INACCESSIBLE" : 34,        # Card cannot be accessed (failed/removed/unpowered)
            "ER_BAD_FP_FORMAT" : 35,            # Unsupported internal floating-point format (internal error)
            "ER_UNCALIBRATED" : 36,             # Sub-unit is not calibrated
            "ER_BAD_RESISTANCE" : 37,           # Unobtainable resistance value
            "ER_BAD_STORE" : 38,                # Invalid calibration store number
            "ER_BAD_MODE" : 39,                 # Invalid mode value
            "ER_SETTINGS_CONFLICT" : 40,        # Conflicting busAndDevice settings
            "ER_CARD_TYPE" : 41,                # Function call incompatible with card type or capabilities
            "ER_BAD_POLE" : 42,                 # Switch pole value out of range
            "ER_MISSING_CAPABILITY" : 43,       # Attempted to activate a non-existent capability
            "ER_MISSING_HARDWARE" : 44,         # Action requires hardware that is not present
            "ER_HARDWARE_FAULT" : 45,           # Faulty hardware
            "ER_EXECUTION_FAIL" : 46,           # Failed to execute (e.g. blocked by a hardware condition)
            "ER_BAD_CURRENT" : 47,              # Current value out of range
            "ER_BAD_RANGE" : 48,                # Invalid range value
            "ER_ATTR_UNSUPPORTED" : 49,         # Attribute not supported
            "ER_BAD_REGISTER" : 50,             # Register number out of range
            "ER_MATRIXP_ILLEGAL" : 51,          # Invalid channel closure or write pattern for MATRIXP sub-unit
            "ER_BUFFER_UNDERSIZE" : 52,         # Data buffer too small
            "ER_ACCESS_MODE" : 53,              # Inconsistent shared access mode
            "ER_POOR_RESISTANCE" : 54,          # Resistance outside limits
            "ER_BAD_ATTR_VALUE" : 55,           # Bad attribute value
            "ER_INVALID_POINTER" : 56,          # Invalid pointer
            "ER_ATTR_READ_ONLY" : 57,           # Attribute is read only
            "ER_ATTR_DISABLED" : 58,            # Attribute is disabled
            "ER_PSU_MAIN_OUTPUT_DISABLED" : 59, # Main output is disabled, cannot enable the channel
            "ER_OUT_OF_MEMORY_HEAP" : 60,       # Unable to allocate memory on Hea
            "ER_INVALID_PROCESSID" : 61,        # Invalid ProcessID
            "ER_SHARED_MEMORY" : 62,            # Shared memory error
            "ER_CARD_OPENED_OTHER_PROCESS" : 63 # Card is opened by a process in exclusive mode
        }

        # Attribute Codes Enum
        self.ATTR = {
            "TYPE" : 0x400,  # Gets/Sets DWORD attribute value of Type of the Sub-unit (values: TYPE_MUXM, TYPE_MUXMS)
            "MODE" : 0x401, # Gets/Sets DWORD attribute value of Mode of the Card

            # Current monitoring attributes
            "CNFGREG_VAL" : 0x402,	# Gets/Sets WORD value of config register
            "SHVLREG_VAL" : 0x403,	# Gets WORD value of shuntvoltage register
            "CURRENT_VAL" : 0x404,	# Gets double current value in Amps

            # Read-only Power Supply attributes
            "INTERLOCK_STATUS" : 0x405,	# Gets BOOL value of interlock status
            "OVERCURRENT_STATUS_MAIN" : 0x406,	# Gets BOOL value of main overcurrent status
            "OVERCURRENT_STATUS_CH" : 0x407,	# Gets BOOL value of overcurrent status on specific channel

            # Read/Write Power Supply attributes
            "OUTPUT_ENABLE_MAIN" : 0x408,	# Gets/Sets BOOL value. Enables/Disables main
            "OUTPUT_ENABLE_CH" : 0x409,	# Gets/Sets BOOL value. Enables/Disables specific channel

            # Read/Write Thermocouple Simulator functions
            "TS_SET_RANGE" : 0x40A,		# Gets/Sets Auto range which toggles between based on the value
            # Read-only function
            "TS_LOW_RANGE_MIN" : 0x40B,
            "TS_LOW_RANGE_MED" : 0x40C,
            "TS_LOW_RANGE_MAX" : 0x40D,
            "TS_LOW_RANGE_MAX_DEV" : 0x40E,
            "TS_LOW_RANGE_PREC_PC" : 0x40F,
            "TS_LOW_RANGE_PREC_DELTA" : 0x410,
            "TS_MED_RANGE_MIN" : 0x411,
            "TS_MED_RANGE_MED" : 0x412,
            "TS_MED_RANGE_MAX" : 0x413,
            "TS_MED_RANGE_MAX_DEV" : 0x414,
            "TS_MED_RANGE_PREC_PC" : 0x415,
            "TS_MED_RANGE_PREC_DELTA" : 0x416,
            "TS_HIGH_RANGE_MIN" : 0x417,
            "TS_HIGH_RANGE_MED" : 0x418,
            "TS_HIGH_RANGE_MAX" : 0x419,
            "TS_HIGH_RANGE_MAX_DEV" : 0x41A,
            "TS_HIGH_RANGE_PREC_PC" : 0x41B,
            "TS_HIGH_RANGE_PREC_DELTA" : 0x41C,
            "TS_POT_VAL" : 0x41D, # Read Pot Value from user store
            # Write-only function
            "TS_SET_POT" : 0x41E,
            "TS_SAVE_POT" : 0x41F,
            "TS_DATA_DUMP" : 0x420,
            "MUXM_MBB" : 0x421,

            "TS_TEMPERATURES_C" : 0x42E, # Read 7 sensors on 1192r0 41-760 I2C Compensation Block in degrees Celsius
            "TS_TEMPERATURES_F" : 0x42F, # Read 7 sensors on 1192r0 41-760 I2C Compensation Block in degrees Farenheit
            "TS_EEPROM" : 0x430, # Read/write 34LC02 eeprom
            "TS_EEPROM_OFFSET" : 0x431,  # Supply offset to eeprom

            # VDT attributes
            "VDT_AUTO_INPUT_ATTEN"				: 0x450,	# Sets/Gets DWORD (0-100) for input gain (Default = 100)
            "VDT_ABS_POSITION"                  : 0x451,	# Sets/Gets DWORD (0-32767) for Both Outputs on LVDT_5_6 WIRE & OutputA on LVDT_4_WIRE
            "VDT_ABS_POSITION_B"                : 0x452,	# Sets/Gets DWORD (0-32767)  for OutputB on LVDT_4_WIRE
            "VDT_PERCENT_POSITION"              : 0x453,	# Sets/Gets DOUBLE (-100.00% to 100.00%) for Both Out on LVDT_5_6 WIRE & OutA on LVDT_4_WIRE
            "VDT_PERCENT_POSITION_B"            : 0x454,	# Sets/Gets DOUBLE (-100.00% to 100.00%) for OutB on LVDT_4_WIRE
            "VDT_VOLTAGE_SUM"                   : 0x455,    # Sets/Gets DOUBLE in Volts  for VSUM value
            "VDT_VOLTAGE_DIFF"                  : 0x456,	# Sets/Gets DOUBLE in Volts  for VDIFF value (the limit is +/- VSUM)
            "VDT_OUT_GAIN"                      : 0x457,	# Sets/Gets DWORD (1 or 2) for 1x or 2x output multiplier  #CALIBRATION ONLY
            "VDT_MANUAL_INPUT_ATTEN"            : 0x458,	# Sets/Gets DWORD (0-255) Pot Value on LVDT
            "VDT_MODE"                          : 0x459,	# Sets/Gets DWORD to set mode 1 = LVDT_5_6_WIRE, mode 2=  LVDT_4_WIRE.
            "VDT_DELAY_A"                       : 0x45A,	# Sets/Gets DWORD (0-6499) delay for OutputA
            "VDT_DELAY_B"                       : 0x45B,	# Sets/Gets DWORD (0-6499) delay for OutputB
            "VDT_INPUT_LEVEL"                   : 0x45C,	# Sets/Gets DWORD (0-65520) for Input Value
            "VDT_INPUT_FREQ"                    : 0x45D,	# Sets/Gets DWORD (300-20000 Hz) for Input Frequency
            "VDT_OUT_LEVEL"                     : 0x45E,	# Sets/Gets DWORD (0-4096)  output level

            # LVDT Mk2 Get only
            "VDT_DSPIC_VERSION"                 : 0x45F,	# Gets DWORD value of for dsPIC firmware version 104 = v0.01.04

            # LVDT Mk2 Set/Get
            "VDT_INVERT_A"        				: 0x460,	# Sets/Gets DWORD (0 or 1)  for OutA
            "VDT_INVERT_B"                      : 0x461,    # Sets/Gets DWORD (0 or 1)  for OutB
            "VDT_PHASE_TRACKING"			    : 0x462,	# 'TP' Phase tracking mode on or off  -CALIBRATION ONLY
            "VDT_SAMPLE_LOAD"				    : 0x463,	# Sets DWORD comprises of Top 16 bits is GAIN (0-100) and lower 16 frequency (300-20000 Hz)
            "VDT_INPUT_FREQ_HI_RES"             : 0x464,	# Gets DWORD value of frequency in Hz
            "VDT_LOS_THRESHOLD"                 : 0x465,	# Sets/Gets DWORD (0 to 32768) for LOS Threshold (Default = 32768)
            "VDT_SMPL_BUFFER_SIZE"              : 0x466,	# Sets/Gets DWORD (1 to 500) for Sample buffer size (Default = 500)
            "VDT_NULL_OFFSET"                   : 0x467,	# Sets/Gets WORD (0 to 100) for null offset (Default = 0)

            # LVDT Get Only
            "VDT_STATUS"                        : 0x468,    # Gets BYTE value (0x00 or 0x01) checking LOS status
            "VDT_MAX_OUT_VOLTAGE"               : 0x469,    # Gets DOUBLE value for maximum output voltage
            "VDT_MIN_OUT_VOLTAGE"               : 0x46A,    # Gets DOUBLE value for minimum output voltage
            "VDT_MAX_IN_VOLTAGE"                : 0x46B,    # Gets DOUBLE value for maximum input voltage
            "VDT_MIN_IN_VOLTAGE"                : 0x46C,    # Gets DOUBLE value for minimum input voltage

            "CARD_PCB_NUM" : 0x43D, # Card PCB Number.
            "CARD_PCB_REV_NUM" : 0x43E, # Card PCB Revision Number.
            "CARD_FW_REV_NUM" : 0x43F  # Card FPGA Firmware Revision Number.
        }

        # Vsource Range Enum
        self.TS_RANGE = {
            "AUTO" : 0,
            "LOW" : 1,
            "MED" : 2,
            "HIGH" : 3
        }

        # Current loop modes Enum
        self.CL_MODE = {
            # 4-20mA mode (set by default)
            "4_20_MA": 1,

            # 0-24mA mode
            "0_24_MA": 2,

            # +/-24mA mode
            "MINUS24_24_MA": 3,

            # 0-5V mode
            "0_5_V": 4,

            # +/- 12V mode
            "MINUS12_12_V": 5,

            # +/- 5V mode
            "MINUS5_5_V": 6
        }

        #endregion

    #region Internal methods

    def _handleError(self, error):
        """Internal method to raise exceptions based on error codes from driver. """
        if error:
            errorString = self.ErrorMessage(error)
            raise Error(errorString, errorCode=error)

    def _calc_dwords(self, bits):
        dwords = floor(bits / 32)
        if ((bits) % 32 > 0):
            dwords += 1

        return int(dwords)

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
            return inputString
        else:
            return inputString.decode()

    #endregion

    def ErrorMessage(self, code):
        code = ctypes.c_uint32(code)
        string = ctypes.create_string_buffer(100)

        err = self.handle.PIL_ErrorMessage(code, ctypes.byref(string))

        return self._pythonString(string.value)

    def Version(self):
        ver = self.handle.PIL_Version()
        return ver

    def CountFreeCards(self):
        count = ctypes.c_uint(0)
        err = self.handle.PIL_CountFreeCards(ctypes.byref(count))
        self._handleError(err)
        return int(count.value)

    def FindFreeCards(self):
        count = self.CountFreeCards()

        buses = (ctypes.c_uint32 * count)()
        devices = (ctypes.c_uint32 * count)()
        err = self.handle.PIL_FindFreeCards(count, ctypes.byref(buses), ctypes.byref(devices))
        self._handleError(err)
        return [(int(buses[i]), int(devices[i])) for i in range(0, len(devices))]

    def OpenCard(self, bus, device):
        return Pi_Card(bus, device)


class Pi_Card(Base):
    def __init__(self, bus, device):

        Base.__init__(self)

        self.disposed = False

        self.card = ctypes.c_uint(0)
        bus = ctypes.c_uint32(bus)
        device = ctypes.c_uint32(device)

        error = self.handle.PIL_OpenSpecifiedCard(bus, device, ctypes.byref(self.card))
        self._handleError(error)

        self.cardInfo = _CardInfo(self.CardId())
    
    def Close(self):

        err = self.handle.PIL_CloseSpecifiedCard(self.card)
        self._handleError(err)
        self.disposed = True

        return

    def __del__(self):

        if self.disposed:
            return
        else:
            self.Close()
        return

    #region Card identity / status functions

    def CardId(self):
        string = ctypes.create_string_buffer(100)

        err = self.handle.PIL_CardId(self.card, ctypes.byref(string))
        self._handleError(err)

        return self._pythonString(string.value)

    def CardLoc(self):
        bus = ctypes.c_uint(0)
        device = ctypes.c_uint(0)
        err = self.handle.PIL_CardLoc(self.card, ctypes.byref(bus), ctypes.byref(device))
        self._handleError(err)

        return int(bus.value), int(device.value)

    def Diagnostic(self):
        string = ctypes.create_string_buffer(100)

        err = self.handle.PIL_Diagnostic(self.card, ctypes.byref(string))
        self._handleError(err)

        return self._pythonString(string.value)

    def SetMode(self, mode):
        mode = ctypes.c_uint32(mode)

        err = self.handle.PIL_SetMode(mode)
        self._handleError(err)
        return

    #endregion

    #region Switching functions

    def ClearCard(self):
        err = self.handle.PIL_ClearCard(self.card)
        self._handleError(err)

        return
        
    def ClearSub(self, subunit):
        subunit = ctypes.c_uint32(subunit)

        err = self.handle.PIL_ClearSub(self.card, subunit)
        self._handleError(err)

        return
        
    def ClosureLimit(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        limit = ctypes.c_uint(0)

        err = self.handle.PIL_ClosureLimit(self.card, subunit, ctypes.byref(limit))
        self._handleError(err)

        return int(limit.value)
    
    def EnumerateSubs(self):
        ins = ctypes.c_uint(0)
        outs = ctypes.c_uint(0)
        err = self.handle.PIL_EnumerateSubs(self.card, ctypes.byref(ins), ctypes.byref(outs))
        self._handleError(err)

        return int(ins.value), int(outs.value)
    
    def MaskBit(self, subunit, bit, action):
        subunit = ctypes.c_uint32(subunit)
        bit = ctypes.c_uint32(bit)
        action = ctypes.c_bool(action)

        err = self.handle.PIL_MaskBit(self.card, subunit, bit, action)
        self._handleError(err)
        return
   
    def MaskCrosspoint(self, subunit, row, column, action):
        subunit = ctypes.c_uint32(subunit)
        row = ctypes.c_uint32(row)
        column = ctypes.c_uint32(column)
        action = ctypes.c_bool(action)

        err = self.handle.PIL_MaskCrosspoint(self.card, subunit, row, column, action)
        self._handleError(err)
        return
        
    def OpBit(self, subunit, bit, action):
        subunit = ctypes.c_uint32(subunit)
        bit = ctypes.c_uint32(bit)
        action = ctypes.c_bool(action)

        err = self.handle.PIL_OpBit(self.card, subunit, bit, action)
        self._handleError(err)
        return
        
    def OpCrosspoint(self, subunit, row, column, action):
        subunit = ctypes.c_uint32(subunit)
        row = ctypes.c_uint32(row)
        column = ctypes.c_uint32(column)
        action = ctypes.c_bool(action)

        err = self.handle.PIL_OpCrosspoint(self.card, subunit, row, column, action)
        self._handleError(err)
        return
        
    def OpSwitch(self, subunit, switchFunc, segNum, subSwitch, switchAction, state):
        subunit = ctypes.c_uint32(subunit)
        switchFunc = ctypes.c_uint32(switchFunc)
        segNum = ctypes.c_uint32(segNum)
        subSwitch = ctypes.c_uint32(subSwitch)
        switchAction = ctypes.c_uint32(switchAction)
        state = ctypes.c_bool(state)

        err = self.handle.PIL_OpSwitch(self.card, subunit, switchFunc, segNum, subSwitch, switchAction, ctypes.byref(state))
        self._handleError(err)
        return bool(state.value)
    
    def ReadBit(self, subunit, bit):
        state = ctypes.c_bool()
        subunit = ctypes.c_uint32(subunit)
        bit = ctypes.c_uint32(bit)

        err = self.handle.PIL_ReadBit(self.card, subunit, bit, ctypes.byref(state))
        self._handleError(err)
        return bool(state.value)

    def ReadSub(self, subunit):
        """Reads the state of an input subunit"""
        subunit = ctypes.c_int(subunit)

        # get size of subunit and create an array to hold the data
        subunitType, rows, cols = self.SubInfo(subunit, 0)

        dwords = self._calc_dwords(rows * cols)
        data = (ctypes.c_uint32 * dwords)()

        err = self.handle.PIL_ReadSub(self.card, subunit, ctypes.byref(data))
        self._handleError(err)
        return [int(dword) for dword in data]

    def SetCrosspointRange(self, subunit, row, start_col, end_col, state):
        """Sets all outputs on a row within a given range"""

        subState = self.GetSubState(subunit)

        for column in range(start_col, end_col + 1):
            subState.PreSetCrosspoint(row, column, state)

        self.WriteSubState(subunit, subState)

        return
    
    def SettleTime(self, subunit):
        """Gets settle time in milliseconds"""
        subunit = ctypes.c_uint32(subunit)
        time = ctypes.c_uint(0)

        err = self.handle.PIL_SettleTime(self.card, subunit, ctypes.byref(time))
        self._handleError(err)
        return int(time.value)
    
    def Status(self):
        status = self.handle.PIL_Status(self.card)
        return status
    
    def SubAttribute(self, subunit, outSub, attrCode):
        attr = ctypes.c_uint(0)
        subunit = ctypes.c_uint32(subunit)
        outSub = ctypes.c_uint32(outSub)
        attrCode = ctypes.c_uint32(attrCode)

        err = self.handle.PIL_SubAttribute(self.card, subunit, outSub, attrCode, ctypes.byref(attr))
        self._handleError(err)
        return attr.value
    
    def SubInfo(self, subunit, outSub):
        stype = ctypes.c_uint(0)
        rows = ctypes.c_uint(0)
        cols = ctypes.c_uint(0)
        subunit = ctypes.c_uint32(subunit)
        outSub = ctypes.c_uint32(outSub)

        err = self.handle.PIL_SubInfo(self.card, subunit, outSub, ctypes.byref(stype), ctypes.byref(rows), ctypes.byref(cols))
        self._handleError(err)
        return stype.value, rows.value, cols.value
    
    def SubSize(self, sub, out_not_in):
        subType, rows, columns = self.SubInfo(sub, out_not_in)

        dwords = self._calc_dwords(rows * columns)
        return dwords

    def SubStatus(self, subunit):
        status = ctypes.c_uint(0)
        subunit = ctypes.c_uint32(subunit)

        err = self.handle.PIL_SubStatus(self.card, subunit, ctypes.byref(status))
        self._handleError(err)
        return int(status.value)
    
    def SubType(self, subunit, outputSubunit):
        string = ctypes.create_string_buffer(100)

        subunit = ctypes.c_uint32(subunit)
        outputSubunit = ctypes.c_bool(outputSubunit)

        err = self.handle.PIL_SubType(self.card, subunit, outputSubunit, ctypes.byref(string))
        self._handleError(err)
        return self._pythonString(string.value)
    
    def ViewBit(self, subunit, bit):
        state = ctypes.c_bool()
        subunit = ctypes.c_uint32(subunit)
        bit = ctypes.c_uint32(bit)

        err = self.handle.PIL_ViewBit(self.card, subunit, bit, ctypes.byref(state))
        self._handleError(err)
        return bool(state.value)
        
    def ViewCrosspoint(self, sub, row, column):
        state = ctypes.c_bool()
        sub = ctypes.c_uint32(sub)
        row = ctypes.c_uint32(row)
        column = ctypes.c_uint32(column)

        err = self.handle.PIL_ViewCrosspoint(self.card, sub, row, column, ctypes.byref(state))
        self._handleError(err)
        return bool(state.value)

    def ViewMask(self, subunit):
        subunit = ctypes.c_int(subunit)

        # get size of subunit and create an array to hold the data
        subType, rows, cols = self.SubInfo(subunit, 1)
        dwords = self._calc_dwords(rows * cols)
        data = (ctypes.c_uint32 * dwords)()

        err = self.handle.PIL_ViewMask(self.card, subunit, ctypes.byref(data))
        self._handleError(err)
        return [int(dword) for dword in data]

    def ViewMaskBit(self, subunit, bit):
        state = ctypes.c_bool()
        subunit = ctypes.c_uint32(subunit)
        bit = ctypes.c_uint32(bit)

        err = self.handle.PIL_ViewMaskBit(self.card, subunit, bit, ctypes.byref(state))
        self._handleError(err)
        return bool(state.value)
    
    def ViewMaskCrosspoint(self, sub, row, column):
        state = ctypes.c_bool()
        sub = ctypes.c_uint32(sub)
        row = ctypes.c_uint32(row)
        column = ctypes.c_uint32(column)

        err = self.handle.PIL_ViewMaskCrosspoint(self.card, sub, row, column, ctypes.byref(state))
        self._handleError(err)
        return bool(state.value)
    
    def ViewSub(self, subunit):
        subunit = ctypes.c_int(subunit)

        # get size of subunit and create an array to hold the data
        subType, rows, cols = self.SubInfo(subunit.value, 1)
        dwords = self._calc_dwords(rows * cols)
        data = (ctypes.c_uint32 * dwords)()

        err = self.handle.PIL_ViewSub(self.card, subunit, ctypes.byref(data))
        self._handleError(err)
        return [int(dword) for dword in data]
    
    def WriteMask(self, subunit, data):
        subunit = ctypes.c_uint32(subunit)
        data = (ctypes.c_uint32 * len(data))(*data)

        err = self.handle.PIL_WriteMask(self.card, subunit, ctypes.byref(data))
        self._handleError(err)
        return

    def WriteSub(self, subunit, data):
        subunit = ctypes.c_int(subunit)
        data = (ctypes.c_uint32 * len(data))(*data)

        err = self.handle.PIL_WriteSub(self.card, subunit, ctypes.byref(data))
        self._handleError(err)
        return

    #endregion

    #region Calibration Functions

    def ReadCal(self, subunit, index):
        data = ctypes.c_uint32(0)
        subunit = ctypes.c_uint32(subunit)
        index = ctypes.c_uint32(index)

        err = self.handle.PIL_ReadCal(self.card, subunit, index, ctypes.byref(data))
        self._handleError(err)
        return int(data.value)

    def WriteCal(self, subunit, index, data):
        subunit = ctypes.c_uint32(subunit)
        index = ctypes.c_uint32(index)
        data = ctypes.c_uint32(data)

        err = self.handle.PIL_WriteCal(self.card, subunit, index, data)
        self._handleError(err)
        return

    def ReadCalFP(self, subunit, store, offset, numValues):
        subunit = ctypes.c_uint32(subunit)
        store = ctypes.c_uint32(store)
        offset = ctypes.c_uint32(offset)
        numValues = ctypes.c_uint32(numValues)

        data = (ctypes.c_double * numValues.value)()

        err = self.handle.PIL_ReadCalFP(
                                         self.card,
                                         subunit,
                                         store,
                                         offset,
                                         numValues,
                                         ctypes.byref(data))
        self._handleError(err)

        return [val.value for val in data]

    def WriteCalFP(self, subunit, store, offset, data):
        subunit = ctypes.c_uint32(subunit)
        store = ctypes.c_uint32(store)
        offset = ctypes.c_uint32(offset)
        numValues = ctypes.c_uint32(len(data))

        data = (ctypes.c_double * numValues.value)(*data)

        err = self.handle.PIL_WriteCalFP(
                                          self.card,
                                          subunit,
                                          store,
                                          offset,
                                          numValues,
                                          data)
        self._handleError(err)

        return

    def WriteCalDate(self, subunit, store, interval):
        subunit = ctypes.c_uint32(subunit)
        store = ctypes.c_uint32(store)
        interval = ctypes.c_uint32(interval)

        err = self.handle.PIL_WriteCalDate(
                                            self.card,
                                            subunit,
                                            store,
                                            interval)
        self._handleError(err)

        return

    def ReadCalDate(self, subunit, store):
        subunit = ctypes.c_uint32(subunit)
        store = ctypes.c_uint32(store)

        year = ctypes.c_uint32()
        day = ctypes.c_uint32()
        interval = ctypes.c_uint32()

        err = self.handle.PIL_ReadCalDate(
                                           self.card,
                                           subunit,
                                           store,
                                           ctypes.byref(year),
                                           ctypes.byref(day),
                                           ctypes.byref(interval))
        self._handleError(err)

        return year.value, day.value, interval.value

    def SetCalPoint(self, subunit, index):
        subunit = ctypes.c_uint32(subunit)
        index = ctypes.c_uint32(index)

        err = self.handle.PIL_SetCalPoint(
                                           self.card,
                                           subunit,
                                           index)
        self._handleError(err)

        return

    #endregion

    #region Subunit state functions

    def GetSubState(self, subunit):
        subType, rows, columns = self.SubInfo(subunit, 1)
        stateData = self.ViewSub(subunit)
        subInfo = self.SubInfo(subunit, 1)

        state = _SubState(rows, columns, subunit, subInfo, stateData)
        return state

    def GetBlankSubState(self, subunit):
        subType, rows, columns = self.SubInfo(subunit, 1)
        stateData = [0] * self._calc_dwords(rows * columns)
        subInfo = self.SubInfo(subunit, 1)

        state = _SubState(rows, columns, subunit, subInfo, stateData)
        return state

    def WriteSubState(self, subunit, subunitState):
        if subunitState.subInfo != self.SubInfo(subunit, 1):
            raise Error("Cannot apply subunit state to different subunit type")

        self.WriteSub(subunit, subunitState.stateData)
        return

    #endregion
    
    #region Attenuator card functions

    def AttenType(self, subunit):
        string = ctypes.create_string_buffer(100)
        subunit = ctypes.c_uint32(subunit)

        err = self.handle.PIL_AttenType(self.card, subunit, ctypes.byref(string))
        self._handleError(err)
        return self._pythonString(string.value)
       
    def AttenInfo(self, subunit):
        size = ctypes.c_float(0.0)
        steps = ctypes.c_uint(0)
        stype = ctypes.c_uint(0)
        subunit = ctypes.c_uint32(subunit)

        err = self.handle.PIL_AttenInfo(self.card, subunit, ctypes.byref(stype), ctypes.byref(steps), ctypes.byref(size))
        self._handleError(err)
        return int(stype.value), int(steps.value), int(size.value)

    def SetAttenuation(self, subunit, attenuation):
        subunit = ctypes.c_uint32(subunit)
        attenuation = ctypes.c_float(attenuation)

        err = self.handle.PIL_AttenSetAttenuation(self.card, subunit, attenuation)
        self._handleError(err)
        return
    
    def GetAttenuation(self, subunit):
        attenuation = ctypes.c_float(0.0)
        subunit = ctypes.c_uint32(subunit)
        err = self.handle.PIL_AttenGetAttenuation(self.card, subunit, ctypes.byref(attenuation))
        self._handleError(err)
        return float(attenuation.value)

    def PadValue(self, subunit, padNum):
        attenuation = ctypes.c_float(0.0)
        subunit = ctypes.c_uint32(subunit)
        padNum = ctypes.c_uint32(padNum)

        err = self.handle.PIL_AttenPadValue(self.card, subunit, padNum, ctypes.byref(attenuation))
        self._handleError(err)
        return float(attenuation.value)

    #endregion

    #region PSU card functions

    def PsuType(self, subunit):
        string = ctypes.create_string_buffer(100)
        subunit = ctypes.c_uint32(subunit)
        err = self.handle.PIL_PsuType(self.card, subunit, ctypes.byref(string), 100)
        self._handleError(err)
        return self._pythonString(string.value)
        
    def PsuInfo(self, subunit):
        stype = ctypes.c_uint(0)
        volts = ctypes.c_double(0.0)
        amps = ctypes.c_double(0.0)
        precis = ctypes.c_uint(0)
        capb = ctypes.c_uint(0)
        subunit = ctypes.c_uint32(subunit)

        err = self.handle.PIL_PsuInfo(self.card, subunit, ctypes.byref(stype), ctypes.byref(volts), ctypes.byref(amps), ctypes.byref(precis), ctypes.byref(capb))
        self._handleError(err)
        return stype.value, volts.value, amps.value, precis.value, capb.value
    
    def PsuGetVoltage(self, subunit):
        volts = ctypes.c_double(0.0)
        subunit = ctypes.c_uint32(subunit)

        err = self.handle.PIL_PsuGetVoltage(self.card, subunit, ctypes.byref(volts))
        self._handleError(err)
        return volts.value

    def PsuSetVoltage(self, subunit, voltage):
        voltage = ctypes.c_double(voltage)
        subunit = ctypes.c_uint32(subunit)

        err = self.handle.PIL_PsuSetVoltage(self.card, subunit, voltage)
        self._handleError(err)
        return

    def PsuEnable(self, subunit, enable):
        subunit = ctypes.c_uint32(subunit)
        enable = ctypes.c_bool(enable)

        err = self.handle.PIL_PsuEnable(self.card, subunit, enable)
        self._handleError(err)
        return

    #endregion

    #region Battery Simulator Functions

    def BattSetVoltage(self, subunit, voltage):
        voltage = ctypes.c_double(voltage)
        subunit = ctypes.c_uint32(subunit)

        err = self.handle.PIL_BattSetVoltage(self.card, subunit, voltage)
        self._handleError(err)
        return

    def BattGetVoltage(self, subunit):
        volts = ctypes.c_double(0.0)
        subunit = ctypes.c_uint32(subunit)

        err = self.handle.PIL_BattGetVoltage(self.card, subunit, ctypes.byref(volts))
        self._handleError(err)
        return float(volts.value)

    def BattSetCurrent(self, subunit, curr):
        current = ctypes.c_double(curr)
        subunit = ctypes.c_uint32(subunit)
        err = self.handle.PIL_BattSetCurrent(self.card, subunit, current)
        self._handleError(err)
        return

    def BattGetCurrent(self, subunit):
        current = ctypes.c_double(0.0)
        subunit = ctypes.c_uint32(subunit)
        err = self.handle.PIL_BattGetCurrent(self.card, subunit, ctypes.byref(current))
        self._handleError(err)
        return float(current.value)

    def BattSetEnable(self, subunit, state):
        subunit = ctypes.c_uint32(subunit)
        state = ctypes.c_bool(state)
        err = self.handle.PIL_BattSetEnable(self.card, subunit, state)
        self._handleError(err)
        return

    def BattGetEnable(self, subunit):
        state = ctypes.c_bool(0)
        subunit = ctypes.c_uint32(subunit)
        err = self.handle.PIL_BattGetEnable(self.card, subunit, ctypes.byref(state))
        self._handleError(err)
        return state.value

    def BattReadInterlockState(self, subunit):
        state = ctypes.c_bool()
        subunit = ctypes.c_uint32(subunit)
        err = self.handle.PIL_BattReadInterlockState(self.card, subunit, ctypes.byref(state))
        self._handleError(err)
        return state.value

    def BattMeasureVoltage(self, subunit):
        """Measures actual voltage value on supported Battery Simulator cards."""

        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        voltage = ctypes.c_double(0)

        err = self.handle.PIL_GetAttribute(self.card,
                                           subunit,
                                           is_output,
                                           Attributes.VOLTAGE_V,
                                           ctypes.byref(voltage))
        self._handleError(err)

        return voltage.value

    def BattMeasureCurrentmA(self, subunit):
        """Measures actual current value in milliamps on supported Battery Simulator cards."""

        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        currentmA = ctypes.c_double()

        err = self.handle.PIL_GetAttribute(self.card,
                                           subunit,
                                           is_output,
                                           Attributes.CURRENT_MA,
                                           ctypes.byref(currentmA))
        self._handleError(err)

        return currentmA.value

    def BattMeasureCurrentA(self, subunit):
        """Measures actual current value in amps on supported Battery Simulator cards."""

        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        current = ctypes.c_double()

        err = self.handle.PIL_GetAttribute(
                                            self.card,
                                            subunit,
                                            is_output,
                                            Attributes.CURRENT_A,
                                            ctypes.byref(current))
        self._handleError(err)

        return current.value

    def BattSetMeasureConfig(self,
                             subunit,
                             numOfSamples,
                             VConversionTimePerSample,
                             IConversionTimePerSample,
                             ModeOfOperation):

        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)

        measureConfig = ((numOfSamples & 0x7)
                         | ((IConversionTimePerSample & 0x7) << 6)
                         | ((VConversionTimePerSample & 0x7) << 9)
                         | ((ModeOfOperation & 0xF) << 12))

        measureConfig = ctypes.c_uint32(measureConfig)

        err = self.handle.PIL_SetAttribute(
                                            self.card,
                                            subunit,
                                            is_output,
                                            Attributes.MEASURE_CONFIG,
                                            ctypes.byref(measureConfig))
        self._handleError(err)

        return

    def BattSetMeasureSet(self, subunit, enabled):

        subunit = ctypes.c_uint32(subunit)
        enabled = ctypes.c_bool(enabled)
        is_output = ctypes.c_uint32(1)

        err = self.handle.PIL_SetAttribute(
                                            self.card,
                                            subunit,
                                            is_output,
                                            Attributes.C_SET_MEASURE_SET,
                                            ctypes.byref(enabled))
        self._handleError(err)

        return

    def BattQuerySetMeasureSet(self, subunit):

        subunit = ctypes.c_uint32(subunit)
        enabled = ctypes.c_bool(0)
        is_output = ctypes.c_uint32(1)

        err = self.handle.PIL_GetAttribute(
                                            self.card,
                                            subunit,
                                            is_output,
                                            Attributes.C_SET_MEASURE_SET,
                                            ctypes.byref(enabled))
        self._handleError(err)

        return enabled.value

    def BattSetLoad(self, subunit, load):

        subunit = ctypes.c_uint32(subunit)
        load = ctypes.c_uint32(load)
        is_output = ctypes.c_uint32(1)

        err = self.handle.PIL_SetAttribute(
                                            self.card,
                                            subunit,
                                            is_output,
                                            Attributes.LOAD,
                                            ctypes.byref(load))
        self._handleError(err)

        return

    #endregion

    #region Resistor Functions

    def ResSetResistance(self, subunit, resistance, mode=0):
        mode = ctypes.c_uint(mode)
        resistance = ctypes.c_double(resistance)
        subunit = ctypes.c_uint32(subunit)

        err = self.handle.PIL_ResSetResistance(self.card, subunit, mode, resistance)
        self._handleError(err)
        return

    def ResGetResistance(self, subunit):
        resistance = ctypes.c_double(0.0)
        subunit = ctypes.c_uint32(subunit)
        err = self.handle.PIL_ResGetResistance(self.card, subunit, ctypes.byref(resistance))
        self._handleError(err)
        return resistance.value

    def ResInfo(self, subunit):
        minres = ctypes.c_double(0.0)
        maxres = ctypes.c_double(0.0)
        refres = ctypes.c_double(0.0)
        precpc = ctypes.c_double(0.0)
        precdelta = ctypes.c_double(0.0)
        int1 = ctypes.c_double(0.0)
        intdelta = ctypes.c_double(0.0)
        caps = ctypes.c_uint(0)
        subunit = ctypes.c_uint32(subunit)

        err = self.handle.PIL_ResInfo(self.card, subunit,
                                      ctypes.byref(minres),
                                      ctypes.byref(maxres),
                                      ctypes.byref(refres),
                                      ctypes.byref(precpc),
                                      ctypes.byref(precdelta),
                                      ctypes.byref(int1),
                                      ctypes.byref(intdelta),
                                      ctypes.byref(caps))
        self._handleError(err)

        return {"MinRes":       minres.value,
                "MaxRes":       maxres.value,
                "RefRes":       refres.value,
                "PrecPC":       precpc.value,
                "PrecDelta":    precdelta.value,
                "Int1":         int1.value,
                "IntDelta":     intdelta.value,
                "Capabilities": caps.value}

    #endregion

    #region Thermocouple functions

    def VsourceSetVoltage(self, subunit, voltage):
        voltage = ctypes.c_double(voltage)
        subunit = ctypes.c_uint32(subunit)

        err = self.handle.PIL_VsourceSetVoltage(self.card, subunit, voltage)
        self._handleError(err)
        return

    def VsourceGetVoltage(self, subunit):
        mvolt = ctypes.c_double(0.0)
        err = self.handle.PIL_VsourceGetVoltage(self.card, subunit, ctypes.byref(mvolt))
        self._handleError(err)
        return mvolt.value
    
    def VsourceSetRange(self, subunit, ts_range):
        err = self.ERRORCODE["ER_BAD_RANGE"]
        isoutsub = ctypes.c_uint32(1)
        subunit = ctypes.c_uint32(subunit)
        if ts_range in self.TS_RANGE.values():
            ts_range = ctypes.c_uint(ts_range)
            err = self.handle.PIL_SetAttribute(self.card, subunit, isoutsub,
                                               self.ATTR["TS_SET_RANGE"], ctypes.byref(ts_range))
        self._handleError(err)
        return

    def VsourceGetRange(self, subunit):
        isoutsub = ctypes.c_uint32(1)
        ts_range = ctypes.c_uint(0)
        subunit = ctypes.c_uint32(subunit)
        err = self.handle.PIL_GetAttribute(self.card, subunit, isoutsub,
                                           self.ATTR["TS_SET_RANGE"], ctypes.byref(ts_range))
        self._handleError(err)
        return ts_range.value

    def VsourceInfo(self, subunit):
        is_output = ctypes.c_uint32(1)
        subunit = ctypes.c_uint32(subunit)

        low_range_min = ctypes.c_double(0.0)
        low_range_med = ctypes.c_double(0.0)
        low_range_max = ctypes.c_double(0.0)
        low_range_max_dev = ctypes.c_double(0.0)
        low_range_prec_pc = ctypes.c_double(0.0)
        low_range_prec_delta = ctypes.c_double(0.0)

        med_range_min = ctypes.c_double(0.0)
        med_range_med = ctypes.c_double(0.0)
        med_range_max = ctypes.c_double(0.0)
        med_range_max_dev = ctypes.c_double(0.0)
        med_range_prec_pc = ctypes.c_double(0.0)
        med_range_prec_delta = ctypes.c_double(0.0)

        high_range_min = ctypes.c_double(0.0)
        high_range_med = ctypes.c_double(0.0)
        high_range_max = ctypes.c_double(0.0)
        high_range_max_dev = ctypes.c_double(0.0)
        high_range_prec_pc = ctypes.c_double(0.0)
        high_range_prec_delta = ctypes.c_double(0.0)

        err = self.handle.PIL_GetAttribute(self.card, subunit,
                                           is_output,
                                           self.ATTR["TS_LOW_RANGE_MIN"],
                                           ctypes.byref(low_range_min))

        err = self.handle.PIL_GetAttribute(self.card, subunit,
                                           is_output,
                                           self.ATTR["TS_LOW_RANGE_MED"],
                                           ctypes.byref(low_range_med))

        err = self.handle.PIL_GetAttribute(self.card, subunit,
                                           is_output,
                                           self.ATTR["TS_LOW_RANGE_MAX"],
                                           ctypes.byref(low_range_max))

        err = self.handle.PIL_GetAttribute(self.card, subunit,
                                           is_output,
                                           self.ATTR["TS_LOW_RANGE_MAX_DEV"],
                                           ctypes.byref(low_range_max_dev))

        err = self.handle.PIL_GetAttribute(self.card, subunit,
                                           is_output,
                                           self.ATTR["TS_LOW_RANGE_PREC_PC"],
                                           ctypes.byref(low_range_prec_pc))

        err = self.handle.PIL_GetAttribute(self.card, subunit,
                                           is_output,
                                           self.ATTR["TS_LOW_RANGE_PREC_DELTA"],
                                           ctypes.byref(low_range_prec_delta))

        err = self.handle.PIL_GetAttribute(self.card, subunit,
                                           is_output,
                                           self.ATTR["TS_MED_RANGE_MIN"],
                                           ctypes.byref(med_range_min))

        err = self.handle.PIL_GetAttribute(self.card, subunit,
                                           is_output,
                                           self.ATTR["TS_MED_RANGE_MED"],
                                           ctypes.byref(med_range_med))

        err = self.handle.PIL_GetAttribute(self.card, subunit,
                                           is_output,
                                           self.ATTR["TS_MED_RANGE_MAX"],
                                           ctypes.byref(med_range_max))

        err = self.handle.PIL_GetAttribute(self.card, subunit,
                                           is_output,
                                           self.ATTR["TS_MED_RANGE_MAX_DEV"],
                                           ctypes.byref(med_range_max_dev))

        err = self.handle.PIL_GetAttribute(self.card, subunit,
                                           is_output,
                                           self.ATTR["TS_MED_RANGE_PREC_PC"],
                                           ctypes.byref(med_range_prec_pc))

        err = self.handle.PIL_GetAttribute(self.card, subunit,
                                           is_output,
                                           self.ATTR["TS_MED_RANGE_PREC_DELTA"],
                                           ctypes.byref(med_range_prec_delta))

        err = self.handle.PIL_GetAttribute(self.card, subunit,
                                           is_output,
                                           self.ATTR["TS_HIGH_RANGE_MIN"],
                                           ctypes.byref(high_range_min))

        err = self.handle.PIL_GetAttribute(self.card, subunit,
                                           is_output,
                                           self.ATTR["TS_HIGH_RANGE_MED"],
                                           ctypes.byref(high_range_med))

        err = self.handle.PIL_GetAttribute(self.card, subunit,
                                           is_output,
                                           self.ATTR["TS_HIGH_RANGE_MAX"],
                                           ctypes.byref(high_range_max))

        err = self.handle.PIL_GetAttribute(self.card, subunit,
                                           is_output,
                                           self.ATTR["TS_HIGH_RANGE_MAX_DEV"],
                                           ctypes.byref(high_range_max_dev))

        err = self.handle.PIL_GetAttribute(self.card, subunit,
                                           is_output,
                                           self.ATTR["TS_HIGH_RANGE_PREC_PC"],
                                           ctypes.byref(high_range_prec_pc))

        err = self.handle.PIL_GetAttribute(self.card, subunit,
                                           is_output,
                                           self.ATTR["TS_HIGH_RANGE_PREC_DELTA"],
                                           ctypes.byref(high_range_prec_delta))

        self._handleError(err)

        return {"LOW_RANGE_MIN":            low_range_min.value,
                "LOW_RANGE_MED":            low_range_med.value,
                "LOW_RANGE_MAX":            low_range_max.value,
                "LOW_RANGE_MAX_DEV":        low_range_max_dev.value,
                "LOW_RANGE_PREC_PC":        low_range_prec_pc.value,
                "LOW_RANGE_PREC_DELTA":     low_range_prec_delta.value,
                "MED_RANGE_MIN":            med_range_min.value,
                "MED_RANGE_MED":            med_range_med.value,
                "MED_RANGE_MAX":            med_range_max.value,
                "MED_RANGE_MAX_DEV":        med_range_max_dev.value,
                "MED_RANGE_PREC_PC":        med_range_prec_pc.value,
                "MED_RANGE_PREC_DELTA":     med_range_prec_delta.value,
                "HIGH_RANGE_MIN":           high_range_min.value,
                "HIGH_RANGE_MED":           high_range_med.value,
                "HIGH_RANGE_MAX":           high_range_max.value,
                "HIGH_RANGE_MAX_DEV":       high_range_max_dev.value,
                "HIGH_RANGE_PREC_PC":       high_range_prec_pc.value,
                "HIGH_RANGE_PREC_DELTA":    high_range_prec_delta.value}

    def VsourceGetTemperature(self, unit):
        err = self.ERRORCODE["ER_BAD_ATTR_CODE"]
        is_output = 1
        sub = 1
        temperatures = (ctypes.c_double * 4)(0.0, 0.0, 0.0, 0.0)
        if unit == self.ATTR["TS_TEMPERATURES_C"] or unit == self.ATTR["TS_TEMPERATURES_F"]:
            err = self.handle.PIL_GetAttribute(self.card, sub,
                                               is_output,
                                               unit,
                                               ctypes.byref(temperatures))
        self._handleError(err)
        return [float(temp) for temp in temperatures]

    ### Deprecated Thermocouple Functions ###

    # def VsourceSetRange(self, sub, ts_range):
    #     rng = c_double(ts_range)
    #     err = self.handle.PIL_PIL_VsourceSetRange(self.card, sub, rng)
    #     return err

    # def VsourceGetRange(self, sub):
    #     rng = c_double(0.0)
    #     err = self.handle.PIL_VsourceGetRange(self.card, sub, byref(rng))
    #     return err, rng.value

    # def VsourceSetEnable(self, sub, pattern):
    #     err = self.handle.PIL_VsourceSetEnable(self.card, sub, pattern)
    #     return err
    
    # def VsourceGetEnable(self, sub):
    #     pattern = c_uint(0)
    #     err = self.handle.VsourceGetEnable(self.card, sub, byref(pattern))
    #     return err, pattern

    #endregion

    #region VDT/Resolver Functions

    def GetCurrentmA(self, subunit):
        current = ctypes.c_uint32()
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["CURRENT_MA"],
                                                ctypes.byref(current))
        self._handleError(err)

        return float(current.value)

    def SetVoltageV(self, subunit, voltage):
        voltage = ctypes.c_uint32(voltage)
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)

        err = self.handle.PIL_SetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VOLTAGE_V"],
                                                ctypes.byref(voltage))
        self._handleError(err)

        return

    def GetVoltageV(self, subunit):
        voltage = ctypes.c_uint32()
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VOLTAGE_V"],
                                                ctypes.byref(voltage))
        self._handleError(err)
        return float(voltage.value)

    def ResolverSetStartStopRotate(self, subunit, state):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)

        if state:
            state = ctypes.c_uint32(1)
        else:
            state = ctypes.c_uint32(0)

        err = self.handle.PIL_SetAttribute(
            self.card,
            subunit,
            is_output,
            Attributes.RESOLVER_START_STOP_ROTATE,
            ctypes.byref(state))
        self._handleError(err)

        return

    def ResolverGetStartStopRotate(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        result = ctypes.c_uint32()

        err = self.handle.PIL_GetAttribute(
            self.card,
            subunit,
            is_output,
            Attributes.RESOLVER_START_STOP_ROTATE,
            ctypes.byref(result))
        self._handleError(err)

        return bool(result.value)

    def ResolverSetNumOfTurns(self, subunit, turns):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        turns = ctypes.c_uint16(turns)

        err = self.handle.PIL_SetAttribute(
            self.card,
            subunit,
            is_output,
            Attributes.RESOLVER_NUM_OF_TURNS,
            ctypes.byref(turns))
        self._handleError(err)

        return

    def ResolverGetNumOfTurns(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        turns = ctypes.c_uint16()

        err = self.handle.PIL_GetAttribute(
            self.card,
            subunit,
            is_output,
            Attributes.RESOLVER_NUM_OF_TURNS,
            ctypes.byref(turns))
        self._handleError(err)

        return float(turns.value)

    def ResolverSetRotateSpeed(self, subunit, speed):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        speed = ctypes.c_double(speed)

        err = self.handle.PIL_SetAttribute(
            self.card,
            subunit,
            is_output,
            Attributes.RESOLVER_ROTATE_SPEED,
            ctypes.byref(speed))
        self._handleError(err)

        return

    def ResolverGetRotateSpeed(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        speed = ctypes.c_double()

        err = self.handle.PIL_GetAttribute(
            self.card,
            subunit,
            is_output,
            Attributes.RESOLVER_ROTATE_SPEED,
            ctypes.byref(speed))
        self._handleError(err)

        return float(speed.value)

    def ResolverSetPosition(self, subunit, position):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        position = ctypes.c_double(position)

        err = self.handle.PIL_SetAttribute(
            self.card,
            subunit,
            is_output,
            Attributes.RESOLVER_POSITION,
            ctypes.byref(position))
        self._handleError(err)

        return

    def ResolverGetPosition(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        position = ctypes.c_double()

        err = self.handle.PIL_GetAttribute(
            self.card,
            subunit,
            is_output,
            Attributes.RESOLVER_POSITION,
            ctypes.byref(position))
        self._handleError(err)

        return float(position.value)

    def ResolverSetPosition0To360(self, subunit, position):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        position = ctypes.c_double(position)

        err = self.handle.PIL_SetAttribute(
            self.card,
            subunit,
            is_output,
            Attributes.RESOLVER_POSITION_0_360,
            ctypes.byref(position))
        self._handleError(err)

        return

    def ResolverGetPosition0To360(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        position = ctypes.c_double()

        err = self.handle.PIL_GetAttribute(
            self.card,
            subunit,
            is_output,
            Attributes.RESOLVER_POSITION_0_360,
            ctypes.byref(position))
        self._handleError(err)

        return position.value

    def VDTSetInputAtten(self, subunit, attenuation):
        attenuation = ctypes.c_uint32(attenuation)
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)

        err = self.handle.PIL_SetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_AUTO_INPUT_ATTEN"],
                                                ctypes.byref(attenuation))
        self._handleError(err)

        return

    def VDTGetInputAtten(self, subunit):
        attenuation = ctypes.c_uint32()
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_AUTO_INPUT_ATTEN"],
                                                ctypes.byref(attenuation))
        self._handleError(err)
        return int(attenuation.value)

    def VDTSetABSPosition(self, subunit, position):
        position = ctypes.c_uint32(position)
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)

        err = self.handle.PIL_SetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_ABS_POSITION"],
                                                ctypes.byref(position))
        self._handleError(err)
        return

    def VDTGetABSPosition(self, subunit):
        position = ctypes.c_uint32()
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_ABS_POSITION"],
                                                ctypes.byref(position))
        self._handleError(err)
        return int(position.value)

    def VDTSetABSPositionB(self, subunit, position):
        position = ctypes.c_uint32(position)
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)

        err = self.handle.PIL_SetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_ABS_POSITION_B"],
                                                ctypes.byref(position))
        self._handleError(err)
        return

    def VDTGetABSPositionB(self, subunit):
        position = ctypes.c_uint32()
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_ABS_POSITION_B"],
                                                ctypes.byref(position))
        self._handleError(err)
        return int(position.value)

    def VDTSetPercentPosition(self, subunit, position):
        position = ctypes.c_double(position)
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)

        err = self.handle.PIL_SetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_PERCENT_POSITION"],
                                                ctypes.byref(position))
        self._handleError(err)
        return

    def VDTGetPercentPosition(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        position = ctypes.c_double()
        is_output = ctypes.c_uint32(1)

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_PERCENT_POSITION"],
                                                ctypes.byref(position))
        self._handleError(err)
        return int(position.value)

    def VDTSetPercentPositionB(self, subunit, position):
        position = ctypes.c_double(position)
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)

        err = self.handle.PIL_SetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_PERCENT_POSITION_B"],
                                                ctypes.byref(position))
        self._handleError(err)
        return

    def VDTGetPercentPositionB(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        position = ctypes.c_double()
        is_output = ctypes.c_uint32(1)

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_PERCENT_POSITION_B"],
                                                ctypes.byref(position))
        self._handleError(err)
        return int(position.value)

    def VDTSetVsum(self, subunit, vsum):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        vsum = ctypes.c_double(vsum)

        err = self.handle.PIL_SetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_VOLTAGE_SUM"],
                                                ctypes.byref(vsum))
        self._handleError(err)
        return

    def VDTGetVsum(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        vsum = ctypes.c_double()

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_VOLTAGE_SUM"],
                                                ctypes.byref(vsum))
        self._handleError(err)
        return float(vsum.value)

    def VDTSetVdiff(self, subunit, vdiff):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        vdiff = ctypes.c_double(vdiff)

        err = self.handle.PIL_SetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_VOLTAGE_DIFF"],
                                                ctypes.byref(vdiff))
        self._handleError(err)
        return

    def VDTGetVdiff(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        vdiff = ctypes.c_double()

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_VOLTAGE_DIFF"],
                                                ctypes.byref(vdiff))
        self._handleError(err)
        return float(vdiff.value)

    def VDTSetOutGain(self, subunit, outgain):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        outgain = ctypes.c_uint32(outgain)

        err = self.handle.PIL_SetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_OUT_GAIN"],
                                                ctypes.byref(outgain))
        self._handleError(err)
        return

    def VDTGetOutGain(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        outgain = ctypes.c_uint32()

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_OUT_GAIN"],
                                                ctypes.byref(outgain))
        self._handleError(err)
        return int(outgain.value)

    def VDTSetManualInputAtten(self, subunit, attenuation):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        attenuation = ctypes.c_uint32(attenuation)

        err = self.handle.PIL_SetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_MANUAL_INPUT_ATTEN"],
                                                ctypes.byref(attenuation))
        self._handleError(err)
        return

    def VDTGetManualInputAtten(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        attenuation = ctypes.c_uint32()

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_MANUAL_INPUT_ATTEN"],
                                                ctypes.byref(attenuation))
        self._handleError(err)
        return int(attenuation.value)

    def VDTSetMode(self, subunit, mode):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        mode = ctypes.c_uint32(mode)

        err = self.handle.PIL_SetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_MODE"],
                                                ctypes.byref(mode))
        self._handleError(err)
        return

    def VDTGetMode(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        mode = ctypes.c_uint32()

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_MODE"],
                                                ctypes.byref(mode))
        self._handleError(err)
        return int(mode.value)

    def VDTSetDelayA(self, subunit, delay):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        delay = ctypes.c_uint32(delay)

        err = self.handle.PIL_SetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_DELAY_A"],
                                                ctypes.byref(delay))
        self._handleError(err)
        return

    def VDTGetDelayA(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        delay = ctypes.c_uint32()

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_DELAY_A"],
                                                ctypes.byref(delay))
        self._handleError(err)
        return int(delay.value)

    def VDTSetDelayB(self, subunit, delay):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        delay = ctypes.c_uint32(delay)

        err = self.handle.PIL_SetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_DELAY_B"],
                                                ctypes.byref(delay))
        self._handleError(err)
        return

    def VDTGetDelayB(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        delay = ctypes.c_uint32()

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_DELAY_B"],
                                                ctypes.byref(delay))
        self._handleError(err)
        return int(delay.value)

    def VDTSetInputLevel(self, subunit, level):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        level = ctypes.c_uint32(level)

        err = self.handle.PIL_SetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_INPUT_LEVEL"],
                                                ctypes.byref(level))
        self._handleError(err)
        return

    def VDTGetInputLevel(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        level = ctypes.c_uint32()

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_INPUT_LEVEL"],
                                                ctypes.byref(level))
        self._handleError(err)
        return int(level.value)

    def VDTSetInputFreq(self, subunit, freq):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        freq = ctypes.c_uint32(freq)

        err = self.handle.PIL_SetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_INPUT_FREQ"],
                                                ctypes.byref(freq))
        self._handleError(err)
        return

    def VDTGetInputFreq(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        freq = ctypes.c_uint32()

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_INPUT_FREQ"],
                                                ctypes.byref(freq))
        self._handleError(err)
        return int(freq.value)

    def VDTSetOutLevel(self, subunit, level):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        level = ctypes.c_uint32(level)

        err = self.handle.PIL_SetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_OUT_LEVEL"],
                                                ctypes.byref(level))
        self._handleError(err)
        return

    def VDTGetOutLevel(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        level = ctypes.c_uint32()

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_OUT_LEVEL"],
                                                ctypes.byref(level))
        self._handleError(err)
        return int(level.value)

    # LVDT mk2 Get only
    def VDTGetDSPICVersion(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        version = ctypes.c_uint32()

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_DSPIC_VERSION"],
                                                ctypes.byref(version))
        self._handleError(err)
        return int(version.value)

    # LVDT mk2 Set/Get
    def VDTSetInvertA(self, subunit, state):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        state = ctypes.c_uint32(state)

        err = self.handle.PIL_SetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_INVERT_A"],
                                                ctypes.byref(state))
        self._handleError(err)
        return

    def VDTGetInvertA(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        state = ctypes.c_uint32()

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_INVERT_A"],
                                                ctypes.byref(state))
        self._handleError(err)
        return int(state.value)

    def VDTSetInvertB(self, subunit, state):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        state = ctypes.c_uint32(state)

        err = self.handle.PIL_SetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_INVERT_B"],
                                                ctypes.byref(state))
        self._handleError(err)
        return

    def VDTGetInvertB(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        state = ctypes.c_uint32()

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_INVERT_B"],
                                                ctypes.byref(state))
        self._handleError(err)
        return int(state.value)

    def VDTSetPhaseTracking(self, subunit, state):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        state = ctypes.c_uint32(state)

        err = self.handle.PIL_SetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_PHASE_TRACKING"],
                                                ctypes.byref(state))
        self._handleError(err)
        return

    def VDTGetPhaseTracking(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        state = ctypes.c_uint32()

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_PHASE_TRACKING"],
                                                ctypes.byref(state))
        self._handleError(err)
        return int(state.value)

    def VDTSetSampleLoad(self, subunit, dword):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        dword = ctypes.c_uint32(dword)

        err = self.handle.PIL_SetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_SAMPLE_LOAD"],
                                                ctypes.byref(dword))
        self._handleError(err)
        return

    def VDTGetInputFreqHiRes(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        freq = ctypes.c_uint32()

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_INPUT_FREQ_HI_RES"],
                                                ctypes.byref(freq))
        self._handleError(err)
        return int(freq.value)

    def VDTSetLOSThreshold(self, subunit, threshold):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        threshold = ctypes.c_uint32(threshold)

        err = self.handle.PIL_SetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_LOS_THRESHOLD"],
                                                ctypes.byref(threshold))
        self._handleError(err)
        return

    def VDTGetLOSThreshold(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        threshold = ctypes.c_uint32()

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_LOS_THRESHOLD"],
                                                ctypes.byref(threshold))
        self._handleError(err)
        return int(threshold.value)

    def VDTSetSampleBufferSize(self, subunit, size):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        size = ctypes.c_uint32(size)

        err = self.handle.PIL_SetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_SMPL_BUFFER_SIZE"],
                                                ctypes.byref(size))
        self._handleError(err)
        return

    def VDTGetSampleBufferSize(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        size = ctypes.c_uint32()

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_SMPL_BUFFER_SIZE"],
                                                ctypes.byref(size))
        self._handleError(err)
        return int(size.value)

    def VDTSetNullOffset(self, subunit, offset):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        offset = ctypes.c_uint16(offset)

        err = self.handle.PIL_SetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_NULL_OFFSET"],
                                                ctypes.byref(offset))
        return err

    def VDTGetNullOffset(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        offset = ctypes.c_uint16()

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_NULL_OFFSET"],
                                                ctypes.byref(offset))
        self._handleError(err)
        return int(offset.value)

    # LVDT Get only
    def VDTGetStatus(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        status = ctypes.c_uint8()

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_STATUS"],
                                                ctypes.byref(status))
        self._handleError(err)
        return int(status.value)

    def VDTGetMaxOutputVoltage(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        voltage = ctypes.c_double()

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_MAX_OUT_VOLTAGE"],
                                                ctypes.byref(voltage))
        self._handleError(err)
        return float(voltage.value)

    def VDTGetMinOutputVoltage(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        voltage = ctypes.c_double()

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_MIN_OUT_VOLTAGE"],
                                                ctypes.byref(voltage))
        self._handleError(err)
        return float(voltage.value)

    def VDTGetMaxInputVoltage(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        voltage = ctypes.c_double()

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_MAX_IN_VOLTAGE"],
                                                ctypes.byref(voltage))
        self._handleError(err)
        return float(voltage.value)

    def VDTGetMinInputVoltage(self, subunit):
        subunit = ctypes.c_uint32(subunit)
        is_output = ctypes.c_uint32(1)
        voltage = ctypes.c_double()

        err = self.handle.PIL_GetAttribute(
                                                self.card,
                                                subunit,
                                                is_output,
                                                self.ATTR["VDT_MIN_IN_VOLTAGE"],
                                                ctypes.byref(voltage))
        self._handleError(err)
        return float(voltage.value)

    #endregion

    #region DIO card functions

    def DIOSetPortDirection(self, subunit, portDirection):

        subunit = ctypes.c_uint32(subunit)
        portDirection = ctypes.c_uint32(portDirection)

        err = self.handle.PIL_DIOSetPortDirection(self.card, subunit, portDirection)
        self._handleError(err)

        return

    def DIOGetPortDirection(self, subunit):

        subunit = ctypes.c_uint32(subunit)
        portDirection = ctypes.c_uint32()

        err = self.handle.PIL_DIOGetPortDirection(self.card, subunit, ctypes.byref(portDirection))
        self._handleError(err)

        return portDirection.value

    def DIOSetChannelDirection(self, subunit, channel, channelDirection):

        subunit = ctypes.c_uint32(subunit)
        channel = ctypes.c_uint32(channel)
        channelDirection = ctypes.c_bool(channelDirection)

        err = self.handle.PIL_DIOSetChannelDirection(self.card, subunit, channel, channelDirection)
        self._handleError(err)

        return

    def DIOGetChannelDirection(self, subunit, channel):

        subunit = ctypes.c_uint32(subunit)
        channel = ctypes.c_uint32(channel)
        channelDirection = ctypes.c_bool()

        err = self.handle.PIL_DIOGetChannelDirection(self.card, subunit, channel, ctypes.byref(channelDirection))
        self._handleError(err)

        return channelDirection.value

    def DIOCheckPortDisabled(self, subunit):

        subunit = ctypes.c_uint32(subunit)
        portDisabled = ctypes.c_bool()

        err = self.handle.PIL_DIOCheckPortDisabled(self.card, subunit, ctypes.byref(portDisabled))
        self._handleError(err)

        return portDisabled.value

    def DIOPortReenable(self, subunit):

        subunit = ctypes.c_uint32(subunit)

        err = self.handle.PIL_DIOPortReenable(self.card, subunit)
        self._handleError(err)

        return

    #endregion

    #region Current Loop Simulator functions

    def CLSetMode(self, subunit, mode):
        mode = ctypes.c_uint32(mode)
        subunit = ctypes.c_uint32(subunit)

        err = self.handle.PIL_SetAttribute(
                                                self.card,
                                                subunit,
                                                1,
                                                0x401,
                                                ctypes.byref(mode))
        self._handleError(err)

        return

    def CLSetCurrent(self, subunit, current):
        current = ctypes.c_double(current)
        subunit = ctypes.c_uint32(subunit)

        err = self.handle.PIL_SetAttribute(self.card,
                                           subunit,
                                           1,
                                           0x440,
                                           ctypes.byref(current))
        self._handleError(err)

        return

    def CLSetVoltage(self, subunit, voltage):
        voltage = ctypes.c_double(voltage)
        subunit = ctypes.c_uint32(subunit)

        err = self.handle.PIL_SetAttribute(
                                                self.card,
                                                subunit,
                                                1,
                                                0x441,
                                                ctypes.byref(voltage))
        self._handleError(err)

        return

    def CLSetSlewRate(self, subunit, slewRate):
        slewRate = ctypes.c_uint8(slewRate)
        subunit = ctypes.c_uint32(subunit)

        err = self.handle.PIL_SetAttribute(
                                                self.card,
                                                subunit,
                                                1,
                                                0x442,
                                                ctypes.byref(slewRate))
        self._handleError(err)

        return

    #endregion

    #region Get/Set Attribute functions - playing with fire

    def GetAttributeDWORD(self, subunit, outputSubunit, attribute):

        subunit = ctypes.c_uint32(subunit)
        outputSubunit = ctypes.c_bool(outputSubunit)
        attribute = ctypes.c_uint32(attribute)

        value = ctypes.c_uint32()

        err = self.handle.PIL_GetAttribute(self.card,
                                           subunit,
                                           outputSubunit,
                                           attribute,
                                           ctypes.byref(value))
        self._handleError(err)

        return value.value

    def GetAttributeDouble(self, subunit, outputSubunit, attribute):
        subunit = ctypes.c_uint32(subunit)
        outputSubunit = ctypes.c_bool(outputSubunit)
        attribute = ctypes.c_uint32(attribute)

        value = ctypes.c_double()

        err = self.handle.PIL_GetAttribute(self.card,
                                           subunit,
                                           outputSubunit,
                                           attribute,
                                           ctypes.byref(value))
        self._handleError(err)

        return value.value

    def GetAttributeByte(self, subunit, outputSubunit, attribute):
        subunit = ctypes.c_uint32(subunit)
        outputSubunit = ctypes.c_bool(outputSubunit)
        attribute = ctypes.c_uint32(attribute)

        value = ctypes.c_byte()

        err = self.handle.PIL_GetAttribute(self.card,
                                           subunit,
                                           outputSubunit,
                                           attribute,
                                           ctypes.byref(value))
        self._handleError(err)

        return value.value

    def GetAttributeDWORDArray(self, subunit, outputSubunit, attribute, array_length):
        subunit = ctypes.c_uint32(subunit)
        outputSubunit = ctypes.c_bool(outputSubunit)
        attribute = ctypes.c_uint32(attribute)
        array_type = ctypes.c_uint32 * array_length
        c_array = array_type()
        c_array_p = ctypes.pointer(c_array)

        err = self.handle.PIL_GetAttribute(self.card, subunit, outputSubunit, attribute, c_array_p)
        self._handleError(err)
        
        return [c_array[i] for i in range(array_length)]

    def SetAttributeDWORD(self, subunit, outputSubunit, attribute, value):
        subunit = ctypes.c_uint32(subunit)
        outputSubunit = ctypes.c_bool(outputSubunit)
        attribute = ctypes.c_uint32(attribute)
        value = ctypes.c_uint32(value)

        err = self.handle.PIL_SetAttribute(self.card, subunit, outputSubunit, attribute, ctypes.byref(value))
        self._handleError(err)

        return value.value

    def SetAttributeDWORDArray(self, subunit, outputSubunit, attribute, values):
        subunit = ctypes.c_uint32(subunit)
        outputSubunit = ctypes.c_bool(outputSubunit)
        attribute = ctypes.c_uint32(attribute)
        array_type = ctypes.c_uint32 * len(values)
        c_array = array_type(*values)

        err = self.handle.PIL_SetAttribute(self.card, subunit, outputSubunit, attribute, ctypes.byref(c_array))
        self._handleError(err)

        return [c_array[i] for i in range(len(c_array))]

    def SetAttributeDouble(self, subunit, outputSubunit, attribute, value):
        subunit = ctypes.c_uint32(subunit)
        outputSubunit = ctypes.c_bool(outputSubunit)
        attribute = ctypes.c_uint32(attribute)
        value = ctypes.c_double(value)

        err = self.handle.PIL_SetAttribute(self.card, subunit, outputSubunit, attribute, ctypes.byref(value))
        self._handleError(err)

        return value.value

    def SetAttributeByte(self, subunit, outputSubunit, attribute, value):
        subunit = ctypes.c_uint32(subunit)
        outputSubunit = ctypes.c_bool(outputSubunit)
        attribute = ctypes.c_uint32(attribute)
        value = ctypes.c_byte(value)

        err = self.handle.PIL_SetAttribute(self.card, subunit, outputSubunit, attribute, ctypes.byref(value))
        self._handleError(err)

        return value.value

    #endregion
    #region Function generator functions

    def PILFG_SetAmplitude(self, SubNum, Amplitude):
        SubNum = ctypes.c_uint32(SubNum)
        Amplitude = ctypes.c_double(Amplitude)
        
        err = self.handle.PILFG_SetAmplitude(self.card, SubNum,Amplitude)
        
        self._handleError(err)
        
        return
    
    def PILFG_GetAmplitude(self, SubNum):
        SubNum = ctypes.c_uint32(SubNum)
        Amplitude = ctypes.c_double(Amplitude)
        
        err = self.handle.PILFG_GetAmplitude(self.card, SubNum, ctypes.byref(Amplitude))
        
        self._handleError(err)
        
        return Amplitude.value
    
    def PILFG_SetDcOffset(self, SubNum, DcOffset):
        SubNum = ctypes.c_uint32(SubNum)
        DcOffset = ctypes.c_double(DcOffset)
        
        err = self.handle.PILFG_SetDcOffset(self.card, SubNum, DcOffset)
        self._handleError(err)
        
        return
    
    def PILFG_GetDcOffset(self, SubNum):
        SubNum = ctypes.c_uint32(SubNum)
        DcOffset = ctypes.c_double(DcOffset)
        
        err = self.handle.PILFG_GetDcOffset(self.card, SubNum, ctypes.byref(DcOffset))
        self._handleError(err)
        
        return DcOffset.value
    
    def PILFG_SetFrequency(self, SubNum, Frequency):
        SubNum = ctypes.c_uint32(SubNum)
        Frequency = ctypes.c_double(Frequency)
        
        err = self.handle.PILFG_SetFrequency(self.card, SubNum, Frequency)
        self._handleError(err)
        
        return
    
    def PILFG_GetFrequency(self, SubNum):
        SubNum = ctypes.c_uint32(SubNum)
        Frequency = ctypes.c_double(Frequency)
        
        err = self.handle.PILFG_GetFrequency(self.card, SubNum, ctypes.byref(Frequency))
        self._handleError(err)
        
        return Frequency.value
    
    def PILFG_SetStartPhase(self, SubNum, StartPhase):
        SubNum = ctypes.c_uint32(SubNum)
        StartPhase = ctypes.c_double(StartPhase)
        
        err = self.handle.PILFG_SetStartPhase(self.card, SubNum, StartPhase)
        self._handleError(err)
        
        return
    
    def PILFG_GetStartPhase(self, SubNum):
        SubNum = ctypes.c_uint32(SubNum)
        StartPhase = ctypes.c_double(StartPhase)
        
        err = self.handle.PILFG_GetStartPhase(self.card, SubNum, ctypes.byref(StartPhase))
        self._handleError(err)
        
        return StartPhase.value
    
    
    def PILFG_SetDutyCycleHigh(self, SubNum, DutyCycleHigh):
        SubNum = ctypes.c_uint32(SubNum)
        DutyCycleHigh = ctypes.c_uint32(DutyCycleHigh)
        
        err = self.handle.PILFG_SetDutyCycleHigh(self.card, SubNum, DutyCycleHigh)
        self._handleError(err)
        
        return
    
    def PILFG_GetDutyCycleHigh(self, SubNum):
        SubNum = ctypes.c_uint32(SubNum)
        DutyCycleHigh = ctypes.c_uint32(DutyCycleHigh)
        
        err = self.handle.PILFG_GetDutyCycleHigh(self.card, SubNum, ctypes.byref(DutyCycleHigh))
        self._handleError(err)
        
        return
    
    def PILFG_SetWaveform(self, SubNum, Waveform):
        SubNum = ctypes.c_uint32(SubNum)
        Waveform = ctypes.c_uint32(Waveform)
        
        err = self.handle.PILFG_SetWaveform(self.card, SubNum, Waveform)
        self._handleError(err)
        
        return
    
    def PILFG_GetWaveform(self, SubNum):
        SubNum = ctypes.c_uint32(SubNum)
        Waveform = ctypes.c_uint32(Waveform)
        
        err = self.handle.PILFG_GetWaveform(self.card, SubNum, ctypes.byref(Waveform))
        self._handleError(err)
        
        return Waveform.value
    
    def PILFG_SetPulseWidth(self, SubNum, PulseWidth):
        SubNum = ctypes.c_uint32(SubNum)
        PulseWidth = ctypes.c_double(PulseWidth)
        
        err = self.handle.PILFG_SetPulseWidth(self.card, SubNum, PulseWidth)
        self._handleError(err)
        
        return
    
    def PILFG_GetPulseWidth(self, SubNum):
        SubNum = ctypes.c_uint32(SubNum)
        PulseWidth = ctypes.c_double(PulseWidth)
        
        err = self.handle.PILFG_GetPulseWidth(self.card, SubNum, ctypes.byref(PulseWidth))
        self._handleError(err)
        
        return PulseWidth.value
    
    def PILFG_ConfigureWaveform(self, SubNum, Waveform, Amplitude, DcOffset, Frequency, StartPhase, DutyCycleHigh, PulseWidth):
        SubNum = ctypes.c_uint32(SubNum)
        Waveform = ctypes.c_uint32(Waveform)
        Amplitude = ctypes.c_uint32(Amplitude)
        DcOffset = ctypes.c_uint32(DcOffset)
        Frequency = ctypes.c_uint32(Frequency)
        StartPhase = ctypes.c_uint32(StartPhase)
        DutyCycleHigh = ctypes.c_uint32(DutyCycleHigh)
        PulseWidth = ctypes.c_uint32(PulseWidth)
        
        err = self.handle.PILFG_ConfigureWaveform(self.card, SubNum, Waveform, Amplitude, DcOffset, Frequency, StartPhase, DutyCycleHigh, PulseWidth)
        self._handleError(err)
        
        return
    
    def PILFG_InitiateGeneration(self, SubNum):
        SubNum = ctypes.c_uint32(SubNum)
        
        err = self.handle.PILFG_InitiateGeneration(self.card, SubNum)
        self._handleError(err)
        
        return

    def PILFG_AbortGeneration(self, SubNum):
        SubNum = ctypes.c_uint32(SubNum)
        err = self.handle.PILFG_AbortGeneration(self.card, SubNum)

        self._handleError(err)
        return
    
    def PILFG_StartStopGeneration(self, State):
        array_type = ctypes.c_uint32 * len(State)
        c_array = array_type(*State)
        
        err = self.handle.PILFG_StartStopGeneration(self.card, ctypes.byref(c_array), len(State))
        self._handleError(err)
        
        return
    
    def PILFG_GetGenerationState(self, SubNum, Size):
        SubNum = ctypes.c_uint32(SubNum)
        array_type = ctypes.c_uint32 * Size
        c_array = array_type()
        c_array_p = ctypes.pointer(c_array)
        
        err = self.handle.PILFG_GetGenerationState(self.card, SubNum, c_array_p, Size)
        self._handleError(err)
        
        return [c_array[i] for i in range(Size)]

    def PILFG_CreateArbitraryWaveform(self, SubNum, SampleSource):
        SubNum = ctypes.c_uint32(SubNum)
        SampleSource = ctypes.c_char_p(SampleSource)
        
        err = self.handle.PILFG_CreateArbitraryWaveform(self.card, SubNum, SampleSource)
        self._handleError(err)
        
        return
    
    def PILFG_SetInputTriggerConfig(self, Trigger):
        Trigger = ctypes.c_uint32(Trigger)
        
        err = self.handle.PILFG_SetInputTriggerConfig(self.card, Trigger)
        self._handleError(err)
        
        return
    
    def PILFG_GetInputTriggerConfig(self):
        Source = ctypes.c_uint32()
        Trigger = ctypes.c_uint32()
        
        err = self.handle.PILFG_GetInputTriggerConfig(self.card, ctypes.byref(Source), ctypes.byref(Trigger))
        self._handleError(err)
        
        return Source.value, Trigger.value
    
    def PILFG_SetOutputTriggerConfig(self, Trigger):
        Trigger = ctypes.c_uint32(Trigger)
        err = self.handle.PILFG_SetOutputTriggerConfig(self.card, Trigger)
        self._handleError(err)
        
        return
    
    def PILFG_GetOutputTriggerConfig(self):
        Trigger = ctypes.c_uint32()
        
        err = self.handle.PILFG_GetOutputTriggerConfig(self.card, ctypes.byref(Trigger))
        self._handleError(err)
        
        return Trigger.value

        
    def PILFG_SetInputTriggerEnable(self, SubNum, Trigger):
        SubNum = ctypes.c_uint32(SubNum)
        array_type = ctypes.c_uint32 * len(Trigger)
        c_array = array_type(*Trigger)
        
        err = self.handle.PILFG_SetInputTriggerEnable(self.card, SubNum, ctypes.byref(c_array), len(Trigger))
        self._handleError(err)
        
        return
    
    def PILFG_GetInputTriggerEnable(self, SubNum, Size):
        SubNum = ctypes.c_uint32(SubNum)
        Trigger = (ctypes.c_uint32 * Size)()
        
        err = self.handle.PILFG_GetInputTriggerEnable(self.card, SubNum, ctypes.byref(Trigger), Size)
        self._handleError(err)
        
        return list(Trigger)

    
    def PILFG_SetOutputTriggerEnable(self, SubNum, Trigger):
        SubNum = ctypes.c_uint32(SubNum)
        array_type = ctypes.c_uint32 * len(Trigger)
        c_array = array_type(*Trigger)
        
        err = self.handle.PILFG_SetOutputTriggerEnable(self.card, SubNum, ctypes.byref(c_array), len(Trigger))
        self._handleError(err)
        
        return
    
    def PILFG_GetOutputTriggerEnable(self, SubNum, Size):
        SubNum = ctypes.c_uint32(SubNum)
        Trigger = (ctypes.c_uint32 * Size)()
        
        err = self.handle.PILFG_GetOutputTriggerEnable(self.card, SubNum, ctypes.byref(Trigger), Size)
        self._handleError(err)
        
        return list(Trigger)

    def PILFG_GenerateOutputTrigger(self, State):
        State = ctypes.c_uint32(State)
        
        err = self.handle.PILFG_GenerateOutputTrigger(self.card, State)
        self._handleError(err)
        
        return
    
    def PILFG_GetTriggerMonitorState(self, SubNum, Size):
        SubNum = ctypes.c_uint32(SubNum)
        State = (ctypes.c_uint32 * Size)()
        
        err = self.handle.PILFG_GetTriggerMonitorState(self.card, SubNum, ctypes.byref(State), Size)
        self._handleError(err)
        
        return list(State)
        
    #endregion
