from flask import Flask, request, jsonify
from flask_socketio import SocketIO
from flask_cors import CORS
from datetime import datetime

# Initialize the web server
app = Flask(__name__)
CORS(app) # Allows our HTML webpage to connect securely
socketio = SocketIO(app, cors_allowed_origins="*")

print("==================================================")
print("☁️  MIDDLEMAN SERVER IS BOOTING UP...")
print("🎧 Listening for emergency signals from wearables...")
print("==================================================")

@app.route('/emergency_dispatch', methods=['POST'])
def receive_emergency():
    incoming_data = request.json
    
    
    # Check if the secret key matches
    if incoming_data.get('token') != "my-secret-watch-token":
        return jsonify({"error": "Unauthorized"}), 403
    
    
    patient_id = incoming_data.get('patient_id')
    gps_location = incoming_data.get('gps_location')
    danger_score = incoming_data.get('danger_score')
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("\n🚨🚨🚨 INCOMING EMERGENCY DISPATCH 🚨🚨🚨")
    print(f"⏰ Time: {timestamp}")
    print(f"👤 Patient ID: {patient_id}")
    print(f"📍 Location: {gps_location}")
    print(f"⚠️ AI Danger Score: {danger_score}")
    
    # This instantly fires the data to any open dashboard webpage
    socketio.emit('stemi_alert', incoming_data)
    print("🖥️  Action: Alert pushed to Doctor's Dashboard instantly!")

    return jsonify({"status": "success", "message": "Dispatch received."}), 200

# ==========================================
# THE NEW ADDITION: Listen for the Doctor's Click
# ==========================================
@socketio.on('doctor_dispatched')
def handle_dispatch():
    print("\n🚑 AMBULANCE DISPATCHED BY DOCTOR! Notifying Family Portal...")
    # Broadcast the confirmation back out to the family portal
    socketio.emit('ambulance_dispatched')


if __name__ == '__main__':
    # Notice we run socketio.run instead of app.run now
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)