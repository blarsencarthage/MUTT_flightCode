# -*- coding: utf-8 -*-
"""Python2 and Python3 wrapper for ClientBridge Power Sequencer API"""

import ctypes
import platform

class Error(Exception):
    def __init__(self, message, errorCode=None):
        self.message = message
        self.errorCode = errorCode

    def __str__(self):
        return self.message

PI_WRAP_PIPSLX_VERSION = "1.1.1"
"""Wrapper version definition"""

TIME_STOP = 0
"""Stop time - ms"""
TIME_START = 1
"""Startup time - ms"""
SEQUENCE_START = 1
"""Startup sequence"""
SEQUENCE_STOP = 0
"""Stop sequence"""

# enum: PipslxErrorCodes: Power sequencer error codes.
ER_PIPSLX_INVALID_SESSION = 0x3001
"""Session ID is invalid => !!! Do not use it anymore !!!Replaced by ER_PICMLX_INVALID_SESSION. """

ER_PIPSLX_FUNC_NOT_LOCAL = 0x3002
"""Function not supported on localhost."""

ER_PIPSLX_NOT_CONNECTED = 0x3003
"""You are not connected to remote host."""

ER_PIPSLX_NOT_INIT = 0x3004
"""Library wasn't initialized!"""

ER_PIPSLX_SWITCH_FAULT = 0x3005
"""Switch fault."""

ER_PIPSLX_BAD_FORMAT_DATA = 0x3006
"""Data or command format is bad."""

ER_PIPSLX_UNKNOWN_CMD = 0x3007
"""Unknown command."""

ER_PIPSLX_BUSY = 0x3008
"""Busy."""

ER_PIPSLX_SEQUPINPROGRESS = 0x3009
"""Up sequence is in progress."""

ER_PIPSLX_SEQDOWNINPROGRESS = 0x300a
"""Down sequence is in progress."""

ER_PIPSLX_CHANTESTINPROGRESS = 0x300b
"""Channel test is running."""

ER_PIPSLX_EMERGENCY_STOP = 0x300c
"""Emergency stop button engaged."""

ER_PIPSLX_PARAM_SIZE = 0x300d
"""Parametr is NULL or size is invalid."""
# End of enum: PipslxErrorCodes


class Pipslx:
    """
    Wrapper for ``Pipslx_wxx.dll`` Power Sequencer library and header ``Pipslx.h``
    """

    def __init__(self, sessionID, openForRead=False):
        """
        Pipslx wrapper constructor - initializes PIPSLX instance.

        :param sessionID: ClientBridge session id obtained from ``Pi_Session.GetSessionID()``
        """
        self._sid = sessionID
        self.disposed = False

        if platform.system() == "Windows":
            arch = platform.architecture()
            if "64bit" in arch:
                self.handleSLX = ctypes.windll.LoadLibrary("Pipslx_w64")
            else:
                self.handleSLX = ctypes.windll.LoadLibrary("Pipslx_w32")
        # MacOS/Linux not tested
        elif platform.system() == "Darwin":
            self.handleSLX = ctypes.cdll.LoadLibrary("Bin/libpipslx.so")
        elif platform.system() == "Linux":
            self.handleSLX = ctypes.cdll.LoadLibrary("libpipslx.so")

        from sys import version_info
        self.pythonMajorVersion = version_info[0]

        if openForRead:
            self.open_for_read()
        else:
            self.open()

    def __del__(self):
        if not self.disposed:
            self.close()

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

    def get_last_error_code(self):
        """Returns last occurred error code.

        :return: ``[last_err]`` where are:

            - last error in ``last_err``.

        :rtype:  int
        """
        last_err = ctypes.c_uint()

        err = self.handleSLX.PIPSLX_GetLastErrorCode(self._sid, ctypes.byref(last_err))
        return int(last_err.value)

    def get_last_error_message(self):
        """Returns last occurred error as a message

        :return: ``[err_msg]``  - where:

            - ``err_msg`` - last error message (if ``err`` is ``0``)

        :rtype: str
        """
        err_msg_size = ctypes.c_uint(1024)
        err_msg = ctypes.create_string_buffer(err_msg_size.value)
        err = self.handleSLX.PIPSLX_GetLastErrorMessage(self._sid, ctypes.byref(err_msg), err_msg_size)
        return self._pythonString(err_msg.value)

    def error_code_to_message(self, err_code):
        """Convert error code to a message.

        :param err_code: error code to convert into message
        :type err_code: ``int``
        :returns: ``[err_msg]`` where:

            - ``err_msg`` error message corresponding to ``err_code`` parameter (if ``err`` is ``0``)

        :rtype: str
        """
        err_msg_size = ctypes.c_uint(1024)
        err_msg = ctypes.create_string_buffer(err_msg_size.value)
        err = self.handleSLX.PIPSLX_ErrorCodeToMessage(err_code, ctypes.byref(err_msg), err_msg_size)
        return self._pythonString(err_msg.value)

    def is_error(self):
        """Returns True if an error occurred on last call or False if none

        :return: True if error occurred
        :rtype: ``bool``
        """
        is_err = self.handleSLX.PIPSLX_IsError(self._sid)
        ret = False
        if is_err != 0:
            ret = True
        return ret

    def _handlePIPSLXError(self, error):
        """Internal method to raise exceptions based on error codes from piplx."""
        if error:
            errorString = self.error_code_to_message(error)
            raise Error(errorString, errorCode=error)
        return

    def get_version(self):
        """Returns a version of library ``Pipslx_wXX.dll``

        :return: library version as integer, for example ``133`` means PIPSLX library version ``1.3.3``
        :rtype: int
        """
        return self.handleSLX.PIPSLX_GetVersion()

    def get_wrapper_version(self):
        """Returns a version of this wrapper for library ``Pipslx_wXX.dll``

        :return: wrapper version as string, for example ``1.1.0``
        :rtype: str
        """
        return PI_WRAP_PIPSLX_VERSION

    def open(self):
        """Opens power sequencer session for full access mode.

        This function should be the 1st to be called after constructor.

        """
        err = self.handleSLX.PIPSLX_Open(self._sid)
        self._handlePIPSLXError(err)
        return

    def open_for_read(self):
        """Opens power sequencer session for getting information mode only.

        This function should be the 1st to be called after constructor.
        """
        err = self.handleSLX.PIPSLX_OpenForRead(self._sid)
        self._handlePIPSLXError(err)
        return

    def close(self):
        """
        Closes Power Sequencer Session.
        """
        self.disposed = True
        err = self.handleSLX.PIPSLX_Close(self._sid)
        return

    def get_chan_state(self, channel):
        """Returns state of specified channel.

        :param channel: channel number (1-based) to query state
        :type channel: ``int``
        :return: ``[state]`` - channel state (``0`` = Off, ``1`` = On)
        :rtype: int
        """
        channel = ctypes.c_uint32(channel)
        out_state = ctypes.c_int()
        err = self.handleSLX.PIPSLX_GetChanState(self._sid, channel, ctypes.byref(out_state))
        self._handlePIPSLXError(err)
        return out_state.value

    def set_chan_state(self, channel, state):
        """Sets channel state. Turn on or turn off a channel.

        :param channel: Index of channel - 1-based
        :type channel: ``int``
        :param state: use ``1`` to ``Power On`` channel or ``0`` to ``Power Off``
        :type state: ``int``
        """
        channel = ctypes.c_uint32(channel)
        state = ctypes.c_bool(state)
        err = self.handleSLX.PIPSLX_SetChanState(self._sid, channel, state)
        self._handlePIPSLXError(err)
        return

    def get_chan_time(self, channel, time_type):
        """Return channel time delay in ms.

        :param channel: channel number (1-based)
        :type channel: ``int``
        :param time_type: ``TIME_STOP`` (0) for down sequence, ``TIME_START`` (1) for up sequence, constants `
        :type  time_type: ``int``
        :return: time_delay - time_delay in ms for given chan,time_type
        :rtype: int
        """
        channel = ctypes.c_uint32(channel)
        time_type = ctypes.c_uint32(time_type)
        time_delay = ctypes.c_uint()
        time_type = ctypes.c_uint(time_type)
        err = self.handleSLX.PIPSLX_GetChanTime(self._sid, channel, time_type, ctypes.byref(time_delay))
        self._handlePIPSLXError(err)
        return time_delay.value

    def set_chan_time(self, channel, time_type, time_delay):
        """Set channel time in Power sequence.

        :param channel: channel number (1-based)
        :type channel: ``int``
        :param time_type: ``TIME_STOP`` (0) for down sequence, ``TIME_START`` (1) for up sequence, constants `
        :type time_type: ``int``
        :param time_delay: time delay in ms
        :type time_delay: ``int``
        """
        channel = ctypes.c_uint32(channel)
        time_type = ctypes.c_uint32(time_type)
        time_delay = ctypes.c_uint32(time_delay)
        err = self.handleSLX.PIPSLX_SetChanTime(self._sid, channel, time_type, time_delay)
        self._handlePIPSLXError(err)
        return

    def get_chan_enabled(self, channel):
        """
        Retrieves information if channel is or isn't in sequence.

        :param channel: Index of channel (1-based)
        :type channel: ``int``
        :return: ``[enabled]`` - channel state (True or False)
        :rtype: ``[bool]``
        """
        enabled_dword = ctypes.c_uint()
        channel = ctypes.c_uint32(channel)
        err = self.handleSLX.PIPSLX_GetChanEnabled(self._sid, channel, ctypes.byref(enabled_dword))
        self._handlePIPSLXError(err)
        enabled = False
        if enabled_dword.value != 0:
            enabled = True
        return enabled

    def set_chan_enabled(self, channel, enabled):
        """Puts or removes channel in/from sequence.

        :param channel: Index of channel
        :type channel: ``int``
        :param enabled: ``True`` = channel will be in sequence, ``False`` it won't.
        :type enabled: ``bool``
        """
        channel = ctypes.c_uint32(channel)
        enabled_dword = ctypes.c_uint(0)
        if enabled:
            enabled_dword.value = 1
        err = self.handleSLX.PIPSLX_SetChanEnabled(self._sid, channel, enabled_dword)
        self._handlePIPSLXError(err)
        return

    def chan_test(self):
        """ Testing all channels. Return value is an array of channel indexes which have a hardware problem.
        """
        bad_chans_len = ctypes.c_uint(100)
        bad_chans = (ctypes.c_uint * bad_chans_len.value)()
        err = self.handleSLX.PIPSLX_ChanTest(self._sid, ctypes.byref(bad_chans), ctypes.byref(bad_chans_len))
        self._handlePIPSLXError(err)

        chan_list = []
        for i in range(0, bad_chans_len.value):
            chan_list.append(bad_chans[i].value)
        return chan_list

    def sequence(self, sequence_type):
        """Start a up or down sequence.

        :param sequence_type: one of ``SEQUENCE_START`` or ``SEQUENCE_STOP`` for Power-Up or Power-Down sequence
        :type sequence_type: ``int``
        """

        sequence_type = ctypes.c_uint32(sequence_type)
        err = self.handleSLX.PIPSLX_Sequence(self._sid, sequence_type)
        self._handlePIPSLXError(err)
        return

    def settle_time(self):
        """Get a relay settling time for all relays.
        """
        settle_time = ctypes.c_uint(0)
        err = self.handleSLX.PIPSLX_SettleTime(self._sid, ctypes.byref(settle_time))
        self._handlePIPSLXError(err)
        return settle_time.value

    def shutdown(self):
        """Emergency down power sequencer without sequence times.
        """
        err = self.handleSLX.PIPSLX_Shutdown(self._sid)
        self._handlePIPSLXError(err)
        return

    def get_chan_count(self):
        """Returns number of available channels.

        :return: number of available channels
        :rtype: int
        """
        chan_count = ctypes.c_uint()
        err = self.handleSLX.PIPSLX_GetChanCount(self._sid, ctypes.byref(chan_count))
        self._handlePIPSLXError(err)
        return chan_count.value

    @property
    def sid(self):
        """
        Returns ClientBridge session id (used by most objects/functions).

        :return: session id
        :rtype: int
        """
        return self._sid.value
