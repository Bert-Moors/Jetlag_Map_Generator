import geopandas
import numpy as np
import shapely
from shapely import get_coordinates, reverse, LineString


class MultiLineToPolygon:
    def __init__(self, _):
        pass

    def process(self, frame):
        grouped_frame = frame.dissolve(by='name', as_index=False)
        grouped_frame["geometry"] = grouped_frame.polygonize()
        return grouped_frame
