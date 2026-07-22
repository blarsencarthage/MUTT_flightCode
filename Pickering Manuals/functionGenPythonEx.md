
# Class Definitions 
```python
class FG_WfTypes(IntEnum): # PILFG Waveform Types
    PILFG_WAVEFORM_SINE         = 0x0,
    PILFG_WAVEFORM_SQUARE		= 0x1,
    PILFG_WAVEFORM_TRIANGLE	    = 0x2,
    PILFG_WAVEFORM_RAMP_UP		= 0x3,
    PILFG_WAVEFORM_RAMP_DOWN	= 0x4,
    PILFG_WAVEFORM_DC			= 0x5,
    PILFG_WAVEFORM_PULSE		= 0x6,
    PILFG_WAVEFORM_PWM			= 0x7,
    PILFG_WAVEFORM_ARB			= 0x8
```

```python
#region Function generator functions

    def PILFG_SetAmplitude(self, SubNum, Amplitude):
        SubNum = ctypes.c_uint32(SubNum)
        Amplitude = ctypes.c_double(Amplitude)
        
        err = self.handle.PILFG_SetAmplitude(self.card, SubNum,Amplitude)
        
        self._handleError(err)
        
        return
    
    def PILFG_GetAmplitude(self, SubNum):
        SubNum = ctypes.c_uint32(SubNum)
        Amplitude = ctypes.c_double(Amplitude)
        
        err = self.handle.PILFG_GetAmplitude(self.card, SubNum, ctypes.byref(Amplitude))
        
        self._handleError(err)
        
        return Amplitude.value
    
    def PILFG_SetDcOffset(self, SubNum, DcOffset):
        SubNum = ctypes.c_uint32(SubNum)
        DcOffset = ctypes.c_double(DcOffset)
        
        err = self.handle.PILFG_SetDcOffset(self.card, SubNum, DcOffset)
        self._handleError(err)
        
        return
    
    def PILFG_GetDcOffset(self, SubNum):
        SubNum = ctypes.c_uint32(SubNum)
        DcOffset = ctypes.c_double(DcOffset)
        
        err = self.handle.PILFG_GetDcOffset(self.card, SubNum, ctypes.byref(DcOffset))
        self._handleError(err)
        
        return DcOffset.value
    
    def PILFG_SetFrequency(self, SubNum, Frequency):
        SubNum = ctypes.c_uint32(SubNum)
        Frequency = ctypes.c_double(Frequency)
        
        err = self.handle.PILFG_SetFrequency(self.card, SubNum, Frequency)
        self._handleError(err)
        
        return
    
    def PILFG_GetFrequency(self, SubNum):
        SubNum = ctypes.c_uint32(SubNum)
        Frequency = ctypes.c_double(Frequency)
        
        err = self.handle.PILFG_GetFrequency(self.card, SubNum, ctypes.byref(Frequency))
        self._handleError(err)
        
        return Frequency.value
    
    def PILFG_SetStartPhase(self, SubNum, StartPhase):
        SubNum = ctypes.c_uint32(SubNum)
        StartPhase = ctypes.c_double(StartPhase)
        
        err = self.handle.PILFG_SetStartPhase(self.card, SubNum, StartPhase)
        self._handleError(err)
        
        return
    
    def PILFG_GetStartPhase(self, SubNum):
        SubNum = ctypes.c_uint32(SubNum)
        StartPhase = ctypes.c_double(StartPhase)
        
        err = self.handle.PILFG_GetStartPhase(self.card, SubNum, ctypes.byref(StartPhase))
        self._handleError(err)
        
        return StartPhase.value
    
    
    def PILFG_SetDutyCycleHigh(self, SubNum, DutyCycleHigh):
        SubNum = ctypes.c_uint32(SubNum)
        DutyCycleHigh = ctypes.c_uint32(DutyCycleHigh)
        
        err = self.handle.PILFG_SetDutyCycleHigh(self.card, SubNum, DutyCycleHigh)
        self._handleError(err)
        
        return
    
    def PILFG_GetDutyCycleHigh(self, SubNum):
        SubNum = ctypes.c_uint32(SubNum)
        DutyCycleHigh = ctypes.c_uint32(DutyCycleHigh)
        
        err = self.handle.PILFG_GetDutyCycleHigh(self.card, SubNum, ctypes.byref(DutyCycleHigh))
        self._handleError(err)
        
        return
    
    def PILFG_SetWaveform(self, SubNum, Waveform):
        SubNum = ctypes.c_uint32(SubNum)
        Waveform = ctypes.c_uint32(Waveform)
        
        err = self.handle.PILFG_SetWaveform(self.card, SubNum, Waveform)
        self._handleError(err)
        
        return
    
    def PILFG_GetWaveform(self, SubNum):
        SubNum = ctypes.c_uint32(SubNum)
        Waveform = ctypes.c_uint32(Waveform)
        
        err = self.handle.PILFG_GetWaveform(self.card, SubNum, ctypes.byref(Waveform))
        self._handleError(err)
        
        return Waveform.value
    
    def PILFG_SetPulseWidth(self, SubNum, PulseWidth):
        SubNum = ctypes.c_uint32(SubNum)
        PulseWidth = ctypes.c_double(PulseWidth)
        
        err = self.handle.PILFG_SetPulseWidth(self.card, SubNum, PulseWidth)
        self._handleError(err)
        
        return
    
    def PILFG_GetPulseWidth(self, SubNum):
        SubNum = ctypes.c_uint32(SubNum)
        PulseWidth = ctypes.c_double(PulseWidth)
        
        err = self.handle.PILFG_GetPulseWidth(self.card, SubNum, ctypes.byref(PulseWidth))
        self._handleError(err)
        
        return PulseWidth.value
    
    def PILFG_ConfigureWaveform(self, SubNum, Waveform, Amplitude, DcOffset, Frequency, StartPhase, DutyCycleHigh, PulseWidth):
        SubNum = ctypes.c_uint32(SubNum)
        Waveform = ctypes.c_uint32(Waveform)
        Amplitude = ctypes.c_uint32(Amplitude)
        DcOffset = ctypes.c_uint32(DcOffset)
        Frequency = ctypes.c_uint32(Frequency)
        StartPhase = ctypes.c_uint32(StartPhase)
        DutyCycleHigh = ctypes.c_uint32(DutyCycleHigh)
        PulseWidth = ctypes.c_uint32(PulseWidth)
        
        err = self.handle.PILFG_ConfigureWaveform(self.card, SubNum, Waveform, Amplitude, DcOffset, Frequency, StartPhase, DutyCycleHigh, PulseWidth)
        self._handleError(err)
        
        return
    
    def PILFG_InitiateGeneration(self, SubNum):
        SubNum = ctypes.c_uint32(SubNum)
        
        err = self.handle.PILFG_InitiateGeneration(self.card, SubNum)
        self._handleError(err)
        
        return

    def PILFG_AbortGeneration(self, SubNum):
        SubNum = ctypes.c_uint32(SubNum)
        err = self.handle.PILFG_AbortGeneration(self.card, SubNum)

        self._handleError(err)
        return
    
    def PILFG_StartStopGeneration(self, State):
        array_type = ctypes.c_uint32 * len(State)
        c_array = array_type(*State)
        
        err = self.handle.PILFG_StartStopGeneration(self.card, ctypes.byref(c_array), len(State))
        self._handleError(err)
        
        return
    
    def PILFG_GetGenerationState(self, SubNum, Size):
        SubNum = ctypes.c_uint32(SubNum)
        array_type = ctypes.c_uint32 * Size
        c_array = array_type()
        c_array_p = ctypes.pointer(c_array)
        
        err = self.handle.PILFG_GetGenerationState(self.card, SubNum, c_array_p, Size)
        self._handleError(err)
        
        return [c_array[i] for i in range(Size)]

    def PILFG_CreateArbitraryWaveform(self, SubNum, SampleSource):
        SubNum = ctypes.c_uint32(SubNum)
        SampleSource = ctypes.c_char_p(SampleSource)
        
        err = self.handle.PILFG_CreateArbitraryWaveform(self.card, SubNum, SampleSource)
        self._handleError(err)
        
        return
    
    def PILFG_SetInputTriggerConfig(self, Trigger):
        Trigger = ctypes.c_uint32(Trigger)
        
        err = self.handle.PILFG_SetInputTriggerConfig(self.card, Trigger)
        self._handleError(err)
        
        return
    
    def PILFG_GetInputTriggerConfig(self):
        Source = ctypes.c_uint32()
        Trigger = ctypes.c_uint32()
        
        err = self.handle.PILFG_GetInputTriggerConfig(self.card, ctypes.byref(Source), ctypes.byref(Trigger))
        self._handleError(err)
        
        return Source.value, Trigger.value
    
    def PILFG_SetOutputTriggerConfig(self, Trigger):
        Trigger = ctypes.c_uint32(Trigger)
        err = self.handle.PILFG_SetOutputTriggerConfig(self.card, Trigger)
        self._handleError(err)
        
        return
    
    def PILFG_GetOutputTriggerConfig(self):
        Trigger = ctypes.c_uint32()
        
        err = self.handle.PILFG_GetOutputTriggerConfig(self.card, ctypes.byref(Trigger))
        self._handleError(err)
        
        return Trigger.value

        
    def PILFG_SetInputTriggerEnable(self, SubNum, Trigger):
        SubNum = ctypes.c_uint32(SubNum)
        array_type = ctypes.c_uint32 * len(Trigger)
        c_array = array_type(*Trigger)
        
        err = self.handle.PILFG_SetInputTriggerEnable(self.card, SubNum, ctypes.byref(c_array), len(Trigger))
        self._handleError(err)
        
        return
    
    def PILFG_GetInputTriggerEnable(self, SubNum, Size):
        SubNum = ctypes.c_uint32(SubNum)
        Trigger = (ctypes.c_uint32 * Size)()
        
        err = self.handle.PILFG_GetInputTriggerEnable(self.card, SubNum, ctypes.byref(Trigger), Size)
        self._handleError(err)
        
        return list(Trigger)

    
    def PILFG_SetOutputTriggerEnable(self, SubNum, Trigger):
        SubNum = ctypes.c_uint32(SubNum)
        array_type = ctypes.c_uint32 * len(Trigger)
        c_array = array_type(*Trigger)
        
        err = self.handle.PILFG_SetOutputTriggerEnable(self.card, SubNum, ctypes.byref(c_array), len(Trigger))
        self._handleError(err)
        
        return
    
    def PILFG_GetOutputTriggerEnable(self, SubNum, Size):
        SubNum = ctypes.c_uint32(SubNum)
        Trigger = (ctypes.c_uint32 * Size)()
        
        err = self.handle.PILFG_GetOutputTriggerEnable(self.card, SubNum, ctypes.byref(Trigger), Size)
        self._handleError(err)
        
        return list(Trigger)

    def PILFG_GenerateOutputTrigger(self, State):
        State = ctypes.c_uint32(State)
        
        err = self.handle.PILFG_GenerateOutputTrigger(self.card, State)
        self._handleError(err)
        
        return
    
    def PILFG_GetTriggerMonitorState(self, SubNum, Size):
        SubNum = ctypes.c_uint32(SubNum)
        State = (ctypes.c_uint32 * Size)()
        
        err = self.handle.PILFG_GetTriggerMonitorState(self.card, SubNum, ctypes.byref(State), Size)
        self._handleError(err)
        
        return list(State)
        
    #endregion
```
