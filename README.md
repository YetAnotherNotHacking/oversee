# OVERSEE Worldwide Viewer

A comprehensive GUI application for monitoring and managing IP cameras worldwide. The application provides multiple views including a map view, matrix view, and list view for efficient camera management.

## Features
- **Map View**: Visualize camera locations on an interactive map
  - Multiple map styles (OpenStreetMap, Google normal, Google satellite) using tkintermapview
  - Clickable markers with camera information (in development)
  - Real-time camera status updates
  - Automatic geolocation of IP addresses (using ipinfo)

- **Matrix View**: Grid display of multiple camera feeds
  - Real-time video streams
  - Customizable grid layout (not much but sure)
  - Camera status indicators

- **List View**: Detailed camera management
  - Comprehensive camera information
  - Camera controls (move, favorite, open in browser)
  - IP information lookup
  - Camera status monitoring

## Installation
Binaries coming soon. They will be located somewhere on silverflag.net. I'll update this with the link when it is ready.

## Function
1. The application will:
   - Initialize the IP coordinates database
   - Load camera information
   - Start the main GUI

2. Using the interface:
   - **Map View**: View and interact with camera locations
   - **Matrix View**: Monitor multiple camera feeds
   - **List View**: Manage individual cameras

## Configuration

### Settings File
The `settings.py` file contains important configuration options:
- IP list file location
- Database paths
- Map tile server settings
- Camera stream parameters

### IP List Format
The IP list file should contain one IP address per line:
The list is automatically scraped from Insecam currently.
```
192.168.1.1
10.0.0.1/video
camera.example.com:8080
```

## Project Structure

```
oversee-main/
├── cam_movement_reversing.md         # Trying to add functionality to the move feature
├── prepforcommit.sh                  # OLD DO NOT USE IT
├── .gitignore                        # ... Obv its git ignore?
├── src/
│   │   ├── maingui.py                # Main GUI implementation
│   ├── gui/                          # All GUI related code
│   │   ├── maingui.py                # Main GUI implementation
│   │   ├── aboutgui.py               # Fancy about menu
│   │   ├── focusedstreamgui.py       # Open stream in new window
│   │   ├── settingsgui.py            # Settigs window
│   │   ├── initgui.py                # Loading menu
│   │   ├── movementgui.py            # Camera movement remote
│   │   ├── focusedmapgui.py          # Focused map view "view on map" in list view
│   │   └── rendermatrix.py           # Matrix view rendering
│   ├── backend/                      # Not really backend, just camera management stuff
│   │   ├── cameradown.py             # All things that are camera > user
│   │   ├── cameraup.py               # All things that are user > camera
│   ├── initdata/                     # All of the prelaunch prep ran by initgui
│   │   ├── getiplistcoordinates.py   # IP coordinate processing
│   │   ├── formatscrapeddata.py      # Make the scraped ip list compliant with the program
│   │   ├── getiplist.py              # Threaded insecam scraper
│   │   ├── headinit.py               # Deprecated and unused function for init (now in initgui)
│   │   ├── validateiplist.py         # Remove IPs that don't respond (intentionally broken)
│   │   └── ip2locdownload.py         # Download less precise backup IP2Loc databases
│   └── utility/                      # Misc escentially.
│       ├── ip2loc.py                 # IP geolocation utilities
│       ├── camera_manager.py         # I think unused (maybe) function for managing timed out streams
│       └── iplist.py                 # IP list handling (e.g. read range)
├── data/                             # Data that the program gets when it runs
│   ├── ip_info.db                    # IP coordinate database (stump to grow is at [here](https://silverflag.net/oversee/ip_info.raw))
│   ├── other                         # General backup ip2loc database files
│   └── cameras.db                    # Camera status database (Online, Offline, Unkown)
├── main.py                           # Application entry point (runs init and everything)
└── requirements.txt                  # Python dependencies
```
## Development

### Adding New Features
1. Fork the repository
2. Create a feature branch
3. Implement your changes
4. Submit a pull request

### Code Style
- Follow PEP 8 guidelines
- Use meaningful variable names
- Add comments for complex logic
- Update documentation as needed

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## License
None. Steal it and put sprinkles on it.

## Acknowledgments
- IP geolocation data provided by ipinfo.io
- Map tiles from OpenStreetMap and Google Maps
- All contributors and users of the project

## Support
For support, please:
1. Check the documentation (there isn't any yet but there will be)
2. Search existing issues (In GitHub)
3. Create a new issue if needed (Also In GitHub)