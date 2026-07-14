# Space imagery attribution

Real-photography plates layered into the Omni universe backdrop. All files
are equirectangular (2:1) and served same-origin from `./space/`.

| File | Subject | Source / credit |
|---|---|---|
| `earth-day-2k.jpg` | Host-world day surface | NASA Visible Earth — **Blue Marble: Next Generation** (NASA Earth Observatory / Reto Stöckli). Public domain (NASA imagery guidelines). |
| `earth-night-2k.jpg` | Host-world night-side city lights | NASA Earth Observatory — **Black Marble / Earth at Night** (NASA/NOAA Suomi NPP VIIRS). Public domain. |
| `earth-clouds-2k.jpg` | Cloud-coverage plate (sampled as coverage, not color) | NASA Visible Earth — Blue Marble cloud fraction composite (Terra/MODIS). Public domain. |
| `starmap-4k.jpg` | Deep starfield backdrop + hull reflections (PMREM environment) | All-sky star map rendered from the ESA **Tycho-2** catalogue as distributed with the globe.gl / three-globe examples. |

Provenance chain: plates obtained from the `three-globe@2.45.2` npm package
(`example/img/`, `example/clouds/`, MIT-licensed repository; the imagery
itself is NASA-credited as above), downscaled/re-encoded with Pillow for web
delivery (2K day/night/clouds, 4K starmap). No other processing.

NASA imagery is not copyrighted; use does not imply NASA endorsement.
