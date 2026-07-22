"""Sample program for Pickering LXI 41-625 Function Generator"""

import pilxi

################
# Channel mask #
#    1 = ON    #
#    0 = OFF   #
################

# set first 4 channels to 1
channel_state = [
    1,1,1,1
]

# fill the rest with 0
for channel in range(len(channel_state), 32):
    channel_state[channel] = 0

############################
# Variables for generation #
############################

waveform_type = [
    pilxi.WaveformTypes.PIFGLX_WAVEFORM_SINE,
    pilxi.WaveformTypes.PIFGLX_WAVEFORM_SQUARE,
    pilxi.WaveformTypes.PIFGLX_WAVEFORM_SINE,
    pilxi.WaveformTypes.PIFGLX_WAVEFORM_SQUARE
]

amplitude = [
    25,
    15,
    25,
    15
]

frequency = [
    10000,
    10000,
    10000,
    10000
]

dc_offset = [
    0,
    2,
    0,
    2
]

# fill the rest with 0
for channel in range(len(channel_state), 32):
    channel_state[channel] = 0

###############################
# Initialize session and card #
###############################

IP_Address = "192.168.11.156"

port = 1024
timeout = 1000

bus = 4
device = 13

subunit = 1

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

# count number of enabled channels
num_channels = 0
for x in range(len(channel_state)):
    if channel_state[x] == 1:
        num_channels += 1


for channel in range(num_channels):
    card.PIFGLX_SetWaveform(channel, waveform_type[channel])
    card.PIFGLX_SetAmplitude(channel, amplitude[channel])
    card.PIFGLX_SetFrequency(channel, frequency[channel])
    card.PIFGLX_SetDcOffset(channel, dc_offset[channel])


