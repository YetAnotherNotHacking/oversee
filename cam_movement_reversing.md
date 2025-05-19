# Camera movements
Reversing the camera movements. Better organization to come.

# Known types
*/SnapshotJPEG
*/cgi-bin/faststream.jpg
*/-wvhttp-01-/GetOneShot

# Known non moving cameras:
*/snap.jpg (BOSCH and similar)
*/video.mjpg (Axis and similar)
*/webcapture.jpg (blocked by a control planel login unknown brand)
*/nph-jpeg.cgi (StarDot Technologies)
*/asp/video.cgi

Mobotic m12 - 87.128.61.124:8082/control/userimage.html
ZOOM IN:
GET http://87.128.61.124:8082/control/click.cgi?zoomrel=250&dummy=425974
ZOOM OUT:
GET	
scheme
	http
host
	87.128.61.124:8082
filename
	/control/click.cgi with zoomrel=200 (copied wrong)

Panasonic BL-C111A 
181.39.25.74:50003/SnapshotJPEG ALL GET OPERATION
http://181.39.25.74:50003/CgiStart?page=Single&Language=11
Down: GET http://181.39.25.74:50003/nphControlCamera?Direction=TiltDown&Resolution=640x480&Quality=Standard&Mode=MPEG-4&RPeriod=0&Size=STD&PresetOperation=Move&Language=11
Up: http://181.39.25.74:50003/nphControlCamera?Direction=TiltUp&Resolution=640x480&Quality=Standard&Mode=MPEG-4&RPeriod=0&Size=STD&PresetOperation=Move&Language=11
Right: http://181.39.25.74:50003/nphControlCamera?Direction=PanRight&Resolution=640x480&Quality=Standard&Mode=MPEG-4&RPeriod=0&Size=STD&PresetOperation=Move&Language=11
Left: http://181.39.25.74:50003/nphControlCamera?Direction=PanLeft&Resolution=640x480&Quality=Standard&Mode=MPEG-4&RPeriod=0&Size=STD&PresetOperation=Move&Language=11
Scan up/down: http://181.39.25.74:50003/nphControlCamera?Direction=TiltScan&Resolution=640x480&Quality=Standard&Mode=MPEG-4&RPeriod=0&Size=STD&PresetOperation=Move&Language=11
Scan left/right: http://181.39.25.74:50003/nphControlCamera?Direction=PanScan&Resolution=640x480&Quality=Standard&Mode=MPEG-4&RPeriod=0&Size=STD&PresetOperation=Move&Language=11
Brightness up: http://181.39.25.74:50003/nphControlCamera?Direction=Brighter&Resolution=640x480&Quality=Standard&Mode=MPEG-4&RPeriod=0&Size=STD&PresetOperation=Move&Language=11
Brightness down: http://181.39.25.74:50003/nphControlCamera?Direction=Darker&Resolution=640x480&Quality=Standard&Mode=MPEG-4&RPeriod=0&Size=STD&PresetOperation=Move&Language=11

Canon VB-M42
* Movement type is slider... that's going to be fun!
e.g. link 120.51.157.146:1024/-wvhttp-01-/GetOneShot
Claim camera control: GET http://120.51.157.146:1024/-wvhttp-01-/claim.cgi?s=822d-5165781b&seq=0.4882067940643404
Move camera tilt http://120.51.157.146:1024/-wvhttp-01-/control.cgi?s=822d-1472900a&c.1.tilt=1000&seq=0.34357813110946833
Move camera pan http://120.51.157.146:1024/-wvhttp-01-/control.cgi?s=822d-1472900a&c.1.pan=1486&seq=0.14247845971460438
Move camera zoom http://120.51.157.146:1024/-wvhttp-01-/control.cgi?s=822d-1472900a&c.1.zoom=971&seq=0.3786534383814879
MAX TILT http://120.51.157.146:1024/-wvhttp-01-/control.cgi?s=822d-1472900a&c.1.tilt=1000&seq=0.2451165698248401
MIN TILT http://120.51.157.146:1024/-wvhttp-01-/control.cgi?s=822d-1472900a&c.1.tilt=-9000&seq=0.5593425581860101
MIN PAN http://120.51.157.146:1024/-wvhttp-01-/control.cgi?s=822d-1472900a&c.1.pan=-17000&seq=0.21382371777689768
MAX PAN http://120.51.157.146:1024/-wvhttp-01-/control.cgi?s=822d-1472900a&c.1.pan=17000&seq=0.10706612394004256
MIN ZOOM http://120.51.157.146:1024/-wvhttp-01-/control.cgi?s=822d-1472900a&c.1.zoom=6040&seq=0.5784726761357728
MAX ZOOM http://120.51.157.146:1024/-wvhttp-01-/control.cgi?s=822d-1472900a&c.1.zoom=320&seq=0.4222188636815958



