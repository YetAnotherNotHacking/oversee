# This file is nessacary :100:
import os

def remove_ip2loc(DB_ZIP, DB_CSV):
    os.remove(DB_ZIP)
    os.remove(DB_CSV)

def remove_iplist(IP_LIST_FILE):
    os.remove(IP_LIST_FILE)