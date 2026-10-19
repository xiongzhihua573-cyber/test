#!/usr/bin/env python3
"""Clip pinned Natural Earth vectors; never infer roads or bridge locations.

Requires shapely. Original source files must be retained in --source-dir.
The default bounding box is a local Ningbo viewing window, not a verified
research-corridor boundary. This script does not identify or highlight S1.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from shapely.geometry import box, mapping, shape
from shapely.validation import make_valid

COMMIT = "ca96624a56bd078437bca8184e78163e5039ad19"
BBOX = [121.4, 29.70, 121.95, 30.05]
PINNED_BLOBS = {
    "roads": "6f294f88d319791af216bcc394aed19a6b0148d6",
    "rivers_lake_centerlines": "61a0d7137a6ff1113cc259525e7479c63d5fec86",
    "lakes": "e48ec603e0943b62f8c81960fb990bb6bab4a4a8",
    "coastline": "ff2cb1a203a39eff0d202302b72e234733dd9bdf",
    "ocean": "7f5c93c471dc99e34976ed760593f8e91c330226",
    "land": "2d76878175b8054acd9c5a52917ee9ea59a36fc5",
    "populated_places": "376fb028c390a7a23213800ae4babaa6f534a0f3",
}
EXPECTED_COUNTS = {
    "roads": 15,
    "rivers_lake_centerlines": 0,
    "lakes": 0,
    "coastline": 3,
    "ocean": 1,
    "land": 3,
    "populated_places": 1,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=Path(__file__).parent / "gis")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "gis")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    window = box(*BBOX)
    manifest = {
        "repository": "https://github.com/nvkelso/natural-earth-vector",
        "git_commit": COMMIT,
        "version_file": "5.2.0-pre",
        "license": "Public domain; see NaturalEarth_LICENSE.md",
        "coordinate_reference_system": "OGC:CRS84 (WGS84 longitude, latitude)",
        "clip_bbox_wgs84": BBOX,
        "map_source_scale": "1:10 million; generalized geographic context",
        "s1_mainline_verified": False,
        "exact_research_corridor_verified": False,
        "verified_bridge_detection_units": 0,
        "source_and_clipped_layers": [],
        "limits": [
            "This viewing window is not a surveyed study-area boundary.",
            "No original road in this window has a usable name or route reference; none is identified as S1.",
            "No Natural Earth river or lake intersects this window. Empty layers must not be supplemented by invented geography.",
            "Ningbo is a city reference point, not a bridge position.",
            "This generalized dataset cannot establish exact bridge or interchange locations.",
        ],
    }
    for layer, blob in PINNED_BLOBS.items():
        filename = f"ne_10m_{layer}.geojson"
        original = (args.source_dir / filename).read_bytes()
        git_blob = hashlib.sha1(f"blob {len(original)}\0".encode() + original).hexdigest()
        if git_blob != blob:
            raise ValueError(f"Original source does not match pinned commit: {filename}")
        source = json.loads(original)
        features = []
        for index, feature in enumerate(source["features"]):
            geom = shape(feature["geometry"])
            if geom.is_empty or not geom.intersects(window):
                continue
            if layer == "populated_places":
                prop = feature["properties"]
                if prop.get("NAME") != "Ningbo" and prop.get("name") != "Ningbo":
                    continue
            if not geom.is_valid:
                geom = make_valid(geom)
            geom = geom.intersection(window)
            if geom.is_empty:
                continue
            features.append({
                "type": "Feature", "id": index,
                "properties": {**feature["properties"], "source_feature_index": index},
                "geometry": mapping(geom),
            })
        if len(features) != EXPECTED_COUNTS[layer]:
            raise AssertionError(f"Unexpected pinned layer feature count: {layer}")
        if layer == "roads":
            assert all(not f["properties"].get(k) for f in features for k in ["name", "routeraw", "label"])
        output_name = (
            "ningbo_city_reference_point_wgs84.geojson" if layer == "populated_places"
            else f"ningbo_ne_10m_{layer}_clipped.geojson"
        )
        output = args.output_dir / output_name
        output.write_text(json.dumps({"type": "FeatureCollection", "bbox": BBOX, "features": features}, ensure_ascii=False), encoding="utf-8")
        manifest["source_and_clipped_layers"].append({
            "layer": layer,
            "original_filename": filename,
            "pinned_source_url": f"https://raw.githubusercontent.com/nvkelso/natural-earth-vector/{COMMIT}/geojson/{filename}",
            "original_sha256": hashlib.sha256(original).hexdigest(),
            "original_git_blob_sha1": git_blob,
            "original_matches_pinned_git_tree": True,
            "original_feature_count": len(source["features"]),
            "clipped_filename": output_name,
            "clipped_feature_count": len(features),
            "clipped_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        })
    (args.output_dir / "GIS_source_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({x["layer"]: x["clipped_feature_count"] for x in manifest["source_and_clipped_layers"]}))


if __name__ == "__main__":
    main()
