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

freqArray_kHz = [10, 20, 50, 100, 200, 500]
attenuation_dB = [0, 5, 5, 10, 10, 10]
offset_V = [3.5,3.5, 3.5,3.5, 3.5, 3.5]
phase_deg = [0, 30, 60, 0, 0, 0]
#Configure all channels of all cards found
#For each card found:
globalCh = 0
for cardIndex, card in enumerate(cards):
    #For each of the 3 channels of the card:
    for ch in range (1,4):
        #Declare objects from card class
        trigSource = card.triggerSources["FRONT"]
        trigMode = card.triggerModes["POSEDGE"]
        shape = card.signalShapes["SINE"]
        #Apply to Channel ch
        card.setActiveChannel(ch)
        card.outputOff()
        #Set Trigger
        card.setTriggerMode(trigSource, trigMode)
        #Set DC Offset
        card.setOutputOffsetVoltage(offset_V[globalCh], True)
        #Set Attenuation
        card.setAttenuation(attenuation_dB[globalCh])
        #Build Signal and enable output
        card.generateSignal(frequency = freqArray_kHz[globalCh],
                            signalType = shape,
                            startPhaseOffset =  phase_deg[globalCh],
                            symmetry = 50, generate = False)
        card.outputOn()
        print("Card {} Channel {} configured for {} kHz, {} dB, {} V offset, {} deg phase".format(cardIndex+1, ch, freqArray_kHz[globalCh], attenuation_dB[globalCh], offset_V[globalCh], phase_deg[globalCh]))
        #Channel is now waiting for trigger to begin signal generation
        globalCh += 1
session.Close()
