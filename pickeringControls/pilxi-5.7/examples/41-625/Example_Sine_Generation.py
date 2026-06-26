"""Sample program for Pickering LXI 41-625 Function Generator"""

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

#########################################
# Function generator specific functions #
#########################################

card.PIFGLX_SetWaveform(subunit, pilxi.WaveformTypes.PIFGLX_WAVEFORM_SINE)

card.PIFGLX_SetAmplitude(subunit, 20)

card.PIFGLX_SetFrequency(subunit, 10000)

card.PIFGLX_SetDcOffset(subunit, 0)

do_run = 1
amplitude = 20
freq = 10000
dc_offset = 0
while(do_run):
    amplitude = int(input("Set new amplitude"))
    freq = int(input("Set new frequency"))
    dc_offset = int(input("Set new DC Offset"))

    if (sys.version_info > (3, 0, 0)):
        amplitude = input("Set new amplitude")
    else:
        amplitude = raw_input("Set new amplitude")

    if (sys.version_info > (3, 0, 0)):
        freq = int(input("Set new frequency"))
    else:
        freq = int(raw_input("Set new frequency"))

    if (sys.version_info > (3, 0, 0)):
        dc_offset = int(input("Set new DC Offset"))
    else:
        dc_offset = int(raw_input("Set new DC Offset"))

    if(amplitude != None):
        card.PIFGLX_SetAmplitude(subunit, amplitude)
    if(freq != None):
        card.PIFGLX_SetFrequency(subunit, freq)
    if(amplitude != None):
        card.PIFGLX_SetDcOffset(subunit, dc_offset)

    if (sys.version_info > (3, 0, 0)):
        do_run = int(input("Enter 0 to abort generation"))
    else:
        do_run = int(raw_input("Enter 0 to abort generation"))

######################
# Clean up and close #
######################
card.PIFGLX_AbortGeneration(subunit)

card.ClearCard()

card.Close()

session.Close()