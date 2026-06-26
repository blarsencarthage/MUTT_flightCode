import pilxi
import time

def main():
    # Session configuration

    IP_Address = '192.168.11.155'
    # Card and channel configuration values (adjust as needed)
    bus = 53        # Bus number from GSFP/Device Manager
    slot = 14        # Slot number from GSFP/Device Manager
    channel = 16     # Channel to which the signal is applied

    # Open a session to to LXI. Using "pxi" as ip address will access PXI connected to the computer.
    try:
        session = pilxi.Pi_Session(IP_Address)
    except Exception as e:
        print("Failed to create session:", e)
        return

    # Open the card.
    try:
        card = session.OpenCard(bus, slot)
    except Exception as e:
        print("Failed to open card:", e)
        return

    print("\n---------------------------PXI Comparator application---------------------------\n")
    try:
        card_id = card.CardId()  # Retrieve card ID
        print("-------------- Card ID:", card_id, "--------------")
    except Exception as e:
        print("Failed to retrieve CardId:", e)

    # ----------------------------- Channel configuration ------------------------------ #
    # Set channel attributes.
    # It is assumed that the following constants exist in the piplx module.
    try:
        # Set polarity (CMP_POL_UNI = 1 for Unipolar Mode)
        polarity = pilxi.CMP_Polarity.CMP_POL_UNI
        card.SetAttributeDWORD(channel, False, pilxi.Attributes.CMP_POLARITY, polarity)
    except Exception as e:
        print("CMP_POLARITY failed:", e)

    try:
        # Set physical trigger mode (CMP_EDGE_EITHER = 3)
        phy_trig_mode = pilxi.CMP_Mode.CMP_EDGE_EITHER
        card.SetAttributeDWORD(channel, False, pilxi.Attributes.CMP_PHY_TRIG_MODE, phy_trig_mode)
    except Exception as e:
        print("CMP_PHY_TRIG_MODE failed:", e)

    try:
        # Set virtual trigger mode (CMP_EDGE_DISABLED = 0)
        vir_trig_mode = pilxi.CMP_Mode.CMP_EDGE_DISABLED
        card.SetAttributeDWORD(channel, False, pilxi.Attributes.CMP_VIR_TRIG_MODE, vir_trig_mode)
    except Exception as e:
        print("CMP_VIR_TRIG_MODE failed:", e)

    try:
        # Select logical operation mode: CMP_VIR_OR (0 for OR operation)
        vir_op = pilxi.CMP_Virt.CMP_VIR_OR
        card.SetAttributeDWORD(channel, False, pilxi.Attributes.CMP_VIR_OR_AND, vir_op)
    except Exception as e:
        print("CMP_VIR_OR_AND failed:", e)

    try:
        # Set range to CMP_RANGE_18V (value 7 as defined)
        range_val = pilxi.CMP_Range.CMP_RANGE_18V
        card.SetAttributeDWORD(channel, False, pilxi.Attributes.CMP_RANGE, range_val)
    except Exception as e:
        print("CMP_RANGE failed:", e)

    try:
        # Set physical mask (0 means none selected)
        phy_mask = 0
        card.SetAttributeDWORD(channel, False, pilxi.Attributes.CMP_PHY_MASK, phy_mask)
    except Exception as e:
        print("CMP_PHY_MASK failed:", e)

    try:
        # Set virtual mask (0 means none selected)
        vir_mask = 0
        card.SetAttributeDWORD(channel, False, pilxi.Attributes.CMP_VIR_MASK, vir_mask)
    except Exception as e:
        print("CMP_VIR_MASK failed:", e)

    try:
        # Set debounce time to 50.0 milliseconds
        debounce_time = 50.0
        card.SetAttributeDouble(channel, False, pilxi.Attributes.CMP_DEBOUNCE_TIME, debounce_time)
    except Exception as e:
        print("CMP_DEBOUNCE_TIME failed:", e)

    try:
        # Set threshold to 5.0 V (default was 10V in the original comments)
        threshold = 5.0
        card.SetAttributeDouble(channel, False, pilxi.Attributes.CMP_THRESHOLD, threshold)
    except Exception as e:
        print("CMP_THRESHOLD failed:", e)

    # ----------------------------- Read back configured values ------------------------------ #
    try:
        polarity_rbk     = card.GetAttributeDWORD(channel, False, pilxi.Attributes.CMP_POLARITY)
        phy_trig_mode_rbk = card.GetAttributeDWORD(channel, False, pilxi.Attributes.CMP_PHY_TRIG_MODE)
        vir_trig_mode_rbk = card.GetAttributeDWORD(channel, False, pilxi.Attributes.CMP_VIR_TRIG_MODE)
        vir_op_rbk       = card.GetAttributeDWORD(channel, False, pilxi.Attributes.CMP_VIR_OR_AND)
        range_rbk        = card.GetAttributeDWORD(channel, False, pilxi.Attributes.CMP_RANGE)
        phy_mask_rbk     = card.GetAttributeDWORD(channel, False, pilxi.Attributes.CMP_PHY_MASK)
        vir_mask_rbk     = card.GetAttributeDWORD(channel, False, pilxi.Attributes.CMP_VIR_MASK)
        debounce_rbk     = card.GetAttributeDouble(channel, False, pilxi.Attributes.CMP_DEBOUNCE_TIME)
        threshold_rbk    = card.GetAttributeDouble(channel, False, pilxi.Attributes.CMP_THRESHOLD)
    except Exception as e:
        print("Error reading back attribute:", e)

    print("Readback Data Channel:", channel)
    print("Phy trig. mode:", phy_trig_mode_rbk)
    print("Vir trig. mode:", vir_trig_mode_rbk)
    print("Logical op:", vir_op_rbk)
    print("Phy Mask:", phy_mask_rbk)
    print("Vir Mask:", vir_mask_rbk)
    print("Polarity:", polarity_rbk)
    print("Range:", range_rbk)
    print("Debounce time: {:.4f} ms".format(debounce_rbk))
    print("Threshold: {:.4f} V".format(threshold_rbk))
    print()

    # ----------------------------- Capture Engine Setup --------------------------------- #
    try:
        # Front Panel physical mask (all channels enabled)
        fp_phy_mask = 0xFFFF
        card.SetAttributeDWORD(channel, False, pilxi.Attributes.CMP_PHY_FPT_MASK, fp_phy_mask)
    except Exception as e:
        print("CMP_PHY_FPT_MASK failed:", e)

    try:
        # Front Panel virtual mask (all channels enabled)
        fp_vir_mask = 0xFFFF
        card.SetAttributeDWORD(channel, False, pilxi.Attributes.CMP_VIR_FPT_MASK, fp_vir_mask)
    except Exception as e:
        print("CMP_VIR_FPT_MASK failed:", e)

    try:
        # Reset the front panel trigger
        card.SetAttributeDWORD(channel, False, pilxi.Attributes.CMP_FPT_RESET, 0)
    except Exception as e:
        print("CMP_FPT_RESET failed:", e)

    try:
        # Set capture append mode to disabled (new events overwrite previous data)
        capture_append = 0
        card.SetAttributeDWORD(channel, False, pilxi.Attributes.CMP_CAPTURE_APPEND, capture_append)
    except Exception as e:
        print("CMP_CAPTURE_APPEND failed:", e)

    # Allow time delay equal to debounce time before enabling capture
    time.sleep(debounce_time / 1000.0)

    try:
        # Enable the capture engine (1 = enable)
        capture_enable = 1
        card.SetAttributeDWORD(channel, False, pilxi.Attributes.CMP_CAPTURE_ENABLE, capture_enable)
    except Exception as e:
        print("CMP_CAPTURE_ENABLE failed:", e)

    print("\nCapturing Events Enabled")
    print("Press 's' to get current state of the card.")
    print("Press any other key to disable capturing and display recorded events.\n")

    disp_columns = False
    while True:
        ch = input("Press a key (s for status, any other to quit): ")
        if ch.lower() == 's':
            try:
                phy_state = card.GetAttributeDWORD(channel, False, pilxi.Attributes.CMP_PHY_STATE)
                vir_state = card.GetAttributeDWORD(channel, False, pilxi.Attributes.CMP_VIR_STATE)
                time_stamp_current = card.GetAttributeDWORDArray(channel, False, pilxi.Attributes.CMP_TIME_STAMP,2)
                index = card.GetAttributeDWORD(channel, False, pilxi.Attributes.CMP_CAPTURE_INDEX)
            except Exception as e:
                print("Error retrieving card state:", e)
                continue

            if not disp_columns:
                print("--------------Current State Data--------------")
                print("Physical State     Virtual State    Index    Timestamp")
                disp_columns = True

            # Display states; hexadecimal formatting is used for bit masks
            print("{:<18} {:<16} {:<8} {}".format(hex(phy_state), hex(vir_state), index, time_stamp_current))
            continue

        # ------------------------ Disable Capture and read events ------------------------ #
        try:
            capture_enable = 0
            card.SetAttributeDWORD(channel, False, pilxi.Attributes.CMP_CAPTURE_ENABLE, capture_enable)
        except Exception as e:
            print("Disabling capture failed:", e)

        try:
            index = card.GetAttributeDWORD(channel, False, pilxi.Attributes.CMP_CAPTURE_INDEX)
            read_offset = 0
            card.SetAttributeDWORD(channel, False, pilxi.Attributes.CMP_READ_OFFSET, read_offset)
            time_stamp_ref = card.GetAttributeDWORDArray(channel, False, pilxi.Attributes.CMP_TIME_STAMP_REF,2)
        except Exception as e:
            print("Error fetching capture parameters:", e)
            index = 0

        if index:
            print("\n---------------------------RECORDED EVENTS---------------------------\n")
            print("Number of recorded events:", index)
            print("Time Stamp Ref:", time_stamp_ref)
            print("Raw Phy Data    Raw Vir Data    Event Phy Data    Event Vir Data    Timestamp")
        else:
            print("\nNO EVENTS RECORDED\n")

        # Loop over each recorded event (each call returns an array of 4 DWORD values)
        for i in range(read_offset, index):
            try:
                data_read = card.GetAttributeDWORDArray(channel, False, pilxi.Attributes.CMP_READ_DDR3,4)
            except Exception as e:
                print("Error reading event data:", e)
                break
            # Data layout interpretation (assuming a 4-element array)
            raw_phy_data   = (data_read[3] >> 16) & 0xFFFF
            raw_vir_data   = data_read[3] & 0xFFFF
            event_phy_data = (data_read[2] >> 16) & 0xFFFF
            event_vir_data = data_read[2] & 0xFFFF
            # Combine a 48-bit timestamp from two DWORDs
            time_stamp_event = (data_read[1] << 32) | data_read[0]
            print("{:<16} {:<16} {:<18} {:<18} {}".format(
                hex(raw_phy_data), hex(raw_vir_data),
                hex(event_phy_data), hex(event_vir_data), time_stamp_event))
        
        ch = input("Press 'y' to restart capture engine, any other key to quit: ")
        if ch.lower() == 'y':
            try:
                capture_enable = 1
                card.SetAttributeDWORD(channel, False, pilxi.Attributes.CMP_CAPTURE_ENABLE, capture_enable)
                print("\nCapturing Events Re-enabled\n")
            except Exception as e:
                print("Restarting capture engine failed:", e)
        else:
            break

    # -------------------- Reset and close the card --------------------- #
    try:
        card.ClearCard()
    except Exception as e:
        print("Clearing card failed:", e)

    try:
        card.Close()
    except Exception as e:
        print("Closing card failed:", e)

if __name__ == "__main__":
    main()

