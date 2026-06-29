"""

    controller = RelayController(port="COM7")
    controller.start()

    controller.signalRelayOn(0)   # turn relay 0 on
    controller.signalRelayOff(0)  # turn relay 0 off

    # Or drive the threading.Event directly:
    controller.relayEvents[2].set()    # ON
    controller.relayEvents[2].clear()  # OFF

    controller.stop()

Numato serial protocol (19200 baud, no flow control):
    relay on  <N>\r   -> turns relay N on
    relay off <N>\r   -> turns relay N off
    relay read <N>\r  -> returns "on" or "off"
"""

import serial
import threading
import time
import logging
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

portName           = "COM7"   # Serial port of the Numato relay board (replace with relevant system port)
baudRate           = 19200    # Numato default baud rate
serialTimeout      = 1.0      # Seconds to wait for a serial read to complete
commandRetryCount  = 2        # Times to retry a failed command before giving up
eventPollInterval  = 0.05     # Seconds between event-loop polls (50 ms)

numRelays = 4                 # Numato USB relay board has relays 0-3

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(threadName)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# RelayController
# ---------------------------------------------------------------------------

class RelayController:
    """

    relayEvents : list[threading.Event]
        One event per relay (index 0-3).  Set = ON, clear = OFF.
        Call signalRelayOn/Off for a named interface, or manipulate
        the events directly for tighter integration.
    """

    def __init__(self, port: str = portName, baud: int = baudRate):
        self.port = port
        self.baud = baud

        # Serial port handle — only touched inside serialLock
        self._ser: Optional[serial.Serial] = None

        # Mutex: ensures only one thread sends/receives on the serial port at a time
        self._serialLock = threading.Lock()

        # Set while the serial link is open and healthy
        self._connected = threading.Event()

        # Signals all background threads to stop
        self._shutdown = threading.Event()

        # External signal interface: one Event per relay (Set=ON, Clear=OFF)
        self.relayEvents: list[threading.Event] = [
            threading.Event() for _ in range(numRelays)
        ]

        # Last state actually applied to the hardware (None = unknown / never applied)
        self._appliedStates: list[Optional[bool]] = [None] * numRelays

        # Background event-loop thread
        self._eventThread = threading.Thread(
            target=self._eventLoop,
            name="RelayEventLoop",
            daemon=True,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Open the serial port and start the event-loop thread."""
        log.info("RelayController starting on %s @ %d baud.", self.port, self.baud)
        self._tryConnect()
        self._eventThread.start()

    def stop(self) -> None:
        """Signal the event-loop thread to stop and close the serial port."""
        log.info("RelayController stopping.")
        self._shutdown.set()
        self._eventThread.join(timeout=2)
        self._closePort()
        log.info("RelayController stopped.")

    def signalRelayOn(self, relayNum: int) -> None:
        """
        External signal: request relay <relayNum> to turn ON.
        The event-loop picks this up within eventPollInterval seconds.
        """
        if not (0 <= relayNum < numRelays):
            log.warning("signalRelayOn: invalid relay index %d (valid: 0-%d).",
                        relayNum, numRelays - 1)
            return
        self.relayEvents[relayNum].set()

    def signalRelayOff(self, relayNum: int) -> None:
        """
        External signal: request relay <relayNum> to turn OFF.
        The event-loop picks this up within eventPollInterval seconds.
        """
        if not (0 <= relayNum < numRelays):
            log.warning("signalRelayOff: invalid relay index %d (valid: 0-%d).",
                        relayNum, numRelays - 1)
            return
        self.relayEvents[relayNum].clear()

    def isConnected(self) -> bool:
        """Return True if the serial link is currently open."""
        return self._connected.is_set()

    # ------------------------------------------------------------------
    # Connection management (internal)
    # ------------------------------------------------------------------

    def _tryConnect(self) -> bool:
        """
        Attempt to open the serial port.
        Returns True on success; False on SerialException.
        """
        try:
            log.info("Connecting to %s...", self.port)
            ser = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                timeout=serialTimeout,
            )
            ser.reset_input_buffer()
            ser.reset_output_buffer()

            with self._serialLock:
                self._ser = ser

            self._connected.set()
            log.info("Connected to relay board on %s.", self.port)
            return True

        except serial.SerialException as exc:
            log.error("Connection failed: %s", exc)
            self._connected.clear()
            return False

    def _closePort(self) -> None:
        """Safely close the serial port and mark as disconnected."""
        with self._serialLock:
            if self._ser and self._ser.is_open:
                try:
                    self._ser.close()
                    log.info("Serial port closed.")
                except Exception as exc:
                    log.debug("Error closing port: %s", exc)
            self._ser = None
        self._connected.clear()

    # ------------------------------------------------------------------
    # Serial I/O (internal)
    # ------------------------------------------------------------------

    def _sendCommand(self, command: str) -> Optional[str]:
        """
        Send one command to the relay board and return the raw response. Returns None if the port is unavailable or an I/O error occurs. Acquires serialLock for the full send-receive cycle.
        """
        with self._serialLock:
            if not self._ser or not self._ser.is_open:
                return None
            try:
                self._ser.write(command.encode())
                response = self._ser.read(25).decode(errors="replace")
                return response
            except (serial.SerialException, OSError) as exc:
                log.warning("Serial I/O error on command '%s': %s", command.strip(), exc)
                self._connected.clear()
                return None

    def _sendCommandWithRetry(self, command: str) -> Optional[str]:
        """
        Try sending a command up to commandRetryCount times. Returns the response string, or None if all attempts fail.
        """
        for attempt in range(1, commandRetryCount + 1):
            if self._shutdown.is_set():
                return None

            response = self._sendCommand(command)
            if response is not None:
                return response

            log.warning(
                "Command '%s' attempt %d/%d failed.",
                command.strip(), attempt, commandRetryCount,
            )

        log.error("All retries failed for command '%s'.", command.strip())
        return None

    # ------------------------------------------------------------------
    # Relay commands (internal)
    # ------------------------------------------------------------------

    def _applyRelay(self, relayNum: int, turnOn: bool) -> bool:
        """
        Issue a relay on/off command and update the local state cache. Returns True on success, False if the command could not be sent.
        """
        action  = "on" if turnOn else "off"
        command = f"relay {action} {relayNum}\r"
        response = self._sendCommandWithRetry(command)

        if response is None:
            log.error("Failed to set relay %d %s.", relayNum, action.upper())
            return False

        self._appliedStates[relayNum] = turnOn
        log.info("Relay %d -> %s", relayNum, action.upper())
        return True

    # ------------------------------------------------------------------
    # Background thread (internal)
    # ------------------------------------------------------------------

    def _eventLoop(self) -> None:
        """
        polls relayEvents at eventPollInterval and issues relay commands whenever an event's state differs from the last successfully applied state.
        """
        log.info("Event loop started (poll=%.0f ms, relays 0-%d).",
                 eventPollInterval * 1000, numRelays - 1)

        while not self._shutdown.is_set():
            if self._connected.is_set():
                for relayNum in range(numRelays):
                    desiredOn = self.relayEvents[relayNum].is_set()

                    if desiredOn != self._appliedStates[relayNum]:
                        self._applyRelay(relayNum, desiredOn)

            time.sleep(eventPollInterval)

        log.info("Event loop stopped.")


# ---------------------------------------------------------------------------
# Example / demo entry-point
# ---------------------------------------------------------------------------

def main():
    controller = RelayController(port=portName, baud=baudRate)
    controller.start()

    try:
        log.info("=== Demo: cycling each relay ON then OFF ===")

        for relayNum in range(numRelays):
            log.info("--- Relay %d: ON ---", relayNum)
            controller.signalRelayOn(relayNum)
            time.sleep(1.5)

            log.info("--- Relay %d: OFF ---", relayNum)
            controller.signalRelayOff(relayNum)
            time.sleep(0.75)

        log.info("Demo complete. Press Ctrl+C to exit.")
        while True:
            time.sleep(1.0)

    except KeyboardInterrupt:
        log.info("Interrupt received — shutting down.")
    finally:
        controller.stop()


if __name__ == "__main__":
    main()



"Yippee!  The relay board is working and the demo ran successfully. "