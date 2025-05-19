# Run all of the tasks to prep newly written code for a commit to the github
echo Cleaning old formatted code
rm tminus/*.py
rm main.py
echo Removed old code
echo Ensuring the directory structure is correct
mkdir -p tminus
echo Directory creation done
echo Running job to format the code to the specifications
python3 format.py src/main.py main.py
python3 format.py src/tminus/__init__.py tminus/__init__.py # IDK
python3 format.py src/tminus/formatscrapeddata.py tminus/formatscrapeddata.py
python3 format.py src/tminus/getiplist.py tminus/getiplist.py
python3 format.py src/tminus/headinit.py tminus/headinit.py
python3 format.py src/tminus/ip2locdownload.py tminus/ip2locdownload.py
echo Done converting
echo Exiting...