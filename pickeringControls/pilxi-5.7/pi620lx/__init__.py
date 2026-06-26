from sys import version_info
import ctypes
import platform

__version__ = "1.0.1"

class Error(Exception):
    def __init__(self, message, errorCode=None):
        self.message = message
        self.errorCode = errorCode

    def __str__(self):
        return self.message

class Base:
    def __init__(self, session):
        self.session = session

        if platform.system() == "Windows":
            arch = platform.architecture()
            if "64bit" in arch:
                self.handle = ctypes.windll.LoadLibrary("Pi620lx_w64")

            else:
                self.handle = ctypes.windll.LoadLibrary("Pi620lx_w32")

        elif platform.system() == "Darwin":
            self.handle = ctypes.cdll.LoadLibrary("Bin/libpi620lx.so")

        elif platform.system() == "Linux":
            self.handle = ctypes.cdll.LoadLibrary("libpi620lx.so")

        self.pythonMajorVersion = version_info[0]

        # Trigger modes enum
        self.triggerModes = {
            "HIGH": 0x0,
            "LOW": 0x1,
            "POSEDGE": 0x2,
            "NEGEDGE": 0x3,
            "POSEDGESINGLE": 0x4,
            "NEGEDGESINGLE": 0x5,
            "CONT": 0x6
        }

        # Signal shape enum
        self.signalShapes = {
            "SINE": 0,
            "TRIANGLE": 1,
            "SQUARE": 2
        }

        # Instrument mode enum
        self.instrumentModes = {
            "CONFIGURE": 0,
            "GENERATE": 1
        }

        # Trigger source enum
        self.triggerSources = {
            "FRONT": 0,
            "PXI0": 1,
            "PXI1": 2,
            "PXI2": 3,
            "PXI3": 4,
            "PXI4": 5,
            "PXI5": 6,
            "PXI6": 7,
            "PXI7": 8,
            "PXI_STAR": 9
        }


    def _stringToStr(self, inputString):
        """Take a string passed to a function in Python 2 or Python 3 and convert to
           a ctypes-friendly ASCII string"""

        # Check for Python 2 or 3
        if self.pythonMajorVersion < 3:
            if type(inputString) is str:
                return inputString
            if type(inputString) is unicode:
                return inputString.encode()
        else:
            if type(inputString) is bytes:
                return inputString
            elif type(inputString) is str:
                return inputString.encode()

    def _pythonString(self, inputString):
        """Ensure returned strings are native in Python 2 and Python 3"""

        # Check for Python 2 or 3
        if self.pythonMajorVersion < 3:
            return inputString
        else:
            return inputString.decode()

    def errorMessage(self, code):
        """ Returns a string description from a given error code """
        errorString = ctypes.create_string_buffer(100)
        error = self.handle.PI620LX_error_message(self.session, 0, code, ctypes.byref(errorString))
        return self._pythonString(errorString.value)

    def findCards(self):
        """Returns a list of bus, device locations of 41-620 cards present in the LXI"""
        sessionID = self.session
        count = ctypes.c_uint32(50)
        buslist = (ctypes.c_uint32 * 50)()
        devicelist = (ctypes.c_uint32 * 50)()

        error = self.handle.PI620LX_FindInstruments(sessionID, ctypes.byref(buslist), ctypes.byref(devicelist), ctypes.byref(count))

        return [(buslist[i], devicelist[i]) for i in range(0, count.value)]

    def openCard(self, bus=None, device=None, idQuery=True, reset=True):
        """Opens a 41-620 card present in the LXI. If no bus and device numbers are specified,
        defaults to opening the first 41-620 found."""

        if bus is None and device is None:
            devices = self.findCards()

            if not devices:
                raise Error("Card not found")
            else:
                bus, device = devices[0]
                card = Card(self.session, bus, device, idQuery, reset)
                return card

        if bus is not None and device is not None:
            card = Card(self.session, bus, device, idQuery, reset)
            return card

        return


class Card(Base):
    def __init__(self, session, bus, device, idQuery=True, reset=True):

        Base.__init__(self, 0)

        self.session = session
        self.disposed = False

        # ViSession handle
        self.vi = ctypes.c_uint32(0)

        resourceString = self._stringToStr("PXI{}::{}::INSTR".format(bus, device))

        error = self.handle.PI620LX_init(self.session, resourceString, bool(idQuery), bool(reset), ctypes.byref(self.vi))

    def __del__(self):
        if not self.disposed:
            self.close()
        return

    def errorMessage(self, code):
        """ Returns a string description from a given error code """
        errorString = ctypes.create_string_buffer(100)
        error = self.handle.PI620LX_error_message(self.session, self.vi, code, ctypes.byref(errorString))

        return self._pythonString(errorString.value)

    def _handleError(self, error):
        """ Private method to raise exceptions based on error codes from driver. """
        if error:
            errorString = self.errorMessage(error)
            raise Error(errorString, errorCode=error)

    def close(self):
        self.disposed = True
        error = self.handle.PI620LX_close(self.session, self.vi)
        return

    def getCalibrationDate(self):
        """ Returns date card was last calibrated """
        year = ctypes.c_uint32()
        month = ctypes.c_uint32()
        day = ctypes.c_uint32()

        error = self.handle.PI620LX_GetCalibrationDate(self.session, self.vi, ctypes.byref(year), ctypes.byref(month), ctypes.byref(day))
        self._handleError(error)

        return int(year.value), int(month.value), int(day.value)

    def generateSignal(self, frequency, signalType, symmetry, startPhaseOffset=0.0, generate=True):
        frequency = ctypes.c_double(frequency)
        symmetry = ctypes.c_double(symmetry)
        startPhaseOffset = ctypes.c_double(startPhaseOffset)
        generate = ctypes.c_bool(generate)

        error = self.handle.PI620LX_GenerateSignalEx(self.session, self.vi, frequency, signalType, symmetry, startPhaseOffset, generate)
        self._handleError(error)
        return

    def generateSweep(self, signalType, symmetry, mode, startFrequency, endFrequency,
                            freqStepSize, freqStepTime):
        signalType = ctypes.c_uint32(signalType)
        symmetry = ctypes.c_double(symmetry)
        mode = ctypes.c_uint32(mode)
        startFrequency = ctypes.c_double(startFrequency)
        endFrequency = ctypes.c_double(endFrequency)
        freqStepSize = ctypes.c_double(freqStepSize)
        freqStepTime = ctypes.c_double(freqStepTime)

        error = self.handle.PI620LX_GenerateSweep(self.session,
                                                  self.vi,
                                                  signalType,
                                                  symmetry,
                                                  mode,
                                                  startFrequency,
                                                  endFrequency,
                                                  freqStepSize,
                                                  freqStepTime)
        self._handleError(error)
        return

    def getOffsetCalCode(self, offset):
        code = ctypes.c_uint32(0)
        offset = ctypes.c_uint32(offset)

        error = self.handle.PI620LX_GetOffsetCalCode(self.session, self.vi, ctypes.byref(code), offset)
        self._handleError(error)
        return int(code.value)

    def getOutputOffsetCalVoltages(self):
        maxvolt = ctypes.c_double(0)
        minvolt = ctypes.c_double(0)

        error = self.handle.PI620LX_GetOutputOffsetCalVoltages(self.session, self.vi, ctypes.byref(maxvolt), ctypes.byref(minvolt))
        self._handleError(error)
        return float(maxvolt.value), float(minvolt.value)

    def getRangeLimitVoltages(self):
        maxvolt = ctypes.c_double(0)
        minvolt = ctypes.c_double(0)

        error = self.handle.pi620_GetRangeLimitVoltages(self.session, self.vi, ctypes.byref(maxvolt), ctypes.byref(minvolt))
        self._handleError(error)
        return float(maxvolt.value), float(minvolt.value)

    def loadArbitraryWaveform(self, waveform, repetitionRate=None):
        waveformlength = ctypes.c_uint32(len(waveform))
        c_waveform = (ctypes.c_double * len(waveform))(*waveform)

        if repetitionRate is None:
            error = self.handle.PI620LX_LoadArbitraryWaveform(self.session, self.vi, waveformlength, c_waveform)
        else:
            repetitionRate = ctypes.c_double(repetitionRate)
            error = self.handle.PI620LX_LoadArbitraryWaveformEx(self.session, self.vi,
                                                                waveformlength,
                                                                ctypes.byref(c_waveform),
                                                                repetitionRate)
        self._handleError(error)
        return

    def memoryTest(self):
        erroraddress = ctypes.c_uint32(0)
        errordata = ctypes.c_uint32(0)
        expectdata = ctypes.c_uint32(0)

        error = self.handle.PI620LX_MemoryTest(self.session, self.vi, ctypes.byref(erroraddress), ctypes.byref(errordata), ctypes.byref(expectdata))
        self._handleError(error)

        return int(erroraddress.value), int(errordata.value), int(expectdata.value)

    def readEeprom(self, eepromAddress):
        data = ctypes.c_uint32(0)

        error = self.handle.PI620LX_ReadEeprom(self.session, self.vi, eepromAddress, ctypes.byref(data))
        self._handleError(error)
        return int(data.value)

    def readInstrumentMemory(self):
        data = ctypes.c_uint32(0)

        error = self.handle.PI620LX_ReadInstrumentMemory(self.session, self.vi, ctypes.byref(data))
        self._handleError(error)
        return int(data.value)

    def readInstrumentMemoryArray(self, length):
        buf32 = (ctypes.c_uint32 * length)

        error = self.handle.PI620LX_ReadInstrumentMemoryArray(self.session, self.vi, length, buf32)
        self._handleError(error)
        return [int(data) for data in buf32]

    def readRegister(self, address):
        data = ctypes.c_uint32(0)

        error = self.handle.PI620LX_ReadRegister(self.session, self.vi, address, ctypes.byref(data))
        self._handleError(error)
        return int(data.value)

    def reset(self):
        error = self.handle.PI620LX_reset(self.session, self.vi)
        self._handleError(error)
        return

    def resetAddressCounter(self):
        error = self.handle.PI620LX_ResetAddressCounter(self.session, self.vi)
        self._handleError(error)
        return

    def resetAddressCounters(self):
        error = self.handle.PI620LX_ResetAddressCounters(self.session, self.vi)
        self._handleError(error)
        return

    def revisionQuery(self):
        driverRev = ctypes.create_string_buffer(100)
        instrumentRev = ctypes.create_string_buffer(100)

        error = self.handle.PI620LX_revision_query(self.session, self.vi, ctypes.byref(driverRev), ctypes.byref(instrumentRev))
        self._handleError(error)
        return self._pythonString(driverRev), self._pythonString(instrumentRev)

    def selfTest(self):
        testResult = ctypes.c_int16(0)
        errorMessage = ctypes.create_string_buffer(100)

        error = self.handle.PI620LX_self_test(self.session, self.vi, ctypes.byref(testResult), ctypes.byref(errorMessage))
        self._handleError(error)
        return int(testResult.value), self._pythonString(errorMessage)

    def setActiveChannel(self, channel):
        channel = ctypes.c_uint32(channel)

        error = self.handle.PI620LX_SetActiveChannel(self.session, self.vi, channel)
        self._handleError(error)
        return

    def setAMMode(self, amMode):
        amMode = ctypes.c_uint32(amMode)

        error = self.handle.PI620LX_SetAMMode(self.session, self.vi, amMode)
        self._handleError(error)
        return

    def setAttenuation(self, attenuation):
        attenuation = ctypes.c_double(attenuation)

        error = self.handle.PI620LX_SetAttenuation(self.session, self.vi, attenuation)
        self._handleError(error)
        return

    def setClockMode(self, mode, startFreq, endFreq, freqStep, freqStepTime):
        mode = ctypes.c_uint32(mode)
        startFreq = ctypes.c_double(startFreq)
        endFreq = ctypes.c_double(endFreq)
        freqStep = ctypes.c_double(freqStep)
        freqStepTime = ctypes.c_double(freqStepTime)

        error = self.handle.PI620LX_SetClockMode(self.session, self.vi, mode, startFreq, endFreq, freqStep, freqStepTime)
        self._handleError(error)
        return

    def setClockSource(self, clockSource, extClockFreq, clockMul):
        clockSource = ctypes.c_uint32(clockSource)
        extClockFreq = ctypes.c_double(extClockFreq)
        clockMul = ctypes.c_uint32(clockMul)

        error = self.handle.PI620LX_SetClockSource(self.session, self.vi, clockSource, extClockFreq, clockMul)
        self._handleError(error)
        return

    def setCounterStep(self, counterStep):
        counterStep = ctypes.c_uint32(counterStep)

        error = self.handle.PI620LX_SetCounterStep(self.session, self.vi, counterStep)
        self._handleError(error)
        return

    def setFSKPin(self, state):
        state = ctypes.c_uint32(state)

        error = self.handle.PI620LX_SetFSKPin(self.session, self.vi, state)
        self._handleError(error)
        return

    def setFSKSource(self, source):
        source = ctypes.c_uint32(source)

        error = self.handle.PI620LX_SetFSKSource(self.session, self.vi, source)
        self._handleError(error)
        return

    def setInstrumentMode(self, mode):
        mode = ctypes.c_uint32(mode)

        error = self.handle.PI620LX_SetInstrumentMode(self.session, self.vi, mode)
        self._handleError(error)
        return

    def setLockMode(self, lock):
        lock = ctypes.c_uint32(lock)
        error = self.handle.PI620LX_SetLockMode(self.session, self.vi, lock)
        self._handleError(lock)
        return

    def setMainDacCode(self, code):
        code = ctypes.c_uint32(code)

        error = self.handle.PI620LX_SetMainDacCode(self.session, self.vi, code)
        self._handleError(error)
        return

    def setOffsetCalCode(self, code, offset):
        code = ctypes.c_uint32(code)
        offset = ctypes.c_uint32(offset)
        error = self.handle.PI620LX_SetOffsetCalCode(self.session, self.vi, code, offset)
        self._handleError(error)
        return

    def setOutputOffsetCalVoltages(self, maxvolt, minvolt):
        maxvolt = ctypes.c_double(maxvolt)
        minvolt = ctypes.c_double(minvolt)

        error = self.handle.PI620LX_SetOutputOffsetCalVoltages(self.session, self.vi, maxvolt, minvolt)
        self._handleError(error)
        return

    def setOutputOffsetDacCode(self, code, connect):
        code = ctypes.c_uint32(code)
        connect = ctypes.c_uint32(connect)

        error = self.handle.PI620LX_SetOutputOffsetDacCode(self.session, self.vi, code, connect)
        self._handleError(error)
        return

    def setOutputOffsetVoltage(self, voltage, connect):
        voltage = ctypes.c_double(voltage)
        connect = ctypes.c_uint32(connect)

        error = self.handle.PI620LX_SetOutputOffsetVoltage(self.session, self.vi, voltage, connect)
        self._handleError(error)
        return

    def setOutputVoltage(self, voltage, method):
        voltage = ctypes.c_double(voltage)
        method = ctypes.c_uint32(method)

        error = self.handle.PI620LX_SetOutputVoltage(self, voltage, method)
        self._handleError(error)
        return

    def setRangeDacCode(self, code):
        code = ctypes.c_uint32(code)
        error = self.handle.PI620LX_SetRangeDacCode(self.session, self.vi, code)
        self._handleError(error)
        return

    def setRangeLimitVoltages(self, maxvolt, minvolt):
        maxvolt = ctypes.c_double(maxvolt)
        minvolt = ctypes.c_double(minvolt)

        error = self.handle.PI620LX_SetRangeLimitVoltages(self.session, self.vi, maxvolt, minvolt)
        self._handleError(error)
        return

    def setSignal(self, signalType, amplitude, startPhase, symmetry):
        signalType = ctypes.c_uint32(signalType)
        amplitude = ctypes.c_double(amplitude)
        startPhase = ctypes.c_double(startPhase)
        symmetry = ctypes.c_double(symmetry)

        error = self.handle.PI620LX_SetSignal(self.session, self.vi, signalType, amplitude, startPhase, symmetry)
        self._handleError(error)
        return

    def setTriggerMode(self, source, mode):
        source = ctypes.c_uint32(source)
        mode = ctypes.c_uint32(mode)

        error = self.handle.PI620LX_SetTriggerMode(self.session, self.vi, source, mode)
        self._handleError(error)
        return

    def storeCalibrationData(self):
        error = self.handle.PI620LX_StoreCalibrationData(self.session, self.vi)
        self._handleError(error)
        return

    def syncChannels(self):
        error = self.handle.PI620LX_SyncChannels(self.session, self.vi)
        self._handleError(error)
        return

    def writeCalibrationDate(self, year, month, day):
        error = self.handle.PI620LX_WriteCalibrationDate(self.session, self.vi, year, month, day)
        self._handleError(error)
        return

    def writeEeprom(self, eepromAddress, data):
        eepromAddress = ctypes.c_uint32(eepromAddress)
        data = ctypes.c_uint32(data)

        error = self.handle.PI620LX_WriteEeprom(self.session, self.vi, eepromAddress, data)
        self._handleError(error)
        return

    def writeCardId(self, cardId):
        cardId = ctypes.c_uint32(cardId)

        error = self.handle.PI620LX_WriteCardId(self.session, self.vi, cardId)
        self._handleError(error)
        return

    def writeInstrumentMemory(self, data):
        data = ctypes.c_uint32(data)

        error = self.handle.PI620LX_WriteInstrumentMemory(self.session, self.vi, data)
        self._handleError(error)
        return

    def writeInstrumentMemoryArray(self, array):
        length = ctypes.c_uint32(len(array))
        buf32 = (ctypes.c_uint32 * len(array))(*array)

        error = self.handle.PI620LX_WriteInstrumentMemoryArray(self.session, self.vi, length, ctypes.byref(buf32))
        self._handleError(error)
        return

    def WriteRegister(self, address, data):
        address = ctypes.c_uint32(address)
        data = ctypes.c_uint32(data)

        error = self.handle.PI620LX_WriteRegister(self.session, self.vi, address, data)
        self._handleError(error)
        return

    def prepareChannelForSoftTrigger(self, source):
        source = ctypes.c_uint32(source)

        error = self.handle.PI620LX_PrepareChannelForSoftTrigger(self.session, self.vi, source)
        self._handleError(error)
        return

    def launchSoftTrigger(self, source):
        source = ctypes.c_uint32(source)

        error = self.handle.PI620LX_LaunchSoftTrigger(self.session, self.vi, source)
        self._handleError(error)
        return

    def clearSoftTrigger(self, source):
        source = ctypes.c_uint32(source)

        error = self.handle.PI620LX_ClearSoftTrigger(self.session, self.vi, source)
        self._handleError(error)
        return

    def setSoftTriggerStatus(self, source, enable, status):
        source = ctypes.c_uint32(source)
        enable = ctypes.c_bool(enable)
        status = ctypes.c_bool(status)

        error = self.handle.PI620LX_SetSoftTriggerStatus(self.session, self.vi, source, enable, status)
        self._handleError(error)
        return

    def getSoftTriggerStatus(self, source):
        source = ctypes.c_uint32(source)
        enabled = ctypes.c_bool(False)
        status = ctypes.c_bool(False)

        error = self.handle.PI620LX_GetSoftTriggerStatus(self.session, self.vi, source, ctypes.byref(enabled), ctypes.byref(status))
        self._handleError(error)
        return

    def readWaveformFromFile(self, filename):
        with open(filename) as f:
            content = f.readlines()
            content = [float(line) for line in content]
        return content

    def outputOff(self):
        error = self.handle.PI620LX_OutputOff(self.session, self.vi)
        self._handleError(error)
        return

    def outputOn(self):
        error = self.handle.PI620LX_OutputOn(self.session, self.vi)
        self._handleError(error)
        return
