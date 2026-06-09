#testSerial = serial.Serial('/dev/ttyUSB0')
#For actual serial port on advantech, check what the device name would be 

#testSerial = serial.Serial(
#    port="COM3",        # depends on what system assigns, should be COM-1 or COM-2
#    baudrate=9600,      # Virgin dependent 
#    bytesize=serial.EIGHTBITS, #I hope a byte is 8 bits
#    parity=serial.PARITY_NONE, #Probably no parity
#    stopbits=serial.STOPBITS_ONE, #Please be 1 
#    timeout=1,          # seconds; read() returns after this if idle

#RS-422 continuous listener for the Advantech UNO-127 (Windows IoT Enterprise).
 
#Reads bytes continuously from a receive-only RS-422 port, accumulates them in a
#buffer, and fires a callback every time an "activation signal" (a configurable
#byte pattern) appears in the stream. Automatically reconnects if the port drops.

#Run:  python rs422_listener.py
#Stop: Ctrl+C

import io 
import time
import logging
import serial as serial # pip install pyserial
 
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger("rs422")
 
# --- Configuration --------------------------------------------------------
PORT       = "COM3"               # Advantech COM port is COM-1 or COM-2 
BAUD       = 9600                 # Depends on virgin standards
BYTESIZE   = 8
PARITY     = serial.PARITY_NONE
STOPBITS   = 1
READ_TIMEOUT    = 0.5             
RECONNECT_DELAY = 2.0             
MAX_BUFFER      = 4096            
#Activation signal: VIGRIN DEPENDENT 
ACTIVATION = b"START"
# The signal to watch for. Replace with your real pattern. Examples:


def onActivation():
    """Called once per detected activation signal. Put your action here."""
    log.info(">>> Activation signal detected -- triggering action.")
    # e.g. set a flag, launch a process, toggle an output, enqueue an event...
 
 
def openPort():
    return serial.Serial(
        port=PORT, baudrate=BAUD, bytesize=BYTESIZE,
        parity=PARITY, stopbits=STOPBITS, timeout=READ_TIMEOUT,
    )
 
# Called by listen() scans the buffer for activation pattern, calls onActivation() when pattern is found
def scan(buffer: bytearray):
    idx = buffer.find(ACTIVATION)
    while idx != -1:
        onActivation()
        del buffer[:idx + len(ACTIVATION)]   # drop through end of the match
        idx = buffer.find(ACTIVATION)
 
    # If the pattern never shows up, keep the buffer from growing without bound.
    # Retain the last (len-1) bytes so a pattern split across the cut survives. 
    if len(buffer) > MAX_BUFFER:
        del buffer[:-(len(ACTIVATION) - 1) or None]
 
#open port, read continuously, and scan for activation signals.
# TODO: add functionality to add other signals to watch for after the activation trigger occurs  
def listen():
    buffer = bytearray()
    while True:
        ser = None
        try:
            ser = openPort()
            ser.reset_input_buffer()
            buffer.clear()
            log.info("Listening on %s @ %d baud", PORT, BAUD)
            while True:
                chunk = ser.read(256)        # returns after READ_TIMEOUT if idle
                if not chunk:
                    continue                 # idle tick; stays responsive
                buffer.extend(chunk)
                scan(buffer)
        #Exception for disconnection from serial port
        except serial.SerialException as e:
            log.warning("Serial error (%s) -- reconnecting in %.1fs",
                        e, RECONNECT_DELAY)
            time.sleep(RECONNECT_DELAY)
        #All other exceptions including manual stop with Ctrl+C
        except KeyboardInterrupt:
            log.info("Stopping.")
            break
        finally:
            if ser is not None and ser.is_open:
                ser.close()
 
 
if __name__ == "__main__":
    listen()
 
