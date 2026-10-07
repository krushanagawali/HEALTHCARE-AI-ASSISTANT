import os
import sqlite3
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, join_room
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

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
    room_name = data.get('room')
    role = data.get('role')
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
        patient_id = data.get('patient_id')
        name = data.get('name')
        mobile = data.get('mobile')
        address = data.get('address', 'N/A')
        
        c.execute('''INSERT OR REPLACE INTO patients (patient_id, patient_name, mobile, address) 
                     VALUES (?, ?, ?, ?)''', (patient_id, name, mobile, address))
        
        c.execute('''SELECT contact_name, mobile, address FROM family WHERE patient_id = ?''', (patient_id,))
        existing_family = c.fetchall()
        
        socketio.emit('existing_family', existing_family, to=request.sid)
        print(f"🫀 Patient {name} activated. Restored {len(existing_family)} family links.")

    elif role == 'family':
        patient_id = data.get('patient_id')
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
            print(f"👨‍👩‍👧 Family member {name} linked to patient {patient[0]}")
        else:
            socketio.emit('link_error', {'message': 'Patient ID not found! Patient must activate their wearable first.'}, to=request.sid)
            print(f"❌ Rejected family login: Patient {patient_id} does not exist.")

    conn.commit()
    conn.close()

# ==========================================
# 3. LIVE WEARABLE VITALS TELEMETRY (NEW)
# ==========================================
@app.route('/update_vitals', methods=['POST'])
def update_vitals():
    """Receives live heart rate from ble_reader.py and broadcasts it immediately."""
    incoming = request.get_json(force=True, silent=True) or {}
    
    patient_id = incoming.get('patient_id', 'PATIENT_DEFAULT')
    heart_rate = incoming.get('heart_rate')
    
    if heart_rate is None:
        return jsonify({"error": "Missing heart_rate"}), 400

    payload = {
        "patient_id": patient_id,
        "heart_rate": int(heart_rate),
        "status": incoming.get('status', 'nominal'),
        "timestamp": incoming.get('timestamp')
    }

    # Store in memory for instant polling
    latest_vitals_cache[patient_id] = payload

    # Broadcast to patient room and doctor channel via WebSockets
    socketio.emit('live_vitals', payload, to=f'room_{patient_id}')
    socketio.emit('live_vitals', payload, to='room_doctors')

    return jsonify({"status": "success", "received": payload}), 200

@app.route('/get_vitals/<patient_id>', methods=['GET'])
def get_vitals(patient_id):
    """Fallback endpoint for frontends polling vitals via HTTP."""
    data = latest_vitals_cache.get(patient_id)
    if data:
        return jsonify(data), 200
    return jsonify({"patient_id": patient_id, "heart_rate": 0, "status": "waiting_for_signal"}), 200

# ==========================================
# 4. ROUTING THE EMERGENCY DISPATCH
# ==========================================
@app.route('/emergency_dispatch', methods=['POST'])
def receive_emergency():
    incoming_data = request.json or {}
    
    if incoming_data.get('token') != SECRET_KEY:
        return jsonify({"error": "Unauthorized"}), 403
    
    patient_id = incoming_data.get('patient_id')
    print(f"\n🚨 [SERVER] RECEIVED STEMI ALERT FOR {patient_id}!")
    
    socketio.emit('stemi_alert', incoming_data, to=f'room_{patient_id}')
    socketio.emit('stemi_alert', incoming_data, to='room_doctors')
    
    return jsonify({"status": "success", "message": "Alert routed to Doctor and Family portals."})

@socketio.on('doctor_dispatched')
def handle_dispatch():
    print("\n🚑 AMBULANCE DISPATCHED BY DOCTOR! Notifying network...")
    socketio.emit('ambulance_dispatched')

# ==========================================
# 5. SESSION VERIFICATION (FIXED SYNTAX)
# ==========================================
@app.route('/verify_session', methods=['POST'])
def verify():
    data = request.json or {}
    patient_id = data.get('patient_id')

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
# 6. RUNNER (RENDER-AWARE PORT)
# ==========================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Middleman Server is running on port {port}...")
    socketio.run(app, host='0.0.0.0', port=port)
