"""

Benchtop test script for the Numato USB 4-channel relay board.

Cycles through relays 0-3 one at a time

"""

import time
import logging
from RelayCode import RelayController, numRelays

# ---------------------------------------------------------------------------
# Test configuration
# ---------------------------------------------------------------------------

portName     = "COM7"  # Change to match your system
relayOnTime  = 2.0     # Seconds each relay stays ON
relayOffTime = 1.0     # Seconds between relays (all off)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    controller = RelayController(port=portName)
    controller.start()

    cycle = 0
    try:
        while True:
            cycle += 1
            log.info("=== Cycle %d ===", cycle)

            for relayNum in range(numRelays):
                log.info("Relay %d ON", relayNum)
                controller.signalRelayOn(relayNum)
                time.sleep(relayOnTime)

                log.info("Relay %d OFF", relayNum)
                controller.signalRelayOff(relayNum)
                time.sleep(relayOffTime)

    except KeyboardInterrupt:
        log.info("Stopped by user.")
    finally:
        controller.stop()


if __name__ == "__main__":
    main()
