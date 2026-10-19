#!/usr/bin/env python3
"""Reproduce the audited Ningbo study-area map from frozen WGS84 GIS files.

Usage (from any working directory)::
    python plot_study_area.py
    python plot_study_area.py --geodata-dir geodata --output-dir out

This script never infers bridge coordinates from a name or chainage, geocodes
addresses, interpolates 59 points, traces the supplied AI image, or downloads
live GIS. An absent/unverified layer is omitted and reported. The default
geodata directory is beside this script, so the delivered folder is portable.
See map_revision_notes.md for source provenance, accuracy and omissions.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import re
import xml.etree.ElementTree as ET

os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir())/'ningbo-map-matplotlib-cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.patches import PathPatch, Polygon, Rectangle
from matplotlib.path import Path as MplPath
import numpy as np
import pandas as pd
from pyproj import Transformer, Geod
from shapely.geometry import shape, box, Point, LineString
from shapely.geometry.polygon import orient
from shapely.ops import transform, unary_union

HERE = Path(__file__).resolve().parent
BBOX = (121.40, 29.70, 121.95, 30.05)
CRS = 'EPSG:32651'
COLORS = dict(land='#f5f5f3', ocean='#b9ddec', water='#b9ddec',
              roads='#d2d2cf', major_roads='#b5b6b4', coastline='#91bfd4',
              s1='#4a4e4a', corridor='#cf383a', bridges='#168447', text='#242924')
PROJECT = Transformer.from_crs('EPSG:4326', CRS, always_xy=True)
INVERSE = Transformer.from_crs(CRS, 'EPSG:4326', always_xy=True)
GEOD = Geod(ellps='WGS84')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_geojson(path, audit, key, required=False):
    path = Path(path)
    if not path.exists():
        if required:
            raise FileNotFoundError(f'Required frozen GIS input missing: {path}')
        audit['inputs'][key] = dict(exists=False, features=0)
        return []
    raw = json.loads(path.read_text(encoding='utf-8-sig'))
    features = raw.get('features', [])
    if raw.get('type') != 'FeatureCollection':
        raise ValueError(f'{path}: expected GeoJSON FeatureCollection')
    crs = raw.get('crs', {}).get('properties', {}).get('name', '')
    if crs and not any(s in crs.lower() for s in ('crs84', '4326')):
        raise ValueError(f'{path}: WGS84 longitude/latitude required, got {crs}')
    audit['inputs'][key] = dict(path=path.name, sha256=sha256(path),
                                exists=True, features=len(features))
    return features


def iter_parts(geom):
    if geom.geom_type.startswith('Multi') or geom.geom_type == 'GeometryCollection':
        for part in geom.geoms:
            yield from iter_parts(part)
    else:
        yield geom


def polygon_path(poly):
    # Opposite orientations preserve holes in SVG/PDF under nonzero fill.
    poly = orient(poly, sign=1)
    vertices, codes = [], []
    for ring in (poly.exterior, *poly.interiors):
        points = np.asarray(ring.coords)
        vertices.extend(points)
        codes.extend([MplPath.MOVETO] + [MplPath.LINETO] * (len(points)-2) + [MplPath.CLOSEPOLY])
    return MplPath(vertices, codes)


def draw_geometries(ax, features, key, facecolor='none', edgecolor='none',
                    linewidth=.5, zorder=1, linestyle='-', clip_geom=None):
    count = 0
    for index, feature in enumerate(features):
        if not feature.get('geometry'):
            continue
        geom = shape(feature['geometry'])
        if geom.is_empty:
            continue
        if not geom.is_valid:
            raise ValueError(f'{key}[{index}] is invalid; repair must be audited before drawing')
        if clip_geom is not None:
            geom = geom.intersection(clip_geom)
        projected = transform(PROJECT.transform, geom)
        for j, part in enumerate(iter_parts(projected)):
            if part.is_empty:
                continue
            if part.geom_type == 'Polygon':
                artist = PathPatch(polygon_path(part), facecolor=facecolor,
                                   edgecolor=edgecolor, linewidth=linewidth,
                                   linestyle=linestyle, zorder=zorder)
                ax.add_patch(artist)
            elif part.geom_type in ('LineString', 'LinearRing'):
                pts = np.asarray(part.coords)
                artist, = ax.plot(pts[:,0], pts[:,1], color=edgecolor,
                                  lw=linewidth, ls=linestyle, zorder=zorder,
                                  solid_capstyle='round', solid_joinstyle='round')
            else:
                continue
            artist.set_gid(f'{key}-{index:05d}-{j}')
            artist.set_rasterized(False)
            count += 1
    return count


def load_verified_bridge_points(path, audit):
    frame = pd.read_csv(path, encoding='utf-8-sig', dtype=str, keep_default_na=False)
    if len(frame) != 59 or frame['unit_id'].nunique() != 59:
        raise ValueError('Expected exactly 59 distinct detection units in bridge CSV')
    audit['inputs']['bridge_locations_check'] = dict(path=Path(path).name,
        sha256=sha256(path), rows=len(frame))
    points = []
    for _, row in frame.iterrows():
        # Strict positive proof, not the absence of a warning.
        verified = row.get('location_status', '').strip().lower() in (
            'verified_coordinate', 'verified_coordinates', 'verified', 'verified_report_coordinate')
        plotted_flag = row.get('map_plotted', '').strip().lower() in ('true','1','yes')
        if not (verified and plotted_flag):
            continue
        if row.get('crs', '').strip().lower() not in ('epsg:4326','wgs84','wgs 84','ogc:crs84'):
            raise ValueError(f'{row["unit_id"]}: verified coordinate CRS is not WGS84')
        lon, lat = float(row['x']), float(row['y'])
        if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            raise ValueError(f'{row["unit_id"]}: verified point outside current map extent')
        if not row.get('location_source', '').strip() or not row.get('location_basis', '').strip():
            raise ValueError(f'{row["unit_id"]}: verified point lacks provenance')
        points.append(dict(unit_id=row['unit_id'], lon=lon, lat=lat))
    audit['bridges'] = dict(total_units=59, verified_units=len(points),
        unresolved_units=59-len(points), plotted_units=len(points),
        plotted_unique_sites=len(set((p['lon'],p['lat']) for p in points)),
        points_generated_by_interpolation=False)
    return points


def label_text(ax, x, y, label, gid, **kwargs):
    artist = ax.text(x, y, label, color=COLORS['text'], **kwargs)
    artist.set_gid(gid)
    return artist


def add_north_arrow(ax, ext, audit):
    xmin,ymin,xmax,ymax=ext
    width,height=xmax-xmin,ymax-ymin
    anchor=np.array([xmin+width*.944,ymin+height*.837])
    lon,lat=INVERSE.transform(*anchor)
    top=np.array(PROJECT.transform(lon,lat+.03))
    direction=(top-anchor)/np.linalg.norm(top-anchor)
    side=np.array([direction[1],-direction[0]])
    length=height*.080
    tip=anchor+direction*length
    notch=anchor+direction*(length*.36)
    left=anchor-side*(length*.24)
    right=anchor+side*(length*.24)
    outline=Polygon([tip,left,notch,right],closed=True,facecolor='white',
                    edgecolor=COLORS['text'],lw=.8,zorder=30)
    outline.set_gid('true-north-arrow-outline');ax.add_patch(outline)
    half=Polygon([tip,left,notch],closed=True,facecolor=COLORS['text'],
                 edgecolor=COLORS['text'],lw=.2,zorder=31)
    half.set_gid('true-north-arrow-left-fill');ax.add_patch(half)
    label_text(ax,tip[0],tip[1]+height*.013,'N','north-label',
               ha='center',va='bottom',fontsize=11,weight='bold',zorder=32)
    audit['north_arrow']=dict(method='project a geographic meridian at arrow location',
        reference_lon_lat=[lon,lat], bearing_degrees_from_projected_y=float(
            np.degrees(np.arctan2(direction[0],direction[1]))))


def add_scale_bar(ax, ext, audit):
    xmin,ymin,xmax,ymax=ext
    width,height=xmax-xmin,ymax-ymin
    length=10000.0
    left=xmax-width*.046-length
    bottom=ymin+height*.055
    barheight=height*.0075
    for i,color in enumerate(('black','white')):
        rect=Rectangle((left+i*length/2,bottom),length/2,barheight,
                       facecolor=color,edgecolor='black',lw=.55,zorder=40)
        rect.set_gid(f'projection-scale-{i}');ax.add_patch(rect)
    for km in (0,5,10):
        label_text(ax,left+km*1000,bottom+barheight+height*.011,str(km),
            f'scale-label-{km}',ha='center',va='bottom',fontsize=7.4,zorder=41)
    label_text(ax,left+length+width*.015,bottom+barheight/2,'km','scale-unit',
               fontsize=7.4,ha='left',va='center',zorder=41)
    lon0,lat0=INVERSE.transform(left,bottom+barheight/2)
    lon1,lat1=INVERSE.transform(left+length,bottom+barheight/2)
    _,_,distance=GEOD.inv(lon0,lat0,lon1,lat1)
    audit['scale_bar']=dict(crs=CRS,projection_length_m=length,
        geodesic_endpoint_distance_m=distance,
        relative_error=abs(distance-length)/length,
        endpoints_wgs84=[[lon0,lat0],[lon1,lat1]])
    if abs(distance-length)/length > .005:
        raise ValueError('Scale check error exceeds 0.5%')


def add_legend(ax, has_points, has_s1, has_corridor):
    # Preserve the requested three symbols; mark their absence explicitly.
    handles=[Line2D([],[],color=COLORS['bridges'],marker='o',lw=0,markersize=5.5),
             Line2D([],[],color=COLORS['s1'],lw=2.4),
             Line2D([],[],color=COLORS['corridor'],lw=1.1,ls=(0,(5,3)))]
    labels=['Study bridge locations','S1 Yongtaiwen Expressway','Study corridor']
    legend=ax.legend(handles,labels,loc='lower left',bbox_to_anchor=(.023,.066),
        borderaxespad=0,fontsize=7.7,handlelength=2.3,handletextpad=1.1,
        borderpad=1.05,labelspacing=.92,frameon=True,facecolor='white',
        edgecolor='#737973',framealpha=.97,fancybox=False,title='Legend',title_fontsize=9)
    legend._legend_box.align='left'
    legend.set_gid('map-legend-conventions')
    legend.set_zorder(80)
    # Symbols are retained as requested, but do not assert feature availability.
    if not all((has_points,has_s1,has_corridor)):
        missing=[]
        if not has_points: missing.append('bridge locations')
        if not has_s1: missing.append('S1 study alignment')
        if not has_corridor: missing.append('study corridor')
        note='Pending verification — not mapped:\n'+', '.join(missing)
        label_text(ax,.027,.025,note,'unverified-layer-note',transform=ax.transAxes,
            fontsize=6.3,ha='left',va='bottom',linespacing=1.35,zorder=100,
            bbox=dict(boxstyle='square,pad=.35',fc='white',ec='none',alpha=.96))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--geodata-dir',type=Path,default=HERE/'geodata')
    parser.add_argument('--output-dir',type=Path,default=HERE)
    parser.add_argument('--bridge-csv',type=Path,default=HERE/'bridge_locations_check.csv')
    args=parser.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/'validation').mkdir(exist_ok=True)
    audit=dict(version=1,projection=CRS,bbox_lon_lat=list(BBOX),inputs={},layers={})
    font_names={f.name for f in font_manager.fontManager.ttflist}
    font=next((f for f in ('Nimbus Roman','TeX Gyre Termes','Liberation Serif','DejaVu Serif') if f in font_names),'DejaVu Serif')
    plt.rcParams.update({'font.family':font,'font.size':8,'svg.fonttype':'none',
        'pdf.fonttype':42,'ps.fonttype':42,'axes.unicode_minus':False,
        'savefig.facecolor':'white','path.simplify':False,'svg.hashsalt':'ningbo-gis-final'})
    audit['font_family']=font
    bbox_geom=box(*BBOX)
    extent_polygon=transform(PROJECT.transform,bbox_geom)
    ext=extent_polygon.bounds
    xmin,ymin,xmax,ymax=ext
    # Single panel in the original 4:3 composition; never a locator-panel redesign.
    fig=plt.figure(figsize=(20/2.54,15/2.54),facecolor='white')
    ax=fig.add_axes([.006,.013,.988,.974])
    ax.set_xlim(xmin,xmax);ax.set_ylim(ymin,ymax);ax.set_aspect('equal')
    ax.set_facecolor('white')
    ax.set_xticks([]);ax.set_yticks([])
    for spine in ax.spines.values():spine.set_visible(False)
    definitions=[('ocean','ningbo_ne_10m_ocean_clipped.geojson',COLORS['ocean'],'none',0,0),
      ('land','ningbo_ne_10m_land_clipped.geojson',COLORS['land'],'none',0,1),
      ('lakes','ningbo_ne_10m_lakes_clipped.geojson',COLORS['water'],'none',0,2),
      ('rivers','ningbo_ne_10m_rivers_lake_centerlines_clipped.geojson','none',COLORS['water'],.8,3),
      ('coastline','ningbo_ne_10m_coastline_clipped.geojson','none',COLORS['coastline'],.35,4)]
    for key,name,face,edge,lw,z in definitions:
        features=load_geojson(args.geodata_dir/name,audit,key,required=key in ('ocean','land','coastline'))
        audit['layers'][key]=draw_geometries(ax,features,key,face,edge,lw,z,clip_geom=bbox_geom)
    # Use real municipal GIS if provided, never synthesised streets.
    city_path=args.geodata_dir/'ningbo_city_roads.geojson'
    if city_path.exists():
        features=load_geojson(city_path,audit,'city_roads')
        audit['layers']['city_roads']=draw_geometries(ax,features,'city-roads',
            edgecolor=COLORS['roads'],linewidth=.24,zorder=5,clip_geom=bbox_geom)
    else:
        features=load_geojson(args.geodata_dir/'ningbo_ne_10m_roads_clipped.geojson',audit,'generalized_roads')
        audit['layers']['generalized_roads']=draw_geometries(ax,features,'generalized-road',
            edgecolor=COLORS['major_roads'],linewidth=.7,zorder=6,clip_geom=bbox_geom)
    # Optional audited water polygons/lines are drawn only as supplied geometries.
    for key,name,face,edge,lw,z in (
        ('local_water_polygons','ningbo_local_water_polygons.geojson',COLORS['water'],'none',0,7),
        ('local_water_lines','ningbo_local_water_lines.geojson','none',COLORS['water'],.6,8)):
        features=load_geojson(args.geodata_dir/name,audit,key)
        audit['layers'][key]=draw_geometries(ax,features,key,face,edge,lw,z,clip_geom=bbox_geom)
    s1_features=[]
    s1_path=args.geodata_dir/'verified_s1_route.geojson'
    if s1_path.exists():
        raw=load_geojson(s1_path,audit,'verified_s1_route')
        # Every route feature must carry explicit positive verification metadata.
        if any(f.get('properties',{}).get('verification_status') != 'verified' for f in raw):
            raise ValueError('S1 features must explicitly state verification_status=verified')
        s1_features=raw
    if s1_features:
        audit['layers']['s1']=draw_geometries(ax,s1_features,'verified-s1',
            edgecolor=COLORS['s1'],linewidth=2.7,zorder=13,clip_geom=bbox_geom)
        # Only the *verified study section* may generate an illustrative corridor.
        if all(f.get('properties',{}).get('study_section_verified') is True for f in s1_features):
            merged=unary_union([transform(PROJECT.transform,shape(f['geometry'])) for f in s1_features])
            corridor=merged.buffer(650,cap_style='round',join_style='round')
            for i,part in enumerate(iter_parts(corridor)):
                if part.geom_type=='Polygon':
                    patch=PathPatch(polygon_path(part),fc='none',ec=COLORS['corridor'],
                                    lw=.95,ls=(0,(5,3)),zorder=12)
                    patch.set_gid(f'symbolic-study-corridor-{i}');ax.add_patch(patch)
            audit['layers']['study_corridor']=dict(buffer_m=650,
                meaning='cartographic emphasis only; not an administrative/sampling boundary')
        # Label only names provided in verified line metadata, no invented endpoints.
        label_geom=unary_union([transform(PROJECT.transform,shape(f['geometry'])) for f in s1_features])
        if label_geom.geom_type=='MultiLineString':
            label_geom=max(label_geom.geoms,key=lambda g:g.length)
        if label_geom.geom_type=='LineString':
            point=label_geom.interpolate(.45,normalized=True)
            label_text(ax,point.x,point.y+(ymax-ymin)*.055,'S1 Yongtaiwen Expressway',
                'verified-s1-name',fontsize=8.2,ha='center',va='bottom',zorder=25,
                bbox=dict(fc='white',ec='#777',lw=.4,pad=3))
    else:
        audit['layers']['s1']=0
    points=load_verified_bridge_points(args.bridge_csv,audit)
    if points:
        xs,ys=PROJECT.transform([p['lon'] for p in points],[p['lat'] for p in points])
        marker=ax.scatter(xs,ys,s=28,c=COLORS['bridges'],edgecolors='white',lw=.65,zorder=20)
        marker.set_gid('verified-bridge-locations')
    # City label is a populated-place point, not an invented bridge or boundary.
    city_features=load_geojson(args.geodata_dir/'ningbo_city_reference_point_wgs84.geojson',audit,'ningbo_reference',required=True)
    for feature in city_features:
        if feature.get('properties',{}).get('NAME')=='Ningbo':
            x,y=PROJECT.transform(*feature['geometry']['coordinates'])
            label_text(ax,x,y,'Ningbo','city-label-ningbo',fontsize=18,weight='bold',
                       ha='center',va='center',zorder=15,
                       bbox=dict(fc='white',ec='none',alpha=.83,pad=2))
    # Optional district labels: source-coordinates, names and label validity audited upstream.
    district_features=load_geojson(args.geodata_dir/'verified_district_label_points.geojson',audit,'district_labels')
    for feature in district_features:
        props=feature.get('properties',{})
        if props.get('verification_status')!='verified':
            raise ValueError('District label requires verified source metadata')
        text=props.get('label_en','')
        if not text or feature.get('geometry',{}).get('type')!='Point':continue
        x,y=PROJECT.transform(*feature['geometry']['coordinates'])
        label_text(ax,x,y,text,'district-'+re.sub(r'[^a-z]+','-',text.lower()),
            fontsize=8.7,ha='center',va='center',zorder=15,
            bbox=dict(fc='white',ec='none',alpha=.75,pad=1.5))
    add_north_arrow(ax,ext,audit)
    add_scale_bar(ax,ext,audit)
    add_legend(ax,bool(points),bool(s1_features),bool(audit['layers'].get('study_corridor')))
    audit['extent_projected_m']=list(ext)
    audit['unverified_bridge_markers_drawn']=False
    audit['ai_reference_traced']=False
    audit['geographic_names_from_unverified_reference_used']=False
    audit['canvas_cm']=[20,15]
    stem=args.output_dir/'Fig1_StudyArea_Final'
    fig.savefig(stem.with_suffix('.svg'),format='svg',metadata={'Creator':'plot_study_area.py; real GIS only','Date':None})
    fig.savefig(stem.with_suffix('.pdf'),format='pdf',metadata={'Title':'Ningbo study area — verified GIS and explicit omissions',
        'Author':'','Creator':'plot_study_area.py','CreationDate':None,'ModDate':None})
    fig.savefig(stem.with_suffix('.png'),format='png',dpi=600,metadata={'Software':'plot_study_area.py'})
    plt.close(fig)
    svg=ET.parse(stem.with_suffix('.svg')).getroot()
    elements=list(svg.iter())
    audit['svg']=dict(images=sum(e.tag.split('}')[-1]=='image' for e in elements),
        paths=sum(e.tag.split('}')[-1]=='path' for e in elements),
        editable_texts=sum(e.tag.split('}')[-1]=='text' for e in elements),
        embedded_raster_data='data:image' in stem.with_suffix('.svg').read_text())
    if audit['svg']['images'] or audit['svg']['embedded_raster_data'] or not audit['svg']['editable_texts']:
        raise AssertionError('SVG is not fully vector geometry plus editable text')
    try:
        import fitz
        document=fitz.open(stem.with_suffix('.pdf'))
        audit['pdf']=dict(pages=len(document),embedded_images=sum(len(p.get_images()) for p in document),
                          vector_drawing_objects=sum(len(p.get_drawings()) for p in document))
        document.close()
        if audit['pdf']['embedded_images']:
            raise AssertionError('PDF unexpectedly contains raster images')
    except ImportError:
        audit['pdf']={'verification':'PyMuPDF unavailable; run independent PDF audit'}
    try:
        from PIL import Image
        with Image.open(stem.with_suffix('.png')) as image:
            audit['png']=dict(pixels=list(image.size),dpi=list(image.info.get('dpi',())))
    except ImportError:
        pass
    for suffix in ('.svg','.pdf','.png'):
        audit.setdefault('outputs',{})[stem.with_suffix(suffix).name]=dict(
            bytes=stem.with_suffix(suffix).stat().st_size,sha256=sha256(stem.with_suffix(suffix)))
    (args.output_dir/'validation'/'plot_audit.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(output_directory=str(args.output_dir.resolve()),svg=audit['svg'],
                         bridges=audit['bridges'],scale_bar=audit['scale_bar']),ensure_ascii=False))

if __name__=='__main__':
    main()
