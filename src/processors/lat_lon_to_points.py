import geopandas


class LatLonToPoints:
    def __init__(self, _):
        pass
    def process(self,frame):
        # long / lat columns to geodataframe geomtry all other columns attributes
        return geopandas.GeoDataFrame(
            geometry=geopandas.points_from_xy(frame.Longitude, frame.Latitude, crs="EPSG:4326"), data=frame
        )