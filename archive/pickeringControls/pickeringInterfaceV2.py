import os
import sys
import csv
import time
import threading
import logging
log = logging.getLogger("mutt.LXI")
_pkg_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_pkg_dir, "pilxi-5.7"))
import pilxi
import pi620lx

# pi620lx.Base/Card.signalShapes only defines these three — see
# pickeringInterface.py's identical map for why RAMP/DC/PULSE/PWM/ARB aren't
# supported. Any unrecognized waveform_type string falls back to SINE.
_WAVEFORM_TYPE_MAP = {
    "SINE":     0,
    "TRIANGLE": 1,
    "SQUARE":   2,

}
_WAVEFORM_TYPE_SINE = _WAVEFORM_TYPE_MAP["SINE"]

# 1-based relay index on the 40-115-021 wired to the FG trigger lines.
_RELAY_SUBUNIT = 1
_RELAY_BIT = 1
_RELAY_PULSE_WIDTH_S = 0.05

def _cardLabel(card):
    """Best-effort human-readable label for a card, for logging.

    pi620lx.Card has no CardId()/CardLoc() (unlike pilxi's Pi_Card_ByDevice).
    _openLXI() stamps _bus/_device onto every 41-620 card it opens; this
    just formats them, falling back gracefully if a card wasn't opened that
    way (e.g. a mock in a test).
    """
    bus = getattr(card, "_bus", None)
    device = getattr(card, "_device", None)
    if bus is None or device is None:
        return "<unknown card>"
    return f"PXI{bus}::{device}"


#TODO: Add monotonic time to avoid connection requests until estimated LXI boot time

class pickeringHeader: 
    """
    Externally accessed wrapper class for interfacing with the 
    Pickering software. All Pickering internal classes and objects are contained 
    so the end user doesn't have to interact with them
    """
    def __init__(self, ipAddress, timeout_ms):
        self.ip_address = ipAddress
        self.timeout_ms = timeout_ms
        self.base = None
        self.cards = []
        self.pair_channels = []
        self.session = None
        self.relayCard = None
        self.connectionStatus = False
        self.hasConnected = False
        self.healthInterval = 5 #sec
        self.phasedArray = pickeringHeader.phasedArray()
        self._stopEvent = threading.Event()
        self._lxiThread = threading.Thread(target=self._monitorLXI, daemon=True)
        self._lxiThread.start()

# ---------------------------------------------------------------------------
# LXI Management Functions
# ---------------------------------------------------------------------------

    def _openLXI(self):
        """
        Makes one connection attempt to the LXI cabinet, updating
        session/cards/relayCard/connectionStatus/hasConnected. No-ops if
        already connected. Called repeatedly by _monitorLXI(); not meant to
        be called directly by external code.

        Card discovery mirrors pickeringInterface.py's initPXIE(): a single
        pilxi.Pi_Session for the LXI unit, pi620lx.Base for the 41-620
        function generator cards (self.cards). The 40-115-021 relay card
        (self.relayCard) isn't a 41-620, so it's found separately by
        scanning session.FindFreeCards() and matching CardId().
        """
        if self.connectionStatus:
            return
        if self.hasConnected:
            log.warning(f"Connection to LXI at {self.ip_address} lost. Attempting to reconnect...")
            print(f"[LXI] Connection to {self.ip_address} lost. Attempting to reconnect...")
        log.info(f"Attempting to connect to LXI cabinet at {self.ip_address}")
        print(f"[LXI] Attempting to connect to LXI cabinet at {self.ip_address}...")
        try:
            self.session = pilxi.Pi_Session(self.ip_address, timeout=self.timeout_ms)
            sessionID = self.session.GetSessionID()
            print(f"[LXI] Session opened, sessionID={sessionID}")

            pi620Base = pi620lx.Base(sessionID)
            cardLocs = pi620Base.findCards()  # [(bus, device), ...] — 41-620 cards only
            print(f"[LXI] pi620lx.Base.findCards() -> {cardLocs}")
            self.cards = []
            for bus, device in cardLocs:
                card = pi620Base.openCard(bus, device)
                card._bus = bus
                card._device = device
                self.cards.append(card)
                print(f"[LXI] Opened function generator card at bus={bus}, device={device}")

            self.relayCard = None
            freeCards = self.session.FindFreeCards()
            print(f"[LXI] session.FindFreeCards() -> {freeCards}")
            for bus, device in freeCards:
                candidate = self.session.OpenCard(bus, device)
                cardId = candidate.CardId()
                print(f"[LXI] Free card at bus={bus}, device={device}: CardId()={cardId!r}")
                if "40-115" in cardId:
                    self.relayCard = candidate
                    print(f"[LXI] Matched relay card at bus={bus}, device={device}")
                    break
            if self.relayCard is None:
                log.warning("No 40-115 relay card found on this LXI unit — "
                            "triggerFuncGens/armFuncGens will be unavailable.")
                print("[LXI] WARNING: No 40-115 relay card found.")
        except Exception as ex:
            log.error(f"Failed to initialize PXI interface: {ex}")
            print(f"[LXI] ERROR: Failed to initialize PXI interface: {ex}")
            self.connectionStatus = False
            return
        if self.session is None:
            log.error("Failed to initialize PXI interface.")
            print("[LXI] ERROR: Failed to initialize PXI interface (session is None).")
            self.connectionStatus = False
            return
        log.info(f"PXI interface initialized successfully. Found {len(self.cards)} "
                 f"function generator card(s), relay card {'found' if self.relayCard else 'not found'}.")
        print(f"[LXI] Connected. {len(self.cards)} function generator card(s), "
              f"relay card {'found' if self.relayCard else 'NOT found'}.")
        self.connectionStatus = True
        self.hasConnected = True

    def _monitorLXI(self):
        """
        Runs for the object's lifetime on its own daemon thread: opens the
        LXI connection, then rechecks every healthInterval seconds and
        reopens it if lost (LOC). Exits once closeLXI() sets _stopEvent.
        """
        while not self._stopEvent.is_set():
            if not self.connectionStatus:
                self._openLXI()
            self._stopEvent.wait(self.healthInterval)

    def closeLXI(self):
        """
        Stops the monitor thread, closes the LXI session, and cleans up
        resources.
        """
        self._stopEvent.set()
        if self.session is not None:
            self.session.Close()
            self.session = None
            self.relayCard = None
            self.connectionStatus = False
            log.info("LXI session closed.")
            print("[LXI] Session closed.")

    def getCards(self):
        """
        Returns a list of cards found in the LXI cabinet.
        """
        if self.session is not None:
            return self.cards
        else:
            log.warning("No active session. Cannot retrieve cards.")
            return []

    def loadWaveConfig(self, configFilePath: str):
        """
        Loads a waveConfigs.csv file into this header's internal phasedArray.

        Callers outside this class work through this method rather than
        touching self.phasedArray directly.
        """
        self.phasedArray.readConfig(configFilePath)
        return self.phasedArray
    
    def _cardChannelConfigs(self):
        """
        Pairs each (card, card-channel 1-3) slot with its phasedArray
        channel config, in the fixed order card0 ch1-3, card1 ch1-3 — the
        same order phasedArray.channels comes out of readConfig() in.
        """
        pairs = []
        configs = iter(self.phasedArray.channels)
        for card in self.cards:
            for cardChannel in range(1, 4):
                try:
                    config = next(configs)
                except StopIteration:
                    return pairs
                pairs.append((card, cardChannel, config))
        return pairs

    def sendConfigToCards(self):
        """
        Sends the configuration loaded into phasedArray to the 41-620
        function generator cards. Configures each channel's waveform but
        does not arm or start generation — see armFuncGens().
        """
        for card, cardChannel, config in self._cardChannelConfigs():
            try:
                card.setActiveChannel(cardChannel)
                card.outputOff()
                card.setOutputOffsetVoltage(config.offset, True)
                card.setAttenuation(config.amplitude)
                card.generateSignal(
                    config.frequency / 1000.0,
                    _WAVEFORM_TYPE_MAP.get(config.waveform_type, _WAVEFORM_TYPE_SINE),
                    config.symmetry,
                    startPhaseOffset=config.phase, generate=False,
                )
            except pi620lx.Error as ex:
                log.error(f"Failed to send config to card {_cardLabel(card)} "
                          f"channel {cardChannel}: {ex.message}")

    def armFuncGens(self):
        """
        Arms every configured channel to wait on the external (FRONT)
        trigger, delivered by relay 1 of the 40-115-021. Ensures the relay
        is open first so a stale closed relay can't immediately fire the
        newly armed channels.
        """
        if self.relayCard is not None:
            try:
                self.relayCard.OpBit(_RELAY_SUBUNIT, _RELAY_BIT, False)
            except pilxi.Error as ex:
                log.error(f"Failed to reset trigger relay before arming: {ex.message}")
        else:
            log.warning("No relay card available — arming function generators without a trigger source.")

        for card, cardChannel, _config in self._cardChannelConfigs():
            try:
                card.setActiveChannel(cardChannel)
                card.setTriggerMode(card.triggerSources["FRONT"], card.triggerModes["POSEDGE"])
                card.outputOn()
            except pi620lx.Error as ex:
                log.error(f"Failed to arm card {_cardLabel(card)} channel {cardChannel}: {ex.message}")

    def disarmFuncGens(self):
        """
        Stops every configured channel from waiting on the trigger and
        de-energizes the relay as a safety reset.
        """
        for card, cardChannel, _config in self._cardChannelConfigs():
            try:
                card.setActiveChannel(cardChannel)
                card.outputOff()
            except pi620lx.Error as ex:
                log.error(f"Failed to disarm card {_cardLabel(card)} channel {cardChannel}: {ex.message}")

        if self.relayCard is not None:
            try:
                self.relayCard.OpBit(_RELAY_SUBUNIT, _RELAY_BIT, False)
            except pilxi.Error as ex:
                log.error(f"Failed to reset trigger relay while disarming: {ex.message}")

    def triggerFuncGens(self):
        """
        Fires relay 1 of the 40-115-021, delivering a 5V pulse onto the
        function generators' external trigger lines. OpBit() already blocks
        for the relay's firmware settle time on each call; the relay is
        left open (de-energized) afterward, ready for the next trigger.
        """
        if self.relayCard is None:
            log.error("No relay card available — cannot trigger function generators.")
            print("[Relay] ERROR: No relay card available — cannot trigger function generators.")
            return
        try:
            self.relayCard.OpBit(_RELAY_SUBUNIT, _RELAY_BIT, True)
            print(f"[Relay] subunit={_RELAY_SUBUNIT} bit={_RELAY_BIT} -> CLOSED (energized)")
            time.sleep(_RELAY_PULSE_WIDTH_S)
            self.relayCard.OpBit(_RELAY_SUBUNIT, _RELAY_BIT, False)
            print(f"[Relay] subunit={_RELAY_SUBUNIT} bit={_RELAY_BIT} -> OPEN (de-energized)")
        except pilxi.Error as ex:
            log.error(f"Failed to trigger function generators: {ex.message}")
            print(f"[Relay] ERROR: Failed to trigger function generators: {ex.message}")

# ---------------------------------------------------------------------------
# Manual Relay Control Functions (for REPL diagnostics/testing)
# ---------------------------------------------------------------------------

    def setRelay(self, bit=_RELAY_BIT, state=True, subunit=_RELAY_SUBUNIT):
        """
        Directly energizes (state=True, closed) or de-energizes (state=False,
        open) a single relay bit on the relay card. For manual REPL testing —
        prefer triggerFuncGens()/armFuncGens()/disarmFuncGens() for the
        normal function-generator trigger workflow.
        """
        if self.relayCard is None:
            print("[Relay] ERROR: No relay card available.")
            log.error("setRelay() called with no relay card available.")
            return
        try:
            self.relayCard.OpBit(subunit, bit, state)
            print(f"[Relay] subunit={subunit} bit={bit} -> {'CLOSED (energized)' if state else 'OPEN (de-energized)'}")
        except pilxi.Error as ex:
            print(f"[Relay] ERROR: Failed to set subunit={subunit} bit={bit} to {state}: {ex.message}")
            log.error(f"Failed to set relay subunit={subunit} bit={bit} to {state}: {ex.message}")

    def pulseRelay(self, bit=_RELAY_BIT, subunit=_RELAY_SUBUNIT, holdTime=_RELAY_PULSE_WIDTH_S):
        """
        Momentarily energizes then de-energizes a single relay bit — fires a
        manual trigger pulse without going through the full arm/trigger
        function-generator workflow. Useful for bench-testing the relay
        card and trigger wiring in isolation from the 41-620s.
        """
        if self.relayCard is None:
            print("[Relay] ERROR: No relay card available.")
            log.error("pulseRelay() called with no relay card available.")
            return
        try:
            self.relayCard.OpBit(subunit, bit, True)
            print(f"[Relay] subunit={subunit} bit={bit} -> CLOSED (energized), holding {holdTime}s")
            time.sleep(holdTime)
            self.relayCard.OpBit(subunit, bit, False)
            print(f"[Relay] subunit={subunit} bit={bit} -> OPEN (de-energized)")
        except pilxi.Error as ex:
            print(f"[Relay] ERROR: Failed to pulse subunit={subunit} bit={bit}: {ex.message}")
            log.error(f"Failed to pulse relay subunit={subunit} bit={bit}: {ex.message}")

    def readRelay(self, bit=_RELAY_BIT, subunit=_RELAY_SUBUNIT):
        """
        Reads back the current state of a single relay bit (True=closed/
        energized, False=open/de-energized). Returns None if unavailable.
        """
        if self.relayCard is None:
            print("[Relay] ERROR: No relay card available.")
            log.error("readRelay() called with no relay card available.")
            return None
        try:
            state = self.relayCard.ReadBit(subunit, bit)
            print(f"[Relay] subunit={subunit} bit={bit} state={'CLOSED' if state else 'OPEN'}")
            return state
        except pilxi.Error as ex:
            print(f"[Relay] ERROR: Failed to read subunit={subunit} bit={bit}: {ex.message}")
            log.error(f"Failed to read relay subunit={subunit} bit={bit}: {ex.message}")
            return None


# ---------------------------------------------------------------------------
# Waveform Mangement Functions
# ---------------------------------------------------------------------------

    class phasedArray:
        """
        Class for storing waveforms for input to pickering cards.

        Mirrors the layout of a waveConfigs.csv: one instance holds all 6
        channels (2 cards x 3 channels each), each channel's parameters kept
        in its own `channel` sub-object.
        """

        NUM_CHANNELS = 6
        
        class channel:
            """Parameters for a single waveform output channel (one CSV row)."""

            def __init__(self, channel=None, frequency=0.0, amplitude=0.0, offset=0.0,
                         phase=0.0, waveform_type="SINE", activeTime=0.0,
                         settlingTime=0.0, symmetry=50.0):
                self.channel = channel
                self.frequency = frequency
                self.amplitude = amplitude
                self.offset = offset
                self.phase = phase
                self.waveform_type = waveform_type
                self.activeTime = activeTime
                self.settlingTime = settlingTime
                self.symmetry = symmetry

            def __repr__(self):
                return (f"channel({self.channel}, freq={self.frequency}, "
                        f"amp={self.amplitude}, offset={self.offset}, "
                        f"phase={self.phase}, type={self.waveform_type}, "
                        f"activeTime={self.activeTime}, "
                        f"settlingTime={self.settlingTime}, "
                        f"symmetry={self.symmetry})")

        def __init__(self):
            self.channels = [pickeringHeader.phasedArray.channel()
                             for _ in range(pickeringHeader.phasedArray.NUM_CHANNELS)]

        def readConfig(self, configFilePath):
            """
            Reads a waveConfigs csv file and populates self.channels in place.

            Expected columns (header row required):
                channel, frequency, amplitude, offset, phase, waveform_type,
                activeTime, settlingTime
            Optional column:
                symmetry (0-100) — defaults to 50 if absent/blank.

            Rows are assigned to self.channels by file order (row 0 -> index
            0, etc.), not by the CSV's own `channel` column value, since that
            value repeats per-card (1-3) rather than uniquely identifying one
            of the 6 stored channels.
            """
            with open(configFilePath, newline="") as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    if i >= self.NUM_CHANNELS:
                        log.warning(f"waveConfig {configFilePath} has more than "
                                    f"{self.NUM_CHANNELS} rows; ignoring extras.")
                        break
                    symmetry_raw = row.get("symmetry", "")
                    self.channels[i] = pickeringHeader.phasedArray.channel(
                        channel=int(row["channel"]),
                        frequency=float(row["frequency"]),
                        amplitude=float(row["amplitude"]),
                        offset=float(row["offset"]),
                        phase=float(row["phase"]),
                        waveform_type=row["waveform_type"].strip().upper(),
                        activeTime=float(row["activeTime"]),
                        settlingTime=float(row["settlingTime"]),
                        symmetry=(float(symmetry_raw)
                                  if symmetry_raw not in (None, "") else 50.0),
                    )
            return self

        def getChannel(self, index):
            return self.channels[index]

        def __repr__(self):
            return "phasedArray(\n  " + "\n  ".join(repr(c) for c in self.channels) + "\n)"