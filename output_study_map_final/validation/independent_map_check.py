#!/usr/bin/env python3
"""Independent read-only GIS/vector/scale/preservation/reproduction acceptance.

Run with the delivered map directory (default: parent of this validation folder).
No plotting implementation is imported; a separate subprocess reproduces to a
temporary directory. Original full GIS sources are optional local-only evidence.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import fitz
from lxml import etree
import numpy as np
from PIL import Image
from pyproj import Geod, Transformer
from shapely.geometry import box, shape
from shapely.ops import transform, unary_union
from shapely.validation import make_valid


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parts(geom):
    if geom.geom_type.startswith('Multi') or geom.geom_type == 'GeometryCollection':
        for item in geom.geoms:
            yield from parts(item)
    else:
        yield geom


def vertices(geom):
    if geom.geom_type == 'Polygon':
        return np.array([p for ring in (geom.exterior, *geom.interiors) for p in ring.coords])
    return np.array(geom.coords)


def svg_points(element):
    # All inspected map paths consist of absolute M/L/Z vertices, never curves.
    data = element.attrib['d']
    assert not re.search(r'[CcQqAaHhVvSsTt]', data)
    numbers = re.findall(r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?', data)
    return np.array(list(map(float, numbers))).reshape(-1, 2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--map-dir', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--full-source-dir', type=Path,
                        default=Path('/workspace/study_map_final_work/gis'))
    parser.add_argument('--preservation-file', type=Path,
                        default=Path('/workspace/study_map_final_work/preserved_inputs.json'))
    parser.add_argument('--output-json', type=Path)
    args = parser.parse_args()
    folder = args.map_dir.resolve()
    output_json = args.output_json or folder / 'validation/independent_map_check.json'
    science_files = [folder / name for name in (
        'Fig1_StudyArea_Final.svg', 'Fig1_StudyArea_Final.pdf', 'Fig1_StudyArea_Final.png',
        'plot_study_area.py', 'prepare_verified_gis.py', 'bridge_locations_check.csv')]
    science_files += sorted((folder / 'geodata').glob('*'))
    snapshot_before = {str(p): sha(p) for p in science_files if p.is_file()}
    audit = json.loads((folder / 'validation/plot_audit.json').read_text())
    manifest = json.loads((folder / 'geodata/GIS_source_manifest.json').read_text())
    bbox = manifest['clip_bbox_wgs84']
    boundary = box(*bbox)
    projector = Transformer.from_crs('EPSG:4326', 'EPSG:32651', always_xy=True)
    inverse = Transformer.from_crs('EPSG:32651', 'EPSG:4326', always_xy=True)
    extent = transform(projector.transform, boundary).bounds
    assert np.allclose(extent, audit['extent_projected_m'], atol=1e-8, rtol=0)
    assert audit['projection'] == 'EPSG:32651'
    document = etree.parse(str(folder / 'Fig1_StudyArea_Final.svg'))
    ns = {'s': 'http://www.w3.org/2000/svg'}
    svg_raw = (folder / 'Fig1_StudyArea_Final.svg').read_text()
    all_ids = [e.attrib['id'] for e in document.xpath('//*[@id]')]
    image_count = len(document.xpath('//s:image', namespaces=ns))
    path_count = len(document.xpath('//s:path', namespaces=ns))
    text_nodes = document.xpath('//s:text', namespaces=ns)
    texts = [''.join(t.itertext()).strip() for t in text_nodes]
    assert (image_count, path_count, len(text_nodes)) == (0, 37, 12)
    assert 'data:image' not in svg_raw and 'base64' not in svg_raw
    assert len(all_ids) == len(set(all_ids))
    for required_id in ['city-label-ningbo', 'true-north-arrow-outline',
                        'true-north-arrow-left-fill', 'projection-scale-0',
                        'projection-scale-1', 'map-legend-conventions', 'unverified-layer-note']:
        assert required_id in all_ids
    assert not any(re.match(r'(verified-bridge|verified-s1|symbolic-study-corridor)', i) for i in all_ids)
    assert 'Fenghua River' not in texts
    forbidden = ['Fenghua', 'Yongjiang', 'Jiangbei', 'Haishu', 'Beilun', 'Yinzhou', 'District', 'Entrance', 'Exit', 'Northbound', 'Northeastbound']
    assert not any(word.lower() in ' '.join(texts).lower() for word in forbidden)
    assert 'Ningbo' in texts
    assert 'Pending verification — not mapped:' in texts
    for expected in ['Study bridge locations', 'S1 Yongtaiwen Expressway', 'Study corridor']:
        assert expected in texts
    assert texts.count('S1 Yongtaiwen Expressway') == 1  # legend convention only
    legend = document.xpath('//*[@id="map-legend-conventions"]')[0]
    assert 'S1 Yongtaiwen Expressway' in ''.join(legend.itertext())

    clip_rect = document.xpath('//s:clipPath/s:rect', namespaces=ns)
    assert len(clip_rect) == 1
    rect = {k: float(v) for k, v in clip_rect[0].attrib.items()}
    def svg_xy(points):
        points = np.array(points)
        return np.column_stack((rect['x'] + (points[:,0]-extent[0])/(extent[2]-extent[0])*rect['width'],
            rect['y'] + rect['height']-(points[:,1]-extent[1])/(extent[3]-extent[1])*rect['height']))
    def projected_xy(points):
        points = np.array(points)
        return np.column_stack((extent[0]+(points[:,0]-rect['x'])/rect['width']*(extent[2]-extent[0]),
            extent[1]+(rect['y']+rect['height']-points[:,1])/rect['height']*(extent[3]-extent[1])))
    def path_for(gid):
        found = document.xpath('//*[@id=$gid]/s:path', gid=gid, namespaces=ns)
        assert len(found) == 1, gid
        return svg_points(found[0])

    layer_checks = []
    loaded = {}
    source_vertex_checks = []
    gid_prefixes = {'roads':'generalized-road', 'land':'land', 'ocean':'ocean', 'coastline':'coastline',
                    'lakes':'lakes', 'rivers_lake_centerlines':'rivers'}
    for entry in manifest['source_and_clipped_layers']:
        clipped = folder / 'geodata' / entry['clipped_filename']
        assert sha(clipped) == entry['clipped_sha256']
        collection = json.loads(clipped.read_text())
        features = collection['features']
        assert len(features) == entry['clipped_feature_count']
        assert all(shape(f['geometry']).is_valid for f in features)
        assert all(boundary.covers(shape(f['geometry'])) for f in features)
        loaded[entry['layer']] = features
        full = args.full_source_dir / entry['original_filename']
        original_checked = False
        if full.exists():
            payload = full.read_bytes()
            assert hashlib.sha256(payload).hexdigest() == entry['original_sha256']
            assert hashlib.sha1(f'blob {len(payload)}\0'.encode() + payload).hexdigest() == entry['original_git_blob_sha1']
            full_features = json.loads(payload)['features']
            for feature in features:
                source_feature = full_features[feature['properties']['source_feature_index']]
                original = shape(source_feature['geometry'])
                if not original.is_valid:
                    original = make_valid(original)
                assert shape(feature['geometry']).equals(original.intersection(boundary))
                expected_props = dict(source_feature['properties'])
                expected_props['source_feature_index'] = feature['properties']['source_feature_index']
                assert expected_props == feature['properties']
            original_checked = True
        # Independently compare every SVG map vertex to the projected source geometry.
        prefix = gid_prefixes.get(entry['layer'])
        if prefix:
            for index, feature in enumerate(features):
                geographic = shape(feature['geometry']).intersection(boundary)
                projected = transform(projector.transform, geographic)
                for part_index, part in enumerate(parts(projected)):
                    if part.geom_type not in ('Polygon','LineString','LinearRing'):
                        continue
                    gid = f'{prefix}-{index:05d}-{part_index}'
                    actual = path_for(gid)
                    expected = svg_xy(vertices(part))
                    distances = np.linalg.norm(actual[:,None,:]-expected[None,:,:],axis=2)
                    max_error = max(distances.min(axis=0).max(), distances.min(axis=1).max())
                    assert max_error < 0.000003, (gid, max_error)
                    source_vertex_checks.append({'gid':gid,'vertices':len(actual), 'max_bidirectional_vertex_error_svg_pt':float(max_error)})
        layer_checks.append({'layer':entry['layer'],'sha256':sha(clipped),'features':len(features),
                             'all_valid':True,'all_inside_bbox':True,'original_source_geometry_and_metadata_equal':original_checked})
    assert len(layer_checks) == 7 and len(source_vertex_checks) == 24
    land = unary_union([shape(f['geometry']) for f in loaded['land']])
    ocean = unary_union([shape(f['geometry']) for f in loaded['ocean']])
    overlap = land.intersection(ocean).area
    gap = boundary.difference(land.union(ocean)).area
    assert overlap < 1e-14 and gap < 1e-14
    assert len(loaded['lakes']) == len(loaded['rivers_lake_centerlines']) == 0
    assert len(loaded['populated_places']) == 1
    city = loaded['populated_places'][0]
    assert city['properties']['NAME'] == 'Ningbo' and city['geometry']['type'] == 'Point'
    label = document.xpath('//*[@id="city-label-ningbo"]/s:text', namespaces=ns)[0]
    city_expected = svg_xy([projector.transform(*city['geometry']['coordinates'])])[0]
    # Text y is a font baseline. The centered label's background box retains
    # the actual geographic anchor in y; text-anchor:middle retains it in x.
    city_box = svg_points(document.xpath('//*[@id="city-label-ningbo"]/s:g/s:path', namespaces=ns)[0])
    city_anchor = np.array([float(label.attrib['x']), (city_box[:,1].min()+city_box[:,1].max())/2])
    assert np.linalg.norm(city_expected-city_anchor) < 0.000003

    with (folder / 'bridge_locations_check.csv').open(encoding='utf-8-sig', newline='') as stream:
        bridge_rows = list(csv.DictReader(stream))
    assert len(bridge_rows) == len(set(r['unit_id'] for r in bridge_rows)) == 59
    assert all(r['location_status'] == 'pending_report_and_alignment_verification' for r in bridge_rows)
    assert all(not r[k] for r in bridge_rows for k in ('x','y','crs','route_name','route_code','chainage_system','route_system'))
    assert all(r['map_plotted'] == 'false' for r in bridge_rows)
    assert audit['bridges']['plotted_units'] == audit['bridges']['verified_units'] == 0
    assert audit['bridges']['unresolved_units'] == 59 and audit['layers']['s1'] == 0
    assert not audit['layers'].get('study_corridor')

    scale0, scale1 = path_for('projection-scale-0'), path_for('projection-scale-1')
    all_scale = np.vstack((scale0,scale1))
    start_svg = [all_scale[:,0].min(), (all_scale[:,1].min()+all_scale[:,1].max())/2]
    end_svg = [all_scale[:,0].max(), start_svg[1]]
    endpoints_projected = projected_xy([start_svg,end_svg])
    length_projected = float(np.linalg.norm(endpoints_projected[1]-endpoints_projected[0]))
    assert abs(length_projected-10000) < 0.001
    endpoints_ll = [list(inverse.transform(*point)) for point in endpoints_projected]
    geod = Geod(ellps='WGS84')
    _,_,length_geod = geod.inv(*endpoints_ll[0], *endpoints_ll[1])
    scale_error = abs(length_geod-10000)/10000
    assert scale_error < .0003
    assert abs(length_geod-audit['scale_bar']['geodesic_endpoint_distance_m']) < .001
    assert np.allclose(endpoints_ll, audit['scale_bar']['endpoints_wgs84'], atol=1e-8, rtol=0)
    assert set(['0','5','10','km']).issubset(texts)
    arrow = projected_xy(path_for('true-north-arrow-outline'))
    observed_direction = arrow[0]-arrow[2]  # tip minus central notch
    lon,lat = audit['north_arrow']['reference_lon_lat']
    a = np.array(projector.transform(lon,lat))
    b = np.array(projector.transform(lon,lat+.03))
    expected_direction = b-a
    bearing = math.degrees(math.atan2(expected_direction[0],expected_direction[1]))
    observed_bearing = math.degrees(math.atan2(observed_direction[0],observed_direction[1]))
    assert abs(observed_bearing-bearing) < .0001
    assert abs(bearing-audit['north_arrow']['bearing_degrees_from_projected_y']) < 1e-8
    assert audit['north_arrow']['method'] == 'project a geographic meridian at arrow location'

    with fitz.open(folder / 'Fig1_StudyArea_Final.pdf') as pdf:
        pdf_check = {'pages':len(pdf),'images':sum(len(p.get_images(full=True)) for p in pdf),
                     'vector_drawing_objects':sum(len(p.get_drawings()) for p in pdf),
                     'extractable_text':' '.join(p.get_text() for p in pdf)}
    assert pdf_check['pages'] == 1 and pdf_check['images'] == 0 and pdf_check['vector_drawing_objects'] == 36
    assert 'Ningbo' in pdf_check['extractable_text'] and 'Pending verification' in pdf_check['extractable_text']
    with Image.open(folder / 'Fig1_StudyArea_Final.png') as image:
        png = {'pixels':list(image.size),'dpi':list(image.info['dpi'])}
    assert png['pixels'] == [4724,3543] and all(abs(v-600) < .002 for v in png['dpi'])

    reproduction = {}
    with tempfile.TemporaryDirectory(prefix='independent-map-reproduction-') as temp:
        result = subprocess.run([sys.executable,str(folder/'plot_study_area.py'),'--output-dir',temp],
                                capture_output=True,text=True,check=True)
        for suffix in ['svg','pdf','png']:
            name = 'Fig1_StudyArea_Final.'+suffix
            reproduction[name] = {'sha256':sha(Path(temp)/name), 'byte_identical':sha(Path(temp)/name)==sha(folder/name)}
            assert reproduction[name]['byte_identical']

    preserved = {}
    if args.preservation_file.exists():
        for path, expected in json.loads(args.preservation_file.read_text()).items():
            actual = sha(path)
            assert actual == expected
            preserved[path] = {'sha256':actual,'unchanged':True}
    snapshot_after = {str(p):sha(p) for p in science_files if p.is_file()}
    assert snapshot_after == snapshot_before
    report = {
        'independent_acceptance_passed':True,
        'scientific_status':'Verified generalized geographic context only. Exact S1 study alignment, corridor and all 59 bridge-unit positions remain unverified and deliberately unmapped. Not a submission-ready precise bridge-distribution map.',
        'no_word_or_source_data_modified':True if preserved else None,
        'external_original_input_preservation_status':'checked' if preserved else 'not_available_in_this_workspace',
        'formal_map_assets_unchanged_by_audit':True,
        'svg':{'images':image_count,'paths':path_count,'editable_texts':len(texts),'raster_payloads':False,
               'all_ids':all_ids,'text_content':texts,'all_24_geographic_paths_match_projected_frozen_GIS_vertices':True,
               'source_vertex_checks':source_vertex_checks},
        'pdf':pdf_check,'png':png,'GIS_layers':layer_checks,
        'natural_earth_commit':manifest['git_commit'],'map_source_scale':manifest['map_source_scale'],
        'all_actual_geographic_geometries_match_pinned_Natural_Earth':all(c['original_source_geometry_and_metadata_equal'] for c in layer_checks),
        'land_ocean_topology':{'overlap_degree2':overlap,'uncovered_degree2':gap,'physical_area_claim':False},
        'bridge_check':{'units':59,'located':0,'unlocated':59,'plotted':0,'all_coordinate_and_unit_route_fields_blank':True,'s1_geographic_features_drawn':0,'corridor_geographic_features_drawn':0},
        'city_label_check':{'Ningbo':'Only a source-defined populated-place label; not a bridge marker or verified district boundary.'},
        'scale_check':{'projection':'EPSG:32651','projection_length_m_from_SVG_geometry':length_projected,
                       'wgs84_endpoints_from_SVG_geometry':endpoints_ll,'geodesic_distance_m':length_geod,
                       'relative_error':scale_error,'percent_error':scale_error*100},
        'north_check':{'method':'Independent EPSG:32651 projection of meridian points (lon,lat) and (lon,lat+0.03); compare SVG tip-notch direction.',
                       'meridian_lonlat_points':[[lon,lat],[lon,lat+.03]],'expected_bearing_deg_from_grid_y':bearing,
                       'observed_SVG_bearing_deg_from_grid_y':observed_bearing,'absolute_error_degrees':abs(bearing-observed_bearing)},
        'reproduction':reproduction,'preserved_original_inputs':preserved,
        'limitations':['Natural Earth 1:10 million data provide generalized context, not local survey accuracy.',
                       'No verifiable local river/lake features intersect this coarse dataset window; empty water layers were not filled with invented features.',
                       'S1 and all 59 bridge locations are pending; legend conventions are accompanied by an explicit not-mapped note.',
                       'Exact bridge-distribution map remains incomplete; use this as the allowed verified-part delivery only.']}
    output_json.parent.mkdir(exist_ok=True)
    output_json.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'independent_acceptance_passed':True,'report':str(output_json),'status':'verified geographic context only; 59 bridge units still unlocated'},ensure_ascii=False))


if __name__ == '__main__':
    main()
