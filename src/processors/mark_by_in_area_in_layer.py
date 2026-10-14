import geopandas
import pandas as pd

from processors.hiding_zones import calculate_epsg


class MarkInAreaInLayer:
    def __init__(self, config):
        self.source_layer = config.get("source_layer")

        self.source_tag_key = config.get("source_tag_key", "name")
        self.target_tag_key = config.get("target_tag_key", self.source_layer)
        self.epsg = config.get("epsg")
        self._context = {}

        if not self.source_layer:
            raise Exception("mark_by_area_in_layer processor requires source_layer")

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

        source = source.rename(columns={self.source_tag_key: "result_data_column"})
        result_gdf = target.sjoin(
            source[["geometry", "result_data_column"]],
            rsuffix="right",
            how="left",
            predicate="within",
        ).rename(columns={"name"+"_left":"name", "result_data_column": "_tag."+self.target_tag_key }).drop(["index_right"], axis=1)

        return result_gdf.to_crs("EPSG:4326").reset_index(drop=True)

    def _source_frame(self):
        layer = self._context.get(self.source_layer)
        if layer is None:
            raise Exception(f"source layer {self.source_layer} is not available")


        return geopandas.GeoDataFrame(pd.concat(layer.values()), geometry="geometry", crs="EPSG:4326")

    def _calculate_epsg(self, frame):
        sample = frame.iloc[0].copy()
        return calculate_epsg(sample)
