from geopandas.geodataframe import GeoDataFrame
from numpy import copysign, floor
from pandas import concat
from shapely import MultiLineString


def calculate_epsg(row):
    point = row["geometry"]
    return int(32700 - (copysign(1, point.y) + 1) / 2 * 100 + (floor((180 + point.x) / 6) + 1))

class HidingZones:
    def __init__(self, config):
        self.size = config.get("size",250)
        self.epsg = config.get("epsg",None)
        self.draw_polygons = config.get("draw_polygons", False)

    def process(self, df):
        new_df = df.copy()
        new_df.set_crs(4326,inplace=True)
        if not self.epsg:
            new_df["epsg"] = new_df.apply(calculate_epsg, axis=1)

        # go through all unique epsg values and draw hiding zones
        partials = []
        for epsg in new_df["epsg"].unique():
            partial_df = new_df[new_df["epsg"] == epsg]
            partial_df.to_crs(epsg, inplace=True)
            if self.draw_polygons:
                partial_df['geometry'] = partial_df['geometry'].buffer(distance=self.size)
            else:
                circles = partial_df.buffer(self.size, 12).boundary
                circles = circles.apply(lambda x: MultiLineString([x.coords, x.coords[-2::]]))
                partial_df['geometry'] = circles
            partial_df.to_crs(4326, inplace=True)
            partials.append(partial_df)
        # re-combine all partial data frames into one
        return GeoDataFrame(concat(partials), crs="EPSG:4326")