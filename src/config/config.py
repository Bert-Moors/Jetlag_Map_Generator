import json
import tomllib
from typing import Dict, Any, List

from loaders.loaders import OverpassLoader, GeoJsonLoader, Loader
from processors.processor_index import get_processor


class Layer:
    """
    Configures the exporting of one data layer within a folder.
    """
    def __init__(self, loader: Loader, processors, typ):
        self.loader = loader
        self.processors = processors
        self.typ = typ

class Folder:
    """
    Contains the config for one folder: contains multiple Layers.
    """

    def __init__(self, name):
        self.name = name
        self.layers = []

    def add_layer(self, layer):
        self.layers.append(layer)


class Config:
    """
    Load a full config from file.
    Accepts both a toml format and json format.
    Note that JSON format may be deprecated in the future
    """

    def __init__(self, file_name: str):
        self.location=""
        self.metadata = {}
        self.folders:List[Folder] = []
        self.name=""

        if file_name is None:
            raise Exception("file_name cannot be None")

        # Pick the correct parser based on extension
        typ = file_name.split(".")[-1]
        if typ =="json":
            self.load_json_config(file_name)
        elif typ == "toml":
            self.load_toml_config(file_name)
        else:
            raise Exception("Wrong config loading format")

    def load_toml_config(self, file_name:str):
        with open(file_name, "rb") as f:
            toml_data = (tomllib.load(f))

            # These keywords are handled by different code parts.
            keywords = ["layers", "location"]

            # All unknown fields end up in the metadata.
            for k in toml_data:
                if k not in keywords:
                    self.metadata[k] = toml_data[k]
                    continue

            # The location is a fixed field for the config.
            self.location = toml_data.get("location", "")

            # Also load all the layers.
            for lay in toml_data.get("layers", []):
                self.folders.append(self.convert_toml_folder(lay, toml_data["layers"][lay]))

    @staticmethod
    def convert_toml_folder(name, folder)-> Folder:
        # Load the processors on folder-level
        folder_processors = []

        for proc in folder.get("processors", []):
            folder_processors.append(get_processor(proc))
        result = Folder(name)

        for key in folder:
            # Processors are handled before
            if key == "processors":
                continue

            # Any key not a processors is a data-layer.
            layer = folder[key]

            processors = []+folder_processors
            for proc in layer.get("processors", []):
                processors.append(get_processor(proc))

            if query := layer.get("query"):
                loader=OverpassLoader(query, layer.get("geom_type"))
            elif file := layer.get("file"):
                loader = GeoJsonLoader(file)
            else:
                continue
            result.add_layer(Layer(loader=loader, processors=processors, typ=key))
        return result

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
                    folder.add_layer(Layer(loader=loader, processors=processors, typ=dat.get("geom_type")))
                self.folders.append(folder)