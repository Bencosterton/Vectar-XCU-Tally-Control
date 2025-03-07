# Vectar Gras Valley Tally Relay

This Flask based app 'listens' to Viz Vectar tally infrmation and relays that info to Grass Valley LDK Gateway for triggering tallies on/off on cameras

## Setup
1. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure the Vectar IP address and camera IPs in `app.py`

3. Run the application:
   ```bash
   python app.py
   ```

4. Access the web interface at `http://localhost:5000`

## Configuration
- The Vectar IP address can be configured in the `app.py` file
- Camera IPs and ports can be configured in the `app.py` file
- XCU Basestation mapping can be configured in the `app.py` file
- Default refresh rate is 1 second
- Web interface runs on port 5000 by default

## Tally Sender Module
The application includes a tally sender module that forwards tally information to camera systems. The module:

- Automatically converts Vectar tally state to camera-compatible XML commands
- Supports XCU Basestation format with the Tally_Ethernet_Red peramiter
- Sends commands to configured camera IPs
- Only sends updates when the tally state changes
- Runs in a background thread for non-blocking operation


## XCU Basestation Integration

This system supports direct integration with Grassvalley XCU Universal basestations for camera tally control. The integration uses socket communication to send XML commands to the basestation.

See https://github.com/Bencosterton/Grass-Valley-LDX for some more info on the Grass Valley XML layouts etc.


### Configuration

Edit `app.py` and enter your Vectar IP address.
You will have to go to Grass Valley LDK Gateway software to investigate the paramiter_ids for the tallys of your cameras, I doubt they will be the same as mine
![Screenshot from 2025-02-27 13-23-38](https://github.com/user-attachments/assets/69d2a41c-6b26-4ac8-a987-0bceb829bdf6)

Open the Log File and play with your exiing control method (RCP, Control System) to see the responses for each camera, which will include the paramter ids.

### Options:
- `--ip`: Gateway IP address
- `--port`: Gateway port
- `--red`: Set red tally
