#RS-422 continuous listener for the Advantech UNO-127 (Windows IoT Enterprise).

#Reads bytes continuously from a receive-only RS-422 port, accumulates them in a
#buffer, and fires a callback every time an "activation signal" (a configurable
#byte pattern) appears in the stream. Automatically reconnects if the port drops.
#Uses two threads: one dedicated to draining the serial port (reader), one to
#scanning the buffer and firing callbacks (processor). This prevents slow callback
#work from ever blocking the read loop and losing bytes from the OS UART buffer.

#Run:  python RS422_V1.py
#Stop: Ctrl+C

import time
import queue
import logging
import threading
import serial  # pip install pyserial

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger("rs422")

# --- Configuration --------------------------------------------------------
PORT            = "COM3"             # Advantech COM port: COM-1 or COM-2
BAUD            = 9600               # Virgin dependent
BYTESIZE        = 8
PARITY          = serial.PARITY_NONE
STOPBITS        = 1
READ_TIMEOUT    = 0.5               # seconds; read() returns after this if idle
RECONNECT_DELAY = 2.0               # seconds to wait before reconnect attempt
MAX_BUFFER      = 4096              # bytes; hard cap to prevent unbounded growth
# Activation signal: VIRGIN DEPENDENT
# Replace with the real byte pattern. Examples:
#   ACTIVATION = b"\xAA\x55"   (two-byte header)
#   ACTIVATION = b"GO"
ACTIVATION      = b"START"

# Shared stop flag — set by main thread on Ctrl+C, read by both worker threads.
_stop = threading.Event()


# --------------------------------------------------------------------------
def onActivation():
    """Called once per detected activation signal. Put your action here."""
    log.info(">>> Activation signal detected -- triggering action.")
    # e.g. set a flag, launch a process, toggle an output, enqueue an event...


def openPort() -> serial.Serial:
    return serial.Serial(
        port=PORT, baudrate=BAUD, bytesize=BYTESIZE,
        parity=PARITY, stopbits=STOPBITS, timeout=READ_TIMEOUT,
    )


def scan(buffer: bytearray):
    """Scan buffer for every occurrence of ACTIVATION and call onActivation()."""
    idx = buffer.find(ACTIVATION)
    while idx != -1:
        onActivation()
        del buffer[:idx + len(ACTIVATION)]   # drop through end of the match
        idx = buffer.find(ACTIVATION)

    # Keep the buffer from growing without bound.
    # Retain the last (len-1) bytes so a pattern split across the cut survives.
    if len(buffer) > MAX_BUFFER:
        del buffer[:-(len(ACTIVATION) - 1) or None]


# --------------------------------------------------------------------------
def _reader(chunk_q: queue.Queue):
    """Producer thread: drain the serial port as fast as possible.

    Chunks are placed on chunk_q for the processor thread to handle.
    Reconnects automatically on SerialException.
    """
    while not _stop.is_set():
        ser = None
        try:
            ser = openPort()
            ser.reset_input_buffer()
            log.info("Reader: listening on %s @ %d baud", PORT, BAUD)
            while not _stop.is_set():
                chunk = ser.read(256)   # returns after READ_TIMEOUT if idle
                if chunk:
                    chunk_q.put(chunk)
        except serial.SerialException as e:
            log.warning("Reader: serial error (%s) -- reconnecting in %.1fs",
                        e, RECONNECT_DELAY)
            time.sleep(RECONNECT_DELAY)
        finally:
            if ser is not None and ser.is_open:
                ser.close()

    log.info("Reader: stopped.")


def _processor(chunk_q: queue.Queue):
    """Consumer thread: pull chunks off the queue and scan for the activation pattern.

    Decoupled from the reader so slow onActivation() work never blocks serial reads.
    """
    buffer = bytearray()
    while not _stop.is_set():
        try:
            chunk = chunk_q.get(timeout=0.1)  # short timeout keeps _stop responsive
            buffer.extend(chunk)
            scan(buffer)
        except queue.Empty:
            continue  # idle tick; check _stop and loop

    # Drain any remaining chunks that arrived before stop was set.
    while not chunk_q.empty():
        try:
            buffer.extend(chunk_q.get_nowait())
        except queue.Empty:
            break
    if buffer:
        scan(buffer)

    log.info("Processor: stopped.")


# --------------------------------------------------------------------------
def listen():
    """Spin up reader and processor threads and block until Ctrl+C."""
    chunk_q: queue.Queue = queue.Queue()

    reader    = threading.Thread(target=_reader,    args=(chunk_q,), daemon=True, name="rs422-reader")
    processor = threading.Thread(target=_processor, args=(chunk_q,), daemon=True, name="rs422-processor")

    reader.start()
    processor.start()

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        log.info("Stopping.")
        _stop.set()

    reader.join(timeout=RECONNECT_DELAY + 1)
    processor.join(timeout=2)


if __name__ == "__main__":
    listen()
