# Python wrapper Library for Pickering LXI ClientBridge driver #

Python wrapper Library for Pickering LXI ClientBridge driver. It supports both Python 2.x and 3.x.
For PIFGLX functionality a C++ ClientBridge >= 1.80.0 is needed.

----------
# Installation Instructions #

We provide both a python module that can be installed to the system using `pip` and can be added manually to a project by copying a file into the directory that you are working in. For either installation method please make sure that you have installed ClientBridge. If you intend to use ClientBridge with PXI please make sure you also install Pickering PXI Installer Package. These can be found at the following addresses:

 - [PXI Installer Package](https://pickeringtest.info/downloads/drivers/PXI_Drivers/)
 - [ClientBridge Driver](https://pickeringtest.info/downloads/drivers/Sys60/)

**Please note that there is an additional dependency 'enum34' for Python 2.x and Python 3.x versions < 3.4. This package must be installed manually prior to using the wrapper with older versions of Python.**

----------
# ChangeLog #

> - 5.7 \
>       - Renamed Version to GetVersion.
>       - Added Version function to get Pilpxi version.
>       - Fixed Pi_Base.Discover(). \
>       - Fixed several examples.  \
>       - Fixed ResGetResistance() and SetAttenuation().
>       - Updated Readme. \
>       - Removed Enum34 install dependency.
> - 5.6 - Fixed typo in SetAttributeDWORD.
> - 5.5 - Added 4x-670 Pole Pair Attributes. Added missing attributes. Renamed ATTR_C_GA_SLOT_ADDRESS to C_GA_SLOT_ADDRESS.
> - 5.4 - Support for ClientBridge versions prior to 1.80.0
> - 5.3 - Added PIFGLX wrapper.
        - Added StatusCodeToMessage function.
> - 5.2 - Addded ATTR_C_GA_SLOT_ADDRESS attribute, updated readme.
> - 5.1 - Updated description and readme.
> - 5.0 - Adds SetAttributeDWORD, SetAttributeDWORDArray, SetAttributeDouble, SetAttributeByte and its getters. Adds DioAllPortData function.
> - 4.9 - Adds ResSetResistance() mode enum and optional parameter to pilxi (brings pilxi version to 2.0.3)
> - 4.8 - Adds calibration functions to pilxi (brings pilxi version to 2.0.2)
> - 4.7 - Adds example code for Precision Resistor cards 
> - 4.6 - Fixes issues in pi743lx findInstrumentsRsrc(), wrapper changes to prevent namespace pollution by ctypes.
> - 4.5: 
>   - Introduces individual version numbering for all packages
>   - Updated LXI_PXM78xx module -> support Trigger Matrix, Timer/Counter groups
>   - Updates battery simulator functionality, including set-measure-set mode and measurement configuration.
>   - Updates example code, including battery simulator example and adds Example_ListCards.py 
> - 4.4 - Imported LXI_PXM78xx module support (VX Instrument's PXM78xx DMM modules)
> - 4.3 - Updates LVDT/resolver functionality and adds Battery Simulator measurement methods 
> - 4.2 - Adds example for multiuser access
> - 4.1 - Fixes issue with ReadSub and ViewSub 
> - 4.0 - Changes to API to add more object-oriented features, exceptions, adds 41-620 and 41-743 support, current loop simulator, 40-419 DIO card, etc.
> - 3.18 - Updates to use native strings in Python 2.x/3.x, adds `pi_base.ErrorCodeToMessage()` and `pi_comm.ErrorCodeToMessage()`
> - 3.17 - Adds pi_card.SetCrosspointRange
         - Adds Thermocouple Simulator Functions
> - 3.16 - Fixes pi_card.WriteSub
> - 3.15 - Adds new constructor and method for opening cards using aliases
> - 3.14 - Changes to return interger value from calc_dwords(). 
> - 3.13 - Fixes pi_base.EchoDirectEx and pi_base.EchoDirectEx pi_base.GetAvailableLXIEntryEx functions (increased description buffer size) 
> - 3.12 - Adds version definition for all wrapper modules (plus function call definition to obtain information)
> - 3.11 - Adds Power Sequencer Python 2 support
> - 3.10 - Adds Power Sequencer support
> - 3.9 - Fixes pi_cards.CloseCards, pi_cards.Close (closes connection properly once card is closed)
> - 3.8 - Adds Linux Support
> - 3.7 - Adds Thermocouple Functions and updates calling conventions to match change in ClientBridge
> - 3.6 - Updates Calling Convetions to match recent change in ClientBridge
> - 3.5 - Fixes Resistor ClientBridge Calls
> - 3.4 - Refactor for use with pip installer
        - Fixes Resistor functions

----------
## Install Using `pip` ##

To install Python Pilxi from our download site using pip - open a command line prompt and navigate to the directory the library has been extracted to. From there enter the following command:
```
pip install .
```

----------
## Install Manually ##

To install Python Pilxi manually please copy pilxi directory containing `__init__.py` to your project. 

----------
# Using Pilxi #

Pilxi can be used to control our 40/50/60 series pickering products.

## Open a session with LXI ## 

In order to query an LXI unit and open/operate cards, you must first open a session. This can be done by passing an IP address to the `pilxi.Pi_Session` constructor. To use local PXI cards, pass "PXI" in place of the IP address.
```python 
import pilxi

IP_Address = "192.168.1.1"

try:
    session = pilxi.Pi_Session(IP_Address)

except pilxi.Error as ex:
    print("Error occurred opening LXI session:", ex.message)
```

## List cards ##

To get a list of the available cards IDs use `GetUsableCards()`. This will return a list of card IDs. To list the bus and slot number for all of the cards use `FindFreeCards()`, which takes in the total card count. Please see below for worked examples on how to use both of these functions:

```python
import pilxi

# Connect to chassis
IP_Address = '192.168.1.1'

# Port, timeout parameters are optional, defaults will be used otherwise.
session = pilxi.Pi_Session(IP_Address)
# or 
session = pilxi.Pi_Session(IP_Address, port=1024, timeout=5000)

# Get list of Card IDs for cards in chassis
cardID_array = session.GetUsableCards(0)
print("Card IDs:", cardID_array)


# Get list of Card Bus and Device Numbers
card_array = session.FindFreeCards()

for card in card_array:
    bus, device = card
    print("Card at bus {} device {}".format(bus, device))
```

## Open Card ##

There are three ways to open a card:
 - Using the Bus and Device number
 - Using the Card ID and Access mode
 - Using an alias specified using Resource Manager

To open a card at a specific bus and device location, use `Pi_Session.OpenCard(bus, device)`. When opening a card with Bus and Slot number only one program can access the card at a time, which means that you cannot have another program monitor the card. To do that the card needs to be opened with the Card ID and specifying the Access mode to allow multiple programs at once. The Card ID can be obtained from the list of cards show in the earlier example. Please see below for a worked example on how to use `pi_card` in either way:

```python
# Open a card by bus and device:
import pilxi

card = session.OpenCard(bus, device)

# accessType parameter is optional, default value is 1 (shared access)
# see pilxi.AccessTypes enum for options
card = session.OpenCardByID(cardID, accessType=pilxi.AccessTypes.MULTIUSER)

# Cards can be closed explicitly, garbage collection will close cards and sessions otherwise
card.Close()
```

Aliases must be specified in the Resource Manager application. From there you can save a copy of the resource file locally which can be copied into your project directory for easy access. You can then open a card by alias using the `pilxi.Pi_Card_ByAlias` class:

```python
rsrcfile = "LocalResources.rml"
alias = "my_alias"

# Resource file, access type and timeout parameters are optional. 
card = pilxi.Pi_Card_ByAlias(alias, rsrcfile, accessType=1, timeout=5000)

card.Close()
```

## Operate Switching cards ##

There are three main types of switching cards:
    - Switches
    - Multiplexer
    - Matrix

To operate Switches and Multiplexers use `OpBit()` providing subunit, switch point, and switch state. Matrices can be controller using `OpCrosspoint()` which requires the subunit, row, column, and switch state. Please see below for worked examples on using these functions:

```python
# Control Switches and Multiplexer cards
subunit = 1
switchpoint = 1

state = True
card.OpBit(subunit, switchpoint, state)
    
state = False
card.OpBit(subunit, switchpoint, state)


# Control Matrix cards
row = 1
column = 1
card.OpCrosspoint(subunit, row, column, True)

card.OpCrosspoint(subunit, row, column, False)


# Set a range of crosspoints on a given row 
start = 1
end = 8
card.SetCrosspointRange(subunit, row, start, end, 1)
```

### Using Subunit States ### 

The Python-Pilxi wrapper contains methods to read entire subunit states, e.g. the current switch configuration of a switching or matrix card, manipulate these states and apply the state back to the card in one single operation. This means, for example, multiple crosspoints can be connected at once, or the user may have multiple desired matrix/switch states and alternate between them. 

Example for manipulating matrix card states:
```python
# Get an object representing the current state of the specified matrix subunit:
subState = card.GetSubState(subunit)

# Set matrix crosspoints 1, 1 and 2, 2 on the subunit state;
# No actual switching occurs yet.
subState.PreSetCrosspoint(1, 1, True)
subState.PreSetCrosspoint(2, 2, True)

# Apply the subunit state.
# Crosspoints changed will now be applied to the physical card. 
card.WriteSubState(subunit, subState)
```
Example for manipulating switching card states:
```python
# Get an object representing the current state of the specified switch subunit:
subState = card.GetSubState(subunit)

# Set switches 1 and 2 on the subunit state;
# No actual switching occurs yet.
subState.PreSetBit(1, True)
subState.PreSetBit(2, True)

# Apply the subunit state.
# Switches changed will now be applied to the physical card. 
card.WriteSubState(subunit, subState)
```
It is also possible to obtain a subunit state object representing a clear subunit:
```python
blankSubunitState = card.GetBlankSubState(subunit)
```

## Operate Resistor Cards ##

Resistor cards come in two varieties: Programmable Resitor, and Presision Resistor. Programmable Resistors are controlled like Switch Cards shown above. Presision Resistor Cards have specific resistor functions. To set a resistance `ResSetResistance` is used and to get the current resistance `ResGetResistance` is used as shown below:

```python
# Set Resistance of given subunit, resistance value in Ohms
mode = 0
resistance = 330.0

card.ResSetResistance(subunit, resistance)

# Retrive current resistance of given subunit
resistance = card.ResGetResistance(subunit)

print("Resistance:", resistance)

# Set Resistance with specific mode:
#    RES_Mode.SET                     # Legacy/Default mode to support existing break before make with settling delay
#    RES_Mode.MBB                     # New mode to suport make before break with settling delay
#    RES_Mode.APPLY_PATTERN_IMMEDIATE # Apply new pattern immediately and wait till settling delay
#    RES_Mode.NO_SETTLING_DELAY       # Disable settling delay,same as DriverMode NO_WAIT, but at sub-unit level
#    RES_Mode.DONT_SET                # Do the calculations but don't set the card

# Set with make-before-break mode 
resistance = card.ResSetResistance(subunit, resistance, mode=pilxi.RES_Mode.MBB)


```

## Operate Attenuator ##

Attenuators have specific functions for controlling them. To set attenuation use `SetAttenuation()` providing the subunit and attenuation expressed in decibels. To retrieve the current attenuation use `GetAttenuation()` giving the subunit. It returns an error code and the attenuation expressed in decibels. Please see below for worked examples on how to use these functions:

```python
# Setting Attenuation
attenuation = 1.5     # Attenuation in dB
card.SetAttenuation(subunit, attenuation)

# Retrieving Attenuation
attenuation = card.GetAttenuation(subunit)

print("Attenuation (dB):", attenuation)
```

## Operate Power Supply ##

Power Supplies have specific functions for controlling them. To set voltage use `PsuSetVoltage()` providing the subunit and voltage. To retrieve voltage use `PsuGetVoltage()` giving the subunit. To enable output use `PsuEnable` providing the subunit and the state to be set. Please see below for worked examples on how to use these functions:

```python
# Set Voltage
volts = 3.3
card.PsuSetVoltage(subunit, volts)

# Enable output
card.PsuEnable(subunit, 1)

# Get Voltage
volts = card.PsuGetVoltage(subunit)

# Disable output
card.PsuEnable(subunit, 0)
```

## Operate Battery Simulator ##

Battery Simulators have specific methods for controlling them. To set voltage use `BattSetVoltage()` providing the subunit and voltage. To retrieve the voltage set use `BattGetVoltage()` giving the subunit. To set current use `BattSetcurrent()` providing the subunit and current. To retrieve the set current use `BattGetcurrent()` giving the subunit. To enable output use `BattSetEnable()` providing the subunit and the state to be set. To retrieve the present output state use `BattGetEnable()`. On supported Battery Simulator cards, real channel voltage and current can be measured back using `BattMeasureVoltage()` and `BattMeasureCurrentmA()` methods. Please see below for worked examples on how to use these functions:

```python
volts = 3.3
current = 0.5

# Set Voltage
card.BattSetVoltage(subunit, volts)

# Set Current
card.BattSetCurrent(subunit, current)

# Enable Output
card.BattSetEnable(subunit, True)

# Get Voltage
volts = card.BattGetVoltage(subunit)

# Set Current
current = card.BattGetCurrent(subunit)

# Get Output state
state = card.BattGetEnable(subunit)
```

If you attempt to enable the outputs of a battery simulator card without the hardware interlock, `BattSetEnable()` will throw an exception (error code 70, hardware interlock error). Therefore it is important to call functions in a `try` block and handle errors appropriately.

### 41-752A-01x functionality 

The 41-752A-01x battery simulator cards have extra capabilities beyond what is supported by other cards. Please consult your manual for information on your product's capabilities. Worked examples on using the extra functionality are below:

```python
# The following functionality is not supported by all battery simulator
# cards. Please consult your product manual for information on your card's 
# functionality. 

# Enable set-measure-set mode (increases measurement accuracy on supported cards)
card.BattSetMeasureSet(subunit, True)

# Configure measurement mode to alter device accuracy/sampling: 
numSamples                  = pilxi.BattNumSamples.SAMPLES_128     # Average values after 128 samples
VConversionTimePerSample    = pilxi.BattConversionTime.T_1052us    # 1052 us voltage sample time
IConversionTimePerSample    = pilxi.BattConversionTime.T_540us     # 540 us current sample time
triggerMode                 = pilxi.BattOperationMode.CONTINUOUS   # Measure continuously (no wait for trigger)

card.BattSetMeasureConfig(subunit, numSamples, VConversionTimePerSample, IConversionTimePerSample, triggerMode)

# The battery simulator (41-752A-01x) has the capability to take into consideration the load
# at which the voltage must be provided. Calculated data for voltage at different loads are
# used to provide this functionality.
load = 100  # units: mA
card.BattSetLoad(subunit, load)

# Measure channel voltage
voltage = card.BattMeasureVoltage(subunit)

# Measure channel current (in milliamps)
currentmA = card.BattMeasureCurrentmA(subunit)

# Measure channel current (in amps)
current = card.BattMeasureCurrentA(subunit)


```

## Operate Thermocouple Simulator ##

Thermocouple Simulators have specific functions for controlling them. To set the range use `VsourceSetRange()` providing the subunit and the range. To retrieve the range use `VsourceGetRange()` providing the subunit. To set the voltage use `VsourceSetVoltage()` providing the subunit and the voltage in millivolts. To retrieve the voltage use `VsourceGetVoltage()` providing the subunit. It returns the voltage in millivolts. To enable or disable outputs use `OpBit()` providing the subunit, bit number for the channel isolations, and the state that should be set. To retrieve the state of the outputs use `ViewBit()` providing the subunit and bit number for the channel isolations. Please refer to the product manual for more information on what subunit and bits to operate. To retrieve temperature readings from a connected thermocouple compensation block us `VsourceGetTemperatures()` providing either `card.ATTR["TS_TEMPERATURES_C"]` or `card.ATTR["TS_TEMPERATURES_F"]` for temperature unit. It will return a list of four temperatures. Please see below for worked examples on how to use these functions:

```python
range = 0.0
mvolts = 0.0
range = card.TS_RANGE["AUTO"]

# Set Range
card.VsourceSetRange(subunit, range)

# Get Range
range = card.VsourceGetRange(subunit)

# Set Voltage
card.VsourceSetVoltage(subunit, mvolts)

# Get Voltage
mvolts = card.VsourceGetVoltage(subunit)

# Set Isolation switches (41-760-001)
isosub = 33
card.OpBit(isosub, 1, 1) # Turn Vo1 on
card.OpBit(isosub, 2, 1) # Turn Vcold1 on

card.OpBit(isosub, 1, 0) # Turn Vo1 off
card.OpBit(isosub, 2, 0) # Turn Vcold1 off

# Get Thermocouple subunit information
# This will return a dictionary containing keys corresponding
# to attributes of the thermocouple subunit and their values. 
VsourceInfoDict = card.VsourceInfo(subunit)

for key, value in VsourceInfoDict.items():
    print("Attribute: {}, Value: {}".format(key, value))

# Get Compensation Block Temperatures
temperatures = card.VsourceGetTemperature(card.ATTR["TS_TEMPERATURE_C"])

for temp in temperatures:
    print(temp)

```

## Error Codes ##

Most of the functions in python-pilxi will raise an exception on any errors. The exception is defined in the python module you are using e.g. pilxi, pi620lx, pipslx. 

```python
try:
    # Call pilxi methods here
    # On error, an exception will be raised 

except pilxi.Error as ex:
    # The exception object contains a string description of the error:
    errorMessage = ex.message
    # It is also possible to retrive the error code returned from the driver:
    errorCode = ex.errorCode
```
## Close Card/Session ##

A card and session can be closed when it is no longer used, or the object's destructor can be called:

```python
# Closes individual card.
card.Close()     

# Closes the session with the LXI.
session.Close()   

# Calling the object's destructor or deleting all references will also call
# the driver's Close() method:

del card
del session
```

# Using Pipslx

Pipslx python module can be used to control Pickering `Power Sequencer`, for
example [600-200-001](https://www.pickeringtest.com/en-US/product/lxi-remote-ac-power-management-switch). (Remote AC power management switch)

Here is a code snippet, how to
connect to `Power Sequencer`, begin the startup and shutdown sequences, as well as
getting and setting individual channel states:

```python
# Required imports
import pilxi
import pipslx

# IP address of the LXI Power Management Switch
IP_Address = "192.168.0.244"

# Open a session with the LXI unit and get the session ID
session = pilxi.Pi_Session(IP_Address)
sessionID = session.GetSessionID()

# Open the pipslx library using the LXI session
powerSequencer = pipslx.Pipslx(sessionID)

# Start sequence
powerSequencer.sequence(pipslx.SEQUENCE_START)

# Get the state of a specified channel
channel = 2
state = powerSequencer.get_chan_state(channel)

# Set the state of a specified channel
state = 1
powerSequencer.set_chan_state(channel, state)

emergency = False

if emergency:
    # In an emergency, call shutdown method to immediately disconnect
    # all channels. No sequence times applied.
    powerSequencer.shutdown()
else:
    # Otherwise, begin the regular shutdown sequence
    powerSequencer.sequence(pipslx.SEQUENCE_STOP)

# Close pipslx
powerSequencer.close()

# Close LXI session
session.Close()

```

# Using Pi620lx

The Pi620lx python module can be used to control Pickering 41-620 Function Generator cards installed in an LXI
chassis. The 41-620 3-channel function generator card can be used to generate arbitrarily defined waveforms, as well as standard
waveforms such as sine, square and triangle with variable attenuation and DC offsets. 

Here is some example code for controlling the 41-620 card using Pi620lx:
```python
import pilxi
import pi620lx 

IP_Address = "192.168.1.1"

# Open an LXI session and get the session ID which must be passed to 
# the pi620lx module
session = pilxi.Pi_Session(IP_Address)
sessionID = session.GetSessionID()

# Open the pi620lx library 
pi620base = pi620lx.Base(sessionID)

# Open a card. With no arguments passed, the openCard() method will open the
# first 41-620 card found in the LXI unit. 
bus = 4
device = 14

card = pi620base.openCard(bus, device)

# Set active channel to use
channel = 1
card.setActiveChannel(channel)

# Switch off channel output before configuring it
card.outputOff()

# Set trigger mode to continuous (no trigger)
card.setTriggerMode(card.triggerSources["FRONT"], card.triggerModes["CONT"])

# Set DC offset to generated waveform (float value from -5 to 5 volts)
# The first argument specifies the desired offset voltage;
# the second enables or disables DC offset.
offsetVoltage = 4.0
enableDCOffset = True
card.setOutputOffsetVoltage(offsetVoltage, enableDCOffset)

# Set attenuation to signal amplitude (float value in dB)
attenuation = 3
card.setAttenuation(attenuation)

# Generate a signal
# Signal shape can be defined using constants available with the Pi620_Card class:
shape = card.signalShapes["SINE"]
# shape = card.signalShapes["SQUARE"]
# shape = card.signalShapes["TRIANGLE"]

# Frequency of signal in kHz:
frequency = 1
# Symmetry of signal (0 - 100):
symmetry = 20

try:
    # Start generating a signal. By default, this method will start generating immediately without
    # first calling card.outputOn().
    # card.generateSignal(frequency, shape, symmetry)

    # The card.generateSignal() method can also be used with optional parameters to specify
    # a start phase offset and to enable/disable immediate signal generation.
    # For example, the following call will set the same signal as above, but with a
    # 90 degree phase offset and will disable signal output until card.outputOn() is called:
    card.generateSignal(frequency, shape, symmetry, startPhaseOffset=90, generate=False)

    # Set output on
    card.outputOn()

except pi620lx.Error as error:
    print("Error generating signal:", error.message)

# Close card. Note this will not stop the card generating a signal.
card.close()
```

## Operate 41-625 ##

## 41-670 ##

To operate PXI/PXIe LVDT/RVDT/Resolver Simulator Module, an approach using attributes is needed. Below is the list of Attributes relevant to 41-670.

### General Attributes (applicable in all 41-670 modes) ###
```python
    # Get / Set
    VDT_AUTO_INPUT_ATTEN                   = 0x450, # Sets/Gets DWORD (0-100) for input gain (Default = 100)
    VDT_VOLTAGE_SUM                        = 0x455, # Sets/Gets DOUBLE in Volts  for VSUM value  
    VDT_VOLTAGE_DIFF                       = 0x456, # Sets/Gets DOUBLE in Volts  for VDIFF value (the limit is +/- VSUM)  
    VDT_MANUAL_INPUT_ATTEN                 = 0x458, # Sets/Gets DWORD (0-255) Pot Value on LVDT  
    VDT_MODE                               = 0x459, # Sets/Gets DWORD to set mode 1 = LVDT_5_6_WIRE, mode 2=  LVDT_4_WIRE.
    VDT_DELAY_A                            = 0x45A, # Sets/Gets DWORD (0-6499) delay for OutputA   
    VDT_DELAY_B                            = 0x45B, # Sets/Gets DWORD (0-6499) delay for OutputB   
    VDT_INPUT_LEVEL                        = 0x45C, # Sets/Gets DWORD (0-65520) for Input Value  
    VDT_INPUT_FREQ                         = 0x45D, # Sets/Gets DWORD (300-20000 Hz) for Input Frequency   
    VDT_OUT_LEVEL                          = 0x45E, # Sets/Gets DWORD (0-4096)  output level
    VDT_INVERT_A        				   = 0x460,	# Sets/Gets DWORD (0 or 1)  for OutA 
    VDT_INVERT_B                           = 0x461, # Sets/Gets DWORD (0 or 1)  for OutB  
    VDT_SAMPLE_LOAD						   = 0x463,	# Sets DWORD comprises of Top 16 bits is GAIN (0-100) and lower 16 frequency (300-20000 Hz)
    VDT_INPUT_FREQ_HI_RES                  = 0x464,	# Gets DOUBLE value of frequency in Hz 
    VDT_LOS_THRESHOLD                      = 0x465,	# Sets/Gets DWORD (0 to 32768) for LOS Threshold (Default = 32768) 
    VDT_SMPL_BUFFER_SIZE                   = 0x466,	# Sets/Gets DWORD (1 to 500) for Sample buffer size (Default = 500) 
    VDT_NULL_OFFSET                        = 0x467,	# Sets/Gets WORD (0 to 100) for null offset (Default = 0)

    # Get Only
    VDT_STATUS                             = 0x468, # Gets BYTE value (0x00 or 0x01) checking LOS status 
    VDT_MAX_OUT_VOLTAGE                    = 0x469, # Gets DOUBLE value for maximum output voltage 
    VDT_MIN_OUT_VOLTAGE                    = 0x46A, # Gets DOUBLE value for minimum output voltage 
    VDT_MAX_IN_VOLTAGE                     = 0x46B, # Gets DOUBLE value for maximum input voltage 
    VDT_MIN_IN_VOLTAGE                     = 0x46C, # Gets DOUBLE value for minimum input voltage 
    VOLTAGE_V                              = 0x441, # Gets DOUBLE value of Voltage in V (LVDT/RVDT/Resolver)
    VDT_DSPIC_VERSION                      = 0x45F,	# Gets DWORD value of for dsPIC firmware version 104 = v0.01.04 
```

### LVDT Mode
```python
    VDT_ABS_POSITION                       = 0x451,	# Sets/Gets DWORD (0-32767) for Both Outputs on LVDT_5_6 WIRE & OutputA on LVDT_4_WIRE  
    VDT_ABS_POSITION_B                     = 0x452,	# Sets/Gets DWORD (0-32767)  for OutputB on LVDT_4_WIRE 
    VDT_PERCENT_POSITION                   = 0x453,	# Sets/Gets DOUBLE (-100.00% to 100.00%) for Both Out on LVDT_5_6 WIRE & OutA on LVDT_4_WIRE 
    VDT_PERCENT_POSITION_B                 = 0x454,	# Sets/Gets DOUBLE (-100.00% to 100.00%) for OutB on LVDT_4_WIRE 
```

### RVDT/Resolver Mode
```python
    RESOLVER_START_STOP_ROTATE				= 0x470, # Sets/Gets BOOL TRUE for Start, FALSE of Stop 
    RESOLVER_NUM_OF_TURNS					= 0x471, # Sets/Gets WORD Number of turns (1-65535)
    RESOLVER_ROTATE_SPEED					= 0x472, # Sets/Gets DOUBLE rotating speed (RPM speed upto 655.35 RPM)
    RESOLVER_POSITION						= 0x473, # Sets/Gets DOUBLE rotation between -180.00 to 180.00 Degrees 
    RESOLVER_POSITION_0_360				    = 0x474, # Sets/Gets DOUBLE rotation between 0.00 to 360.00 Degrees 
```


## Using Attributes ##
Most of card specific features are controlled via attributes. Attributes do apply to either specific subunit or whole card. Attributes which apply to your product are listed in it's user manual.

### Setting Attribute Values ###
The Pilxi python library offers a set of functions for setting the attributes. Each functions differs in variable type they are either setting or getting. The functions are
- `SetAttributeDWORD(subunit, outputSubunit, attribute, value)`
  - A **integer** variable is expected to be passed as a `value`.
- `SetAttributeDWORDArray(subunit, outputSubunit, attribute, values)`
  - A **python list** is expected to be passed as a `values`.
- `SetAttributeDouble(subunit, outputSubunit, attribute, value)`
  - A **double** is expected to be passed as a `value`.
- `SetAttributeByte(subunit, outputSubunit, attribute, value)`
  - A **python byte object** is expected to be passed as a `value`.
### Getting Attribute Values ###
The Pilxi python library offers a set of functions for getting the attributes. Each function differs in the variable type they return.
- `GetAttributeDWORD(subunit, outputSubunit, attribute)`
  - Returns an **integer** value.
- `GetAttributeDWORDArray(subunit, outputSubunit, attribute)`
  - Returns a **python list**.
- `GetAttributeDouble(subunit, outputSubunit, attribute)`
  - Returns a **double** value.
- `GetAttributeByte(subunit, outputSubunit, attribute)`
  - Returns a **python bytes object**.

### Attribute List ###
An attribute list can be accessed with
```python
pilxi.<ATTR_NAME>

# Example
card.SetAttributeDWORD(subunit, outputSubunit, pilxi.Attributes.VDT_OUTPUT_GAIN, 128)

out_gain = card.GetAttributeDWORD(subunit, outputSubunit, pilxi.Attributes.VDT_OUT_GAIN)
```
Attributes specific for your product are listed in the user manual of the product. \
**Important**: Attributes in python Pilxi library are without the `ATTR_` prefix.
```
ATTR_TS_SET_RANGE

is

pilxi.Attributes.TS_SET_RANGE
```

All attributes and their types are listed below.
```python
class Attributes(IntEnum):
    TYPE				= 0x400,	# Gets/Sets DWORD attribute value of Type of the Sub-unit (values: TYPE_MUXM, TYPE_MUXMS) 
    MODE				= 0x401,	# Gets/Sets DWORD attribute value of Mode of the Card 

        # Current monitoring attributes 
    CNFGREG_VAL			= 0x402,	# Gets/Sets WORD value of config register 
    SHVLREG_VAL			= 0x403,	# Gets WORD value of shuntvoltage register 
    CURRENT_A			= 0x404,	# Gets double current value in Amps
                                    # Was CURRENT_VAL earlier, renamed to specify that current value returned in Amps

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

    VAMP_OFFSET_VAL                       	= 0x4A0,    # Sets/Gets offset value for specific channel of voltage amplifier card (DWORD) 

    THERMO_SET_TEMPERATURE					= 0x4B0,	# Set DOUBLE for temperature value
    THERMO_TYPE							    = 0x4B1,	# Get/Set BYTE for thermocouple type
    THERMO_TEMPERATURE_SCALE				= 0x4B2,	# Get/Set BYTE for temperature scale
    THERMO_GET_VOLTAGE						= 0x4B3,	# Get DOUBLE for voltage value
    THERMO_CALC_VOLTAGE					    = 0x4B4,	# Set DOUBLE for temperature value
    THERMO_CALC_TEMP						= 0x4B5,	# Get DOUBLE for temperature value

    PRT_SET_TEMPERATURE					    = 0x4B6,	# Set DOUBLE for temperature value
    PRT_TYPE								= 0x4B7,	# Get/Set BYTE for RTD standard
    PRT_TEMPERATURE_SCALE					= 0x4B8,	# Get/Set BYTE for temperature scale
    PRT_RES_R0								= 0x4B9,	# Get/Set DOUBLE for R0 value
    PRT_GET_OHMS							= 0x4BA,	# Get DOUBLE for resistance value
    RTD_TEMPCO								= 0x4BB,	# Get/Set DOUBLE for temperature coefficient value
    PRT_CALC_RESISTANCE					    = 0x4BC,	# Set DOUBLE for temperature value
    PRT_CALC_TEMP							= 0x4BD,	# Get DOUBLE for temperature value
    PRT_COEFF_USR_A						    = 0x4BE,	# Get/Set DOUBLE for the temperature coefficient A
    PRT_COEFF_USR_B						    = 0x4BF,	# Get/Set DOUBLE for the temperature coefficient B
    PRT_COEFF_USR_C						    = 0x4C0,	# Get/Set DOUBLE for the temperature coefficient C

    RESOLVER_REV_START_STOP_ROTATE			= 0x4C1,	# Sets/Gets BOOL TRUE for Reverse_Start, FALSE of Reverse_Stop 

    HW_INT_MULTI_CONFIG					    = 0x4D0,	# Get the configuration status for MULTI type cards with I2C HW Interlock
    HW_INT_MULTI_CONFIG_CARD_POPULATION	    = 0x4D1,	# Get the card population status for MULTI type cards with I2C HW Interlock

    MULTI_Y								    = 0x4D2,	# For Internal Use, Sets DWORD value
    RESOLVER_POLE_PAIR						= 0x4D3,	# Set/Get DWORD as Number of Pole Pairs - outputRPM multiplier, default: 1, min: 1, max: 64
    RESOLVER_MAX_RPM						= 0x4D4,	# Get DOUBLE as Maximum allowed RPM for Resolver, max: 20,000 or 131,070 RPM depending on Resolver type
    RESOLVER_ROTATE_SPEED_OUTPUT			= 0x4D5,	# Get DOUBLE as RPM on Output of Resolver, outputRPM = RPM * PolePairs
                                                
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
    C_FLUSH_RC_DATA_SYNC_OPTION        = 0x1104,   # FLAG = 1 -> Generates db file for a card if on board memory is present (DWORD)
                                                        # FLAG = 2 -> Updates the db file as well as memory with current relay count values (DWORD)*/
    C_LEGACY_MODE						= 0x1105,	# Get the status of aliasMode flag for the selected cardNum(BOOL) */
    C_LEGACY_REAL_CARD_ID              = 0x1106,	# Get the Real Card ID for the selected card (CHAR*) */
    # Comparator Card (4X-450)
    CMP_POLARITY						= 0x1200,	# Set/Get DWORD as Polarity*/
    CMP_PHY_TRIG_MODE					= 0x1201,	# Set/Get DWORD as Physical Trigger Mode*/
    CMP_VIR_TRIG_MODE					= 0x1202,	# Set/Get DWORD as Virtual Trigger Mode*/
    CMP_VIR_OR_AND						= 0x1203,	# Set/Get DWORD as Logical operation of the Virtual Channel*/
    CMP_RANGE							= 0x1204,	# Set/Get DWORD as Operation Range*/
    CMP_THRESHOLD						= 0x1205,	# Set/Get Double as Voltage Threshold*/
    CMP_DEBOUNCE_TIME					= 0x1206,	# Set/Get Double as Debounce Time*/
    CMP_PHY_MASK						= 0x1207,	# Set/Get DWORD as Physical Mask of the Virtual Channel*/
    CMP_VIR_MASK						= 0x1208,	# Set/Get DWORD as Virtual Mask of the Virtual Channel*/

    CMP_CAPTURE_ENABLE					= 0x1209,	# Set DWORD as the Signal to Enable the Capture Engine*/
    CMP_CAPTURE_APPEND					= 0x120A,	# Set DWORD as the Signal to Enable Appending Events*/
    CMP_CAPTURE_INDEX					= 0x120B,	# Get DWORD as the index of the most recently recorded event*/
    CMP_READ_OFFSET					= 0x120C,	# Set/Get DWORD as the index in the DDR3 memory to read data from*/
    CMP_READ_DDR3						= 0x120D,	# Get 4 DWORDs as Event Data from DDR3 Memory*/
    CMP_PHY_STATE						= 0x120E,	# Get DWORD as Raw Physical State Data*/
    CMP_VIR_STATE						= 0x120F,	# Get DWORD as Raw Virtual State Data*/
    CMP_PHY_FPT_MASK					= 0x1210,	# Set/Get DWORD as mask of physical channels generating Front Panel Interrupts*/
    CMP_VIR_FPT_MASK					= 0x1211,	# Set/Get DWORD as mask of virtual channels generating Front Panel Interrupts*/
    CMP_FPT_RESET						= 0x1212,	# Set - Reset Front Panel Interrupt Pins - Data Type Irrelevant (Not Used)*/
    CMP_DDR3_RESET						= 0x1213,	# Set - Reset DDR3 Memory - Data Type Irrelevant (Not Used)*/
    CMP_TIME_STAMP						= 0x1214,	# Get 2 DWORDs as Time Stamp*/
    CMP_TIME_STAMP_REF					= 0x1215,	# Get 2 DWORDs as Time Stamp Reference*/

```
# Migrating from old versions of the pilxi Python wrapper 

From wrapper version 4.0 onwards, major changes were made to the Python pilxi wrapper API. Most notably, 
opening/listing cards and error handling conventions have changed. The new wrapper does not rely on returning 
an integer error code from every method, as is conventional in a C program. Instead. Python-style exceptions are 
raised, and the exception contains attributes giving the integer error code, and a human-readable description of
the error. 
### Old wrapper example:

```python
from pilxi import *

# Connect to chassis
ip_address = "192.168.1.1"
port = 1024
timeout = 1000

# Opening a session with LXI device. 
# Note that strings must be encoded with str.encode()
com = pi_comm(0, str.encode(ip_address), port, timeout)

mode = 0            # Last two parameters treated as Bus and Slot
bus = 19
slot = 1
card_obj = pi_card(0, str.encode(ip_address), port, timeout, mode, bus, slot)

column = 1
row = 1
subunit = 1
state = 1

err = card_obj.OpCrosspoint(subunit, row, column, state)

# C-style error checking
# Note that strings must be decoded from byte strings (Python 3.x only)
if err:
    error, err_str = card_obj.ErrorCodeToMessage(err)
    print(err_str.decode())

err = card_obj.OpCrosspoint(subunit, column, row, 0)
if err:
    error, err_str = card_obj.ErrorCodeToMessage(err)
    print(err_str.decode())

# Cards must be closed explicitly or they will not be released
card_obj.CloseSpecifiedCard()

# Session must be closed explicitly or they may be orphaned
com.Disconnect()
```

### New wrapper example:
```python
import pilxi

# Connect to chassis and open a card by bus and device IDs.
# Error checking is done using try/except blocks to catch
# exceptions.
try:
    # Port, timeout parameters are optional, defaults will be used otherwise.
    IP_Address = '192.168.1.5'
    session = pilxi.Pi_Session(IP_Address)

    bus = 19
    device = 1
    card = session.OpenCard(bus, device)
    
except pilxi.Error as ex:
    print("Error connecting to chassis/opening card: ", ex.message)
    print("Driver error code:", ex.errorCode)
    exit()

# Set and unset a matrix crosspoint, with error checking:
try:    
    row = 1
    column = 1
    subunit = 1
    
    card.OpCrosspoint(subunit, row, column, True)
    
    card.OpCrosspoint(subunit, row, column, False)
    
except pilxi.Error as ex:
    print("Error operating crosspoint: ", ex.message)
    print("Driver error code: ", ex.errorCode)
    
# Close session and card explicitly. This is entirely optional, cards and sessions
# will be closed by Python's garbage collection.

card.Close()
session.Close()
```

Function signatures remain largely identical between versions of the wrapper, except error codes are not returned. 
Therefore, previously a function returning a value would also return an error code:
```python
error, resistance = card.ResGetResistance(subunit)
```
Would now become:
```python
resistance = card.ResGetResistance(subunit)
```
Errors would be caught in a try/except block. 