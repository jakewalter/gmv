#!/usr/bin/env python
"""
Name:
    gmv_batch_m8_catalog.py

Description:
    This script queries the USGS Earthquake Hazards Program API to find all magnitude 7.5 or greater
    earthquakes since 2010. For each earthquake found, it runs the gmv_generalized.py script to generate
    a ground motion visualization (GMV) animation. The output videos are saved with filenames following
    the pattern: YYYYMMDD_Magnitude8.2.mp4 (for example).
    
    Networks included: All networks globally (OK, US, Y7, Y9, ZP, O2, etc.)
    Channels included: Broadband (LH*, BH*, HH*) and non-broadband (EH*, SH*) stations

Usage:
    python gmv_batch_m8_catalog.py

Requirements:
    - requests library for HTTP requests
    - ObsPy for earthquake data handling
    - gmv_generalized.py script in the same directory
    - Internet access to query USGS API

Author:
    Created for GMV analysis of major earthquakes

History:
    2025-11-03: Initial creation
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


def get_usgs_earthquakes(min_magnitude=8.0, start_year=2010):
    """
    Query the USGS Earthquake Hazards Program API for earthquakes meeting criteria.
    
    Parameters:
    -----------
    min_magnitude : float
        Minimum magnitude to retrieve (default: 8.0)
    start_year : int
        Starting year for earthquake query (default: 2010)
    
    Returns:
    --------
    list : List of earthquake dictionaries with relevant information
    """
    
    start_date = f"{start_year}-01-01"
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    # USGS GeoJSON API endpoint for earthquake data
    url = (f"https://earthquake.usgs.gov/fdsnws/event/1/query?"
           f"format=geojson"
           f"&starttime={start_date}"
           f"&endtime={end_date}"
           f"&minmagnitude={min_magnitude}")
    
    print(f"\n[INFO] Querying USGS Earthquake Catalog...")
    print(f"[INFO] URL: {url}\n")
    
    try:
        req = Request(url)
        response = urlopen(req)
        data = json.loads(response.read().decode('utf-8'))
        response.close()
        
        earthquakes = []
        features = data.get('features', [])
        
        print(f"[INFO] Found {len(features)} earthquakes with magnitude >= {min_magnitude} since {start_year}")
        
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
    Run the gmv_generalized.py script for a given earthquake.
    
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
        
        # Extract region from place string (e.g., "8 km NW of Prague, Oklahoma" -> "Oklahoma")
        # or use the place string if it's short
        place_parts = place.split(', ')
        region = place_parts[-1] if len(place_parts) > 1 else place
        
        # Create output filename with shortened Magnitude to M
        mag_str = f"{mag:.1f}".replace('.', '_')
        output_filename = f"{date_str}_M{mag_str}_{region.replace(' ', '')}"
        
        # Format magnitude for title
        mag_formatted = f"{mag:.1f}"
        
        # Create the command to run gmv_generalized.py
        # Include broadband (LH*, BH*, HH*) and non-broadband (EH*, SH*) stations
        cmd = [
            sys.executable,
            gmv_script_path,
            '-e', f"{lat},{lon}",
            '-z', str(depth),
            '-m', str(mag),
            '-t', iso_time,
            '-r', 'ok',  # Using Oklahoma region as default (or modify as needed)
            '-n', 'all',  # Use all networks including O2, Y7, Y9, ZP, etc.
            '-b', 'LH,BH,HH,EH,SH',  # Include broadband and non-broadband channels
            '-S', 'SMO',  # Use SMO station in OKC as reference if available
            '-N', 'Y',    # Network containing SMO (US network)
            '-o', output_filename
        ]
        
        print(f"\n{'='*80}")
        print(f"[INFO] Processing Earthquake")
        print(f"{'='*80}")
        print(f"[INFO] Date/Time:    {human_time}")
        print(f"[INFO] Location:     {place}")
        print(f"[INFO] Region:       {region}")
        print(f"[INFO] Coordinates:  Lat {lat:.4f}, Lon {lon:.4f}")
        print(f"[INFO] Depth:        {depth:.1f} km")
        print(f"[INFO] Magnitude:    {mag_formatted}")
        print(f"[INFO] Output File:  {output_filename}.mp4")
        print(f"[INFO] Running GMV Script...")
        print(f"{'-'*80}\n")
        
        # Run the gmv script
        result = subprocess.run(cmd, capture_output=False, text=True)
        
        if result.returncode == 0:
            print(f"\n[INFO] Successfully generated GMV for {human_time} M{mag_formatted} earthquake")
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
    print(f"  USGS M8+ Earthquake Catalog - GMV Batch Processing")
    print(f"{'*'*80}\n")
    
    # Get the path to the gmv_generalized.py script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    gmv_script = os.path.join(script_dir, 'gmv_generalized.py')
    
    # Verify the gmv script exists
    if not os.path.isfile(gmv_script):
        print(f"[ERR] gmv_generalized.py not found at {gmv_script}")
        sys.exit(1)
    
    print(f"[INFO] GMV script location: {gmv_script}\n")
    
    # Query USGS for M7.5+ earthquakes since 2010
    earthquakes = get_usgs_earthquakes(min_magnitude=7.5, start_year=2010)
    
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
            place = eq['place']
            place_parts = place.split(', ')
            region = place_parts[-1] if len(place_parts) > 1 else place
            mag_str = f"{eq['magnitude']:.1f}".replace('.', '_')
            output_filename = f"{date_str}_M{mag_str}_{region.replace(' ', '')}"
            
            if report_only:
                print(f"{idx:2d}. {human_time} | M{eq['magnitude']:.1f} | "
                      f"Lat {eq['latitude']:7.2f}, Lon {eq['longitude']:8.2f} | "
                      f"{region} | Output: {output_filename}.mp4")
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
