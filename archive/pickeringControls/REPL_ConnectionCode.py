import pilxi; import pi620lx 
LXI_IP = "169.254.112.5"
session = pilxi.Pi_Session(LXI_IP) 
sessionID = session.GetSessionID()
base = pi620lx.Base(sessionID)
cardIDs = base.findCards()
cards = []
for cardID in cardIDs: 
    bus, device = cardID
    
    print("Found 41-620 card at bus {} device {}".format(bus, device))
    cards.append(base.openCard(bus, device)) 

START_FREQ_HZ = 100
STOP_FREQ_HZ = 12000
SWEEP_TIME_MS = 5000
FREQ_STEP_TIME_MS = 5  # ms/step -- matches vendor's known-working example; 1000 was rejected by the driver

startFrequency = START_FREQ_HZ / 1000.0
endFrequency = STOP_FREQ_HZ / 1000.0
numSteps = SWEEP_TIME_MS / FREQ_STEP_TIME_MS
freqStepSize = (endFrequency - startFrequency) / numSteps

for cardIndex, card in enumerate(cards):
    for ch in range (1,4):
        trigSource = card.triggerSources["FRONT"]
        trigMode = card.triggerModes["POSEDGE"]
        shape = card.signalShapes["SINE"]

        card.setActiveChannel(ch)
        card.outputOff()
        card.setTriggerMode(trigSource, trigMode)
        card.setOutputOffsetVoltage(4.5, True)
        card.setAttenuation(0)
        card.generateSweep(signalType = shape, startFrequency = startFrequency, mode = 0, endFrequency = endFrequency,
                           freqStepSize = freqStepSize, freqStepTime = FREQ_STEP_TIME_MS, symmetry = 50)
        card.outputOn()
        print("Card {} Channel {} configured for sweep from {} Hz to {} Hz over {} ms, 0 dB, 4.5 V offset".format(
            cardIndex+1, ch, START_FREQ_HZ, STOP_FREQ_HZ, SWEEP_TIME_MS))

        
        
       