import os.path
import generator.config as genconfig
import geopandas as gpd
import shapely
import simplekml
from typing import Dict

class Generator:
    def __init__(self, config_file: str, output_path: str):
        self._config = genconfig.load_config(config_file)
        self._output_path = output_path
        self._kml = simplekml.Kml()

    def generate(self):
        for folder in self._config.folders:
            kml_folder = self._kml.newfolder(name=folder.name)
            frames = {}
            for data in folder.datasource:
                frame = data.loader.load()

                for processor in data.processors:
                    frame = processor.process(frame)

                frame["type"] = data.typ
                frames[data.typ] = frame
            self.__add_to_kml(frames, kml_folder)
        if not os.path.isdir(self._output_path):
            os.makedirs(self._output_path, exist_ok=False)
        self._kml.save(f"{self._output_path}/{self._config.location}.kml")

    def __add_to_kml(self, frames: Dict[str, gpd.GeoDataFrame], folder: simplekml.Folder) -> None:
        for type in frames.keys():
            fol = folder.newfolder(name=type)
            for _, row in frames[type].iterrows():
                match row["geometry"].geom_type:
                    case "Point":
                        coords = shapely.get_coordinates(row["geometry"])
                        pt = fol.newpoint(name=row["name"],coords=coords)
                        pt.extendeddata.newdata("type", type)
                    case "Polygon":
                        shapes = row["geometry"]
                        multipolygon = fol.newmultigeometry(name=row["name"])
                        multipolygon.extendeddata.newdata("type", type)
                        multipolygon.newpolygon(name=row["name"], outerboundaryis=shapely.get_coordinates(shapes))
                    case "MultiLineString":
                        lines = row["geometry"].geoms
                        multiLine = fol.newmultigeometry(name=row["name"])
                        multiLine.extendeddata.newdata("type", type)
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
                        multipolygon.extendeddata.newdata("type", type)
                        for shape in shapes:
                            multipolygon.newpolygon(name=row["name"], outerboundaryis=shapely.get_coordinates(shape))
