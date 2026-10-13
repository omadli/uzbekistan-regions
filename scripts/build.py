import json, re, sys, difflib, subprocess, unicodedata, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
OVERPASS = "https://overpass.kumi.systems/api/interpreter"
QUERY = ('[out:json][timeout:500];area["ISO3166-1"="UZ"][admin_level=2]->.a;'
         'rel(area.a)["boundary"="administrative"]["admin_level"~"^(3|4|6)$"];out geom;')
PALETTE = {
    "UZ-QR": "#e9c98b", "UZ-XO": "#7fbfaa", "UZ-NW": "#c3a8d9", "UZ-BU": "#f2a582",
    "UZ-SA": "#8db9e3", "UZ-QA": "#ecd682", "UZ-SU": "#9fcf8c", "UZ-JI": "#f2a9bb",
    "UZ-SI": "#7ccbd0", "UZ-TO": "#b9cf7f", "UZ-TK": "#e88f8f", "UZ-NG": "#eab57f",
    "UZ-AN": "#de94c0", "UZ-FA": "#86cba8",
}
PROJ = "+proj=lcc +lat_1=38 +lat_2=43 +lat_0=41 +lon_0=64 +datum=WGS84"

ALIAS = {
    "qonirat": "qongirot", "moynaq": "moynoq", "shomanay": "shumanay", "qanlikol": "qanliko'l",
    "xojeli": "xo'jayli", "nokis": "nukus", "shimbay": "chimboy", "qaraozek": "qorao'zak",
    "amiwdarya": "amudaryo", "taxtakopir": "taxtako'pir", "tortkul": "to'rtko'l", "ellikqala": "ellikqal'a",
    "taqiyatas": "taxiatosh", "bozataw": "bo'zatov",
    "sergeli": "sirg'ali", "yangi hayot": "yangihayot", "past dargom": "pastdarg'om",
    "showot": "shovot", "toyloq": "tayloq", "boston": "bo'z",
}


def mapshaper(*args):
    subprocess.run(["node", ROOT / "node_modules/mapshaper/bin/mapshaper", *args], check=True, cwd=BUILD)


def norm(s):
    s = unicodedata.normalize("NFKD", (s or "").replace("ı", "i")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[`'‘’ʻʼ]", "", s)
    s = re.sub(r"\b(tumani|shahri|rayoni|qalasi hakimiyati|district|city)\b", "", s)
    s = re.sub(r"[^a-z ]", "", s).strip()
    s = ALIAS.get(s, s)
    return re.sub(r"[^a-z]", "", s)


def is_city(name):
    return bool(re.search(r"\bshahri\b|qalas", name, re.I))


def split_layers():
    feats = json.load(open(BUILD / "osm.geojson", encoding="utf8"))["features"]
    keys = ["name", "name:ru", "name:en"]
    for fn, levels, extra in (("regions.geojson", ("3", "4"), ["ISO3166-2"]), ("districts.geojson", ("6",), [])):
        fs = [{"type": "Feature", "geometry": f["geometry"],
               "properties": {"osm_id": int(f["id"].split("/")[1]), **{k.replace(":", "_"): f["properties"].get(k) for k in keys + extra}}}
              for f in feats
              if f["properties"].get("admin_level") in levels and f["geometry"]["type"] in ("Polygon", "MultiPolygon")]
        json.dump({"type": "FeatureCollection", "features": fs}, open(BUILD / fn, "w", encoding="utf8"), ensure_ascii=False)


def attach_names():
    ref = json.load(open(ROOT / "uzbekistan_regions_districts.json", encoding="utf8"))["regions"]
    by_code = {"UZ-" + r["code"]: r for r in ref}
    feats = json.load(open(BUILD / "districts_joined.json", encoding="utf8"))["features"]
    unmatched = []
    for f in feats:
        p = f["properties"]
        r = by_code[p["region"]]
        city = is_city(p["name"])
        typed = {norm(d["name"]["uz"]): d for d in r["districts"] if city == is_city(d["name"]["uz"])}
        anytype = {norm(d["name"]["uz"]): d for d in r["districts"]}
        key = norm(p["name"])
        hit = typed.get(key) or anytype.get(key) or anytype.get((difflib.get_close_matches(key, anytype, 1, 0.85) or [None])[0])
        names = hit["name"] if hit else {"uz": p["name"].replace(" Tumani", " tumani"), "ru": p.get("name_ru") or "", "en": p.get("name_en") or ""}
        if not hit:
            unmatched.append((p["region"], p["name"]))
        f["properties"] = {"id": f"{p['region']}-{p['osm_id']}", "region": p["region"], "region_name": r["name"]["uz"],
                           "type": "city" if is_city(names["uz"]) else "district",
                           "name_uz": names["uz"], "name_ru": names["ru"], "name_en": names["en"], "osm_id": p["osm_id"]}
    used = {(f["properties"]["region"], f["properties"]["name_uz"]) for f in feats}

    for g in json.load(open(BUILD / "gaps.json", encoding="utf8"))["features"]:
        code = g["properties"]["ISO3166-2"]
        r = by_code[code]
        cand = [d for d in r["districts"] if is_city(d["name"]["uz"]) and (code, d["name"]["uz"]) not in used]
        assert len(cand) == 1, f"can't name {g['properties']['km2']:.0f} km2 gap in {code}: {cand}"
        n = cand[0]["name"]
        used.add((code, n["uz"]))
        feats.append({"type": "Feature", "geometry": g["geometry"],
                      "properties": {"id": f"{code}-{norm(n['uz'])}", "region": code, "region_name": r["name"]["uz"], "type": "city",
                                     "name_uz": n["uz"], "name_ru": n["ru"], "name_en": n["en"], "osm_id": None}})
    json.dump({"type": "FeatureCollection", "features": feats}, open(BUILD / "districts_named.json", "w", encoding="utf8"), ensure_ascii=False)

    print(f"{len(feats)} polygons; not in reference JSON: {unmatched}")
    print("reference entries without own polygon (inside their district in OSM):",
          [d["name"]["uz"] for r in ref for d in r["districts"] if ("UZ-" + r["code"], d["name"]["uz"]) not in used])
    dup = [k for k in used if sum((f["properties"]["region"], f["properties"]["name_uz"]) == k for f in feats) > 1]
    assert not dup, f"two polygons matched the same name: {dup}"
    assert all(f["properties"]["region"] in by_code for f in feats)


def main():
    BUILD.mkdir(exist_ok=True)
    raw = BUILD / "osm.json"
    if "--refresh" in sys.argv or not raw.exists():
        req = urllib.request.Request(OVERPASS, urllib.parse.urlencode({"data": QUERY}).encode(), {"User-Agent": "uzbekistan-regions-map"})
        raw.write_bytes(urllib.request.urlopen(req, timeout=900).read())
    sys.stdout.reconfigure(encoding="utf-8")
    with open(BUILD / "osm.geojson", "wb") as out:
        subprocess.run(["node", ROOT / "node_modules/osmtogeojson/osmtogeojson", raw], check=True, stdout=out)
    split_layers()
    mapshaper(*"-i districts.geojson -join regions.geojson point-method fields=ISO3166-2"
              " -rename-fields region=ISO3166-2 -o districts_joined.json format=geojson".split())
    mapshaper(*"-i regions.geojson -erase districts_joined.json -explode -each km2=this.area/1e6"
              " -filter km2>20 -o gaps.json format=geojson".split())
    attach_names()
    palette = json.dumps(PALETTE, separators=(",", ":"))
    mapshaper(*"-i districts_named.json name=all -filter type=='city' + name=cities"
              " -filter type!='city' target=all + name=dists -erase cities target=dists"
              " -merge-layers target=cities,dists name=districts"
              " -simplify dp interval=30 keep-shapes -clean gap-fill-area=1km2"
              " -o ../uzbekistan_districts.geojson format=geojson precision=0.00001".split(),
              "-proj", PROJ,
              "-each", f"color={palette}[region]", "target=districts",
              *"-dissolve region + name=regions copy-fields=region_name"
              " -style target=districts fill=color stroke=#ffffff stroke-width=0.4"
              " -points inner target=regions + name=labels -each lbl=\"label-\"+region target=labels"
              " -style target=labels label-text=region_name"
              " -each border=\"border-\"+region target=regions -style target=regions fill=none stroke=#374151 stroke-width=1"
              " -split region target=districts"
              " -o target=UZ-*,regions,labels ../uzbekistan_districts.svg format=svg width=1600 precision=0.02"
              " id-field=id,border,lbl svg-data=name_uz,name_ru,name_en,type,region,region_name".split())
    svg = (ROOT / "uzbekistan_districts.svg").read_text(encoding="utf8").split("?>", 1)[-1]
    page = (ROOT / "scripts/map_template.html").read_text(encoding="utf8").replace("{{SVG}}", svg)
    (ROOT / "uzbekistan_map.html").write_text(page, encoding="utf8")


if __name__ == "__main__":
    main()
