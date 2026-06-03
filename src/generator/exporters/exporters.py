import geopandas as gpd
import pandas as pd
from geopandas.geodataframe import GeoDataFrame
from numpy import copysign, floor
from pandas import concat

from shapely import MultiLineString

from .exporter_util import add_to_kml
import simplekml
from typing import Protocol


class Exporter(Protocol):
    def export(self):
        pass

class GoogleMyMapsKmlExporter:
    def __init__(self):
        self._kml = simplekml.Kml()

    def export(self, data: dict, output_path):
        for layer_name in data.keys():
            data[layer_name] = gpd.GeoDataFrame(pd.concat(data[layer_name].values()))

        add_to_kml(data, self._kml)

        self._kml.save(f"{output_path} GMM.kml")

class FullKmlExporter:
    def __init__(self):
        self._kml = simplekml.Kml()

    def export(self, data: dict, output_path):
        for layer_name in data.keys():
            folder = self._kml.newfolder(name=layer_name)
            add_to_kml(data[layer_name], folder)
        self._kml.save(f"{output_path} FULL.kml")

class HidingZoneExporter:
    def __init__(self):
        self._kml = simplekml.Kml()

    @staticmethod
    def calculate_epsg(row):
        point = row["geometry"]
        return int(32700 - (copysign(1, point.y) + 1) / 2 * 100 + (floor((180 + point.x) / 6) + 1))

    @staticmethod
    def remove_without_size( df):
        new_df = df.copy()
        new_df.reset_index(drop=True,inplace=True)
        for x in new_df.iterrows():
            if not x[1]["hiding_size"]:
                new_df.drop(x[0],inplace=True)
        return new_df

    def export(self, data: dict, output_path):
        layer = self._kml.newfolder(name="Hiding Zones")
        partials = []

        for layer_name in data.keys():
            for ln in data[layer_name].keys():
                    row = data[layer_name][ln]
                    if 'hiding_size' not in row.columns:
                        continue
                    rw = self.remove_without_size(row)

                    rw.set_crs(4326, inplace=True)
                    rw["epsg"] = rw.apply(HidingZoneExporter.calculate_epsg, axis=1)

                    for epsg in rw["epsg"].unique():
                        partial_df = rw[rw["epsg"] == epsg]
                        partial_df.to_crs(epsg, inplace=True)

                        circles = partial_df.buffer(partial_df["hiding_size"], 12).boundary
                        circles = circles.apply(lambda x: MultiLineString([x.coords, x.coords[-2::]]))
                        partial_df['geometry'] = circles
                        partial_df.to_crs(4326, inplace=True)
                        partials.append(partial_df)

        dat = GeoDataFrame(concat(partials), crs="EPSG:4326")
        add_to_kml({'hiding_zones':dat}, layer)
        self._kml.save(f"{output_path} HZ.kml")