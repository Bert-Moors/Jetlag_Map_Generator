import generator.config as genconfig
import geopandas as gpd
import os.path
import pandas as pd


class Generator:
    def __init__(self, config_file: str, output_path: str):
        self._config = genconfig.load_config(config_file)
        self._output_path = output_path
        self._gathered_data = {}
        self._processed_datasources = {}

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
                self.__apply_style(frame, data)
                self._gathered_data[layer.name][data.name_type] = frame

    def __process_data(self):
        for layer in self._config.layers:
            self._processed_datasources[layer.name] = {}
            for data in layer.datasources:
                for processor in data.processors:
                    if hasattr(processor, "set_context"):
                        processor.set_context(self._processed_datasources)
                    self._gathered_data[layer.name][data.name_type] = processor.process(self._gathered_data[layer.name][data.name_type])
                self.__apply_style(self._gathered_data[layer.name][data.name_type], data)
                self._processed_datasources[layer.name][data.name_type] = self._gathered_data[layer.name][data.name_type]
            if layer.processors:
                layer_frame = gpd.GeoDataFrame(pd.concat(self._gathered_data[layer.name].values()))
                for processor in layer.processors:
                    if hasattr(processor, "set_context"):
                        processor.set_context(self._processed_datasources)
                    layer_frame = processor.process(layer_frame)
                split_frames = {}
                for type in layer_frame["type"].unique():
                    split_frames[type] = layer_frame[layer_frame["type"] == type]
                self._gathered_data[layer.name] = split_frames

    def __export_data(self):
        if not os.path.isdir(self._output_path):
            os.makedirs(self._output_path, exist_ok=False)
        for exporter in self._config.exporters:
            exporter.export(self._gathered_data.copy(), f"{self._output_path}/{self._config.name}")

    def __apply_style(self, frame, data):
        frame["style_color"] = data.style.get("color")
        frame["style_secondary_color"] = data.style.get("secondary_color")
        frame["style_href"] = data.style.get("href")
        frame["style_svg"] = data.style.get("svg")
        frame["style_scale"] = data.style.get("scale")
        frame["style_width"] = data.style.get("width")
        frame["style_ignore_for_map_boundaries"] = data.style.get("ignore_for_map_boundaries")
        frame["style_with_label"] = data.style.get("with_label")
        frame["style_fixed_label"] = data.style.get("fixed_label")
        frame["style_label_size"] = data.style.get("label_size")
        frame["style_label_direction"] = data.style.get("label_direction")
        type_to_color = data.style.get("type_to_color")
        frame["style_type_to_color"] = [type_to_color] * len(frame) if isinstance(type_to_color, dict) else type_to_color
        frame["style_dotted"] = data.style.get("dotted")
