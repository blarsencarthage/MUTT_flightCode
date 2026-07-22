from __future__ import print_function
import pilxi

IPaddr = "192.168.11.12"

session = pilxi.Pi_Session(IPaddr)

sessions = session.GetForeignSessions()

for s in sessions:
    session.ReleaseForeignSession(s)

session.Disconnect()
