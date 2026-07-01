from flask import Flask, request, jsonify
from flask_socketio import SocketIO, join_room
from flask_cors import CORS
import sqlite3

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# ==========================================
# 1. DATABASE SETUP
# ==========================================
def init_db():
    conn = sqlite3.connect('hospital.db')
    c = conn.cursor()
    
    # Patients Table (Now includes Address)
    c.execute('''CREATE TABLE IF NOT EXISTS patients 
                 (patient_id TEXT PRIMARY KEY, patient_name TEXT, mobile TEXT, address TEXT)''')
    
    # Family Table (Now includes Address)
    c.execute('''CREATE TABLE IF NOT EXISTS family 
                 (family_id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id TEXT, contact_name TEXT, mobile TEXT, address TEXT)''')
    
    # Doctors Table
    c.execute('''CREATE TABLE IF NOT EXISTS doctors 
                 (doctor_id TEXT PRIMARY KEY, doctor_name TEXT, hospital_name TEXT, mobile TEXT, landline TEXT, address TEXT)''')
    
    conn.commit()
    conn.close()
    print("🗄️ Real-world Database initialized with Doctor, Patient, and Family tables!")

init_db()

SECRET_KEY = "my-secret-watch-token"

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
        
        # Save Doctor to Database
        c.execute('''INSERT OR REPLACE INTO doctors (doctor_id, doctor_name, hospital_name, mobile, landline, address) 
                     VALUES (?, ?, ?, ?, ?, ?)''', (doc_id, name, hosp, mobile, landline, address))
        print(f"🩺 Doctor {name} saved to database.")

    elif role == 'patient':
        patient_id = data.get('patient_id')
        name = data.get('name')
        mobile = data.get('mobile')
        address = data.get('address', 'N/A')
        
        # Save Patient to Database
        c.execute('''INSERT OR REPLACE INTO patients (patient_id, patient_name, mobile, address) VALUES (?, ?, ?, ?)''', (patient_id, name, mobile, address))
        
        # Fetch Family
        c.execute('''SELECT contact_name, mobile, address FROM family WHERE patient_id = ?''', (patient_id,))
        existing_family = c.fetchall()
        
        socketio.emit('existing_family', existing_family, to=request.sid)
        print(f"🫀 Patient {name} activated. Restored {len(existing_family)} family links.")

    elif role == 'family':
        patient_id = data.get('patient_id')
        name = data.get('name')
        mobile = data.get('mobile')
        address = data.get('address', 'N/A')
        
        # Check if Patient Exists
        c.execute('''SELECT patient_name, mobile, address FROM patients WHERE patient_id = ?''', (patient_id,))
        patient = c.fetchone()
        
        if patient:
            # Save Family to Database
            c.execute('''SELECT * FROM family WHERE patient_id = ? AND mobile = ?''', (patient_id, mobile))
            if not c.fetchone():
                c.execute("INSERT INTO family (patient_id, contact_name, mobile, address) VALUES (?, ?, ?, ?)", (patient_id, name, mobile, address))
            
            socketio.emit('family_connected', {'name': name, 'mobile': mobile, 'address': address}, to=room_name)
            
            socketio.emit('link_success', {
                'patient_id': patient_id,
                'patient_name': patient[0],
                'patient_mobile': patient[1],
                'patient_address': patient[2]
            }, to=request.sid)
            print(f"👨‍👩‍👧 Family member {name} securely linked to patient {patient[0]}")
        else:
            socketio.emit('link_error', {'message': 'Patient ID not found! The patient must activate their wearable first.'}, to=request.sid)
            print(f"❌ Rejected family login: Patient {patient_id} does not exist.")

    conn.commit()
    conn.close()

# ==========================================
# 3. ROUTING THE EMERGENCY
# ==========================================
@app.route('/emergency_dispatch', methods=['POST'])
def receive_emergency():
    incoming_data = request.json
    
    # FIXED: ge8t typo corrected to get
    if incoming_data.get('token') != SECRET_KEY:
        return jsonify({"error": "Unauthorized"}), 403
    
    # FIXED: incoming_d ukata typo corrected to incoming_data
    patient_id = incoming_data.get('patient_id')
    print(f"\n🚨 [SERVER] RECEIVED STEMI ALERT FOR {patient_id}!")
    
    socketio.emit('stemi_alert', incoming_data, to=f'room_{patient_id}')
    socketio.emit('stemi_alert', incoming_data, to='room_doctors')
    
    return jsonify({"status": "success", "message": "Alert routed to Doctor and Family portals."})

@socketio.on('doctor_dispatched')
def handle_dispatch():
    print("\n🚑 AMBULANCE DISPATCHED BY DOCTOR! Notifying network...")
    socketio.emit('ambulance_dispatched')
#4.verify storage
@app.route('/verify_session', methods=['POST'])
def verify():
    data = request.json
    # Logic to check if this user exists in your sqlite hospital.db
    # Return the user's saved info so the dashboard can re-populate its UI
    return jsonify({"status": "active", "profile": ...})


if __name__ == '__main__':
    print("🚀 Middleman Server is running on port 5000...")
    socketio.run(app, host='0.0.0.0', port=5000)
