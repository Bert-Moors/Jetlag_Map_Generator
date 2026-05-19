import json
import tomllib

from generator.config import Config, Layer, Datasource
from loaders.loaders import OverpassLoader, GeoJsonLoader
from processors.processor_index import get_processor


def load_config(file_name: str) -> Config:
    """
    takes a config file and delegates loading logic based on file type.
    return a config object
    """
    if file_name is None:
        raise Exception("file_name cannot be None")

    file_type = file_name.split(".")[-1]
    match file_type:
        case "json":
            return load_json_config(file_name)
        case "toml":
            return load_toml_config(file_name)
        case "yml":
            return load_yml_config()
        case _:
            raise Exception("Wrong config loading format")

def load_json_config(file_name: str) -> Config:
    config = Config(file_name)
    with open(file_name, encoding="utf-8") as file:
        data = json.load(file)
        keywords = ["layers", "location"]
        for k in data:
            if k not in keywords:
                config.metadata[k] = data[k]
                continue
        config.location = data.get("location", "")
        for layer in data.get("folders", []):
            procs = []
            for processor in layer.get("processors", []):
                procs.append(get_processor(processor))
            folder = Layer(name=layer.get("name"), processors=procs)
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
                folder.add_datasource(Datasource(loader=loader, processors=processors, typ=dat.get("geom_type")))
            config.folders.append(folder)
    return config

def load_toml_config(file_name: str) -> Config:
    config = Config(file_name)
    with open(file_name, "rb") as f:
        toml_data = (tomllib.load(f))

        # These keywords are handled by different code parts.
        keywords = ["layers", "location"]

        # All unknown fields end up in the metadata.
        for k in toml_data:
            if k not in keywords:
                config.metadata[k] = toml_data[k]
                continue

        # The location is a fixed field for the config.
        config.location = toml_data.get("location", "")

        # Also load all the layers.
        for lay in toml_data.get("layers", []):
            config.folders.append(convert_toml_folder(lay, toml_data["layers"][lay]))
    return config

@staticmethod
def convert_toml_folder(name, folder)-> Layer:
    # Load the processors on folder-level
    folder_processors = []

    for proc in folder.get("processors", []):
        folder_processors.append(get_processor(proc))
    result = Layer(name)

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
        result.add_datasource(Datasource(loader=loader, processors=processors, typ=key))
    return result

def load_yml_config() -> Config:
    pass