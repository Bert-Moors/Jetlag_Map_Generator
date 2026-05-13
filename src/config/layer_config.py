from typing import Dict

import geopandas
import pandas
import pandas as pd
import shapely

from config import util
from overpass.overpass import overpass_query_with_cache


class OverpassLoader:
    def __init__(self, query, geo_type):
        self.query = query
        self.geo_type = geo_type

    def load(self):
        data = overpass_query_with_cache(self.query)
        return self.__parse_json(data, self.geo_type)

    # ----------------------------------------------Parsing Functions--------------------------------------------------
    def __parse_json(self, json_data: Dict, geom_type: str) -> geopandas.GeoDataFrame:
        frame = geopandas.GeoDataFrame()
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

    def __parse_border(self, json_response: Dict) -> geopandas.GeoDataFrame:
        p_frame = pandas.DataFrame(columns=["geometry", "name"])
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
        return geopandas.GeoDataFrame(p_frame)

    def __parse_points(self, json_response: Dict) -> geopandas.GeoDataFrame:
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
        return geopandas.GeoDataFrame(p_frame)

    def __parse_polygons(self, json_response: Dict) -> geopandas.GeoDataFrame:
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
        return geopandas.GeoDataFrame(p_frame)

    def __parse_routes(self, json_response: Dict) -> geopandas.GeoDataFrame:
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
        return geopandas.GeoDataFrame(p_frame)


class GeoJsonLoader:
    def __init__(self, file_name=None):
        if file_name is not None:
            self._contents = geopandas.read_file(file_name)
        else:
            raise Exception("file_name cannot be None")

    def load(self):
        return self._contents