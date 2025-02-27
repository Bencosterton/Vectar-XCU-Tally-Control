from flask import Flask, render_template, jsonify
import requests
from requests.auth import HTTPDigestAuth
import xml.etree.ElementTree as ET
from datetime import datetime
import threading
import time
import subprocess
import os

app = Flask(__name__)

# Configuration
VECTAR_IP = "10.9.81.80"
SWITCHER_URL = f"http://{VECTAR_IP}/v1/dictionary?key=switcher"
TALLY_URL = f"http://{VECTAR_IP}/v1/dictionary?key=tally"
UPDATE_INTERVAL = 1  # seconds

# Camera to XCU mapping
CAMERA_TO_XCU = {
    'input8': 'XCU-08',
    'input9': 'XCU-09',
    'input10': 'XCU-10',
}

# Authentication credentials
VECTAR_USER = 'admin'
VECTAR_PASS = 'XY23qazwsx18'

# Create auth object - using Digest Authentication
auth = HTTPDigestAuth(VECTAR_USER, VECTAR_PASS)

# Headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Accept': 'application/xml'
}

# Global variables to store the current state
current_state = {
    'program': [],  # List of program sources
    'preview': None,  # Single preview source
    'last_update': None,
    'status': 'Not Connected'
}

# Global variables to track tally states
tally_states = {}

# Path to the gv_tally_control.py script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GV_TALLY_SCRIPT = os.path.join(SCRIPT_DIR, "gv_tally_control.py")

def send_tally_command(xcu, tally_type, state):
    """
    Send tally command to a specific XCU using gv_tally_control.py
    
    Args:
        xcu: XCU identifier (e.g., XCU-09)
        tally_type: Type of tally (red, green, yellow)
        state: Tally state (True for on, False for off)
    """
    if not xcu:
        print(f"No XCU specified for tally command")
        return
    
    # Convert boolean state to on/off string
    state_str = "on" if state else "off"
    
    # Build the command
    cmd = [
        "python", 
        GV_TALLY_SCRIPT,
        f"--xcu", xcu,
        f"--{tally_type}", state_str
    ]
    
    # Log the command
    print(f"Sending {tally_type} tally {state_str} command to {xcu}")
    
    try:
        # Execute the command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        print(f"Successfully sent {tally_type} tally {state_str} to {xcu}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error sending tally command: {e.stderr}")
        return False

def get_source_labels(session):
    """Get the friendly names for all inputs from switcher endpoint"""
    try:
        response = session.get(SWITCHER_URL, auth=auth, headers=HEADERS, timeout=5)
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            labels = {}
            
            # Process physical inputs
            for input_elem in root.findall('.//physical_input'):
                input_num = input_elem.get('physical_input_number').lower()  # Convert Input1 to input1
                label = input_elem.get('iso_label')
                labels[input_num] = label
                
            return labels
        else:
            print(f"Error getting labels: HTTP {response.status_code}")
            return {}
    except Exception as e:
        print(f"Error getting labels: {e}")
        return {}

def get_tally_state(session, labels):
    """Get the current tally state from tally endpoint"""
    try:
        response = session.get(TALLY_URL, auth=auth, headers=HEADERS, timeout=5)
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            
            # Find all sources that are on program or preview
            program_sources = []
            preview_source = None
            
            for column in root.findall('.//column'):
                name = column.get('name')
                on_pgm = column.get('on_pgm') == 'true'
                on_prev = column.get('on_prev') == 'true'
                
                # Get friendly name if available
                friendly_name = labels.get(name, name)
                
                if on_pgm:
                    program_sources.append({
                        'source': name,
                        'label': friendly_name
                    })
                if on_prev:
                    preview_source = {
                        'source': name,
                        'label': friendly_name
                    }
            
            return program_sources, preview_source
        else:
            print(f"Error getting tally: HTTP {response.status_code}")
            return [], None
    except Exception as e:
        print(f"Error getting tally: {e}")
        return [], None

def update_tally_state():
    """Fetch and parse the XML data from Vectar"""
    global tally_states
    
    # Initialize tally states dictionary
    for camera in CAMERA_TO_XCU:
        tally_states[camera] = {
            'red': False,
            'green': False
        }
    
    while True:
        try:
            # Create a session to maintain cookies
            session = requests.Session()
            
            # First get the labels
            labels = get_source_labels(session)
            
            # Then get tally state
            program_sources, preview_source = get_tally_state(session, labels)
            
            # Update global state
            current_state['program'] = program_sources
            current_state['preview'] = preview_source
            current_state['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            current_state['status'] = 'Connected'
            
            # Debug output
            print("\nCurrent State:")
            print(f"Program Sources: {[p['label'] for p in program_sources]}")
            print(f"Preview Source: {preview_source['label'] if preview_source else 'None'}")
            
            # Update tally lights based on program and preview sources
            # Extract source names from program_sources
            program_source_names = [p['source'] for p in program_sources]
            preview_source_name = preview_source['source'] if preview_source else None
            
            # Process each camera
            for camera, xcu in CAMERA_TO_XCU.items():
                # Determine desired tally states
                should_be_red = camera in program_source_names
                should_be_green = camera == preview_source_name
                
                # Check if red tally state needs to change
                if tally_states[camera]['red'] != should_be_red:
                    send_tally_command(xcu, 'red', should_be_red)
                    tally_states[camera]['red'] = should_be_red
                
                # Check if green tally state needs to change
                if tally_states[camera]['green'] != should_be_green:
                    send_tally_command(xcu, 'green', should_be_green)
                    tally_states[camera]['green'] = should_be_green
                
        except Exception as e:
            print(f"Error updating state: {e}")
            current_state['status'] = f'Error: {str(e)}'
        
        # Wait before next update
        time.sleep(UPDATE_INTERVAL)

@app.route('/')
def index():
    return render_template('index.html', state=current_state)

@app.route('/status')
def status():
    return jsonify(current_state)

if __name__ == '__main__':
    # Start the background thread for updating tally state
    update_thread = threading.Thread(target=update_tally_state, daemon=True)
    update_thread.start()
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)
