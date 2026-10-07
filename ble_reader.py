import asyncio
import requests
from bleak import BleakClient
from datetime import datetime

# --- SETUP VARIABLES ---
# Note: Replaced hyphens with colons, which is standard for Bleak on Windows/Linux
MAC_ADDRESS = "95:AF:30:EF:51:03" 

# CRITICAL FIX: The standard BLE Heart Rate Characteristic UUID is 0x2A37.
# Bleak requires the full 128-bit standard UUID string:
HR_UUID = "00002a37-0000-1000-8000-00805f9b34fb" 

# Your Render Backend
RENDER_URL = "https://healthcare-ai-assistant-d3p8.onrender.com/update_vitals"
PATIENT_ID = "TEST_ID" # This matches the URL you just tested in the browser!

async def run(address):
    print(f"📡 Searching for Fire-Boltt Watch ({address})...")
    
    try:
        async with BleakClient(address) as client:
            print("✅ Connected to Watch!")
            
            # This function runs instantly every time the watch sends a new pulse
            def hr_handler(sender, data):
                try:
                    # Decode standard BLE Heart Rate format
                    bpm = data[1] 
                    print(f"🫀 Live Heart Rate: {bpm} BPM")
                    
                    # Create the JSON payload for your Render server
                    payload = {
                        "patient_id": PATIENT_ID,
                        "heart_rate": bpm,
                        "status": "active",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    
                    # Send data to the Cloud! (timeout=2 ensures Bluetooth doesn't freeze if Wi-Fi lags)
                    response = requests.post(RENDER_URL, json=payload, timeout=2)
                    
                    if response.status_code == 200:
                        print("   ☁️  Cloud Sync: SUCCESS")
                    else:
                        print(f"   ⚠️ Cloud Error: {response.status_code}")
                        
                except Exception as e:
                    print(f"   ❌ Data processing error: {e}")

            print("⏳ Initiating Heart Rate Stream...")
            await client.start_notify(HR_UUID, hr_handler)
            
            print("🟢 System is LIVE. Streaming data to Render... (Press Ctrl+C to stop)")
            
            # Changed from 60 seconds to run infinitely until you stop it
            while True:
                await asyncio.sleep(1)
                
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        print("Tip: Make sure the watch screen is awake, Bluetooth is on, and it isn't connected to your phone's official app right now.")

# Run the Bluetooth script
if __name__ == "__main__":
    asyncio.run(run(MAC_ADDRESS))
