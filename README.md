# O'zbekiston — tumanlar kesimidagi SVG xarita

- `uzbekistan_districts.svg` — 205 ta tuman/shahar `<path>`, viloyatlar bo'yicha `<g id="UZ-XX">` guruhlarda, oxirida `<g id="regions">` — viloyat chegaralari.
  Har bir path: `id`, `data-name_uz`, `data-name_ru`, `data-name_en`, `data-type` (district/city), `data-region`, `data-region_name`.
- `uzbekistan_districts.geojson` — xuddi shu poligonlar (WGS84).
- `uzbekistan_map.html` — interaktiv xarita (hover, bosish, qidiruv, zoom/pan), serversiz ochiladi. Shabloni: `scripts/map_template.html`.

Aniqlik: chegaralar OSM chizig'idan ≤ 30–36 m chetlashadi (Douglas–Peucker, 30 m).

Qayta yig'ish: `npm install && python scripts/build.py` (`--refresh` — OSM'dan yangidan yuklash).

Chegaralar: © OpenStreetMap contributors, [ODbL](https://www.openstreetmap.org/copyright) — foydalanganda atributsiya shart.
Nomlar: `uzbekistan_regions_districts.json`.
