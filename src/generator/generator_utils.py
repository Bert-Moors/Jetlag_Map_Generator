import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
import shapely
import simplekml

from typing import List

#--------------Functions--------------
# Read data into frame and add the columns required for de-duplication
def read_station_frame(file_path:str, station_type:str) -> gpd.GeoDataFrame:
    frame = gpd.read_file(file_path, encoding="utf-8")
    frame.set_crs(4326, inplace=True)
    frame["type"] = station_type
    frame["latitude"] = frame["geometry"].y
    frame["longitude"] = frame["geometry"].x
    return frame

# Remove points that are too close together based on given distance in km
def dedup_frame(df:gpd.GeoDataFrame, distance:float):
    # Map priority: Train > Subway > Tram > Bus
    priority_order = {"train": 4, "subway": 3, "tram": 2, "bus": 1}
    df["priority"] = df["type"].map(priority_order).fillna(0)
    df.sort_values(by="priority", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)

    coords_rad = np.radians(df[["latitude", "longitude"]].astype(float).values)
    tree = cKDTree(coords_rad)
    radius_rad = distance / 6371  # Earth's radius in km

    pairs = tree.query_pairs(radius_rad)
    to_remove = set()
    for i, j in pairs:
        if df.loc[i, "priority"] >= df.loc[j, "priority"]:
            to_remove.add(j)
        else:
            to_remove.add(i)

    dedup_df = df.drop(index=to_remove).drop(columns="priority")
    return dedup_df
# create hiding zones for station frame
def create_hiding_zones(df: gpd.GeoDataFrame, distance: int) -> gpd.GeoDataFrame:
    frames = []
    # split operation based on calculated epsg for the individual points
    for epsg in df["epsg"].unique():
        subframe = df["epsg" == epsg]
        # convert dataframe to chosen crs
        subframe.to_crs(epsg, inplace=True)
        # calculate the zone polygons
        circles = subframe.buffer(distance, 12).boundary
        circles = circles.apply(lambda x: shapely.MultiLineString([x.coords, x.coords[-2::]]))
        # set the calculated polygons as the geometry of the dataframe
        subframe["geometry"] = circles
        # convert dataframe back to degree based coords
        subframe.to_crs(4326, inplace=True)
        frames.append(subframe)
    combined = pd.concat(frames)
    return gpd.GeoDataFrame(combined, geometry=combined["geometry"])

def output_csv(frame:gpd.GeoDataFrame, filepath: str, columns: List[str]) -> None:
    frame["WKT"] = frame["geometry"].to_wkt(rounding_precision=7, trim=False)
    columns.insert(0, "WKT")
    frame.to_csv(filepath, columns=columns, index=False, quotechar='"')

def output_kml(frame:gpd.GeoDataFrame, filepath: str, columns: List[str]) -> None:
    # setup kml file
    kml = simplekml.Kml()
    # loop over all geoms in frame
    for _, row in frame:
        geom = row["geometry"]
