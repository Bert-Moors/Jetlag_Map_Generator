from typing import Dict
import geopandas as gpd
import pandas as pd
import shapely
import simplekml


def add_to_kml(frames: Dict[str, gpd.GeoDataFrame], folder) -> None:
    for layer_name in frames.keys():
        fol = folder.newfolder(name=layer_name)
        for _, row in frames[layer_name].iterrows():
            match row["geometry"].geom_type:
                case "Point":
                    coords = shapely.get_coordinates(row["geometry"])
                    pt = fol.newpoint(name=row["name"], coords=coords)
                    pt.extendeddata.newdata("type", row["type"])
                    _set_description(pt, row)
                case "Polygon":
                    shapes = row["geometry"]
                    multipolygon = fol.newmultigeometry(name=row["name"])
                    multipolygon.extendeddata.newdata("type", row["type"])
                    _set_description(multipolygon, row)
                    multipolygon.newpolygon(name=row["name"], outerboundaryis=shapely.get_coordinates(shapes))
                case "MultiLineString":
                    lines = row["geometry"].geoms
                    multiLine = fol.newmultigeometry(name=row["name"])
                    multiLine.extendeddata.newdata("type", row["type"])
                    _set_description(multiLine, row)
                    for line in lines:
                        multiLine.newlinestring(coords=shapely.get_coordinates(line))
                case "LineString":
                    if not row.get("name"):
                        continue
                    line = row["geometry"]
                    ln = fol.newlinestring(name=row["name"], coords=shapely.get_coordinates(line))
                    _set_description(ln, row)
                    style = simplekml.Style()
                    style.linestyle.width = 3
                    style.linestyle.color = row.get("color")
                    folder.styles.append(style)
                    ln.style = style
                case "MultiPolygon":
                    shapes = row["geometry"].geoms
                    multipolygon = fol.newmultigeometry(name=row["name"])
                    multipolygon.extendeddata.newdata("type", row["type"])
                    _set_description(multipolygon, row)
                    for shape in shapes:
                        multipolygon.newpolygon(name=row["name"], outerboundaryis=shapely.get_coordinates(shape))


def _set_description(placemark, row) -> None:
    description = _row_description(row)
    if description is not None:
        placemark.description = description


def _row_description(row):
    for column in ("description", "Description"):
        value = row.get(column)
        if not _is_empty(value):
            return value
    return None


def _is_empty(value) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False
