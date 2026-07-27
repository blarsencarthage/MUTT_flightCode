# -*- coding: utf-8 -*-

""" Python wrapper for the Pickering 41-620 PXI Function Generator driver """

from ctypes import *
import ctypes.util
import platform
import warnings

# Exceptions definitions
class Error(Exception):
    """ Base error class provides optional error message and error code from driver. """
    def __init__(self, message=None, errorCode=None):
        self.message = message
        self.errorCode = errorCode


class Pi_Base:
    """Base class to load driver dll and provide base functionality, card discovery/opening functions."""
    def __init__(self):

        arch = platform.architecture()

        if "64bit" in arch:
            library = ctypes.util.find_library("pi620_64")
            self.handle = windll.LoadLibrary(library)
        else:
            library = ctypes.util.find_library("pi620_32")
            self.handle = windll.LoadLibrary(library)

        # Error Codes Enum
        ERROR_BASE = 0xBFFC0900
        self.errors = {
            "PI620_ERROR_MEMTEST":          ERROR_BASE + 0x1,
            "PI620_ERROR_OPEN":             ERROR_BASE + 0x2,
            "PI620_ERROR_INVALID_RSCNAME":  ERROR_BASE + 0x3,
            "PI620_ERROR_DRIVER":           ERROR_BASE + 0x4,
            "PI620_ERROR_ALLOC":            ERROR_BASE + 0x5,
            "PI620_ERROR_INV_HANDLE":       ERROR_BASE + 0x6
        }

        # Warning codes enum
        WARN_BASE = 0x3FFC0900
        self.warnings = {
            "PI620_WARNING_EEPROMCHECK":    WARN_BASE + 0x1,
            "PI620_WARNING_CALPARAMETER":   WARN_BASE + 0X2
        }

        # Trigger modes enum
        self.triggerModes = {
            "HIGH":             0x0,
            "LOW":              0x1,
            "POSEDGE":          0x2,
            "NEGEDGE":          0x3,
            "POSEDGESINGLE":    0x4,
            "NEGEDGESINGLE":    0x5,
            "CONT":             0x6
        }

        # Signal shape enum
        self.signalShapes = {
            "SINE":     0,
            "TRIANGLE": 1,
            "SQUARE":   2
        }

        # Instrument mode enum
        self.instrumentModes = {
            "CONFIGURE":    0,
            "GENERATE":     1
        }

        # Trigger source enum
        self.triggerSources = {
            "FRONT":    0,
            "PXI0":     1,
            "PXI1":     2,
            "PXI2":     3,
            "PXI3":     4,
            "PXI4":     5,
            "PXI5":     6,
            "PXI6":     7,
            "PXI7":     8,
            "PXI_STAR": 9
        }

    @staticmethod
    def stringToStr(inputString):
        """ Take a string passed to a function in Python 2 or Python 3 and convert to
            a C-friendly ASCII-type string """
        import sys

        # Check if using Python 2 or 3:
        if sys.version_info[0] < 3:
            if type(inputString) is str:
                return inputString
            if type(inputString) is unicode:
                return inputString.encode()
        else:
            if type(inputString) is bytes:
                return inputString
            elif type(inputString) is str:
                return inputString.encode()

    @staticmethod
    def pythonString(inputString):
        """ Ensure returned strings are native in Python 2 and Python 3 """
        import sys

        # Check for Python 2 or 3
        if sys.version_info[0] < 3:
            return inputString
        else:
            return inputString.decode()

    def __toResource(self, bus, device):
        resourceStringFormat = "PXI[bus]::[device]::INSTR"
        resourceStringFormat = resourceStringFormat.replace("[bus]", str(bus))
        resourceStringFormat = resourceStringFormat.replace("[device]", str(device))
        return resourceStringFormat

    def openCard(self, resource=None, cardNumber=None, idQuery=False, reset=False):
        """ Opens a card using either a resource string or a card number.
            If neither are passed, defaults to opening the first 41-620 card found. """

        # If no resource or card number are specified, open the first 41-620 found
        if resource is None and cardNumber is None:
            devices = self.findCards()

            if not devices:
                raise Error("Card not found")
            else:
                resourceString = devices[0]
                card = Pi620_Card(resourceString, idQuery, reset)
                return card

        # If a resource string is specified
        elif resource is not None:
            card = Pi620_Card(resource, idQuery, reset)
            return card

        # If a card number is specified
        elif cardNumber is not None:
            devices = self.findCards()

            try:
                resourceString = devices[cardNumber]
            except IndexError:
                raise Error("Card not found")

            card = Pi620_Card(resourceString, idQuery, reset)
            return card
        else:
            raise ValueError("Resource and cardNumber arguments are mutually exclusive")

    def findCards(self):
        """ pi620 function to discover compatible Function Generator cards
            returns a list of bus, device pairs where cards are found."""
        buslist = (c_uint32 * 100)()
        devicelist = (c_uint32 * 100)()
        count = c_uint32(0)

        error = self.handle.pi620_FindInstruments(byref(buslist), byref(devicelist), byref(count))

        instrumentList = []
        if int(count.value) == 0:
            return instrumentList
        else:
            for index in range(0, count.value):
                bus = buslist[index]
                device = devicelist[index]
                instrumentList.append(self.__toResource(bus, device))
            return instrumentList

    def __del__(self):
        del self.handle


class Pi620_Card(Pi_Base):
    """ Card class provides all card functionality """
    def __init__(self, resource, idQuery, reset):

        Pi_Base.__init__(self)

        # Sanitise resource string as bytes
        resource = self.stringToStr(resource)

        # ViSession handle
        self.vi = c_ulong(0)

        # Init pi620 driver
        error = self.handle.pi620_init(resource, idQuery, reset, byref(self.vi))
        self.__handleError(error)

    # Error/Session functions

    def close(self):
        error = self.handle.pi620_close(self.vi)
        self.__handleError(error)
        return

    def __handleError(self, error):
        """ Private method to raise exceptions based on error codes from driver. """
        if error:
            errorString = self.errorMessage(error)
            raise Error(errorString, errorCode=error)

    def errorMessage(self, code):
        """ Returns a string description from a given error code """
        errorString = create_string_buffer(100)
        error = self.handle.pi620_error_message(self.vi, code, byref(errorString))

        return self.pythonString(errorString.value)

    def getCalibrationDate(self):
        """ Returns date card was last calibrated """
        year = c_uint32()
        month = c_uint32()
        day = c_uint32()

        error = self.handle.pi620_GetCalibrationDate(self.vi, byref(year), byref(month), byref(day))
        self.__handleError(error)

        return int(year.value), int(month.value), int(day.value)

    def generateSignal(self, frequency, signalType, symmetry, startPhaseOffset=0.0, generate=True):
        frequency = c_double(frequency)
        symmetry  = c_double(symmetry)
        startPhaseOffset = c_double(startPhaseOffset)
        generate = c_bool(generate)

        error = self.handle.pi620_GenerateSignalEx(self.vi, frequency, signalType, symmetry, startPhaseOffset, generate)
        self.__handleError(error)
        return

    def generateSweep(self, signalType, symmetry, mode, startFrequency, endFrequency,
                            freqStepSize, freqStepTime):
        signalType = c_uint32(signalType)
        symmetry = c_double(symmetry)
        mode = c_uint32(mode)
        startFrequency = c_double(startFrequency)
        endFrequency = c_double(endFrequency)
        freqStepSize = c_double(freqStepSize)
        freqStepTime = c_double(freqStepTime)

        error = self.handle.pi620_GenerateSweep(self.vi,
                                                signalType,
                                                symmetry,
                                                mode,
                                                startFrequency,
                                                endFrequency,
                                                freqStepSize,
                                                freqStepTime)
        self.__handleError(error)
        return

    def getCardId(self):
        """ Returns card  ID """
        cardId = c_uint32(0)
        error = self.handle.pi620_GetCardId(self.vi, byref(cardId))
        self.__handleError(error)
        return int(cardId.value)

    def getOffsetCalCode(self, offset):
        code = c_uint32(0)
        offset = c_uint32(offset)

        error = self.handle.pi620_GetOffsetCalCode(self.vi, byref(code), offset)
        self.__handleError(error)
        return int(code.value)

    def getOutputOffsetCalVoltages(self):
        maxvolt = c_double(0)
        minvolt = c_double(0)

        error = self.handle.pi620_GetOutputOffsetCalVoltages(self.vi, byref(maxvolt), byref(minvolt))
        self.__handleError(error)
        return float(maxvolt.value), float(minvolt.value)

    def getRangeLimitVoltages(self):
        maxvolt = c_double(0)
        minvolt = c_double(0)

        error = self.handle.pi620_GetRangeLimitVoltages(self.vi, byref(maxvolt), byref(minvolt))
        self.__handleError(error)
        return float(maxvolt.value), float(minvolt.value)

    def loadArbitraryWaveform(self, waveform, repetitionRate=None):
        waveformlength = c_uint32(len(waveform))
        c_waveform = (c_double * len(waveform))(*waveform)

        if repetitionRate is None:
            error = self.handle.pi620_LoadArbitraryWaveform(self.vi, waveformlength, c_waveform)
        else:
            repetitionRate = c_double(repetitionRate)
            error = self.handle.pi620_LoadArbitraryWaveformEx(self.vi,
                                                              waveformlength,
                                                              byref(c_waveform),
                                                              repetitionRate)
        self.__handleError(error)
        return

    def memoryTest(self):
        erroraddress = c_uint32(0)
        errordata = c_uint32(0)
        expectdata = c_uint32(0)

        error = self.handle.pi620_MemoryTest(self.vi, byref(erroraddress), byref(errordata), byref(expectdata))
        self.__handleError(error)

        return int(erroraddress.value), int(errordata.value), int(expectdata.value)

    def readEeprom(self, eepromAddress):
        data = c_uint32(0)

        error = self.handle.pi620_ReadEeprom(self.vi, eepromAddress, byref(data))
        self.__handleError(error)
        return int(data.value)

    def readInstrumentMemory(self):
        data = c_uint32(0)

        error = self.handle.pi620_ReadInstrumentMemory(self.vi, byref(data))
        self.__handleError(error)
        return int(data.value)

    def readInstrumentMemoryArray(self, length):
        buf32 = (c_uint32 * length)

        error = self.handle.pi620_ReadInstrumentMemoryArray(self.vi, length, buf32)
        self.__handleError(error)
        return [int(data) for data in buf32]

    def readRegister(self, address):
        data = c_uint32(0)
        
        error = self.handle.pi620_ReadRegister(self.vi, address, byref(data))
        self.__handleError(error)
        return int(data.value)

    def reset(self):
        error = self.handle.pi620_reset(self.vi)
        self.__handleError(error)
        return

    def resetAddressCounter(self):
        error = self.handle.pi620_ResetAddressCounter(self.vi)
        self.__handleError(error)
        return

    def revisionQuery(self):
        driverRev = create_string_buffer(100)
        instrumentRev = create_string_buffer(100)

        error = self.handle.pi620_revision_query(self.vi, byref(driverRev), byref(instrumentRev))
        self.__handleError(error)
        return self.pythonString(driverRev), self.pythonString(instrumentRev)

    def selfTest(self):
        testResult = c_int16(0)
        errorMessage = create_string_buffer(100)

        error = self.handle.pi620_self_test(self.vi, byref(testResult), byref(errorMessage))
        self.__handleError(error)
        return int(testResult.value), self.pythonString(errorMessage)

    def setActiveChannel(self, channel):
        channel = c_uint32(channel)

        error = self.handle.pi620_SetActiveChannel(self.vi, channel)
        self.__handleError(error)
        return

    def setAMMode(self, amMode):
        amMode = c_uint32(amMode)

        error = self.handle.pi620_SetAMMode(self.vi, amMode);
        self.__handleError(error)
        return

    def setAttenuation(self, attenuation):
        attenuation = c_double(attenuation)

        error = self.handle.pi620_SetAttenuation(self.vi, attenuation)
        self.__handleError(error)
        return

    def setClockMode(self, mode, startFreq, endFreq, freqStep, freqStepTime):
        mode = c_uint32(mode)
        startFreq = c_double(startFreq)
        endFreq = c_double(endFreq)
        freqStep = c_double(freqStep)
        freqStepTime = c_double(freqStepTime)

        error = self.handle.pi620_SetClockMode(self.vi, mode, startFreq, endFreq, freqStep, freqStepTime)
        self.__handleError(error)
        return

    def setClockSource(self, clockSource, extClockFreq, clockMul):
        clockSource = c_uint32(clockSource)
        extClockFreq = c_double(extClockFreq)
        clockMul = c_uint32(clockMul)

        error = self.handle.pi620_SetClockSource(clockSource, extClockFreq, clockMul)
        self.__handleError(error)
        return

    def setCounterStep(self, counterStep):
        counterStep = c_uint32(counterStep)

        error = self.handle.pi620_SetCounterStep(self.vi, counterStep)
        self.__handleError(error)
        return

    def setFSKPin(self, state):
        state = c_uint32(state)

        error = self.handle.pi620_SetFSKPin(self.vi, state)
        self.__handleError(error)
        return

    def setFSKSource(self, source):
        source = c_uint32(source)

        error = self.handle.pi620_SetFSKSource(self.vi, source)
        self.__handleError(error)
        return

    def setInstrumentMode(self, mode):
        mode = c_uint32(mode)

        error = self.handle.pi620_SetInstrumentMode(self.vi, mode)
        self.__handleError(error)
        return

    def setLockMode(self, lock):
        lock = c_uint32(lock)
        error = self.handle.pi620_SetLockMode(self.vi, lock)
        self.__handleError(lock)
        return

    def setMainDacCode(self, code):
        code = c_uint32(code)

        error = self.handle.pi620_SetMainDacCode(self.vi, code)
        self.__handleError(error)
        return

    def setOffsetCalCode(self, code, offset):
        code = c_uint32(code)
        offset = c_uint32(offset)
        error = self.handle.pi620_SetOffsetCalCode(self.vi, code, offset)
        self.__handleError(error)
        return

    def setOutputOffsetCalVoltages(self, maxvolt, minvolt):
        maxvolt = c_double(maxvolt)
        minvolt = c_double(minvolt)

        error = self.handle.pi620_SetOutputOffsetCalVoltages(self.vi, maxvolt, minvolt)
        self.__handleError(error)
        return

    def setOutputOffsetDacCode(self, code, connect):
        code = c_uint32(code)
        connect = c_uint32(connect)

        error = self.handle.pi620_SetOutputOffsetDacCode(self.vi, code, connect)
        self.__handleError(error)
        return

    def setOutputOffsetVoltage(self, voltage, connect):
        voltage = c_double(voltage)
        connect = c_uint32(connect)

        error = self.handle.pi620_SetOutputOffsetVoltage(self.vi, voltage, connect)
        self.__handleError(error)
        return

    def setOutputVoltage(self, voltage, method):
        voltage = c_double(voltage)
        method = c_uint32(method)

        error = self.handle.pi620_SetOutputVoltage(self, voltage, method)
        self.__handleError(error)
        return

    def setRangeDacCode(self, code):
        code = c_uint32(code)
        error = self.handle.pi620_SetRangeDacCode(self.vi, code)
        self.__handleError(error)
        return

    def setRangeLimitVoltages(self, maxvolt, minvolt):
        maxvolt = c_double(maxvolt)
        minvolt = c_double(minvolt)

        error = self.handle.pi620_SetRangeLimitVoltages(self.vi, maxvolt, minvolt)
        self.__handleError(error)
        return

    def setSignal(self, signalType, amplitude, startPhase, symmetry):
        signalType = c_uint32(signalType)
        amplitude = c_double(amplitude)
        startPhase = c_double(startPhase)
        symmetry = c_double(symmetry)

        error = self.handle.pi620_SetSignal(self.vi, signalType, amplitude, startPhase, symmetry)
        self.__handleError(error)
        return

    def setTriggerMode(self, source, mode):
        source = c_uint32(source)
        mode = c_uint32(mode)

        error = self.handle.pi620_SetTriggerMode(self.vi, source, mode)
        self.__handleError(error)
        return

    def storeCalibrationData(self):
        error = self.handle.pi620_StoreCalibrationData(self.vi)
        self.__handleError(error)
        return

    def writeCalibrationDate(self, year, month, day):
        error = self.handle.pi620_WriteCalibrationDate(self.vi, year, month, day)
        self.__handleError(error)
        return

    def writeEeprom(self, eepromAddress, data):
        eepromAddress = c_uint32(eepromAddress)
        data = c_uint32(data)

        error = self.handle.pi620_WriteEeprom(self.vi, eepromAddress, data)
        self.__handleError(error)
        return

    def writeCardId(self, cardId):
        cardId = c_uint32(cardId)

        error = self.handle.pi620_WriteCardId(self.vi, cardId)
        self.__handleError(error)
        return

    def writeInstrumentMemory(self, data):
        data = c_uint32(data)

        error = self.handle.pi620_WriteInstrumentMemory(self.vi, data)
        self.__handleError(error)
        return

    def writeInstrumentMemoryArray(self, array):
        length = c_uint32(len(array))
        buf32 = (c_uint32 * len(array))(*array)

        error = self.handle.pi620_WriteInstrumentMemoryArray(self.vi, length, byref(buf32))
        self.__handleError(error)
        return

    def WriteRegister(self, address, data):
        address = c_uint32(address)
        data = c_uint32(data)

        error = self.handle.pi620_WriteRegister(self.vi, address, data)
        self.__handleError(error)
        return

    def prepareChannelForSoftTrigger(self, source):
        source = c_uint32(source)

        error = self.handle.pi620_PrepareChannelForSoftTrigger(self.vi, source)
        self.__handleError(error)
        return

    def launchSoftTrigger(self, source):
        source = c_uint32(source)

        error = self.handle.pi620_LaunchSoftTrigger(self.vi, source)
        self.__handleError(error)
        return

    def clearSoftTrigger(self, source):
        source = c_uint32(source)

        error = self.handle.pi620_ClearSoftTrigger(self.vi, source)
        self.__handleError(error)
        return

    def setSoftTriggerStatus(self, source, enable, status):
        source = c_uint32(source)
        enable = c_bool(enable)
        status = c_bool(status)

        error = self.handle.pi620_SetSoftTriggerStatus(self.vi, source, enable, status)
        self.__handleError(error)
        return

    def getSoftTriggerStatus(self, source):
        source = c_uint32(source)
        enabled = c_bool(0)
        status  = c_bool(0)

        error = self.handle.pi620_GetSoftTriggerStatus(self.vi, source, byref(enabled), byref(status))
        self.__handleError(error)
        return

    def readWaveformFromFile(self, filename):
        with open(filename) as f:
            content = f.readlines()
            content = [float(line) for line in content]
        return content

    def outputOff(self):
        error = self.handle.pi620_OutputOff(self.vi)
        self.__handleError(error)
        return

    def outputOn(self):
        error = self.handle.pi620_OutputOn(self.vi)
        self.__handleError(error)
        return
