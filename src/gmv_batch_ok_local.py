#!/usr/bin/env python
"""
Name:
    gmv_batch_ok_local.py

Description:
    This script queries the USGS Earthquake Hazards Program API to find all magnitude 4.5 or greater
    earthquakes within Oklahoma since 2010. For each earthquake found, it runs the gmv_generalized.py 
    script to generate a ground motion visualization (GMV) animation using Oklahoma seismic stations.
    The script automatically picks P and S phases for stations within Oklahoma. Output videos are saved 
    with filenames following the pattern: YYYYMMDD_OKlocal_Magnitude4.5.mp4
    
    Networks included: OK, US, N4, XO, O2, Y7, Y9, ZP, TA, IU (Oklahoma-focused)
    Channels included: Broadband (LH*, BH*, HH*) and non-broadband (EH*, SH*) stations

Usage:
    python gmv_batch_ok_local.py [--report-only]

Requirements:
    - requests library for HTTP requests
    - ObsPy for earthquake data handling
    - gmv_generalized.py script in the same directory
    - Internet access to query USGS API

Author:
    Created for local Oklahoma seismic analysis

History:
    2025-11-03: Initial creation for local Oklahoma events
"""

import sys
import os
import json
import subprocess
import time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from datetime import datetime

# Add the parent directory to the path to import gmv utilities
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import gmv_utils as utils
except ImportError:
    print("[ERR] Could not import gmv_utils. Make sure gmv_utils.py is in the same directory.")
    sys.exit(1)


# Oklahoma region boundaries
OK_MIN_LAT = 33.6
OK_MAX_LAT = 37.0
OK_MIN_LON = -103.0
OK_MAX_LON = -94.4


def get_oklahoma_earthquakes(min_magnitude=4.5, start_year=2010):
    """
    Query the USGS Earthquake Hazards Program API for earthquakes in Oklahoma.
    
    Parameters:
    -----------
    min_magnitude : float
        Minimum magnitude to retrieve (default: 4.5)
    start_year : int
        Starting year for earthquake query (default: 2010)
    
    Returns:
    --------
    list : List of earthquake dictionaries with relevant information
    """
    
    start_date = f"{start_year}-01-01"
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    # USGS GeoJSON API endpoint for earthquake data within Oklahoma bounds
    url = (f"https://earthquake.usgs.gov/fdsnws/event/1/query?"
           f"format=geojson"
           f"&starttime={start_date}"
           f"&endtime={end_date}"
           f"&minmagnitude={min_magnitude}"
           f"&minlatitude={OK_MIN_LAT}"
           f"&maxlatitude={OK_MAX_LAT}"
           f"&minlongitude={OK_MIN_LON}"
           f"&maxlongitude={OK_MAX_LON}")
    
    print(f"\n[INFO] Querying USGS Earthquake Catalog for Oklahoma Events...")
    print(f"[INFO] Region: Lat [{OK_MIN_LAT}, {OK_MAX_LAT}], Lon [{OK_MIN_LON}, {OK_MAX_LON}]")
    print(f"[INFO] URL: {url}\n")
    
    try:
        req = Request(url)
        response = urlopen(req)
        data = json.loads(response.read().decode('utf-8'))
        response.close()
        
        earthquakes = []
        features = data.get('features', [])
        
        print(f"[INFO] Found {len(features)} earthquakes with magnitude >= {min_magnitude} in Oklahoma since {start_year}")
        
        for feature in features:
            props = feature.get('properties', {})
            coords = feature.get('geometry', {}).get('coordinates', [])
            
            eq_info = {
                'time': props.get('time'),  # milliseconds since epoch
                'latitude': coords[1] if len(coords) > 1 else None,
                'longitude': coords[0] if len(coords) > 0 else None,
                'depth': coords[2] if len(coords) > 2 else 0,
                'magnitude': props.get('mag'),
                'place': props.get('place', 'Unknown'),
                'usgs_id': props.get('code'),
                'url': props.get('url')
            }
            
            if eq_info['magnitude'] is not None and eq_info['latitude'] is not None:
                earthquakes.append(eq_info)
        
        # Sort by time (ascending)
        earthquakes.sort(key=lambda x: x['time'])
        
        return earthquakes
    
    except HTTPError as er:
        print(f"[ERR] HTTP Error: {er}")
        return []
    except URLError as er:
        print(f"[ERR] URL Error: {er}")
        return []
    except Exception as er:
        print(f"[ERR] Error querying USGS API: {er}")
        return []


def format_time(timestamp_ms):
    """
    Convert USGS timestamp (milliseconds since epoch) to human-readable format and YYYY-MM-DDTHH:MM:SS format.
    
    Parameters:
    -----------
    timestamp_ms : int
        Timestamp in milliseconds since epoch
    
    Returns:
    --------
    tuple : (human_readable_date, iso_format_time, date_string_for_filename)
    """
    timestamp_s = timestamp_ms / 1000.0
    dt = datetime.utcfromtimestamp(timestamp_s)
    
    human_readable = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    iso_format = dt.strftime("%Y-%m-%dT%H:%M:%S")
    filename_date = dt.strftime("%Y%m%d")
    
    return human_readable, iso_format, filename_date


def run_gmv_script(earthquake, gmv_script_path):
    """
    Run the gmv_generalized.py script for a given Oklahoma earthquake.
    Uses only Oklahoma seismic networks and stations for phase picking.
    
    Parameters:
    -----------
    earthquake : dict
        Dictionary containing earthquake information
    gmv_script_path : str
        Path to the gmv_generalized.py script
    
    Returns:
    --------
    bool : True if successful, False otherwise
    """
    
    try:
        # Extract earthquake data
        lat = earthquake['latitude']
        lon = earthquake['longitude']
        mag = earthquake['magnitude']
        depth = earthquake['depth']
        place = earthquake['place']
        
        human_time, iso_time, date_str = format_time(earthquake['time'])
        
        # Create output filename with "OKlocal" identifier
        mag_str = f"{mag:.1f}".replace('.', '_')
        output_filename = f"{date_str}_OKlocal_Magnitude{mag_str}"
        
        # Format magnitude for title
        mag_formatted = f"{mag:.1f}"
        
        # Create the command to run gmv_generalized.py
        # Use Oklahoma networks: OK, US, N4, XO, O2, Y7, Y9, ZP and other available networks
        # Include broadband (LH*, BH*, HH*) and non-broadband (EH*, SH*) stations
        cmd = [
            sys.executable,
            gmv_script_path,
            '-e', f"{lat},{lon}",
            '-z', str(depth),
            '-m', str(mag),
            '-t', iso_time,
            '-r', 'ok_local',  # Use zoomed Oklahoma region
            '-n', 'OK,US,N4,XO,O2,Y7,Y9,ZP,TA,IU',  # Oklahoma and other available networks
            '-b', 'LH,BH,HH,EH,SH',  # Include broadband and non-broadband channels
            '-d', '600',  # Animation duration: 600 seconds (10 minutes) instead of default 2400
            '-p', '-10',  # Animation delay: start 10 seconds before event (instead of -20)
            '-S', 'SMO',  # Use SMO station in OKC as reference if available
            '-N', 'OK',   # Network containing SMO
            '-P', '10',   # Phase spacing: 10 seconds between labels for tight zoom
            '-f', '0.05', # local override: bandpass low freq (Hz) - slightly extended from default
            '-F', '2.0',  # local override: bandpass high freq (Hz) - more signal than default for better visualization
            '-o', output_filename
        ]
        
        print(f"\n{'='*80}")
        print(f"[INFO] Processing Local Oklahoma Earthquake")
        print(f"{'='*80}")
        print(f"[INFO] Date/Time:    {human_time}")
        print(f"[INFO] Location:     {place}")
        print(f"[INFO] Coordinates:  Lat {lat:.4f}, Lon {lon:.4f}")
        print(f"[INFO] Depth:        {depth:.1f} km")
        print(f"[INFO] Magnitude:    {mag_formatted}")
        print(f"[INFO] Networks:     OK, US, N4, XO, O2, Y7, Y9, ZP, TA, IU")
        print(f"[INFO] Channels:     LH*, BH*, HH*, EH*, SH* (broadband + non-broadband)")
        print(f"[INFO] Map View:     Oklahoma (zoomed)")
        print(f"[INFO] Duration:     600 seconds (10 minutes)")
        print(f"[INFO] Ref Station:  SMO (OKC)")
        print(f"[INFO] Output File:  {output_filename}.mp4")
        print(f"[INFO] Running GMV Script...")
        print(f"{'-'*80}\n")
        
        # Run the gmv script
        result = subprocess.run(cmd, capture_output=False, text=True)
        
        if result.returncode == 0:
            print(f"\n[INFO] Successfully generated local GMV for {human_time} M{mag_formatted} earthquake")
            return True
        else:
            print(f"\n[ERR] GMV script failed with return code {result.returncode}")
            return False
    
    except Exception as er:
        print(f"[ERR] Error running GMV script: {er}")
        return False


def main():
    """Main execution function."""
    
    print(f"\n{'*'*80}")
    print(f"  Oklahoma Local Earthquake Catalog - GMV Batch Processing")
    print(f"{'*'*80}\n")
    
    # Get the path to the gmv_generalized.py script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    gmv_script = os.path.join(script_dir, 'gmv_generalized.py')
    
    # Verify the gmv script exists
    if not os.path.isfile(gmv_script):
        print(f"[ERR] gmv_generalized.py not found at {gmv_script}")
        sys.exit(1)
    
    print(f"[INFO] GMV script location: {gmv_script}\n")
    
    # Query USGS for M4.5+ earthquakes in Oklahoma since 2010
    earthquakes = get_oklahoma_earthquakes(min_magnitude=4.5, start_year=2010)
    
    if not earthquakes:
        print("[WARN] No earthquakes found matching criteria.")
        sys.exit(0)
    
    # Check for command line argument for report-only mode
    report_only = '--report-only' in sys.argv or '-r' in sys.argv
    
    if report_only:
        print(f"\n[INFO] REPORT MODE - Showing what will be generated (no actual processing)\n")
    else:
        print(f"\n[INFO] Starting GMV generation for {len(earthquakes)} earthquake(s)...\n")
    
    # Process each earthquake
    successful = 0
    failed = 0
    
    for idx, eq in enumerate(earthquakes, 1):
        try:
            human_time, iso_time, date_str = format_time(eq['time'])
            mag_str = f"{eq['magnitude']:.1f}".replace('.', '_')
            output_filename = f"{date_str}_OKlocal_Magnitude{mag_str}"
            
            if report_only:
                print(f"{idx:3d}. {human_time} | M{eq['magnitude']:.1f} | "
                      f"Lat {eq['latitude']:7.2f}, Lon {eq['longitude']:8.2f} | "
                      f"Depth {eq['depth']:6.1f}km | {output_filename}.mp4")
                successful += 1
            else:
                if run_gmv_script(eq, gmv_script):
                    successful += 1
                else:
                    failed += 1
        except KeyboardInterrupt:
            print(f"\n[INFO] Processing interrupted by user at earthquake #{idx}")
            break
        except Exception as er:
            print(f"[ERR] Unexpected error processing earthquake #{idx}: {er}")
            failed += 1
        
        # Add a small delay between runs to avoid overwhelming resources (skip in report mode)
        if not report_only and idx < len(earthquakes):
            print(f"[INFO] Waiting 5 seconds before next earthquake...\n")
            time.sleep(5)
    
    # Print summary
    print(f"\n{'='*80}")
    print(f"  BATCH PROCESSING SUMMARY")
    print(f"{'='*80}")
    print(f"Total earthquakes processed: {len(earthquakes)}")
    print(f"Successful:                 {successful}")
    print(f"Failed:                     {failed}")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    main()
