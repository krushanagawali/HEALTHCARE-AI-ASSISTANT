import os
import sqlite3
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, join_room
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

SECRET_KEY = "my-secret-watch-token"

# In-memory store for the latest telemetry reading per patient
latest_vitals_cache = {}

# ==========================================
# 1. DATABASE SETUP
# ==========================================
def init_db():
    conn = sqlite3.connect('hospital.db')
    c = conn.cursor()
    
    # Patients Table
    c.execute('''CREATE TABLE IF NOT EXISTS patients 
                 (patient_id TEXT PRIMARY KEY, patient_name TEXT, mobile TEXT, address TEXT)''')
    
    # Family Table
    c.execute('''CREATE TABLE IF NOT EXISTS family 
                 (family_id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id TEXT, contact_name TEXT, mobile TEXT, address TEXT)''')
    
    # Doctors Table
    c.execute('''CREATE TABLE IF NOT EXISTS doctors 
                 (doctor_id TEXT PRIMARY KEY, doctor_name TEXT, hospital_name TEXT, mobile TEXT, landline TEXT, address TEXT)''')
    
    conn.commit()
    conn.close()
    print("🗄️ Database initialized with Doctor, Patient, and Family tables.")

init_db()

# ==========================================
# 2. MANAGING PRIVATE ROOMS & DB SAVING
# ==========================================
@socketio.on('join_system')
def on_join(data):
    role = str(data.get('role', '')).strip().lower()
    patient_id = str(data.get('patient_id', '')).strip().upper()
    room_name = f'room_{patient_id}' if patient_id else str(data.get('room', '')).strip()

    if room_name:
        join_room(room_name)
    print(f"🔒 {role.upper()} connected to channel: {room_name}")

    conn = sqlite3.connect('hospital.db')
    c = conn.cursor()

    if role == 'doctor':
        doc_id = data.get('doctor_id')
        name = data.get('name')
        hosp = data.get('hospital')
        mobile = data.get('mobile', 'N/A')
        landline = data.get('landline', 'N/A')
        address = data.get('address', 'N/A')
        
        c.execute('''INSERT OR REPLACE INTO doctors (doctor_id, doctor_name, hospital_name, mobile, landline, address) 
                     VALUES (?, ?, ?, ?, ?, ?)''', (doc_id, name, hosp, mobile, landline, address))
        print(f"🩺 Doctor {name} saved to database.")

    elif role == 'patient':
        name = data.get('name')
        mobile = data.get('mobile')
        address = data.get('address', 'N/A')
        
        c.execute('''INSERT OR REPLACE INTO patients (patient_id, patient_name, mobile, address) 
                     VALUES (?, ?, ?, ?)''', (patient_id, name, mobile, address))
        
        c.execute('''SELECT contact_name, mobile, address FROM family WHERE patient_id = ?''', (patient_id,))
        existing_family = c.fetchall()
        
        socketio.emit('existing_family', existing_family, to=request.sid)
        print(f"🫀 Patient {name} ({patient_id}) activated. Restored {len(existing_family)} family links.")

    elif role == 'family':
        name = data.get('name')
        mobile = data.get('mobile')
        address = data.get('address', 'N/A')
        
        c.execute('''SELECT patient_name, mobile, address FROM patients WHERE patient_id = ?''', (patient_id,))
        patient = c.fetchone()
        
        if patient:
            c.execute('''SELECT * FROM family WHERE patient_id = ? AND mobile = ?''', (patient_id, mobile))
            if not c.fetchone():
                c.execute("INSERT INTO family (patient_id, contact_name, mobile, address) VALUES (?, ?, ?, ?)", 
                          (patient_id, name, mobile, address))
            
            socketio.emit('family_connected', {'name': name, 'mobile': mobile, 'address': address}, to=room_name)
            socketio.emit('link_success', {
                'patient_id': patient_id,
                'patient_name': patient[0],
                'patient_mobile': patient[1],
                'patient_address': patient[2]
            }, to=request.sid)
            print(f"👨‍👩‍👧 Family member {name} linked to patient {patient[0]} in {room_name}")
        else:
            socketio.emit('link_error', {'message': 'Patient ID not found! Patient must activate their wearable first.'}, to=request.sid)
            print(f"❌ Rejected family login: Patient {patient_id} does not exist.")

    conn.commit()
    conn.close()

# ==========================================
# 3. LIVE WEARABLE VITALS TELEMETRY
# ==========================================
@app.route('/update_vitals', methods=['POST'])
def update_vitals():
    """Receives live vitals from ble_reader.py or ESP32 and broadcasts immediately."""
    incoming = request.get_json(force=True, silent=True) or {}
    
    patient_id = str(incoming.get('patient_id', 'PATIENT_DEFAULT')).strip().upper()
    heart_rate = incoming.get('heart_rate')
    ecg_value = incoming.get('ecg_value')
    
    if heart_rate is None:
        return jsonify({"error": "Missing heart_rate"}), 400

    payload = {
        "patient_id": patient_id,
        "heart_rate": int(heart_rate),
        "ecg_value": ecg_value,
        "status": incoming.get('status', 'nominal'),
        "timestamp": incoming.get('timestamp')
    }

    latest_vitals_cache[patient_id] = payload

    target_room = f'room_{patient_id}'
    print(f"💓 Broadcasting live_vitals to {target_room}: HR={payload['heart_rate']}, ECG={ecg_value}")
    socketio.emit('live_vitals', payload, to=target_room)
    socketio.emit('live_vitals', payload, to='room_doctors')

    return jsonify({"status": "success", "received": payload}), 200

@app.route('/get_vitals/<patient_id>', methods=['GET'])
def get_vitals(patient_id):
    """Fallback endpoint for frontends polling vitals via HTTP."""
    clean_id = str(patient_id).strip().upper()
    data = latest_vitals_cache.get(clean_id)
    if data:
        return jsonify(data), 200
    return jsonify({"patient_id": clean_id, "heart_rate": 0, "status": "waiting_for_signal"}), 200

# ==========================================
# 4. ROUTING THE EMERGENCY DISPATCH
# ==========================================
@app.route('/emergency_dispatch', methods=['POST'])
def receive_emergency():
    incoming_data = request.json or {}
    
    if incoming_data.get('token') != SECRET_KEY:
        return jsonify({"error": "Unauthorized"}), 403
    
    patient_id = str(incoming_data.get('patient_id', '')).strip().upper()
    print(f"\n🚨 [SERVER] RECEIVED STEMI ALERT FOR {patient_id}!")
    
    socketio.emit('stemi_alert', incoming_data, to=f'room_{patient_id}')
    socketio.emit('stemi_alert', incoming_data, to='room_doctors')
    
    return jsonify({"status": "success", "message": "Alert routed to Doctor and Family portals."})

@socketio.on('doctor_dispatched')
def handle_dispatch():
    print("\n🚑 AMBULANCE DISPATCHED BY DOCTOR! Notifying network...")
    socketio.emit('ambulance_dispatched')

# ==========================================
# 5. SESSION VERIFICATION
# ==========================================
@app.route('/verify_session', methods=['POST'])
def verify():
    data = request.json or {}
    patient_id = str(data.get('patient_id', '')).strip().upper()

    conn = sqlite3.connect('hospital.db')
    c = conn.cursor()
    c.execute('SELECT patient_id, patient_name, mobile, address FROM patients WHERE patient_id = ?', (patient_id,))
    patient = c.fetchone()
    conn.close()

    if patient:
        return jsonify({
            "status": "active",
            "profile": {
                "patient_id": patient[0],
                "name": patient[1],
                "mobile": patient[2],
                "address": patient[3]
            }
        }), 200

    return jsonify({"status": "not_found", "profile": None}), 404

# ==========================================
# 6. HIGH-SPEED REAL ECG RELAY
# ==========================================
@socketio.on('stream_real_ecg')
def handle_real_ecg(data):
    """Instantly relays the real ESP32 ECG wave from Patient to Family."""
    patient_id = str(data.get('patient_id', '')).strip().upper()
    if patient_id:
        target_room = f'room_{patient_id}'
        print(f"📡 Relaying ECG to {target_room}: raw={data.get('raw_ecg')}, mv={data.get('mv_ecg')}")
        socketio.emit('live_real_ecg', data, to=target_room)
    else:
        print("⚠️ stream_real_ecg received WITHOUT patient_id:", data)

# ==========================================
# 7. RUNNER (RENDER-AWARE PORT)
# ==========================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Middleman Server is running on port {port}...")
    socketio.run(app, host='0.0.0.0', port=port)
