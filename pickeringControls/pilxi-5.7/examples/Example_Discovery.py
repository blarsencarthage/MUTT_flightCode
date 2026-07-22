from __future__ import print_function
import pilxi


base = pilxi.Pi_Base()

print("LXI Discovery example program using the Pickering ClientBridge Python wrapper")

print("pilxi wrapper version: {}".format(pilxi.__version__))

try:
    LXIs = base.Discover(address="192.168.0.255")
    print("Number of LXIs available:", len(LXIs))

# Print description of any errors and exit
except pilxi.Error as ex:
    print("Error occurred:", ex.message)
    exit()

for address, description in LXIs:
    print("Found LXI at {}, description: {}".format(address, description))

