# GMV Batch Processing Scripts - Summary

## Overview
Two complementary batch processing scripts have been created for comprehensive earthquake visualization:

---

## 1. Global M7.5+ Events: `gmv_batch_m8_catalog.py`

**Purpose:** Process major global earthquakes (M7.5 or greater) since 2010

**Key Features:**
- Queries USGS Earthquake Catalog for M7.5+ events globally
- **80 earthquakes** available to process
- Reference station: **SMO (OKC)** - Oklahoma City seismic station
- Networks: **All networks globally** (OK, US, Y7, Y9, ZP, O2, TA, IU, etc.)
- Channels: **Broadband** (LH*, BH*, HH*) **and non-broadband** (EH*, SH*) stations
- Output format: `YYYYMMDD_Magnitude8.8.mp4`

**Usage:**
```bash
# View which earthquakes will be processed
python gmv_batch_m8_catalog.py --report-only

# Run full batch processing (background)
nohup python gmv_batch_m8_catalog.py > batch_processing.log 2>&1 &

# Monitor progress
tail -f batch_processing.log
```

**Notable Events in Dataset:**
- 2010-02-27: Chile M8.8
- 2011-03-11: Japan (Tohoku) M9.1 - **LARGEST**
- 2012-04-11: Sumatra M8.6
- 2015-09-16: Chile (Illapel) M8.3
- 2025-07-29: Eastern Russia (Kamchatka) M8.8 - **Most Recent**

---

## 2. Local Oklahoma M4.5+ Events: `gmv_batch_ok_local.py`

**Purpose:** Process local Oklahoma earthquakes (M4.5 or greater) since 2010 with focus on P/S phase picking

**Key Features:**
- Queries USGS for Oklahoma-only events (Lat 33.6-37.0°N, Lon -103.0 to -94.4°W)
- **15 earthquakes** available to process
- Reference station: **SMO (OKC)** - Oklahoma City seismic station
- Networks: **OK, US, N4, XO, O2, Y7, Y9, ZP, TA, IU** (Oklahoma-focused with multiple temporary arrays)
- Channels: **Broadband** (LH*, BH*, HH*) **and non-broadband** (EH*, SH*) stations
- Phase spacing: 15 seconds between labels for clear P and S picks
- Output format: `YYYYMMDD_OKlocal_Magnitude4.5.mp4`

**Usage:**
```bash
# View which Oklahoma earthquakes will be processed
python gmv_batch_ok_local.py --report-only

# Run full batch processing (background)
nohup python gmv_batch_ok_local.py > batch_ok_local.log 2>&1 &

# Monitor progress
tail -f batch_ok_local.log
```

**Oklahoma Earthquakes in Dataset:**
1. 2024-02-03: Prague, OK - M5.1 (Most Recent)
2. 2022-01-31: Medford, OK - M4.5
3. 2018-04-09: Marshall, OK - M4.6
4. 2018-04-07: Lucien, OK - M4.6
5. 2016-11-07: Cushing, OK - M5.0
6. 2016-09-03: Pawnee, OK - M5.8
7. 2016-02-13: Waynoka, OK - M5.1
8. 2016-01-07: Waynoka, OK - M4.7
9. 2015-11-30: Nescatunga, OK - M4.7
10. 2015-11-19: Lambert, OK - M4.7
11. 2015-07-27: Crescent, OK - M4.5
12. 2013-12-07: Arcadia, OK - M4.5
13. 2011-11-08: Sparks, OK - M4.8
14. 2011-11-06: Prague, OK - M5.7
15. 2011-11-05: Sparks, OK - M4.8

---

## Key Differences

| Feature | Global M7.5+ | Local M4.5+ |
|---------|-------------|-----------|
| Magnitude Threshold | M7.5+ | M4.5+ |
| Geographic Scope | Worldwide | Oklahoma only |
| Events to Process | 80 | 15 |
| Networks | All global (OK, US, Y7, Y9, ZP, O2, TA, IU, etc.) | OK, US, N4, XO, O2, Y7, Y9, ZP, TA, IU |
| Channels | LH*, BH*, HH*, EH*, SH* | LH*, BH*, HH*, EH*, SH* |
| Reference Station | SMO (OKC) | SMO (OKC) |
| Phase Picking | Standard | Oklahoma-focused (P/S emphasis) |
| Output Prefix | Standard | OKlocal |

---

## Running Scripts

Both scripts support the following modes:

### Report-Only Mode (Preview):
```bash
python gmv_batch_m8_catalog.py --report-only    # Global events
python gmv_batch_ok_local.py --report-only       # Local Oklahoma events
```
Shows what will be generated without actually processing.

### Full Processing:
```bash
# Start in background
nohup python gmv_batch_m8_catalog.py > batch_processing.log 2>&1 &
nohup python gmv_batch_ok_local.py > batch_ok_local.log 2>&1 &

# Check running processes
ps aux | grep gmv

# Monitor logs
tail -f batch_processing.log
tail -f batch_ok_local.log

# Stop if needed
pkill -f gmv_batch
```

---

## Output Files

All generated videos are saved to: `/Users/jwalter/gmv/video/`

**Global M7.5+ naming example:**
- `20110311_Magnitude9_1.mp4` (Japan Tohoku earthquake)

**Local OK M4.5+ naming example:**
- `20240203_OKlocal_Magnitude5_1.mp4` (Prague, OK earthquake)

---

## Notes

- Each earthquake generates a complete GMV animation showing ground motion propagation
- Processing time: ~5-15 minutes per earthquake depending on data availability
- Reference station SMO (OKC) will be used if available; the script can fall back to nearby stations
- All scripts are configured to exclude temporary seismic networks (1-2 letter codes starting with X, Y, Z)
- Internet connection required for USGS data access

