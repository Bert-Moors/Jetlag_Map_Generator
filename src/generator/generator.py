import os.path

from processors.processor_index import get_processor
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
                if data.get("file"):
                    frame = gpd.read_file(data["file"])
                elif data.get("query"):
                    json_data = overpass_query_with_cache(data["query"])
                    frame = self.__parse_json(json_data, data["geom_type"])
                else:
                    raise Exception("Neither query nor file found in when loading "+folder["name"])


                # Loop through all the processors that exist on this data layer, and run them on the frame.
                for proc_data in data.get("processors", []):
                    if isinstance(proc_data, dict):
                        # Fetch the class
                        processor_class = get_processor(proc_data.get("name"))
                        if processor_class is None:
                            print("Invalid processor class", proc_data.get("name"))
                            continue
                        processor = processor_class(proc_data)
                        frame = processor.process(frame)

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
                        ln.extendeddata.newdata("type", type)

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
                    case _:
                        print(row["geometry"].geom_type, "Skipped due to being unsupported geom type")

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
                frame = self.__parse_lines(json_data)
            case "routes":
                frame = self.__parse_routes(json_data)
            case "polygons":
                frame = self.__parse_polygons(json_data)
        # if frame did not get overwritten or empty geom type is not supported
        if frame.empty:
            raise Exception("geom type not supported")
        return frame

    # This parser may not be generic enough
    def __parse_lines(self, json_response: Dict) -> gpd.GeoDataFrame:
        p_frame = pd.DataFrame(columns=["geometry", "name", "color"])
        for line in json_response.get("elements"):
            if not line.get("type") == "way":
                if line.get("members"):
                    row = []
                    for member in line["members"]:
                        if not member.get("type") == "way":
                            continue
                        row.append(shapely.LineString(map(lambda x: [x["lon"], x["lat"]],member["geometry"])))
                    geom = shapely.MultiLineString(row)
                    p_frame.loc[len(p_frame)] = {"name": line.get("tags").get("name"), "geometry": geom}
                continue
            geom = shapely.LineString(line["geometry"])
            p_frame.loc[len(p_frame)]={"name":line.get("tags").get("name"), "geometry":geom}
        return gpd.GeoDataFrame(p_frame)

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
                        if element.get("center"):
                            geom = shapely.Point(element["center"]["lon"], element["center"]["lat"])
                        elif element.get("bounds"):
                            lat = (element["bounds"]["maxlat"] + element["bounds"]["minlat"]) / 2
                            lon = (element["bounds"]["maxlon"] + element["bounds"]["minlon"]) / 2
                            geom = shapely.Point(lon, lat)
                        else:
                            raise Exception("Point has no valid data")
                    case "relation":
                        if element.get("center"):
                            geom = shapely.Point(element["center"]["lon"], element["center"]["lat"])
                        elif element.get("bounds"):
                            lat = (element["bounds"]["maxlat"] + element["bounds"]["minlat"]) / 2
                            lon = (element["bounds"]["maxlon"] + element["bounds"]["minlon"]) / 2
                            geom = shapely.Point(lon, lat)
                        else:
                            raise Exception("Point has no valid data")
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