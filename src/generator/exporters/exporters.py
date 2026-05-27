import geopandas as gpd
import pandas as pd
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