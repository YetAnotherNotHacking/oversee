# Camera movements
Reversing the camera movements. Better organization to come.

# Known types
*/SnapshotJPEG
*/cgi-bin/faststream.jpg


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
181.39.25.74:50003/SnapshotJPEG
http://181.39.25.74:50003/CgiStart?page=Single&Language=11
Down: GET http://181.39.25.74:50003/nphControlCamera?Direction=TiltDown&Resolution=640x480&Quality=Standard&Mode=MPEG-4&RPeriod=0&Size=STD&PresetOperation=Move&Language=11
Up: http://181.39.25.74:50003/nphControlCamera?Direction=TiltUp&Resolution=640x480&Quality=Standard&Mode=MPEG-4&RPeriod=0&Size=STD&PresetOperation=Move&Language=11
Right: http://181.39.25.74:50003/nphControlCamera?Direction=PanRight&Resolution=640x480&Quality=Standard&Mode=MPEG-4&RPeriod=0&Size=STD&PresetOperation=Move&Language=11
Left: http://181.39.25.74:50003/nphControlCamera?Direction=PanLeft&Resolution=640x480&Quality=Standard&Mode=MPEG-4&RPeriod=0&Size=STD&PresetOperation=Move&Language=11
Scan up/down: http://181.39.25.74:50003/nphControlCamera?Direction=TiltScan&Resolution=640x480&Quality=Standard&Mode=MPEG-4&RPeriod=0&Size=STD&PresetOperation=Move&Language=11
Scan left/right: http://181.39.25.74:50003/nphControlCamera?Direction=PanScan&Resolution=640x480&Quality=Standard&Mode=MPEG-4&RPeriod=0&Size=STD&PresetOperation=Move&Language=11
Brightness up: http://181.39.25.74:50003/nphControlCamera?Direction=Brighter&Resolution=640x480&Quality=Standard&Mode=MPEG-4&RPeriod=0&Size=STD&PresetOperation=Move&Language=11
Brightness down: http://181.39.25.74:50003/nphControlCamera?Direction=Darker&Resolution=640x480&Quality=Standard&Mode=MPEG-4&RPeriod=0&Size=STD&PresetOperation=Move&Language=11

Generic Canon
e.g. link 153.142.207.159:80/-wvhttp-01-/GetOneShot
