import asyncio
from bleak import BleakClient

# --- REPLACE THESE WITH YOUR NRF CONNECT DATA ---
MAC_ADDRESS = "95-AF-30-EF-51-03"
HR_UUID = "0x2902"

async def run(address):
    print(f"Connecting to {address}...")
    async with BleakClient(address) as client:
        print("Connected!")
        
        # This function runs every time the watch sends a new pulse
        def hr_handler(sender, data):
            # Decode the hexadecimal data. 
            # (Assuming standard BLE Heart Rate format where data[1] is the BPM)
            bpm = data[1] 
            print(f"Live Heart Rate: {bpm} BPM")
            
            # --- NEXT PHASE: We will add code here to send 'bpm' to your Streamlit app ---

        # Start listening to the watch
        await client.start_notify(HR_UUID, hr_handler)
        
        print("Listening for 60 seconds...")
        await asyncio.sleep(60)
        
        await client.stop_notify(HR_UUID)

# Run the Bluetooth script
asyncio.run(run(MAC_ADDRESS))
