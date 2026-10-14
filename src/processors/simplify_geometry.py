import geopandas


class SimplifyGeometry:
    def __init__(self, config):
        self.tolerance = config.get("tolerance", 0.001)

    def process(self, frame):
        frame = frame.copy()
        frame["geometry"] = frame.geometry.simplify(self.tolerance, preserve_topology=True)
        return frame
