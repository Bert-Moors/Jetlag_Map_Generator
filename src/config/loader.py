import json
import tomllib
from typing import Protocol, Dict, Any, List

import geopandas

from config.layer_config import OverpassLoader, GeoJsonLoader
from processors.processor_index import get_processor


class Loader(Protocol):
    def load(self) -> geopandas.geodataframe.GeoDataFrame:
        pass

class LayerConfig:
    def __init__(self, loader: Loader, processors, export_config: Dict[str, Any], typ):
        self.loader = loader
        self.processors = processors
        self.export_config = export_config
        self.typ = typ

class Folder:
    def __init__(self, name, processors=None):
        if processors is None:
            processors = []
        self.name = name
        self.layers = []
        self.processors=processors

    def add_layer(self, layer):
        self.layers.append(layer)


class Config:
    def __init__(self, file_name: str):
        self.location=""
        self.metadata = {}
        self.layers:List[Folder] = []
        self.name=""

        if file_name is None:
            raise Exception("file_name cannot be None")

        typ = file_name.split(".")[-1]
        if typ =="json":
            self.load_json_config(file_name)
        elif typ == "toml":
            self.load_toml_config(file_name)
        else:
            raise Exception("Wrong config loading format")

    @staticmethod
    def convert_toml_layers(name, layers)-> Folder:
        processors = []

        for proc in layers.get("processors", []):
            processors.append(get_processor(proc))
        folder = Folder(name, processors=processors)

        for idx in layers:
            if idx == "processors":
                continue
            layer = layers[idx]

            processors = []
            for proc in layer.get("processors", []):
                processors.append(get_processor(proc))
            if query:=layer.get("query"):
                loader=OverpassLoader(query, layer.get("geom_type"))
            elif file := layer.get("file"):
                loader = GeoJsonLoader(file)
            else:
                continue
            folder.add_layer(LayerConfig(loader=loader, processors=processors, export_config={}, typ=idx))
        return folder

    def load_toml_config(self, file_name:str):
        with open(file_name, "rb") as f:
            toml_data = (tomllib.load(f))
            keywords = ["layers", "location"]

            for k in toml_data:
                if k not in keywords:
                    self.metadata[k] = toml_data[k]
                    continue
            self.location = toml_data.get("location", "")
            for lay in toml_data.get("layers", []):
                self.layers.append(self.convert_toml_layers(lay, toml_data["layers"][lay]))

    def load_json_config(self, file_name: str):
        with open(file_name, encoding="utf-8") as file:
            data = json.load(file)
            keywords = ["layers", "location"]
            for k in data:
                if k not in keywords:
                    self.metadata[k] = data[k]
                    continue
            self.location = data.get("location", "")
            for layer in data.get("folders", []):
                procs = []
                for processor in layer.get("processors", []):
                    procs.append(get_processor(processor))
                folder  = Folder(name=layer.get("name"), processors=procs)
                for dat in layer.get("data", []):
                    processors = []
                    for proc in dat.get("processors", []):
                        processors.append(get_processor(proc))
                    if query := dat.get("query"):
                        loader = OverpassLoader(query, dat.get("geom_type"))
                    elif file := dat.get("file"):
                        loader = GeoJsonLoader(file)
                    else:
                        print("skipping wrongly configured data", dat)
                        continue
                    folder.add_layer(LayerConfig(loader=loader, processors=processors, export_config={}, typ=dat.get("geom_type")))
                self.layers.append(folder)