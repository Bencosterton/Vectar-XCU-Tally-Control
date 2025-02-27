# Vectar Switcher Monitor

A Flask-based web application that monitors and displays the program and preview sources from a Viz Vectar switcher, and sends tally commands to camera systems.

## Features
- Real-time monitoring of program and preview sources
- Displays friendly names (iso_labels) for each source
- Auto-refreshing web interface
- Clean and intuitive display
- Camera tally control via XML commands
- Support for multiple program sources
- XCU Basestation integration for tally control

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
- Supports XCU Basestation format with Tally_Ethernet_Red and Tally_Ethernet_Green parameters
- Sends commands to configured camera IPs
- Only sends updates when the tally state changes
- Runs in a background thread for non-blocking operation
- Generates XML files for manual transfer when direct network connection is not available

### Testing Tally Commands
You can test tally commands directly using:

```bash
python tally_sender.py --test
```

This will send test program, preview, and off commands to all configured cameras.

## XCU Basestation Integration

This system supports direct integration with Grassvalley XCU Universal basestations for camera tally control. The integration uses socket communication to send XML commands to the basestation.

### Configuration

Configure the XCU basestation in `app.py`:

```python
# Controllers configuration
CONTROLLERS = [
    {
        'name': 'XCU Basestation',
        'type': 'xml',
        'ip': '10.10.126.51',  # Replace with your basestation IP
        'port': 8080,          # Replace with your basestation port
        'serial': '03G36P',    # Replace with your basestation serial number
        'device_id': 'XCU-09', # Replace with your basestation device ID
        'package': 'v05.00'    # Replace with your basestation package version
    }
]

# Camera to XCU mapping
CAMERA_TO_XCU = {
    'input1': 'XCU-01',
    'input2': 'XCU-02',
    # Add mappings for all your cameras
}
```

### XML Command Formats

The system supports multiple XML command formats for XCU basestations:

1. **Standard Format**: Basic tally control format
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <request type="tally-control">
     <camera id="input9">
       <tally program="true" preview="false" />
     </camera>
   </request>
   ```

2. **XCU Format 1**: Command structure with parameters
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <Command version="2.0">
     <SetParameter>
       <Device serial="03G36P">XCU-09</Device>
       <Parameter name="Tally_Ethernet_Red">ON</Parameter>
       <Parameter name="Tally_Ethernet_Green">OFF</Parameter>
     </SetParameter>
   </Command>
   ```

3. **XCU Format 2**: Simple basestation structure
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <Basestation serial="03G36P">
     <DeviceId>
       <XCU-09>
         <Tally_Ethernet_Red>ON</Tally_Ethernet_Red>
         <Tally_Ethernet_Green>OFF</Tally_Ethernet_Green>
       </XCU-09>
     </DeviceId>
   </Basestation>
   ```

4. **XCU Format 3**: GVG-style direct parameter
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <C2IP version="2.0">
     <BaseStation serial="03G36P" type="XCU Univ" package="v05.00">
       <Camera id="09">
         <Control type="Tally" program="true" preview="false" />
       </Camera>
     </BaseStation>
   </C2IP>
   ```

5. **XCU Format 5**: Simplified camera tally format
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <request>
     <camera id="09">
       <tally red="ON" green="OFF" />
     </camera>
   </request>
   ```

6. **XCU Format 6**: Parameter-based format
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <request>
     <set-parameter>
       <device id="09" />
       <parameter name="tally.red" value="true" />
       <parameter name="tally.green" value="false" />
     </set-parameter>
   </request>
   ```

7. **XCU Format 7**: C2IP protocol format
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <C2IP version="1.1">
     <Camera id="09">
       <Tally red="ON" green="OFF" />
     </Camera>
   </C2IP>
   ```

The system will automatically try all formats in sequence until one succeeds.

### Communication Methods

The system uses the following communication methods in order of preference:

1. **Socket Connection**: Direct TCP socket connection to the basestation
2. **HTTP Connection**: HTTP POST request to the basestation
3. **File Output**: If both connection methods fail, the system will write the XML commands to files

### Testing

Use the `test_xcu_direct_send.py` script to test communication with the basestation:

```bash
python test_xcu_direct_send.py --ip 10.10.126.51 --port 8080 --red
```

Options:
- `--ip`: Basestation IP address
- `--port`: Basestation port
- `--red`: Set red tally
- `--green`: Set green tally
- `--format`: XML format to use (0=all, 1-7=specific format)
- `--method`: Connection method (http, socket, both)

## File-Based Tally Control
When cameras don't have direct network connectivity, the system generates XML files in the `tally_xml_output` directory. These files can be:

1. Manually transferred to the camera control system
2. Accessed via a network share
3. Processed by a custom script

The system generates multiple XML formats with timestamp-based filenames:
- `tally_[camera]_[timestamp].xml`: Standard format
- `tally_[camera]_[timestamp]_xcu.xml`: Primary XCU format
- `xcu_tally_[camera]_[timestamp]_alt1.xml`: Alternative XCU format 1
- `xcu_tally_[camera]_[timestamp]_alt2.xml`: Alternative XCU format 2
- `xcu_tally_[camera]_[timestamp]_alt3.xml`: Alternative XCU format 3 (LDK Connect Gateway)

This multi-format approach ensures compatibility with different camera control systems and provides fallback options if one format doesn't work.

## Port Scanner
The application includes a port scanner to help identify camera tally control endpoints:

```bash
python port_scanner.py --common --probe
```

Options:
- `--common`: Scan only common ports
- `--full`: Scan all ports (1-65535)
- `--probe`: Probe open ports for HTTP and XML services
