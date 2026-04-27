from geopandas import GeoSeries
from geopandas.geodataframe import GeoDataFrame
from numpy import copysign, floor


class HidingZones:
    def __init__(self, config):
        self.size = config.get('size',250)
        self.epsg = config.get('epsg',None)

    def calculate_epsg(self, row):
        if isinstance(row, GeoSeries):
            point = row[0]
        elif isinstance(row, GeoDataFrame):
            point = row
        else:
            raise NotImplementedError
        y,x =point.y, point.x
        return int(32700 - (copysign(1, y ) + 1) / 2 * 100 + (floor((180 + x) / 6) + 1))


    def process(self, df):
        new_df = df.copy()
        new_df.set_crs(4326,inplace=True)
        epsg = self.epsg
        if not epsg:
            epsg = self.calculate_epsg(new_df.centroid)
        new_df.to_crs(epsg, inplace=True)

        new_df['geometry'] = new_df['geometry'].buffer(distance=self.size)
        new_df.to_crs(4326,inplace=True)
        return new_df