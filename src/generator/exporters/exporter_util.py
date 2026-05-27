from typing import Dict
import geopandas as gpd
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
                    style = simplekml.Style()
                    style.linestyle.width = 3
                    style.linestyle.color = row.get("color")
                    folder.styles.append(style)
                    ln.style = style
                case "MultiPolygon":
                    shapes = row["geometry"].geoms
                    multipolygon = fol.newmultigeometry(name=row["name"])
                    multipolygon.extendeddata.newdata("type", row["type"])
                    for shape in shapes:
                        multipolygon.newpolygon(name=row["name"], outerboundaryis=shapely.get_coordinates(shape))