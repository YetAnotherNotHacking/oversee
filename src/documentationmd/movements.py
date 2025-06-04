documentationmovements = """
# Camera Movements
Reversing the camera movements. Better organization to come.
Many of these are used to send movement commands to systems that serve JPEG images from known endpoints.

## Known Image Endpoints (Snapshot URLs)
These are typical paths used to fetch snapshots or streams from IP cameras:
*/SnapshotJPEG
*/cgi-bin/faststream.jpg
*/-wvhttp-01-/GetOneShot

## Non-Moving Cameras (or movement unknown/unavailable)
*/snap.jpg — BOSCH and similar
*/video.mjpg — Axis and similar
*/webcapture.jpg — Blocked by control panel login (unknown brand)
*/nph-jpeg.cgi — StarDot Technologies
*/asp/video.cgi

## Camera-Specific Movement Commands
### Mobotix M12
URL: 87.128.61.124:8082/control/userimage.html
#### Zoom Controls
##### Zoom In
GET http://87.128.61.124:8082/control/click.cgi?zoomrel=250&dummy=425974
##### Zoom Out
GET http://87.128.61.124:8082/control/click.cgi?zoomrel=200

### Panasonic BL-C111A
Base URL: http://181.39.25.74:50003
Snapshot Path: /SnapshotJPEG (GET)
#### Movement Commands
##### Down
/nphControlCamera?Direction=TiltDown&Resolution=640x480&Quality=Standard&Mode=MPEG-4&RPeriod=0&Size=STD&PresetOperation=Move&Language=11
##### Up
/nphControlCamera?Direction=TiltUp...
##### Right
/nphControlCamera?Direction=PanRight...
##### Left
/nphControlCamera?Direction=PanLeft...
##### Scan Up/Down
/nphControlCamera?Direction=TiltScan...
##### Scan Left/Right
/nphControlCamera?Direction=PanScan...
##### Brightness Up
/nphControlCamera?Direction=Brighter...
##### Brightness Down
/nphControlCamera?Direction=Darker...
### Canon VB-M482
Movement uses sliders (pan, tilt, zoom) with control tokens.
Snapshot Example:
http://120.51.157.146:1024/-wvhttp-01-/GetOneShot
#### Control Examples
##### Claim Camera Control
GET http://120.51.157.146:1024/-wvhttp-01-/claim.cgi?s=822d-5165781b&seq=0.4882067940643404
##### Tilt
GET http://120.51.157.146:1024/-wvhttp-01-/control.cgi?s=822d-1472900a&c.1.tilt=1000&seq=...
##### Pan
GET http://120.51.157.146:1024/-wvhttp-01-/control.cgi?s=822d-1472900a&c.1.pan=1486&seq=...
##### Zoom
GET http://120.51.157.146:1024/-wvhttp-01-/control.cgi?s=822d-1472900a&c.1.zoom=971&seq=...
##### Range Examples
MAX TILT: c.1.tilt=1000
MIN TILT: c.1.tilt=-9000
MIN PAN: c.1.pan=-17000
MAX PAN: c.1.pan=17000
MIN ZOOM: c.1.zoom=6040
MAX ZOOM: c.1.zoom=320
"""