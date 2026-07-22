"""RS422 — threaded RS-422 serial listener with named signal detection.

Usage
-----
    from RS422 import RS422

    listener = RS422(port="COM3", baud=9600)
    listener.addSignal("launch",  b"START", returnValue="LAUNCH")
    listener.addSignal("abort",   b"ABORT", returnValue="ABORT")
    listener.addSignal("standby", b"STBY",  returnValue="STANDBY")

    listener.start()

    while True:
        result = listener.detected("launch")
        if result:
            print(f"Launch signal received, value: {result}")   # "LAUNCH"

        result = listener.detected("abort")
        if result:
            print(f"Abort signal received, value: {result}")    # "ABORT"

    listener.stop()

    # Or use as a context manager:
    with RS422(port="COM3") as listener:
        listener.addSignal("launch", b"START", returnValue="LAUNCH")
        ...
"""

import time
import queue
import logging
import threading
from typing import Any, Dict, Optional, Tuple
import serial  # pip install pyserial

log = logging.getLogger("rs422")


class RS422:
    """Threaded RS-422 listener that watches for user-defined byte patterns.

    Each registered signal has a name and a byte pattern. Call detected(name)
    to check (and consume) whether that pattern has arrived since the last call.

    Two internal threads keep serial reads decoupled from pattern scanning so
    slow handling code never causes bytes to be dropped from the OS UART buffer.
    """

    def __init__(
        self,
        port: str = "COM3",
        baud: int = 9600,
        bytesize: int = 8,
        parity: str = serial.PARITY_NONE,
        stopbits: int = 1,
        readTimeout: float = 0.5,
        reconnectDelay: float = 2.0,
        maxBuffer: int = 4096,
    ):
        self.port            = port
        self.baud            = baud
        self.bytesize        = bytesize
        self.parity          = parity
        self.stopbits        = stopbits
        self.readTimeout     = readTimeout
        self.reconnectDelay  = reconnectDelay
        self.maxBuffer       = maxBuffer

        # name -> (pattern, returnValue, threading.Event)
        # Event is set when the pattern is found; detected() clears it and returns returnValue.
        self._signals: Dict[str, Tuple[bytes, Any, threading.Event]] = {}
        self._signalsLock = threading.Lock()

        self._chunkQ: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._readerThread    = None
        self._processorThread = None

    # ------------------------------------------------------------------
    # Signal registration
    # ------------------------------------------------------------------

    def addSignal(self, name: str, pattern: bytes, returnValue: Any = True) -> None:
        """Register a named byte pattern to watch for.

        returnValue is what detected(name) returns when the pattern is found.
        Defaults to True so existing boolean checks still work unchanged.
        Can be called before or after start().
        """
        if not pattern:
            raise ValueError("pattern must be a non-empty bytes object")
        with self._signalsLock:
            self._signals[name] = (pattern, returnValue, threading.Event())
        log.debug("Signal added: %r = %r -> %r", name, pattern, returnValue)

    def removeSignal(self, name: str) -> None:
        """Unregister a previously added signal."""
        with self._signalsLock:
            self._signals.pop(name, None)
        log.debug("Signal removed: %r", name)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def detected(self, name: str) -> Optional[Any]:
        """Return the signal's returnValue if it arrived since the last call, then reset.

        Returns None if the signal has not been seen or the name is unknown.
        This is a consume-once read: calling it twice in a row without a new
        arrival returns the value then None.
        """
        with self._signalsLock:
            entry = self._signals.get(name)
        if entry is None:
            return None
        _, returnValue, event = entry
        if event.is_set():
            event.clear()
            return returnValue
        return None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start reader and processor threads. Safe to call only once."""
        if self._readerThread and self._readerThread.is_alive():
            return
        self._stop.clear()
        self._readerThread = threading.Thread(
            target=self._reader, daemon=True, name="rs422-reader"
        )
        self._processorThread = threading.Thread(
            target=self._processor, daemon=True, name="rs422-processor"
        )
        self._readerThread.start()
        self._processorThread.start()
        log.info("RS422 listener started on %s @ %d baud", self.port, self.baud)

    def stop(self) -> None:
        """Signal threads to stop and wait for them to finish."""
        self._stop.set()
        if self._readerThread:
            self._readerThread.join(timeout=self.reconnectDelay + 1)
        if self._processorThread:
            self._processorThread.join(timeout=2)
        log.info("RS422 listener stopped.")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()

    # ------------------------------------------------------------------
    # Internal threads
    # ------------------------------------------------------------------

    def _openPort(self) -> serial.Serial:
        return serial.Serial(
            port=self.port, baudrate=self.baud, bytesize=self.bytesize,
            parity=self.parity, stopbits=self.stopbits, timeout=self.readTimeout,
        )

    def _reader(self):
        """Producer: drain the serial port continuously, put chunks on the queue."""
        while not self._stop.is_set():
            ser = None
            try:
                ser = self._openPort()
                ser.reset_input_buffer()
                log.info("Reader: connected to %s", self.port)
                while not self._stop.is_set():
                    chunk = ser.read(256)
                    if chunk:
                        self._chunkQ.put(chunk)
            except serial.SerialException as e:
                log.warning("Reader: serial error (%s) — reconnecting in %.1fs",
                            e, self.reconnectDelay)
                time.sleep(self.reconnectDelay)
            finally:
                if ser is not None and ser.is_open:
                    ser.close()
        log.debug("Reader: stopped.")

    def _processor(self):
        """Consumer: pull chunks off the queue and scan for all registered patterns."""
        buffer = bytearray()
        while not self._stop.is_set():
            try:
                chunk = self._chunkQ.get(timeout=0.1)
                buffer.extend(chunk)
                self._scan(buffer)
            except queue.Empty:
                continue

        # Drain any in-flight chunks before exiting.
        while not self._chunkQ.empty():
            try:
                buffer.extend(self._chunkQ.get_nowait())
            except queue.Empty:
                break
        if buffer:
            self._scan(buffer)
        log.debug("Processor: stopped.")

    def _scan(self, buffer: bytearray):
        """Scan buffer for every registered pattern and set its event when found."""
        with self._signalsLock:
            signals = list(self._signals.items())  # snapshot to avoid holding lock during scan

        # Track the furthest consumed position so we only trim once per call.
        trimTo = 0

        for name, (pattern, returnValue, event) in signals:
            idx = buffer.find(pattern)
            while idx != -1:
                log.info("Signal detected: %r -> %r", name, returnValue)
                event.set()
                end = idx + len(pattern)
                trimTo = max(trimTo, end)
                idx = buffer.find(pattern, end)

        if trimTo:
            del buffer[:trimTo]

        # Hard cap: retain the tail so patterns split across the cut can still match.
        if len(buffer) > self.maxBuffer:
            maxPatternLen = max((len(p) for _, (p, _, _) in signals), default=1)
            del buffer[:-(maxPatternLen - 1) or None]
