import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import geopandas as gpd
import shapely
import contextily as ctx
import os
import seaborn as sns
import requests
sns.set(style='white')

def postcodes_data(postcodes):
    """
    Retrieve data for a list of postcodes from postcodes.io

    Returns a tuple (good_results, bad_postcodes).
    """

    postcodes = np.sort(np.unique(postcodes))

    url = "https://api.postcodes.io/postcodes"
    postcodes = {"postcodes": postcodes}
    r = requests.post(url, data = postcodes)
    if r.status_code != 200:
        raise RuntimeError("Error making request {}".format(r.status_code))
    query_results = r.json()['result']
    good_results = [el['result'] for el in query_results
                    if el['result'] is not None]
    good_results = pd.DataFrame(good_results).set_index('postcode')
    bad_results = [el['query'] for el in query_results
                   if el['result'] is None]
    return good_results, bad_results

def long_lat_to_spherical_mercator(longs, lats):
    """
    Convert sequences of longitudes and latitudes into spherical Mercator
    coordinates.
    """
    data = [shapely.geometry.Point(lng, lat) for lng, lat in zip(longs, lats)]
    gdf = gpd.GeoSeries(data, crs="EPSG:4326")
    gdf = gdf.to_crs(epsg=3857)
    return gdf.geometry.x.values, gdf.geometry.y.values

def add_basemap(ax, zoom, url='http://tile.stamen.com/terrain/tileZ/tileX/tileY.png'):
    xmin, xmax, ymin, ymax = ax.axis()
    basemap, extent = ctx.bounds2img(xmin, ymin, xmax, ymax, zoom=zoom, url=url)
    ax.imshow(basemap, extent=extent, interpolation='bilinear')
    # restore original x/y limits
    ax.axis((xmin, xmax, ymin, ymax))

def plot_locations(longs, lats, jitter=None, zoom=14, url=ctx.sources.OSM_A,
                   save_file=None, wait=0.01, retries=10):
    x, y = long_lat_to_spherical_mercator(longs, lats)
    if jitter is not None:
        x += np.random.normal(scale=jitter, size=len(x))
        y += np.random.normal(scale=jitter, size=len(y))
    f, ax = plt.subplots(1, 1, figsize=(24, 24))
    ax.scatter(x, y, s=50, c='r', edgecolors='0.25')
    add_basemap(ax, zoom, ctx.sources.OSM_A)
    sns.despine(bottom=True, left=True)
    ax.xaxis.set_major_formatter(ticker.NullFormatter())
    ax.yaxis.set_major_formatter(ticker.NullFormatter())
    if save_file is not None:
        f.savefig(save_file, dpi=300, bbox_inches='tight')
    return f

def distance_between(loc, others_lng, other_lat):
    """
    Assumes loc is a (longitude, latitude) tuple. Others is
    assumed to be a list of such tuples.
    """
    loc = gpd.GeoSeries([shapely.geometry.Point(*loc)], crs="EPSG:4326").to_crs(epsg=7405)
    data = [shapely.geometry.Point(lng, lat) for (lng, lat) in zip(others_lng, other_lat)]
    others = gpd.GeoSeries(data, crs="EPSG:4326").to_crs(epsg=7405)
    return others.distance(loc.iloc[0]).values

def distance_between_sr(loc, others):
    def metric(x1, x2):
        r = 6371*1000
        cos_lat_0_2 = np.cos(np.radians(51.63))**2
        x1, x2 = np.radians(x1), np.radians(x2)
        return r * np.sqrt((x2[1]-x1[1])**2 +
                           cos_lat_0_2 * (x2[0] - x1[0])**2)
    return [metric(loc, other) for other in others]
