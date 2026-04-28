from geopandas.geoseries import GeoSeries
from shapely import MultiPolygon


class MultiLineToPolygon:
    def __init__(self, _):
        pass

    def process(self, frame):
        grouped_frame = frame.dissolve(by='name',as_index=False)
        result = frame[0:0]
        for value in grouped_frame['name']:
            sub = grouped_frame[grouped_frame['name'] == value]
            geom = sub.geometry.polygonize(node=True)
            if isinstance(geom, GeoSeries):
                geom = MultiPolygon(geom)
            row = {'name':value, 'geometry': geom}
            result.loc[len(result)] = row
        return result
