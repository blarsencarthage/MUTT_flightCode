# Python Py620 # 
Python Py620 is a Python wrapper for the Pickering 41-620 PXI Function Generator card.
It supports both Python 2 and Python 3. 

# Changelog # 
> - 0.1 - Initial release

# Installation Instructions # 
We provide a python module that can be both installed to the system using pip and can be added manually 
to a project by copying the module into the directory that you are working in. Please make sure you have 
installed the Pi620 driver.

### Installation using `pip` ###
In order to install Py620 using `pip`, first `cd` to the Py620 directory and run the following command:
```
pip install . 
```


# Using Py620 # 

Py620 provides a simple, pure Python interface to control Pickering PXI 41-620
Function Generator cards. Most functions are the same as the C library functions
shown in the product manual. Card discovery, opening and error handling
are slightly different in Python.  


### Listing available 41-620 Cards ###
To get a list of available 41-620 cards use `Pi_Base.findCards()`. This will return a list of 
VISA resource strings that can be used to open cards. Example below:
```python
base = py620.Pi_Base()
try:
    devices = base.findCards()
except py620.Error as error:
    print("Exception Occurred:", error.message)
    
# Print a list of cards found
for resource in devices:
    print("Card at {}".format(resource))
```
### Opening 41-620 Cards ### 
41-620 function generator cards are typically opened using a VISA resource string, for example `PXI1::2::INSTR`, 
where 1 is the bus number and 2 is the device number. This would be done in the following way:
```python
base = py620.Pi_Base()
try:
    card = base.openCard(resource="PXI1::2::INSTR")
except py620.Error as error:
    print("Exception occurred:", error.message)
```
Notice that the resource parameter is optional. With no resource string specified, `findCards()` will open
the first card found. This is useful in test systems where only one 41-620 is present. Thus, the following is 
a simple, valid way to open a card:
```python
base = py620.Pi_Base()

card = base.openCard()
```
Other optional parameters are `idQuery` and `reset`. `idQuery` specifies
whether the card should be queried on whether it is a 41-620 compliant card, while `reset` specifies
whether the card should be reset on opening. Both are default `True`.

### Setting up an Output Channel ### 

Some setup is necessary to generate a signal on the 41-620 card. Once you have opened a card, 
you can set the channel you wish to use, and set the output to off before configuring it:
```python
card.setActiveChannel(1)
card.outputOff()
```
Configuring the card should include setting the desired trigger source and mode, and setting the desired DC
offset value (-5v to 5v):
```python
# Set trigger mode to continuous (no trigger)
card.setTriggerMode(card.triggerSources["FRONT"], card.triggerModes["CONT"])

offsetVoltage = 1.0
enableDCOffset = True
card.setOutputOffsetVoltage(offsetVoltage, enableDCOffset)
```
You can optionally set an attenuation value from 0 - 40 dB:
```python
card.setAttenuation(6)
```
### Generating a Signal ### 

Once an output channel is set up, it is ready to generate a signal:
```python
frequency = 10                      # In kHz
shape = card.signalShapes["SINE"]   # Defined in py620.Pi_Card, can also be TRIANGLE or SQUARE
symmetry = 0                        # Symmetry value in % 

card.generateSignal(frequency, shape, symmetry)
```
The card.generateSignal() method can also take optional parameters `startPhaseOffset` and `generate`:
```python
card.generateSignal(frequency, shape, symmetry, startPhaseOffset=90, generate=False)
```
The `startPhaseOffset` parameter specifies an initial phase offset to the signal, and `generate` specifies whether
the card should start generating a signal immediately. When set to `False`, output can be enabled at a later point:
```python
card.outputOn()
```
### Closing Cards and Ending Sessions ### 

Closing a session can be done as follows:
```python
card.close()
```
This will not stop the card generating any signals unless you call `card.outputOff()` before closing the card. 

### Error handling ### 

The Py620 wrapper functions will raise a py620.Error exception on any errors. Errors will generally have 
message and error code attributes from the driver. For example, if you were to try opening a card with an 
invalid resource string:
```python
try:
    card = base.openCard(resource="Invalid Resource String")
except py620.Error as ex:
    print("Exception occurred:", ex.message)
    print("Driver error code: {:X}".format(ex.errorCode))
```

