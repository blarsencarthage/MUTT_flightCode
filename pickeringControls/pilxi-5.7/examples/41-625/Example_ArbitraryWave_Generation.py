"""Sample program for Pickering LXI 41-625 Function Generator"""

"""Sample program for Pickering LXI 41-625 Function Generator"""

import sys

import pilxi
import os

###############################
# Initialize session and card #
###############################

IP_Address = "192.168.11.156"

port = 1024
timeout = 1000

bus = 4
device = 13

subunit = 1

waveform = pilxi.WaveformTypes.PIFGLX_WAVEFORM_SINE

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

sample_source = ('{}/extras/MyARB.txt', os.getcwd())

card.PIFGLX_SetFrequency(subunit, 10000)
card.PIFGLX_CreateArbitraryWaveform(subunit, sample_source)

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