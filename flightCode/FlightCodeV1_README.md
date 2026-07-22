## Functions 

**`configureLogging()`**
Parameters: none | Returns: none
Sets up the root Python logger with a timestamped file handler (e.g. `flight_2026-06-24_15-30-00.log`) and a stream handler. The filename is generated at call time so each run produces a unique log file. Attaches a formatter that includes timestamp, thread name, and log level to every record. Must be called once before any logging occurs.

---

**`logMsg(level, message)`**
Parameters: `level` (str — e.g. `"INFO"`, `"ERROR"`, `"CRITICAL"`), `message` (str) | Returns: none
Enqueues a `(level, message)` tuple onto `logQueue` for the telemetry thread to write. All worker threads should use this instead of calling the logging module directly so all file I/O is confined to one thread and callers are never blocked.

---

**`_emitLog(level, message)`**
Parameters: `level` (str), `message` (str) | Returns: none
Internal helper called only by `telemetry_ThreadManager`. Converts the level string to a `logging` constant and writes the record to the configured handlers. Never call this from worker threads — use `logMsg` instead.

---

**`updateHeartbeat(threadName)`**
Parameters: `threadName` (str) | Returns: none
Writes the current `time.monotonic()` timestamp into the `heartbeat` dictionary under the given thread name. Called once per iteration of every worker loop so the watchdog can detect stuck or deadlocked threads.

---

**`routeCommand(cmd)`**
Parameters: `cmd` (str) | Returns: none
Parses an incoming spacecraft command string by its prefix and places it on the correct hardware queue (`pxiQueue` for `"PXI:"` prefixed commands, `relayQueue` for `"RELAY:"` prefixed commands). Unrecognised commands are logged as warnings. Extend the prefix table here as the command protocol is defined.

---

**`craftSerial_ThreadManager()`**
Parameters: none | Returns: none (runs until `stopEvent` is set)
Worker thread body for the spacecraft RS-422 serial bus. Polls the `RS422` listener for registered signals and forwards any detected values into `routeCommand()`. Includes a 0.5 s back-off on exceptions to prevent CPU spin if the serial port drops.

---

**`pxi_ThreadManager()`**
Parameters: none | Returns: none (runs until `stopEvent` is set)
Worker thread body for the Pickering PXI cabinet and 41-620 function generator cards. Drains `pxiQueue` and dispatches waveform update commands to the appropriate card via `PI.updateWaveform()`. Acquire `pxiLock` around all `pxiCards` access in case the watchdog reinitialises the connection concurrently.

---

**`relay_ThreadManager()`**
Parameters: none | Returns: none (runs until `stopEvent` is set)
Worker thread body for the Numato USB relay board. Drains `relayQueue` and writes ASCII relay commands (e.g. `relay on N\r`) to `relaySer`.

---

**`telemetry_ThreadManager()`**
Parameters: none | Returns: none (runs until `stopEvent` is set, then drains remaining entries)
Worker thread body for flight event logging. Drains `logQueue` and calls `_emitLog()` for each entry. Continues draining after `stopEvent` is set so no log entries are lost during shutdown.

---

**`startThread(name)`**
Parameters: `name` (str — key in `THREAD_FACTORIES`) | Returns: `threading.Thread`
Builds a fresh `Thread` object from the factory lambda for the given name, registers it in `threads`, pre-stamps its heartbeat, and calls `.start()`. Returns the new thread object. Used for both initial startup and watchdog-triggered restarts.

---

**`restartThread(name)`**
Parameters: `name` (str) | Returns: none
Increments the restart counter for the named thread and calls `startThread()`. If the counter exceeds `THREAD_RESTART_LIMIT`, calls `triggerSafeMode()` instead of attempting another restart.

---

**`checkPXIHealth()`**
Parameters: none | Returns: `bool` (`True` if all cards respond, `False` otherwise)
Pings every card in `pxiCards` by calling `card.CardId()`. A `pilpxi.Error` or unexpected exception on any card causes an immediate `False` return. Called from the watchdog under `pxiLock`; should not be called from other threads.

---

**`reinitPXI()`**
Parameters: none | Returns: none
Closes all existing PXI card handles, clears `pxiCards`, and re-runs `PI.initPXIE()` to rebuild the connection from scratch. All list manipulation occurs under `pxiLock`. Resets `pxiReinitCount` to zero on a successful recovery. Calls `triggerSafeMode()` after `PXI_REINIT_LIMIT` consecutive failures.

---

**`watchdog_ThreadManager()`**
Parameters: none | Returns: none (runs until `stopEvent` is set)
Health monitor thread. Every `WATCHDOG_INTERVAL` seconds checks all four conditions: (1) thread liveness, (2) heartbeat staleness, (3) queue depth thresholds, and (4) PXI hardware ping (on its own `PXI_HEALTH_INTERVAL` cadence). Triggers restarts or safe mode as needed. The main loop serves as its own backstop if the watchdog itself dies.

---

**`triggerSafeMode()`**
Parameters: none | Returns: none
Drives all hardware to a known-inert state: opens all Numato relay channels, zeroes all PXI function generator outputs, and sends a fault signal to the spacecraft bus. Each hardware action is wrapped in its own try/except so one failure cannot prevent the others from running. Sets `safeModeEvent` and no-ops on subsequent calls.

---

**`initHardware()`**
Parameters: none | Returns: `bool` (`True` if all devices initialised successfully)
Brings up the three hardware connections in order: Pickering PXI cabinet (`PI.initPXIE()`), Numato relay board (`serial.Serial`), and spacecraft RS-422 listener (`RS422.start()`). Logs errors per device and returns `False` if any initialisation fails, allowing the caller to decide whether to abort or continue.

---

**`shutdown()`**
Parameters: none | Returns: none
Sets `stopEvent` to signal all workers to exit, stops the `RS422` listener, then joins every thread with a `JOIN_TIMEOUT` second bound. The telemetry thread is joined last so it can flush any final log entries before the process exits.

---

**`main()`**
Parameters: none | Returns: none
Entry point. Configures logging, starts the telemetry thread first (so hardware init messages are captured), calls `initHardware()`, starts the remaining worker threads, then starts the watchdog. Enters the main idle loop which supervises the watchdog and sleeps 1 s between checks. Handles `KeyboardInterrupt` and calls `shutdown()` in the `finally` block.

---

## Variables 

heartbeat - dictionary with entries for each thread. Each completion of the loop updates the monotonic time (NOTE: monotonic time counts from a undefined reference point, only consider deltas of monoatomic time as valid). 

pxiCards - array of Pi_Card objects that contain the bus and device of each card, the card object is addressed to access each induvidual function generator 

relaySer - serial object for the Numato board, commands to the serial port for the usb are addressed here 

craftListener - instance of the RS422 object for recieving craft signals 

relayStates - publically accessed array with the state of each relay, other modules update this array and the relay manager reads it for updates

currentRelayState - the private array that the relay manager compares against to check each relays status, once each relay has been flipped the relay manager updates this variable

waveformStates - record of the current waveform states that the function generators are outputting 

## Architecture 
The code is split into 5 worker threads, each of the threads executes its own section and prevents waiting for hardware responses or other delays to cause delays in execution. 

- craftSerial - listens for serial signals from the crafts connections COM port. 
TODO: Will read bytes from a buffer seraching from a library of craft signals and update a state variable that other functions are listening for (state variable vs function call to allow for a checksum in the case of missed flight signals) 

- PXI - checks state variables for flight events and time passed events. When signal is recieved, updates waveform according to array configuration library. 

- Relay - checks state variables for flight and time passed events. Works to confirm current states matches the relay states.

- Telemetry - Writes updates from all other processes to a log file and on shutdown confirms 

- Watchdog - Checks for condtions of the threads and corrects issues. 


## Heartbeat/Watchdog
The watchdog will check for 3 conditions of each thread at a rate determined by WATCHDOG_INTERVAL. The 3 conditions are: 
1. Thread Death - if a thread object died and will restart the thread if thats the case, this starts the processing thread again. Any commands still in the queue are preserved, however mid process commands will be lost 
2. Bad Heartbeat - each complete execution of a threadmanager funciton resets its threads entry in the heartbeat dictionary. This dictionary is updated and records the time since last check in. If the last check-in (threadmanager completion) exceeds HEARTBEAT_TIMEOUT, the thread is restarted. 
3. Big Queue - Checks to see if each threads' queue is larger than QUEUE_DEPTH_ALARM or QUEUE_DEPTH_WARN, it will log a message in the log. 


