# Author: Braedon Larsen
# Created: 6.30.26

import time
import queue
import threading
import serial  # pip install pyserial


PORT            = "COM3"             # Advantech COM port: COM-1 or COM-2
BAUD            = 6800               # bit/sec
BYTESIZE        = 8
PARITY          = serial.PARITY_NONE
STOPBITS        = 1
READ_TIMEOUT    = 0.5               # seconds; read() returns after this if idle
RECONNECT_DELAY = 2.0               # seconds to wait before reconnect attempt
MAX_BUFFER      = 4096              # bytes; hard cap to prevent unbounded growth

SYNC_BYTES      = b'\xAA\x55'

# Packet layout (84 bytes total):
#   [0-1]   sync bytes 0xAA55
#   [2-79]  78 bytes of telemetry (ignored)
#   [80]    byte 78 post-sync: bits 3-7 are signals (MSB-first, bit 0 = MSB)
#   [81-83] bytes 79-81 post-sync: all 8 bits are signals
PACKET_LENGTH   = 84   # bytes
SIGNAL_START    = 80   # absolute offset of first signal byte within packet
SIGNAL_BIT_START = 3   # first signal bit in SIGNAL_START byte (MSB-first: 0=MSB, 7=LSB)

SIGNAL_NAMES: tuple[str, ...] = (
    # byte 78 (packet offset 80), bits 3-7
    "discrete03", "discrete02", "discrete01", "rcsRollLeft", "rcsRollRight",
    # byte 79 (packet offset 81), bits 0-7
    "rcsYawLeft", "rcsYawRight", "rcsPitchDown", "rcsPitchUp",
    "stoppedOnRunway", "approach", "reentryStart", "microgravityEnd",
    # byte 80 (packet offset 82), bits 0-7
    "apogee", "microgravityStart", "engineCutoff", "rocketFiring",
    "release", "minusTen", "takeOff", "extra",

)


class serialCraftInterface():

    def __init__(self):
        self._segments = queue.Queue()   # raw byte chunks: reader -> processor
        self._results  = queue.Queue()   # parsed signal dicts: processor -> caller
        self._stop     = threading.Event()

        threading.Thread(target=self._reader,    daemon=True).start()
        threading.Thread(target=self._processor, daemon=True).start()

    # --- private ---

    def _openPort(self) -> serial.Serial:
        return serial.Serial(
            port=PORT, baudrate=BAUD, bytesize=BYTESIZE,
            parity=PARITY, stopbits=STOPBITS, timeout=READ_TIMEOUT,
        )

    #TODO: Add logging to note craft connection and DC
    def _reader(self):
        comm = None
        while not self._stop.is_set():
            try:
                comm = self._openPort()
                comm.reset_input_buffer()
                while not self._stop.is_set():
                    data = comm.read(1024)
                    if data:
                        self._segments.put(data)
            except serial.SerialException:
                time.sleep(RECONNECT_DELAY)
            finally:
                if comm is not None and comm.is_open:
                    comm.close()
                time.sleep(RECONNECT_DELAY)

    def _processor(self):
        buffer = bytearray()
        while not self._stop.is_set():
            try:
                chunk = self._segments.get(timeout=0.1)
                buffer.extend(chunk)
                if len(buffer) > MAX_BUFFER:
                    buffer = buffer[-MAX_BUFFER:]
                self._scan(buffer)
            except queue.Empty:
                pass

    def _scan(self, buffer: bytearray):
        idx = buffer.find(SYNC_BYTES)
        if idx == -1:
            return

        if len(buffer) < idx + PACKET_LENGTH:
            return   # full packet not yet in buffer

        raw_bits: list[bool] = []

        # First signal byte: bits SIGNAL_BIT_START through 7 (MSB-first, bit 0 = MSB)
        b = buffer[idx + SIGNAL_START]
        for bit in range(SIGNAL_BIT_START, 8):
            raw_bits.append(bool((b >> (7 - bit)) & 1))

        # Remaining three signal bytes: all 8 bits each
        for offset in range(SIGNAL_START + 1, SIGNAL_START + 4):
            b = buffer[idx + offset]
            for bit in range(8):
                raw_bits.append(bool((b >> (7 - bit)) & 1))

        self._results.put(dict(zip(SIGNAL_NAMES, raw_bits)))
        del buffer[:idx + PACKET_LENGTH]   # consume the parsed packet

    # --- public ---

    def getSignalBits(self, timeout: float = 5.0) -> dict[str, bool]:
        """Block until the next parsed packet arrives and return its signal states."""
        return self._results.get(timeout=timeout)