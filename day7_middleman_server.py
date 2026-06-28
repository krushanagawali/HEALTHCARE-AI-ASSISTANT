from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
import sqlite3

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Database helper
def get_db():
    conn = sqlite3.connect('hospital.db')
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    return conn

@socketio.on('join_system')
def handle_join(data):
    patient_id = data.get('patient_id')
    family_id = request.sid # Using socket ID as family member session ID
    
    conn = get_db()
    c = conn.cursor()
    
    # Fetch patient record
    c.execute('SELECT * FROM patients WHERE patient_id = ?', (patient_id,))
    patient = c.fetchone()
    
    if patient:
        # Convert sqlite3.Row to dict for easy JSON emission
        patient_info = dict(patient)
        
        # 1. Update internal state (mapping family session to patient)
        # Assuming you have a dictionary tracking these connections
        # connected_families[family_id] = patient_id
        
        # 2. Emit the FULL info back to the family dashboard
        emit('link_success', {
            'patient_id': patient_info['patient_id'],
            'patient_name': patient_info['patient_name'],
            'patient_mobile': patient_info['patient_mobile'],
            'patient_address': patient_info['patient_address']
        }, to=family_id)
        
        # 3. Notify the Patient Dashboard that a family member has joined
        # (Assuming you track the patient's specific socket connection)
        emit('family_connected', {
            'name': patient_info['patient_name'],
            'mobile': patient_info['patient_mobile'],
            'address': patient_info['patient_address']
        }, room=f"patient_{patient_id}")
        
    conn.close()

# Add a route for the patient to join their own room
@socketio.on('patient_login')
def handle_patient_login(data):
    patient_id = data.get('patient_id')
    # Join the room specific to this patient
    from flask_socketio import join_room
    join_room(f"patient_{patient_id}")

if __name__ == '__main__':
    socketio.run(app, port=5000, debug=True)
