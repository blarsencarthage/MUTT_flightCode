from sys import version_info
import ctypes
import platform

__version__ = "1.1.0"

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
                self.handle = ctypes.windll.LoadLibrary("Pi743lx_w64")

            else:
                self.handle = ctypes.windll.LoadLibrary("Pi743lx_w32")

        elif platform.system() == "Darwin":
            self.handle = ctypes.cdll.LoadLibrary("Bin/libpi743lx.so")

        elif platform.system() == "Linux":
            self.handle = ctypes.cdll.LoadLibrary("libpi743lx.so")

        self.pythonMajorVersion = version_info[0]

        self.ConnectionStatus = {
            "CON_DISCONNECT": 0,
            "CON_2WIRE_INTERNAL": 1,
            "CON_4WIRE_EXTERNAL": 2
        }

        self.OverCurrentStatus = {
            "OC_STAT_NOOC": 0,
            "OC_STAT_OCPENDING": 1,
            "OC_STAT_OCLATCHED": 2,
            "PI743LX_OC_STAT_OCLATCHPEND": 3
        }

        self.TriggerSource = {
            "TRIG_SRC_NOTRIG": 0,
            "TRIG_SRC_FRONT": 1,
            "TRIG_SRC_SOFTWARE": 2,
            "TRIG_SRC_PXI0": 3,
            "TRIG_SRC_PXI1": 4,
            "TRIG_SRC_PXI2": 5,
            "TRIG_SRC_PXI3": 6,
            "TRIG_SRC_PXI4": 7,
            "TRIG_SRC_PXI5": 8,
            "TRIG_SRC_PXI6": 9,
            "TRIG_SRC_PXI7": 10,
            "TRIG_SRC_PXISTAR": 11
        }

        self.TriggerAction = {
            "TRIG_ACT_NOACT"
            "TRIG_ACT_VC_UPDATE"
            "TRIG_ACT_V_CAPTURE"
            "TRIG_ACT_C_CAPTURE"
            "TRIG_ACT_V_UPDATE_CAPTURE"
            "TRIG_ACT_C_UPDATE_CAPTURE"
        }

        self.TriggerLevel = {
            "PI743LX_TRIG_LVL_LOW": 0,
            "PI743LX_TRIG_LVL_HIGH": 1
        }

        self.TriggerMode = {
            "PI743LX_TRIG_MODE_EDGE": 0,
            "PI743LX_TRIG_MODE_LEVEL": 1
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

    def _handleError(self, error):
        """ Private method to raise exceptions based on error codes from driver. """
        if error:
            errorString = self.errorMessage(error)
            raise Error(errorString, errorCode=error)

    def errorMessage(self, code):
        """ Returns a string description from a given error code """
        errorString = ctypes.create_string_buffer(100)
        error = self.handle.PI743LX_ErrorCodeToMessage(self.session, int(code), ctypes.byref(errorString))
        return self._pythonString(errorString.value)

    def openCard(self, resource=None, idQuery=True, reset=True):

        # If no resource is provided open the first card found
        if resource is None:

            resources = self.findInstrumentsRsrc()

            try:
                card = Card(self.session, resources[0], idQuery, reset)
            except IndexError:
                raise Error("No 41-743 card found")

        else:
            card = Card(self.session, resource, idQuery, reset)

        return card

    def findInstrumentsRsrc(self):

        count = ctypes.c_uint32(50)
        buslist = (ctypes.c_uint32 * 50)()
        devicelist = (ctypes.c_uint32 * 50)()

        err = self.handle.PI743LX_FindInstruments(self.session,
                                                  ctypes.byref(buslist),
                                                  ctypes.byref(devicelist),
                                                  ctypes.byref(count))
        self._handleError(err)

        resources = []

        for i in range(0, count.value):
            resources.append("PXI{}::{}::INSTR".format(buslist[i], devicelist[i]))

        return resources

    def getVersion(self):

        version = ctypes.c_uint32()
        self.handle.PI743LX_GetVersion(ctypes.byref(version))

        return version.value

    def getVersionString(self):

        versionString = ctypes.create_string_buffer(100)
        err = self.handle.PI743LX_GetVersionString(ctypes.byref(versionString), 100)

        return self._pythonString(versionString.value)

    def getLastErrorCode(self):

        errorCode = ctypes.c_uint32()
        err = self.handle.PI743LX_GetLastErrorCode(self.session, ctypes.byref(errorCode))

        return errorCode.value

    def version(self):

        version = ctypes.c_uint32()

        err = self.handle.PI743LX_Version(self.session, ctypes.byref(version))
        self._handleError(err)

        return version.value


class Card(Base):
    def __init__(self, session, resource, idQuery, reset):
        Base.__init__(self, 0)

        self.session = session
        self.disposed = True

        # Card handle
        self.vi = ctypes.c_uint32(0)

        resource = self._stringToStr(resource)
        err = self.handle.PI743LX_init(self.session,
                                       resource,
                                       bool(idQuery),
                                       bool(reset),
                                       ctypes.byref(self.vi))

        self._handleError(err)

    def __del__(self):
        if not self.disposed:
            self.close()
        return

    def close(self):
        self.disposed = True
        err = self.handle.PI743LX_close(self.session, self.vi)
        self._handleError(err)

        return

    def clearOverCurrentStatus(self):
        err = self.handle.PI743LX_ClearOverCurrentStatus(self.session, self.vi)
        self._handleError(err)

        return

    def clearTriggerStatus(self):
        err = self.handle.PI743LX_ClearTriggerStatus(self.session, self.vi)
        self._handleError(err)

        return

    def getAddressCounter(self):
        addressCounter = ctypes.c_uint32()
        err = self.handle.PI743LX_GetAddressCounter(self.session, self.vi, ctypes.byref(addressCounter))
        self._handleError(err)

        return addressCounter.value

    def getClockDivider(self):
        divider = ctypes.c_uint32()

        err = self.handle.PI743LX_GetClockDivider(self.session, self.vi, ctypes.byref(divider))
        self._handleError(err)

        return divider.value

    def getMeasuredOutputCurrent(self):
        current = ctypes.c_double()

        err = self.handle.PI743LX_GetMeasuredOutputCurrent(self.session, self.vi, ctypes.byref(current))
        self._handleError(err)

        return current.value

    def getMeasuredOutputVoltage(self):
        voltage = ctypes.c_double()

        err = self.handle.PI743LX_GetMeasuredOutputVoltage(self.session, self.vi, ctypes.byref(voltage))
        self._handleError(err)

        return voltage.value

    def getOutputAll(self):
        """Returns voltage, current, power, connection status"""

        voltage = ctypes.c_double()
        current = ctypes.c_double()
        power = ctypes.c_double()
        connectionStatus = ctypes.c_uint32()

        err = self.handle.PI743LX_GetOutputAll(self.session,
                                               self.vi,
                                               ctypes.byref(voltage),
                                               ctypes.byref(current),
                                               ctypes.byref(power),
                                               ctypes.byref(connectionStatus))

        self._handleError(err)

        return voltage.value, current.value, power.value, connectionStatus.value

    def getOutputConnection(self):
        connectionStatus = ctypes.c_uint32()

        err = self.handle.PI743LX_GetOutputConnection(self.session, self.vi, ctypes.byref(connectionStatus))
        self._handleError(err)

        return connectionStatus.value

    def getOutputCurrentLimit(self):
        current = ctypes.c_double()

        err = self.handle.PI743LX_GetOutputCurrentLimit(self.session, self.vi, ctypes.byref(current))
        self._handleError(err)

        return current.value

    def getOutputVoltage(self):
        voltage = ctypes.c_double()

        err = self.handle.PI743LX_GetOutputVoltage(self.session, self.vi, ctypes.byref(voltage))
        self._handleError(err)

        return voltage.value

    def getOverCurrentStatus(self):
        overcurrent = ctypes.c_uint32()

        err = self.handle.PI743LX_GetOverCurrentStatus(self.session, self.vi, ctypes.byref(overcurrent))
        self._handleError(err)

        return overcurrent.value

    def getPowerSupplyStatus(self):
        PSUstatus = ctypes.c_uint32()

        err = self.handle.PI743LX_GetPowerSupplyStatus(self.session, self.vi, ctypes.byref(PSUstatus))
        self._handleError(err)

        return PSUstatus.value

    def getTrigger(self):
        source = ctypes.c_uint32()
        action = ctypes.c_uint32()
        level = ctypes.c_uint32()
        mode = ctypes.c_uint32()

        err = self.handle.PI743LX_GetTrigger(self.session,
                                             self.vi,
                                             ctypes.byref(source),
                                             ctypes.byref(action),
                                             ctypes.byref(level),
                                             ctypes.byref(mode))
        self._handleError(err)

        return source.value, action.value, level.value, mode.value

    def getTriggerCurrent(self):
        current = ctypes.c_double()

        err = self.handle.PI743LX_GetTriggerCurrent(self.session, self.vi, ctypes.byref(current))
        self._handleError(err)

        return current.value

    def getTriggerStatus(self):
        status = ctypes.c_uint32()

        err = self.handle.PI743LX_GetTriggerStatus(self.session, self.vi, ctypes.byref(status))
        self._handleError(err)

        return status.value

    def getTriggerVoltage(self):
        voltage = ctypes.c_double()

        err = self.handle.PI743LX_GetTriggerVoltage(self.session, self.vi, ctypes.byref(voltage))
        self._handleError(err)

        return voltage.value

    def memoryTest(self, logsize):
        errorAddress = (ctypes.c_uint32 * logsize)()
        errorData = (ctypes.c_uint32 * logsize)()
        expectData = (ctypes.c_uint32 * logsize)()
        foundErrors = (ctypes.c_uint32 * logsize)()
        logsize = ctypes.c_uint32(logsize)

        err = self.handle.PI743LX_MemoryTest(self.session,
                                             self.vi,
                                             logsize,
                                             ctypes.byref(errorAddress),
                                             ctypes.byref(errorData),
                                             ctypes.byref(expectData),
                                             ctypes.byref(foundErrors))
        self._handleError(err)

        return [e.value for e in errorAddress], [e.value for e in errorData], [e.value for e in expectData], [e.value for e in foundErrors]

    def readCapturedCurrent(self, count):

        current = (ctypes.c_double * count)()
        count = ctypes.c_uint32(count)

        err = self.handle.PI743LX_ReadCapturedCurrent(self.session, self.vi, ctypes.byref(current), count)
        self._handleError(err)

        return [c.value for c in current]

    def readCapturedVoltage(self, count):

        voltages = (ctypes.c_double * count)()
        count = ctypes.c_uint32(count)

        err = self.handle.PI743LX_ReadCapturedVoltage(self.session, self.vi, ctypes.byref(voltages), count)
        self._handleError(err)

        return [v.value for v in voltages]

    def readCurrentCalValues(self):

        offsetCurrentcdac = ctypes.c_double()
        gainCurrentcdac = ctypes.c_double()
        offsetCodecdac = ctypes.c_uint32()
        gainCodecdac = ctypes.c_uint32()

        err = self.handle.PI743LX_ReadCurrentCalValues(self.session,
                                                       self.vi,
                                                       ctypes.byref(offsetCurrentcdac),
                                                       ctypes.byref(gainCurrentcdac),
                                                       ctypes.byref(offsetCodecdac),
                                                       ctypes.byref(gainCodecdac))
        self._handleError(err)

        return offsetCurrentcdac.value, gainCurrentcdac.value, offsetCodecdac.value, gainCodecdac.value

    def readID(self):

        id = ctypes.c_uint32()

        err = self.handle.PI743LX_ReadID(self.session, self.vi, ctypes.byref(id))
        self._handleError(err)

        return id.value

    def readMaximumPower(self):

        power = ctypes.c_double()

        err = self.handle.PI743LX_ReadMaximumPower(self.session, self.vi, ctypes.byref(power))
        self._handleError(err)

        return power.value

    def readVoltageCalValues(self):

        offsetVoltagevdac = ctypes.c_double()
        gainVoltagevdac = ctypes.c_double()
        offsetCodevadc = ctypes.c_uint32()
        gainCodevadc = ctypes.c_uint32()

        err = self.handle.PI743LX_ReadVoltageCalValues(self.session,
                                                       self.vi,
                                                       ctypes.byref(offsetVoltagevdac),
                                                       ctypes.byref(gainVoltagevdac),
                                                       ctypes.byref(offsetCodevadc),
                                                       ctypes.byref(gainCodevadc))
        self._handleError(err)

        return offsetVoltagevdac.value, gainVoltagevdac.value, offsetCodevadc.value, gainCodevadc.value

    def reset(self):

        err = self.handle.PI743LX_reset(self.session, self.vi)
        self._handleError(err)

        return

    def selfTest(self):

        testResult = ctypes.c_bool()
        errorMessageSize = ctypes.c_uint32(1024)
        errorMessage = ctypes.create_string_buffer(errorMessageSize.value)

        err = self.handle.PI743LX_self_test(self.session,
                                            self.vi,
                                            ctypes.byref(testResult),
                                            ctypes.byref(errorMessage),
                                            errorMessageSize)
        self._handleError(err)

        return testResult.value, self._pythonString(errorMessage.value)

    def setAddressCounter(self, addressCounter):

        addressCounter = ctypes.c_uint32(addressCounter)

        err = self.handle.PI743LX_SetAddressCounter(self.session, self.vi, addressCounter)
        self._handleError(err)

        return

    def setClockDivider(self, divider):

        divider = ctypes.c_uint32(divider)

        err = self.handle.PI743LX_SetClockDivider(self.session, self.vi, divider)
        self._handleError(err)

        return

    def setOutputAll(self, voltage, current, power, connection):

        voltage = ctypes.c_double(voltage)
        current = ctypes.c_double(current)
        power = ctypes.c_double(power)
        connection = ctypes.c_uint32(connection)

        err = self.handle.PI743LX_SetOutputAll(self.session, self.vi, voltage, current, power, connection)
        self._handleError(err)

        return

    def setOutputConnection(self, connection):

        connection = ctypes.c_uint32(connection)

        err = self.handle.PI743LX_SetOutputConnection(self.session, self.vi, connection)
        self._handleError(err)

        return

    def setOutputCurrentLimit(self, currentLimit):

        currentLimit = ctypes.c_double(currentLimit)

        err = self.handle.PI743LX_SetOutputCurrentLimit(self.session, self.vi, currentLimit)
        self._handleError(err)

        return

    def setOutputVoltage(self, voltage):

        voltage = ctypes.c_double(voltage)

        err = self.handle.PI743LX_SetOutputVoltage(self.session, self.vi, voltage)
        self._handleError(err)

        return

    def setPowerSupplyStatus(self, status):

        status = ctypes.c_uint32(status)

        err = self.handle.PI743LX_SetPowerSupplyStatus(self.session, self.vi, status)
        self._handleError(err)

        return

    def setSoftwareTrigger(self):

        err = self.handle.PI743LX_SetSoftwareTrigger(self.session, self.vi)
        self._handleError(err)

        return

    def setTrigger(self, source, action, level, mode):

        source = ctypes.c_uint32(source)
        action = ctypes.c_uint32(action)
        level = ctypes.c_uint32(level)
        mode = ctypes.c_uint32(mode)

        err = self.handle.PI743LX_SetTrigger(self.session, self.vi, source, action, level, mode)
        self._handleError(err)

        return

    def setTriggerCurrent(self, current):

        current = ctypes.c_double(current)

        err = self.handle.PI743LX_SetTriggerCurrent(self.session, self.vi, current)
        self._handleError(err)

        return

    def setTriggerVoltage(self, voltage):

        voltage = ctypes.c_double(voltage)

        err = self.handle.PI743LX_SetTriggerVoltage(self.session, self.vi, voltage)
        self._handleError(err)

        return

    def storeCurrentCalValues(self, offsetCurrent, gainCurrent, offsetCode, gainCode):

        offsetCurrent = ctypes.c_double(offsetCurrent)
        gainCurrent = ctypes.c_double(gainCurrent)
        offsetCode = ctypes.c_uint32(offsetCode)
        gainCode = ctypes.c_uint32(gainCode)

        err = self.handle.PI743LX_StoreCurrentCalValues(self.session,
                                                        self.vi,
                                                        offsetCurrent,
                                                        gainCurrent,
                                                        offsetCode,
                                                        gainCode)
        self._handleError(err)

        return

    def storeVoltageCalValues(self, offsetVoltage, gainVoltage, offsetCode, gainCode):

        offsetVoltage = ctypes.c_double(offsetVoltage)
        gainVoltage = ctypes.c_double(gainVoltage)
        offsetCode = ctypes.c_uint32(offsetCode)
        gainCode = ctypes.c_uint32(gainCode)

        err = self.handle.PI743LX_StoreVoltageCalValues(self.session,
                                                        self.vi,
                                                        offsetVoltage,
                                                        gainVoltage,
                                                        offsetCode,
                                                        gainCode)
        self._handleError(err)

        return

    def writeMaximumPower(self, power):

        power = ctypes.c_double(power)

        err = self.handle.PI743LX_WriteMaximumPower(self.session, self.vi, power)
        self._handleError(err)

        return

    def isStabilized(self):

        stabilized = ctypes.c_bool()

        err = self.handle.PI743LX_IsStabilized(self.session, self.vi, ctypes.byref(stabilized))
        self._handleError(err)

        return

    def waitForStabilized(self, timeout):

        timeout = ctypes.c_uint32(timeout)

        err = self.handle.PI743LX_WaitForStabilized(self.session, self.vi, timeout)
        self._handleError(err)

        return

    def writeMemory(self, memoryData):

        dataLength = ctypes.c_uint32(len(memoryData))
        memoryData = (ctypes.c_double * len(memoryData))(*memoryData)

        err = self.handle.PI743LX_WriteMemory(self.session, self.vi, memoryData, dataLength)
        self._handleError(err)

        return










