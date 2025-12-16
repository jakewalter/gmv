#!/usr/bin/env python
"""
Quick test script to check Oklahoma earthquake catalog without full processing.
"""

import json
from urllib.request import Request, urlopen
from datetime import datetime

# Oklahoma region boundaries
OK_MIN_LAT = 33.6
OK_MAX_LAT = 37.0
OK_MIN_LON = -103.0
OK_MAX_LON = -94.4

start_date = "2010-01-01"
end_date = datetime.now().strftime("%Y-%m-%d")

url = (f"https://earthquake.usgs.gov/fdsnws/event/1/query?"
       f"format=geojson"
       f"&starttime={start_date}"
       f"&endtime={end_date}"
       f"&minmagnitude=4.5"
       f"&minlatitude={OK_MIN_LAT}"
       f"&maxlatitude={OK_MAX_LAT}"
       f"&minlongitude={OK_MIN_LON}"
       f"&maxlongitude={OK_MAX_LON}")

print(f"[INFO] Querying USGS for Oklahoma M4.5+ earthquakes since 2010...")
print(f"[INFO] Region: Lat [{OK_MIN_LAT}, {OK_MAX_LAT}], Lon [{OK_MIN_LON}, {OK_MAX_LON}]")

try:
    req = Request(url)
    response = urlopen(req, timeout=30)
    data = json.loads(response.read().decode('utf-8'))
    response.close()
    
    features = data.get('features', [])
    print(f"\n[INFO] Found {len(features)} M4.5+ earthquakes in Oklahoma since 2010\n")
    
    if len(features) > 0:
        print("Event List:")
        print("-" * 100)
        for idx, feature in enumerate(features, 1):
            props = feature.get('properties', {})
            coords = feature.get('geometry', {}).get('coordinates', [])
            
            timestamp_s = props.get('time', 0) / 1000.0
            dt = datetime.utcfromtimestamp(timestamp_s)
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            
            lat = coords[1] if len(coords) > 1 else 0
            lon = coords[0] if len(coords) > 0 else 0
            depth = coords[2] if len(coords) > 2 else 0
            mag = props.get('mag', 0)
            place = props.get('place', 'Unknown')
            
            print(f"{idx:3d}. {time_str} | M{mag:.1f} | Lat {lat:7.2f}, Lon {lon:8.2f} | Depth {depth:6.1f}km | {place}")
        print("-" * 100)

except Exception as er:
    print(f"[ERR] Error: {er}")
