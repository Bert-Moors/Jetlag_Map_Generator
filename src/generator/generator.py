import generator.config as genconfig
import geopandas as gpd
import os.path
import pandas as pd


class Generator:
    def __init__(self, config_file: str, output_path: str):
        self._config = genconfig.load_config(config_file)
        self._output_path = output_path
        self._gathered_data = {}

    def generate(self):
        self.__import_data()
        self.__process_data()
        self.__export_data()

    def __import_data(self):
        for layer in self._config.layers:
            self._gathered_data[layer.name] = {}
            for data in layer.datasources:
                frame = data.loader.load()

                frame["type"] = data.name_type
                self._gathered_data[layer.name][data.name_type] = frame

    def __process_data(self):
        for layer in self._config.layers:
            for data in layer.datasources:
                for processor in data.processors:
                    self._gathered_data[layer.name][data.name_type] = processor.process(self._gathered_data[layer.name][data.name_type])
            if layer.processors:
                layer_frame = gpd.GeoDataFrame(pd.concat(self._gathered_data[layer.name].values()))
                for processor in layer.processors:
                    layer_frame = processor.process(layer_frame)
                split_frames = {}
                for type in layer_frame["type"].unique():
                    split_frames[type] = layer_frame[layer_frame["type"] == type]
                self._gathered_data[layer.name] = split_frames
            for data in layer.datasources:
                for processor in data.post_processors:
                    self._gathered_data[layer.name][data.name_type] = processor.process(
                        self._gathered_data[layer.name][data.name_type])

    def __export_data(self):
        if not os.path.isdir(self._output_path):
            os.makedirs(self._output_path, exist_ok=False)
        for exporter in self._config.exporters:
            exporter.export(self._gathered_data.copy(), f"{self._output_path}/{self._config.name}")
