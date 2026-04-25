import os.path

from . import util
from .overpass import overpass_query, overpass_query_with_cache

import geopandas as gpd
import json
import pandas as pd
import shapely
import simplekml
from typing import Dict

class Generator():
    def __init__(self, settings: str, output_path: str):
        if settings is None or output_path is None:
            raise Exception("settings or output path can not be none")
        with open(settings, encoding="utf-8") as file:
            self._settings = json.load(file)
        self._output_path = output_path
        self._kml = simplekml.Kml()

    def generate(self):
        for folder in self._settings["folders"]:
            kml_folder = self._kml.newfolder(name=folder["name"])
            frames = {}
            for data in folder["data"]:
                json_data = overpass_query_with_cache(data["query"])
                frame = self.__parse_json(json_data, data["geom_type"])
                frame["type"] = data["type"]
                frames[data["type"]] = frame
            self.__add_to_kml(frames, kml_folder)
        if not os.path.isdir(self._output_path):
            os.makedirs(self._output_path, exist_ok=False)
        self._kml.save(f"{self._output_path}/{self._settings["location"]}.kml")

    def __add_to_kml(self, frames: Dict[str, gpd.GeoDataFrame], folder: simplekml.Folder) -> None:
        for type in frames.keys():
            fol = folder.newfolder(name=type)
            for _, row in frames[type].iterrows():
                match row["geometry"].geom_type:
                    case "Point":
                        coords = shapely.get_coordinates(row["geometry"])
                        fol.newpoint(name=row["name"],coords=coords)
                    case "MultiLineString":
                        lines = row["geometry"].geoms
                        multiLine = fol.newmultigeometry(name=row["name"])
                        for line in lines:
                            multiLine.newlinestring(coords=shapely.get_coordinates(line))
                    case "MultiPolygon":
                        shapes = row["geometry"].geoms
                        multipolygon = fol.newmultigeometry(name=row["name"])
                        for shape in shapes:
                            multipolygon.newpolygon(name=row["name"], outerboundaryis=shapely.get_coordinates(shape))

    # ----------------------------------------------Parsing Functions--------------------------------------------------
    def __parse_json(self, json_data: Dict, geom_type: str) -> gpd.GeoDataFrame:
        frame = gpd.GeoDataFrame()
        # change parsing method based on
        match geom_type:
            case "border":
                frame = self.__parse_border(json_data)
            case "points":
                frame = self.__parse_points(json_data)
            case "lines":
                pass
            case "routes":
                frame = self.__parse_routes(json_data)
            case "polygons":
                frame = self.__parse_polygons(json_data)
        # if frame did not get overwritten or empty geom type is not supported
        if frame.empty:
            raise Exception("geom type not supported")
        return frame

    def __parse_border(self, json_response: Dict) -> gpd.GeoDataFrame:
        p_frame = pd.DataFrame(columns=["geometry", "name"])
        if json_response["elements"]:
            for element in json_response["elements"]:
                lines = []
                for member in element["members"]:
                    if member["type"] == "way":
                        points = []
                        for point in member["geometry"]:
                            points.append([point["lon"], point["lat"]])
                        lines.append(points)
                geom = shapely.MultiLineString(lines)
                p_frame.loc[len(p_frame)] = {"name": "border", "geometry": geom}
        else:
            raise Exception("Response is empty")
        return gpd.GeoDataFrame(p_frame)

    def __parse_points(self, json_response: Dict) -> gpd.GeoDataFrame:
        p_frame = pd.DataFrame(columns=["geometry", "name"])
        if json_response["elements"]:
            for element in json_response["elements"]:
                match element["type"]:
                    case "node":
                        geom = shapely.Point(element["lon"], element["lat"])
                    case "way":
                        geom = shapely.Point(element["center"]["lon"], element["center"]["lat"])
                p_frame.loc[len(p_frame)] = {"name": element["tags"]["name"], "geometry": geom}
        else:
            raise Exception("Response is empty")
        return gpd.GeoDataFrame(p_frame)

    def __parse_polygons(self, json_response: Dict) -> gpd.GeoDataFrame:
        p_frame = pd.DataFrame(columns=["geometry", "name"])
        if json_response["elements"]:
            for element in json_response["elements"]:
                lines = []
                for member in element["members"]:
                    if member["type"] == "way":
                        points = []
                        for point in member["geometry"]:
                            points.append([point["lon"], point["lat"]])
                        lines.append(points)
                polygons = []
                shapes = util.order_lines(lines)
                for poly in shapes:
                    polygons.append(shapely.geometry.Polygon(poly))
                geom = shapely.geometry.MultiPolygon(polygons)
                p_frame.loc[len(p_frame)] = {"name": element["tags"]["name"], "geometry": geom}
        else:
            raise Exception("Response is empty")
        return gpd.GeoDataFrame(p_frame)

    def __parse_routes(self, json_response: Dict) -> gpd.GeoDataFrame:
        p_frame = pd.DataFrame(columns=["geometry", "name"])
        if json_response["elements"]:
            for element in json_response["elements"]:
                lines = []
                for member in element["members"]:
                    if member["type"] == "way" and member["role"] != "platform":
                        points = []
                        for point in member["geometry"]:
                            points.append([point["lon"], point["lat"]])
                        lines.append(points)
                geom = shapely.MultiLineString(lines)
                p_frame.loc[len(p_frame)] = {"name": element["tags"]["name"], "geometry": geom}
        else:
            raise Exception("Response is empty")
        return gpd.GeoDataFrame(p_frame)