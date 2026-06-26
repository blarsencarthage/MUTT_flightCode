import pickeringInterface as pI 

cards = pI.initPXIE()

channel = 1 
frequency = 255000 #hz 
amplitude = 1.0 #volts 
offset = 0.0 #volts 
phase = 0.0 #degrees 


wave = pI.waveAtributes(channel, frequency, amplitude, offset, phase)
pI.updateWaveform(cards[0], wave)
