import pilxi

print("Example program to list cards in a Pickering LXI chassis")
print("pilxi wrapper version: {}".format(pilxi.__version__))
print()

IP_Address = "192.168.2.80"

session = pilxi.Pi_Session(IP_Address)

cards = session.FindFreeCards()
index = 1

if len(cards) > 0:
    print("Found cards:")

    for cardLocation in cards:

        bus, device = cardLocation
        card = session.OpenCard(bus, device)

        cardID = card.CardId()

        print(f"Card {index}: bus {bus} device {device}: {cardID}")

        index += 1

else:
    print("Found no cards.")
