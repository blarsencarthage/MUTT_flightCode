import pickeringInterface as pI

session, waves = pI.initPXIE()

channel = 1
frequency = 255000  # hz (converted to kHz internally by updateWaveform())
amplitude = 1.0  # dB attenuation (card.setAttenuation()) — NOT volts, see pickeringInterface.waveAtributes
offset = 0.0  # volts, -5 to 5
phase = 0.0  # degrees

# waves is indexed: card_index * 3 + (channel - 1)
# Channel 1 of the first card = waves[0]
wave = waves[channel - 1]
wave.setFrequency(frequency)
wave.setAmplitude(amplitude)
wave.setOffset(offset)
wave.setPhase(phase)
pI.updateWaveform(wave._card, wave)
