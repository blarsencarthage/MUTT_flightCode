""" Sample program for Pickering 41-620 Function Generator cards using the Py620 Python Wrapper"""

from __future__ import print_function
import py620

if __name__ == "__main__":

    # Py620 base class contains functions for card discovery:
    base = py620.Pi_Base()

    # Pi_Base.findCards() returns a list of VISA resource strings
    # representing 41-620 devices:
    try:
        devices = base.findCards()
    except py620.Error as error:
        print("Exception Occurred:", error.message)

    # Print a list of cards found
    for resource in devices:
        print("Card at {}".format(resource))

    # Open a card. Optional parameters include resource, idQuery and reset.
    # If no arguments are given, the openCard() method will open the first 41-620 card found.
    try:
        card = base.openCard(resource="PXI20::12::INSTR")
    except py620.Error as ex:
        print("Exception occurred:", ex.message)
        exit()

    # Py620 methods will raise a py620.Error exception on errors. For example, if you try to open
    # a card with an invalid resource string, an exception will be thrown. Exceptions most often
    # will have a message attribute associated with them. Additionally, a numerical error code can be
    # obtained from the driver.
    try:
        card = base.openCard(resource="Invalid Resource String")
    except py620.Error as ex:
        print("Exception occurred:", ex.message)
        print("Driver error code: {:X}".format(ex.errorCode))

    card.close()