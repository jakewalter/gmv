#!/usr/bin/env python3
"""Create a GMV-style animation from local seismic files.

Usage example:
    python scripts/local_gmv.py \
        --data-dir /media/jwalter/Tryon_3D_Earthquake \
        --station-csv /path/to/stations.csv \
        --start 2000-01-01T00:00:00 \
        --end 2000-01-01T00:10:00 \
        --time-step 1 \
        --out /tmp/local_gmv.mp4

Station CSV format (if StationXML not available):
    network,station,latitude,longitude
    XX,ABC,45.1,-123.4

Notes:
- Supports MiniSEED (.mseed, .msd), SAC (.sac) and SEG-Y (.sgy/.segy) files via ObsPy.
- Requires ObsPy, matplotlib, numpy, mpl_toolkits.basemap (or cartopy modifications).
- The script uses a simplified styling derived from the gmv codebase in this repo.
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
import datetime as dt
from typing import Dict, Tuple, List

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import animation
from matplotlib import cm

from obspy import UTCDateTime, read, Stream, Inventory, Trace, read_inventory

try:
    from mpl_toolkits.basemap import Basemap
except Exception:
    Basemap = None

# Optional SEG-Y support (segyio). If installed, we can extract GroupX/GroupY geometry
try:
    import segyio
    from segyio import TraceField, BinField
    HAS_SEGYIO = True
except Exception:
    segyio = None
    TraceField = None
    BinField = None
    HAS_SEGYIO = False


def find_waveforms(data_dir: str) -> List[str]:
    patterns = ["**/*.mseed", "**/*.msd", "**/*.sac", "**/*.sgy", "**/*.seg-y", "**/*.segy"]
    files = list()
    for p in patterns:
        files.extend(glob.glob(os.path.join(data_dir, p), recursive=True))
    return sorted(files)


def load_station_csv(path: str) -> Dict[str, Tuple[float, float]]:
    d = dict()
    with open(path) as fp:
        hdr = fp.readline().strip().split(',')
        # expect network,station,lat,lon but accept station,lat,lon
        for line in fp:
            if not line.strip():
                continue
            parts = [x.strip() for x in line.strip().split(',')]
            if len(parts) == 4:
                net, sta, lat, lon = parts
                key = f"{net}.{sta}"
            elif len(parts) == 3:
                sta, lat, lon = parts
                key = sta
            else:
                continue
            d[key] = (float(lat), float(lon))
    return d


def inventory_to_positions(inv: Inventory) -> Dict[str, Tuple[float, float]]:
    d = dict()
    for net in inv.networks:
        for sta in net.stations:
            key = f"{net.code}.{sta.code}"
            d[key] = (sta.latitude, sta.longitude)
    return d


def stream_station_key(tr) -> str:
    # Some data may not have network set; fall back to station only as key
    try:
        return f"{tr.stats.network}.{tr.stats.station}"
    except Exception:
        return f"{tr.stats.station}"


def _pick_segy_scale(gx_vals, gy_vals):
    """Heuristic: test a set of candidate scales and pick one that maps most points into valid lat/lon ranges."""
    import numpy as _np
    candidates = [1e-3, 1e-4, 1e-5, 1e-6, 1e-7, 1e-8, 1e-9]
    best = None
    best_score = -1
    for sc in candidates:
        lon = gx_vals * sc
        lat = gy_vals * sc
        ok = _np.logical_and(_np.logical_and(lon > -180, lon < 180), _np.logical_and(lat > -90, lat < 90))
        score = float(_np.sum(ok)) / len(ok)
        if score > best_score:
            best_score = score
            best = sc
    # require at least 95% in-range to be confident
    if best_score >= 0.95:
        return best
    return None


def segy_to_stream(path):
    """Convert a SEG-Y file into an ObsPy Stream and a positions dict mapping trace keys to (lat, lon).

    Uses segyio; returns (st, positions). If segyio is not available, raises RuntimeError.
    """
    if not HAS_SEGYIO:
        raise RuntimeError('segyio not available')
    from obspy import Trace
    from obspy import UTCDateTime
    st = Stream()
    positions = {}
    with segyio.open(path, 'r', ignore_geometry=True) as s:
        # sample interval (microseconds) -> sampling rate
        try:
            sample_interval = s.bin[BinField.Interval]
            sr = 1e6 / float(sample_interval)
        except Exception:
            # fallback guess
            sr = 100.0
        n = s.tracecount
        gx = []
        gy = []
        headers = []
        for i in range(n):
            hdr = s.header[i]
            headers.append(hdr)
            gx.append(hdr.get(TraceField.GroupX, 0))
            gy.append(hdr.get(TraceField.GroupY, 0))
        gx = np.array(gx, dtype=float)
        gy = np.array(gy, dtype=float)
        scale = _pick_segy_scale(gx, gy)
        if scale is None:
            # if we couldn't find a good scale, default to 1e-6 (common microdegree encoding)
            scale = 1e-6
        # Build traces
        for i in range(n):
            data = s.trace[i].astype(float)
            hdr = headers[i]
            trace_num = int(hdr.get(TraceField.TraceSequenceLine, i + 1)) if TraceField.TraceSequenceLine in hdr else i + 1
            name = f"SGY.{trace_num:05d}"
            # estimate starttime from header if available
            try:
                y = int(hdr.get(TraceField.YearDataRecorded))
                doy = int(hdr.get(TraceField.DayOfYear))
                hr = int(hdr.get(TraceField.HourOfDay) or 0)
                mn = int(hdr.get(TraceField.MinuteOfHour) or 0)
                sec = int(hdr.get(TraceField.SecondOfMinute) or 0)
                start = UTCDateTime(y) + (doy - 1) * 86400 + hr * 3600 + mn * 60 + sec
            except Exception:
                start = UTCDateTime(1970, 1, 1)
            tr = Trace(data=data)
            tr.stats.network = 'SGY'
            tr.stats.station = name
            tr.stats.starttime = start
            tr.stats.sampling_rate = sr
            # attach raw segy header for reference
            tr.stats.segy = {str(k): hdr.get(k) for k in hdr.keys()}
            st.append(tr)
            lon = float(hdr.get(TraceField.GroupX, 0)) * scale
            lat = float(hdr.get(TraceField.GroupY, 0)) * scale
            positions[f"{tr.stats.network}.{tr.stats.station}"] = (lat, lon)
    return st, positions


def prepare_meta(st: Stream, positions: Dict[str, Tuple[float, float]],
                 start: UTCDateTime, end: UTCDateTime, time_step: float) -> Tuple[Dict[str, Trace], np.ndarray, Dict]:
    """Prepare trimmed station traces and a times array for streaming frame generation.

    This avoids materializing all frames in memory by keeping per-station traces (trimmed
    to the requested window and downcast to float32) and returning a times array. The
    caller can then sample each trace on-the-fly for each frame.
    """
    station_traces = dict()
    station_max = dict()
    for tr in st:
        key = stream_station_key(tr)
        if key not in positions:
            continue
        # trim to requested window
        tr2 = tr.copy()
        try:
            tr2.trim(start, end, pad=False, nearest_sample=True)
        except Exception:
            continue
        if len(tr2.data) == 0:
            continue
        # downcast to float32 to reduce memory footprint
        tr2.data = tr2.data.astype(np.float32)
        station_traces[key] = tr2
        station_max[key] = max(1.0, float(np.max(np.abs(tr2.data))))

    times = np.arange(start.timestamp, end.timestamp, time_step)
    meta = {'times': times, 'station_keys': list(station_traces.keys()), 'station_max': station_max}
    return station_traces, times, meta


def make_animation(station_traces: Dict[str, Trace], positions: Dict[str, Tuple[float, float]], meta: Dict,
                   times: np.ndarray, out_file: str, time_step: float, fps: int = 10):
    # Basic world map centered at data
    lats = [positions[k][0] for k in meta['station_keys']]
    lons = [positions[k][1] for k in meta['station_keys']]

    lat0 = np.mean(lats)
    lon0 = np.mean(lons)
    lat_span = max(lats) - min(lats) if len(lats) > 1 else 10
    lon_span = max(lons) - min(lons) if len(lons) > 1 else 10

    fig = plt.figure(figsize=(10, 6))
    ax_map = fig.add_axes([0.05, 0.25, 0.9, 0.7])

    if Basemap is None:
        raise RuntimeError('Basemap not available in this Python environment. Install mpl_toolkits.basemap or modify the script to use cartopy.')

    m = Basemap(projection='merc', llcrnrlat=min(lats) - lat_span * 0.1, urcrnrlat=max(lats) + lat_span * 0.1,
                llcrnrlon=min(lons) - lon_span * 0.1, urcrnrlon=max(lons) + lon_span * 0.1, resolution='i')
    m.drawcoastlines()
    m.drawmapboundary(fill_color='lightblue')
    m.fillcontinents(color='lightgray', lake_color='lightblue')

    xs, ys = m(lons, lats)
    sc = ax_map.scatter(xs, ys, c=[0]*len(xs), cmap=cm.seismic, vmin=-1.0, vmax=1.0, s=60, edgecolors='k')
    # annotate station names
    for i, key in enumerate(meta['station_keys']):
        ax_map.text(xs[i], ys[i], key.split('.')[-1], fontsize=6, ha='left', va='bottom')

    ax_time = fig.add_axes([0.05, 0.05, 0.9, 0.15])
    # choose a reference station with data
    ref_key = meta['station_keys'][0] if meta['station_keys'] else None
    if ref_key is None:
        raise RuntimeError('No station traces found inside requested time window')

    # Prepare a simple time-series for reference: collect amplitudes for ref station on-the-fly
    def sample_tr_at_time(tr, t):
        idx = int(round((UTCDateTime(t) - tr.stats.starttime) * tr.stats.sampling_rate))
        if idx < 0 or idx >= len(tr.data):
            return 0.0
        return float(tr.data[idx])

    ref_tr = station_traces[ref_key]
    ref_max = meta['station_max'].get(ref_key, 1.0)
    ref_amps = [sample_tr_at_time(ref_tr, t) / ref_max for t in times]
    ln_ref, = ax_time.plot(times, ref_amps, color='k', lw=0.7)

    time_marker = ax_time.axvline(times[0], color='red')
    ax_time.set_xlim(times[0], times[-1])
    ax_time.set_ylabel('norm amp')

    def update(i):
        vals = []
        for key in meta['station_keys']:
            tr = station_traces[key]
            maxv = meta['station_max'].get(key, 1.0)
            v = sample_tr_at_time(tr, times[i]) / maxv
            vals.append(v)
        sc.set_array(np.array(vals))
        time_marker.set_xdata(times[i])
        fig.suptitle(UTCDateTime(times[i]).strftime('%Y-%m-%d %H:%M:%S UTC'))
        return sc, time_marker

    ani = animation.FuncAnimation(fig, update, frames=len(times), interval=1000 * time_step, blit=False)

    Writer = animation.writers['ffmpeg']
    writer = Writer(fps=fps, metadata=dict(artist='local_gmv'))
    ani.save(out_file, writer=writer)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description='Create a GMV-style animation from local seismic files')
    p.add_argument('--data-dir', required=True, help='Top-level data directory to search for waveform files')
    p.add_argument('--station-xml', required=False, help='StationXML file with station metadata')
    p.add_argument('--station-csv', required=False, help='CSV mapping network,station -> lat,lon')
    p.add_argument('--start', required=False, help='Start time (ISO) for the movie')
    p.add_argument('--end', required=False, help='End time (ISO) for the movie')
    p.add_argument('--time-step', type=float, default=1.0, help='Seconds between frames (default: 1s)')
    p.add_argument('--out', required=True, help='Output mp4 file')
    p.add_argument('--fps', type=int, default=10, help='Output frames per second for the movie')
    p.add_argument('--max-frames', type=int, default=10000, help='Maximum frames allowed to generate (default: 10000)')
    p.add_argument('--max-mem-mb', type=int, default=4096, help='Maximum estimated memory in MiB for frames (default: 4096)')
    p.add_argument('--dry-run', action='store_true', help='Estimate frames/memory and exit without creating frames or animation')
    args = p.parse_args()

    files = find_waveforms(args.data_dir)
    if not files:
        print('No waveform files found in', args.data_dir)
        sys.exit(1)
    print(f'Found {len(files)} waveform files; reading...')

    # Station positions (may be populated by SEG-Y geometry detection below)
    positions = dict()

    st = Stream()
    for fn in files:
        # If SEG-Y and segyio is available, convert traces and extract geometry from headers
        if fn.lower().endswith(('.sgy', '.segy')) and HAS_SEGYIO:
            try:
                s2, pos2 = segy_to_stream(fn)
                st += s2
                # merge positions but do not overwrite if user provided station CSV/XML later
                positions.update(pos2)
                continue
            except Exception as e:
                print('Warning: could not process SEG-Y', fn, e)
                # fall back to trying to read with ObsPy
        try:
            st += read(fn)
        except Exception as e:
            print('Warning: could not read', fn, e)

    # If user provided station XML or CSV, merge those with any positions discovered in SEG-Y
    if args.station_xml and os.path.exists(args.station_xml):
        inv = read_inventory(args.station_xml)
        positions.update(inventory_to_positions(inv))
    elif args.station_csv and os.path.exists(args.station_csv):
        positions.update(load_station_csv(args.station_csv))
    else:
        # try to infer from SAC headers (merge with any segy-detected positions)
        for tr in st:
            if hasattr(tr.stats, 'sac'):
                sac = tr.stats.sac
                if hasattr(sac, 'stla') and hasattr(sac, 'stlo') and sac.stla is not None:
                    key = stream_station_key(tr)
                    # do not overwrite existing position
                    if key not in positions:
                        positions[key] = (sac.stla, sac.stlo)


    if not positions:
        print('No station positions found. Provide --station-xml or --station-csv or ensure SAC headers have stla/stlo.')
        sys.exit(1)

    # Start/end times
    if args.start:
        start = UTCDateTime(args.start)
    else:
        start = UTCDateTime(min([tr.stats.starttime for tr in st]))
    if args.end:
        end = UTCDateTime(args.end)
    else:
        end = UTCDateTime(max([tr.stats.endtime for tr in st]))

    # Safety checks: estimate number of frames and estimated memory usage to avoid runaway runs
    duration = end.timestamp - start.timestamp
    n_frames = int(np.ceil(duration / args.time_step)) if duration > 0 else 0
    n_stations = max(1, len(positions))
    # Estimate memory using an on-the-fly/frame-buffered approach (float32 per sample)
    est_bytes = n_frames * n_stations * 4  # assume one float32 per station per frame (streaming)
    est_mb = est_bytes / (1024.0 ** 2)
    safety_multiplier = 1.5  # account for overhead and plotting buffers

    if n_frames <= 0:
        print('No frames to generate for the requested time window (start >= end)')
        sys.exit(1)

    if n_frames > args.max_frames:
        print(f'Requested {n_frames} frames which exceeds --max-frames ({args.max_frames}).\n'
              'Reduce time window, increase --time-step, or raise --max-frames.')
        sys.exit(1)

    if est_mb * safety_multiplier > args.max_mem_mb:
        print(f'Estimated memory for frames: {est_mb * safety_multiplier:.0f} MiB which exceeds --max-mem-mb ({args.max_mem_mb}).\n'
              'Reduce time window, increase --time-step, or limit stations to reduce memory use.')
        sys.exit(1)

    print(f'Generating {n_frames} frames for {n_stations} stations (estimated {est_mb:.0f} MiB memory).')

    if args.dry_run:
        print('DRY RUN: no frames or animation will be created.')
        print(f'  frames: {n_frames}\n  stations: {n_stations}\n  estimated memory: {est_mb:.0f} MiB')
        sys.exit(0)

    try:
        station_traces, times, meta = prepare_meta(st, positions, start, end, args.time_step)
    except MemoryError:
        print('MemoryError while preparing traces; try reducing station count or increasing --time-step')
        sys.exit(1)

    if not meta['station_keys']:
        print('No station traces found inside requested time window')
        sys.exit(1)

    n_frames = len(times)
    print(f'Creating animation with {n_frames} frames, saving to {args.out}')
    try:
        make_animation(station_traces, positions, meta, times, args.out, args.time_step, fps=args.fps)
    except MemoryError:
        print('MemoryError while creating animation; try reducing frame count, limiting stations, or increasing --time-step')
        sys.exit(1)
    except Exception as e:
        print('Error while creating animation:', e)
        sys.exit(1)
    print('Done')


if __name__ == '__main__':
    main()
