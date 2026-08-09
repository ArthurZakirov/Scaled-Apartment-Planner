#!/usr/bin/env python3
"""Render the active apartment layout to SVG and PNG without a browser."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

import cairosvg

from geometry import expand_apartment_geometry
from furniture import resolve_scenario_data

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def points(points_):
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in points_)


def rotate(point, angle_deg, center):
    x, y = point
    cx, cy = center
    a = math.radians(angle_deg)
    dx, dy = x - cx, y - cy
    return (cx + dx * math.cos(a) - dy * math.sin(a), cy + dx * math.sin(a) + dy * math.cos(a))


def furniture_polygon(obj, cm_per_px):
    if obj["render"]["shape"] == "l_desk":
        dims = obj["dimensionsCm"]
        w, d = dims["width"] / cm_per_px, dims["depth"] / cm_per_px
        main = dims["mainTopDepth"] / cm_per_px
        ret = dims["returnDepth"] / cm_per_px
        x, y = obj["positionPx"]["topLeft"]
        if obj["positionPx"].get("handedness") == "left":
            local = [(0, 0), (w, 0), (w, main), (ret, main), (ret, d), (0, d)]
        else:
            local = [(0, 0), (w, 0), (w, d), (w - ret, d), (w - ret, main), (0, main)]
        return [rotate((x + px, y + py), obj["positionPx"].get("rotationDeg", 0), (x, y)) for px, py in local]

    dims = obj["dimensionsCm"]
    w, d = dims["width"] / cm_per_px, dims["depth"] / cm_per_px
    cx, cy = obj["positionPx"]["center"]
    local = [(cx - w/2, cy - d/2), (cx + w/2, cy - d/2), (cx + w/2, cy + d/2), (cx - w/2, cy + d/2)]
    return [rotate(p, obj["positionPx"].get("rotationDeg", 0), (cx, cy)) for p in local]


def door_arc_path(door):
    hx, hy = door["hinge"]
    cx, cy = door["closedPoint"]
    ox, oy = door["openPoint"]
    r = max(math.hypot(cx-hx, cy-hy), math.hypot(ox-hx, oy-hy))
    v1 = (cx-hx, cy-hy)
    v2 = (ox-hx, oy-hy)
    sweep = 1 if v1[0]*v2[1] - v1[1]*v2[0] > 0 else 0
    return f"M {cx} {cy} A {r:.2f} {r:.2f} 0 0 {sweep} {ox} {oy}"


def centroid(poly):
    return (sum(x for x, _ in poly)/len(poly), sum(y for _, y in poly)/len(poly))


def render(output_svg: Path, output_png: Path):
    apartment = expand_apartment_geometry(load_json(ROOT / "data/apartment.json"))
    fixtures = load_json(ROOT / "data/fixed-fixtures.json")
    catalog = load_json(ROOT / "data/furniture-catalog.json")
    scenario_data = load_json(ROOT / "data/layout-scenarios.json")
    furniture = resolve_scenario_data(scenario_data, catalog)
    layout = next(x for x in furniture["layouts"] if x["id"] == furniture["activeLayoutId"])
    _, _, vw, vh = apartment["coordinateSystem"]["viewBox"]

    svg = Element("svg", {
        "xmlns": "http://www.w3.org/2000/svg",
        "viewBox": f"0 0 {vw} {vh}",
        "width": "1600",
        "height": str(round(1600 * vh / vw)),
    })
    style = SubElement(svg, "style")
    style.text = """
      text { font-family: Inter, Arial, sans-serif; }
      .space-interior { fill:#fcfcfa; stroke:#cad1cc; stroke-width:1; }
      .space-exterior { fill:#e8f0ea; stroke:#aebbb2; stroke-width:1.5; }
      .wall { stroke:#172a24; stroke-linecap:square; }
      .wall-interior { stroke:#263b34; stroke-linecap:butt; }
      .balustrade { fill:none; stroke:#8ea096; stroke-width:1.5; }
      .window { stroke:#88cad1; stroke-width:5; stroke-linecap:round; }
      .fixture { fill:#d7ded7; stroke:#819086; stroke-width:1.2; }
      .fixture-detail { fill:#f3f5f2; stroke:#67766e; stroke-width:1; }
      .wardrobe { fill:#d39135aa; stroke:#8f5a12; stroke-width:2; }
      .bed { fill:#427eb373; stroke:#28618e; stroke-width:2; }
      .mattress { fill:#ffffff70; stroke:#28618e; stroke-width:1; }
      .desk { fill:#438f677a; stroke:#267348; stroke-width:2; }
      .storage { fill:#8267ab6b; stroke:#73559c; stroke-width:2; }
      .door { fill:none; stroke:#c27627; stroke-width:1.5; }
      .label { font-size:10px; font-weight:700; text-anchor:middle; fill:#4a5752; }
      .f-label { font-size:8px; font-weight:800; text-anchor:middle; fill:#15241f; }
      .title { font-size:18px; font-weight:800; fill:#17211e; }
      .subtitle { font-size:9px; fill:#64706b; }
    """
    SubElement(svg, "rect", {"width": str(vw), "height": str(vh), "fill": "#eef1ec"})
    SubElement(svg, "rect", {"x":"12", "y":"12", "width":str(vw-24), "height":str(vh-24), "rx":"10", "fill":"white", "stroke":"#d7ddd8"})

    g = SubElement(svg, "g", {"transform":"translate(0,18) scale(0.93) translate(25,0)"})
    for space in apartment["spaces"]:
        SubElement(g, "polygon", {"points": points(space["points"]), "class": f"space-{space['type']}"})
    for niche in apartment.get("niches", []):
        SubElement(g, "polygon", {"points": points(niche["points"]), "class": "niche"})
    for bal in apartment["balustrades"]:
        tag = "polygon" if bal.get("closed") else "polyline"
        SubElement(g, tag, {"points": points(bal["points"]), "class":"balustrade"})
    for wall in apartment["walls"]:
        SubElement(g, "line", {
            "x1":str(wall["start"][0]), "y1":str(wall["start"][1]),
            "x2":str(wall["end"][0]), "y2":str(wall["end"][1]),
            "stroke-width":str(wall["thicknessPx"]),
            "class":f"wall wall-{wall['kind']}"
        })
    for win in apartment["windows"]:
        SubElement(g, "line", {"x1":str(win["start"][0]), "y1":str(win["start"][1]), "x2":str(win["end"][0]), "y2":str(win["end"][1]), "class":"window"})

    for f in fixtures["fixtures"]:
        SubElement(g, "rect", {"x":str(f["x"]), "y":str(f["y"]), "width":str(f["widthPx"]), "height":str(f["depthPx"]), "class":"fixture"})
        if f["type"] in {"sink", "hob"}:
            SubElement(g, "rect", {"x":str(f["x"]+5), "y":str(f["y"]+5), "width":str(max(1,f["widthPx"]-10)), "height":str(max(1,f["depthPx"]-10)), "class":"fixture-detail"})

    cm_per_px = apartment["scale"]["cmPerPixel"]
    for obj in layout["objects"]:
        poly = furniture_polygon(obj, cm_per_px)
        cls = {"wardrobe":"wardrobe", "bed":"bed", "desk":"desk", "storage":"storage"}.get(obj["type"], "desk")
        SubElement(g, "polygon", {"points":points(poly), "class":cls})
        if obj["render"]["shape"] == "bed":
            mw = obj["mattressCm"]["width"] / cm_per_px
            md = obj["mattressCm"]["depth"] / cm_per_px
            cx, cy = obj["positionPx"]["center"]
            inner = [(cx-mw/2,cy-md/2),(cx+mw/2,cy-md/2),(cx+mw/2,cy+md/2),(cx-mw/2,cy+md/2)]
            inner = [rotate(p,obj["positionPx"]["rotationDeg"],(cx,cy)) for p in inner]
            SubElement(g,"polygon",{"points":points(inner),"class":"mattress"})
        cx, cy = centroid(poly)
        t = SubElement(g,"text",{"x":f"{cx:.1f}","y":f"{cy:.1f}","class":"f-label"})
        t.text = obj["render"]["label"]

    for door in apartment["doors"]:
        hx, hy = door["hinge"]
        ox, oy = door["openPoint"]
        SubElement(g,"line",{"x1":str(hx),"y1":str(hy),"x2":str(ox),"y2":str(oy),"class":"door"})
        SubElement(g,"path",{"d":door_arc_path(door),"class":"door"})
        SubElement(g,"circle",{"cx":str(hx),"cy":str(hy),"r":"2.3","fill":"#c27627"})

    for label in apartment["labels"]:
        t=SubElement(g,"text",{"x":str(label["position"][0]),"y":str(label["position"][1]),"class":"label"})
        t.text=label["text"]

    title=SubElement(svg,"text",{"x":"30","y":"35","class":"title"})
    title.text="Wohnung 264 – Layout-Experiment"
    subtitle=SubElement(svg,"text",{"x":"30","y":"51","class":"subtitle"})
    subtitle.text="Schlafbereich-Experiment · Bett, Kommode und PAX · Eingangstür als 100-cm-Anker bestätigt"
    note=SubElement(svg,"text",{"x":"30","y":str(vh-20),"class":"subtitle"})
    note.text="Planungsstand: geometrische Näherung; der Originalgrundriss ist laut Quelle nicht maßstabsgerecht."

    output_svg.parent.mkdir(parents=True, exist_ok=True)
    output_svg.write_bytes(tostring(svg, encoding="utf-8", xml_declaration=True))
    cairosvg.svg2png(bytestring=output_svg.read_bytes(), write_to=str(output_png), output_width=1600)
    print(output_png)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--svg", type=Path, default=ROOT/"docs/current-layout.svg")
    parser.add_argument("--png", type=Path, default=ROOT/"docs/current-layout.png")
    args=parser.parse_args()
    render(args.svg,args.png)

if __name__ == "__main__":
    main()
