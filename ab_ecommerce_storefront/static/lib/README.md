# Branch locator libraries

Loaded on the branch locator page through Odoo's asset loader. No CDN dependency for the libraries.

- Leaflet 1.9.4: https://leafletjs.com/ and https://registry.npmjs.org/leaflet/-/leaflet-1.9.4.tgz. BSD-2-Clause; license retained in `leaflet/LICENSE`.
- Leaflet.markercluster 1.5.3: https://github.com/Leaflet/Leaflet.markercluster and https://registry.npmjs.org/leaflet.markercluster/-/leaflet.markercluster-1.5.3.tgz. MIT; license retained in `leaflet_markercluster/LICENSE`.

Map tiles are requested directly from OpenStreetMap with visible attribution. Do not prefetch tiles or remove attribution. Directions open Google Maps using the branch's published coordinates.
