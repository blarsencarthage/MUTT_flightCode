"""Sample program for Pickering LXI 41-625 Function Generator"""

import sys

import pilxi

###############################
# Initialize session and card #
###############################

IP_Address = "192.168.11.162"

port = 1024
timeout = 1000

bus = 4
device = 1

subunit = 1

waveform = pilxi.WaveformTypes.PIFGLX_WAVEFORM_SINE

amplitude = 20
frequency = 10000
dc_offset = 0
start_phase = 0
duty_cycle = 20

# Pulse waveform only
pulse_width = 150

# Connect to chassis
session = pilxi.Pi_Session(IP_Address, port, timeout)

# Open card
try:
    card = session.OpenCard(bus, device)
except pilxi.Error as ex:
    print("Error occurred: {}".format(ex.message))
    exit()

# Get and print the Card ID
cardId = card.CardId()

print("Successfully connected to card at bus", bus, "device", device)
print("Card ID: ", cardId)

card.ClearCard()

#########################################
# Function generator specific functions #
#########################################

card.PIFGLX_SetInputTriggerConfig(pilxi.TriggerInputSource.PIFGLX_TRIG_IN_FRONT, pilxi.TriggerInputModes.PIFGLX_TRIG_IN_EDGE_RISING)

card.PIFGLX_SetOutputTriggerConfig(pilxi.TriggerOutputModes.PIFGLX_TRIG_OUT_GEN_PULSE_POS, 0)

card.PIFGLX_SetInputTriggerEnable(subunit, [1])

card.PIFGLX_SetOutputTriggerEnable(subunit, [1])

card.PIFGLX_SetWaveform(subunit, waveform)

card.PIFGLX_SetAmplitude(subunit, amplitude)

card.PIFGLX_SetDcOffset(subunit, dc_offset)

card.PIFGLX_SetFrequency(subunit, frequency)

card.PIFGLX_SetStartPhase(subunit, start_phase)

card.PIFGLX_SetDutyCycleHigh(subunit, duty_cycle)

if waveform == pilxi.WaveformTypes.PIFGLX_WAVEFORM_PULSE:
    card.PIFGLX_SetPulseWidth(pulse_width)

# Wait for user input to abort generation

if (sys.version_info > (3, 0, 0)):
    input_var = input("Press Enter to continue ")
else:
    input_var = raw_input("Please Enter to continue ")

######################
# Clean up and close #
######################
card.PIFGLX_AbortGeneration(subunit)

card.ClearCard()

card.Close()

session.Close()