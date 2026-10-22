# HoloLunar

An augmented reality framework for real-time visualization of subsurface ice distribution at Faustini crater, using Chandrayaan-2 DFSAR backscatter data.

## What it does

- Builds a 60 km x 60 km view of Faustini crater (about 87.3 S, 77 E) from real data
  - CPR (circular polarization ratio) from Chandrayaan-2 DFSAR L-band, 25 m per pixel
  - Terrain relief from a lunar DEM, resampled onto the same 25 m grid
- Shows a whole-Moon globe in Unity, with a pulsing marker at Faustini
  - Drag to rotate, pinch or scroll to zoom
  - Zoom in or tap the marker to open the detailed CPR terrain
- Runs on desktop (preview) and on Android AR through a Vuforia Image Target

## Data

- **CPR layer:** ISRO ISSDC PRADAN product `ch2_sar_ndxl_20250630mpcpspwest_d_fp_xxx`
  - L4 polar mosaic, L-band (1.25 GHz), 25 m pixels, Moon 2000 south polar stereographic
  - Built from about 600 scenes acquired 2019-09-22 to 2023-10-18
  - CPR definition: Putrevu et al., 2023, DOI 10.1029/2023JE007745
  - The raw data (about 7 GB) is **not** in this repository. Download it from PRADAN.
- **Elevation:** `Data/dem_faustini_v2.tif`, native resolution 120 m
  - Source: TODO (write the exact product name before submission)
- **Globe basemap:** NASA SVS 4720, CGI Moon Kit, LROC color map (4096 x 2048)
  - Not included. Download `lroc_color_16bit_srgb_4k.tif` from https://svs.gsfc.nasa.gov/4720

## Pipeline (run in order, from the repository root)

- `clip_faustini_cpr.py` - clips the CPR mosaic to the Faustini window, writes `faustini_cpr_clip.tif`
- `align_dem.py` - resamples the DEM onto the CPR grid, writes `faustini_dem_clip.tif`
- `export_cpr_textures.py` - writes the Unity textures (confidence, valid mask, CPR > 1 mask)
- `export_heightmap_raw.py` - writes `faustini_height_2049.bytes` (16-bit heights for Unity)

Setup:

```
python -m venv .venv
.venv\Scripts\activate
pip install rasterio pyproj pillow numpy
```

## Key numbers from the clip

- Valid CPR pixels: about 78.2 percent (the rest are gaps between SAR strips, shown dark gray)
- Pixels with CPR above 1: about 0.51 percent of valid pixels
- Median CPR: about 0.26

## Unity

- Unity 6 (6000.6), URP, Vuforia for AR
- Scripts: `TerrainGenerator.cs`, `MoonGlobe.cs`, `PinchZoom.cs`
- Open `UnityProject` in Unity Hub
- Vuforia license key is not committed. Add your own under Window > Vuforia Configuration.

## Limitations

- High CPR is ice-consistent, not proof of ice. Rough, rocky terrain also gives high CPR.
- The product has no degree-of-polarization layer, so the CPR + DOP criterion used in the literature cannot be reproduced from this product alone.
- The DEM is 120 m resolution, so small craters visible in the 25 m CPR layer are not in the terrain geometry.
- The globe shows the LROC basemap only. Real CPR appears in the Faustini detail view.

## Credits

- Chandrayaan-2 DFSAR data: ISRO / ISSDC PRADAN
- Moon basemap: NASA Scientific Visualization Studio, CGI Moon Kit
- Lunar elevation: TODO (LOLA / NASA PDS, confirm product)
