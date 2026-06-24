Session Summary — 6.23–6.24.26
What was built
flightCode/flightLoopV1.py — first-pass threading framework for the suborbital experiment flight controller, implemented according to the CLAUDE.md architecture spec. Starting from a 4-stub skeleton (flightLoopV1), the following was implemented:

Threading framework
Four worker threads (craftSerial_ThreadManager, pxi_ThreadManager, relay_ThreadManager, telemetry_ThreadManager) following the required pattern: stopEvent-gated loop, queue.get(timeout=0.2) on every queue access, exceptions logged and continued, updateHeartbeat() called every iteration
THREAD_FACTORIES dict of lambda constructors so a fresh Thread object can be built on restart without referencing a dead one
startThread(name) / restartThread(name) — factory-based restart with per-thread attempt counting
logMsg() / _emitLog() — queue-based logging so workers never block on I/O; telemetry thread drains the queue and continues draining after shutdown to avoid losing final events
Watchdog (watchdog_ThreadManager)
Four health checks run every WATCHDOG_INTERVAL:

Hard failure — t.is_alive() false → thread crashed → restart
Soft failure — heartbeat older than HEARTBEAT_TIMEOUT → deadlock/stuck → restart
Queue depth — warn at 10, alarm at 50 items
PXI hardware ping — runs on its own PXI_HEALTH_INTERVAL (5 s) cadence via checkPXIHealth() / reinitPXI()
PXI hardware watchdog
checkPXIHealth() — pings every card via card.CardId(); returns False on first non-response
reinitPXI() — closes all card handles, calls PI.initPXIE() to rebuild the connection under pxiLock; resets count on clean recovery, calls triggerSafeMode() after PXI_REINIT_LIMIT failures
pxiLock added to protect pxiCards from a race between watchdog reinit and the PXI worker
Safe mode (triggerSafeMode)
Opens all Numato relay channels
Zeroes all PXI outputs
Sends fault signal to spacecraft bus
Each action isolated in its own try/except; sets safeModeEvent and no-ops on subsequent calls
Other changes
File moved from repo root flightLoopV1 → flightCode/flightLoopV1.py
sys.path bootstrap added so hardware package imports resolve regardless of launch method (direct run, Windows service, etc.)
Log filename timestamped at startup: flight_YYYY-MM-DD_HH-MM-SS.log
Documentation
flightCode/FlightCodeV1_README.md — Functions section filled in with all 18 functions: parameters, return type, and description for each. Existing Variables / Architecture / Heartbeat / Main Loop sections left untouched.

Still marked TODO (hardware calls not yet defined)
craftSerial_ThreadManager — signal set and craftListener.detected() polling
pxi_ThreadManager — command parsing → PI.updateWaveform(card, wave) under pxiLock
relay_ThreadManager — command parsing → relaySer.write(f"relay on {n}\r".encode())
triggerSafeMode — actual hardware shutdown calls
initHardware — relay self-check and PI.waveformSelfCheck()
Command protocol prefixes in routeCommand()