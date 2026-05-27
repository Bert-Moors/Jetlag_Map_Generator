import os.path

import pandas as pd

import generator.config as genconfig
import geopandas as gpd
import shapely
import simplekml
from typing import Dict

from generator.exporters.exporters import Exporter


class Generator:
    def __init__(self, config_file: str, output_path: str):
        self._config = genconfig.load_config(config_file)
        self._output_path = output_path
        self._gathered_data = {}
        self._kml = simplekml.Kml()

    def generate(self):
        self.__gather_data()
        self.__process_data()
        self.__export_data()

    def __gather_data(self):
        for layer in self._config.layers:
            self._gathered_data[layer.name] = {}
            for data in layer.datasources:
                frame = data.loader.load()

                frame["type"] = data.name_type
                self._gathered_data[layer.name][data.name_type] = frame

    def __process_data(self):
        for layer in self._config.layers:
            for data in layer.datasources:
                for processor in data.processors:
                    self._gathered_data[layer.name][data.name_type] = processor.process(self._gathered_data[layer.name][data.name_type])
            if layer.processors:
                layer_frame = gpd.GeoDataFrame(pd.concat(self._gathered_data[layer.name].values()))
                for processor in layer.processors:
                    layer_frame = processor.process(layer_frame)
                split_frames = {}
                for type in layer_frame["type"].unique():
                    split_frames[type] = layer_frame[layer_frame["type"] == type]
                self._gathered_data[layer.name] = split_frames

    def __export_data(self):
        if not os.path.isdir(self._output_path):
            os.makedirs(self._output_path, exist_ok=False)
        for exporter in self._config.exporters:
            exporter.export(self._gathered_data, f"{self._output_path}/{self._config.name}")

    def __add_to_kml(self, frames: Dict[str, gpd.GeoDataFrame], folder) -> None:
        for layer_name in frames.keys():
            fol = folder.newfolder(name=layer_name)
            for _, row in frames[layer_name].iterrows():
                match row["geometry"].geom_type:
                    case "Point":
                        coords = shapely.get_coordinates(row["geometry"])
                        pt = fol.newpoint(name=row["name"],coords=coords)
                        pt.extendeddata.newdata("type", row["type"])
                    case "Polygon":
                        shapes = row["geometry"]
                        multipolygon = fol.newmultigeometry(name=row["name"])
                        multipolygon.extendeddata.newdata("type", row["type"])
                        multipolygon.newpolygon(name=row["name"], outerboundaryis=shapely.get_coordinates(shapes))
                    case "MultiLineString":
                        lines = row["geometry"].geoms
                        multiLine = fol.newmultigeometry(name=row["name"])
                        multiLine.extendeddata.newdata("type", row["type"])
                        for line in lines:
                            multiLine.newlinestring(coords=shapely.get_coordinates(line))
                    case "LineString":
                        if not row.get("name"):
                            continue
                        line = row["geometry"]
                        ln = fol.newlinestring(name=row["name"], coords=shapely.get_coordinates(line))
                        stle = simplekml.Style()
                        stle.linestyle.width=3
                        stle.linestyle.color=row.get("color")
                        self._kml.styles.append(stle)
                        ln.style=stle
                    case "MultiPolygon":
                        shapes = row["geometry"].geoms
                        multipolygon = fol.newmultigeometry(name=row["name"])
                        multipolygon.extendeddata.newdata("type", row["type"])
                        for shape in shapes:
                            multipolygon.newpolygon(name=row["name"], outerboundaryis=shapely.get_coordinates(shape))
