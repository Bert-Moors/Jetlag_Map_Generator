import geopandas
import pandas as pd

from processors.hiding_zones import calculate_epsg


class FilterByDistanceToLayer:
    def __init__(self, config):
        self.source_layer = config.get("source_layer")
        self.source_type = config.get("source_type")
        self.distance = config.get("distance")
        self.epsg = config.get("epsg")
        self._context = {}

        if not self.source_layer:
            raise Exception("filter_by_distance_to_layer processor requires source_layer")
        if self.distance is None:
            raise Exception("filter_by_distance_to_layer processor requires distance")

    def set_context(self, context):
        self._context = context

    def process(self, frame):
        if frame.empty:
            return frame

        source = self._source_frame()
        if source.empty:
            return frame.iloc[0:0].reset_index(drop=True)

        target = geopandas.GeoDataFrame(frame.copy(), geometry="geometry", crs=frame.crs or "EPSG:4326").reset_index(drop=True)
        source = geopandas.GeoDataFrame(source.copy(), geometry="geometry", crs=source.crs or "EPSG:4326").reset_index(drop=True)
        target = target[target.geometry.notna() & ~target.geometry.is_empty]
        source = source[source.geometry.notna() & ~source.geometry.is_empty]
        if target.empty or source.empty:
            return target.iloc[0:0].to_crs("EPSG:4326").reset_index(drop=True)

        epsg = self.epsg or self._calculate_epsg(target)
        target_projected = target.to_crs(epsg)
        source_projected = source.to_crs(epsg)

        source_matches, target_matches = target_projected.sindex.query(
            source_projected.geometry,
            predicate="dwithin",
            distance=self.distance,
        )
        keep_indices = target_projected.index[target_matches].unique()

        return target.loc[keep_indices].to_crs("EPSG:4326").reset_index(drop=True)

    def _source_frame(self):
        layer = self._context.get(self.source_layer)
        if layer is None:
            raise Exception(f"source layer {self.source_layer} is not available")

        if self.source_type:
            source = layer.get(self.source_type)
            if source is None:
                raise Exception(f"source type {self.source_type} is not available in layer {self.source_layer}")
            return source

        return geopandas.GeoDataFrame(pd.concat(layer.values()), geometry="geometry", crs="EPSG:4326")

    def _calculate_epsg(self, frame):
        sample = frame.iloc[0].copy()
        return calculate_epsg(sample)
