import asyncio
import datetime
import requests
from bleak import BleakClient

# Device Configuration from nRF Connect
MAC_ADDRESS = "95:AF:30:EF:51:03"
# Standard Bluetooth SIG Heart Rate Measurement Characteristic UUID
HR_UUID = "00002a37-0000-1000-8000-00805f9b34fb"

# Render Server Endpoint
SERVER_URL = "https://healthcare-ai-assistant-d3p8.onrender.com/update_vitals"
PATIENT_ID = "PATIENT_DEFAULT"


def parse_heart_rate(data: bytearray) -> int:
    """Decodes standard BLE Heart Rate Measurement payload (GATT 0x2A37)."""
    flags = data[0]
    # Bit 0 of flags determines if HR is 8-bit (uint8) or 16-bit (uint16)
    if (flags & 0x01) == 0:
        hr_value = data[1]
    else:
        hr_value = int.from_bytes(data[1:3], byteorder="little")
    return hr_value


def notification_handler(sender, data: bytearray):
    bpm = parse_heart_rate(data)
    now_str = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now_str}] 💓 Live Heart Rate from Fire-Boltt: {bpm} BPM")

    # Relay reading to Render backend
    payload = {
        "patient_id": PATIENT_ID,
        "heart_rate": bpm,
        "status": "nominal" if bpm < 120 else "elevated",
        "timestamp": now_str,
    }
    try:
        response = requests.post(SERVER_URL, json=payload, timeout=2)
        if response.status_code == 200:
            print(f"  -> Dispatched to Render server successfully.")
        else:
            print(f"  -> Render returned status {response.status_code}")
    except Exception as e:
        print(f"  -> Relay notice: Could not reach Render endpoint ({e})")


async def main():
    print(f"Scanning & connecting to Fire-Boltt ({MAC_ADDRESS})...")
    async with BleakClient(MAC_ADDRESS, timeout=20.0) as client:
        if client.is_connected:
            print(f"✅ Successfully paired and connected to {MAC_ADDRESS}!")

            # Subscribe to Heart Rate notifications
            await client.start_notify(HR_UUID, notification_handler)
            print("📡 Streaming live heart rate packets. Press Ctrl+C to stop.")

            # Keep connection alive
            try:
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                await client.stop_notify(HR_UUID)
                print("Stream stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDisconnected cleanly.")
    except Exception as err:
        print(f"\n❌ Connection error: {err}")
