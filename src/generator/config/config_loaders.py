import json
import tomllib
import yaml

from generator.config import Config, Layer, Datasource
from loaders.loaders import OverpassLoader, GeoJsonLoader
from processors import get_processor
from generator.exporters import  get_exporter

def load_config(file_name: str) -> Config:
    """
    takes a config file and delegates loading logic based on file type.
    return a config object
    """
    if file_name is None:
        raise Exception("file_name cannot be None")

    config_dict = {}
    match file_name.split(".")[-1]:
        case "json":
            config_dict = load_json_config(file_name)
        case "toml":
            config_dict = load_toml_config(file_name)
        case "yml" | "yaml":
            config_dict = load_yml_config(file_name)
        case _:
            raise Exception("Wrong config loading format")
    return dict_to_config(config_dict)

#--------------Loader Functions--------------
def load_json_config(file_name: str) -> dict:
    with open(file_name, "r") as file:
        json_data = json.load(file)
    return json_data

def load_toml_config(file_name: str) -> dict:
    with open(file_name, "rb") as f:
        toml_data = (tomllib.load(f))
        config_dict = {"config": toml_data["config"], "layers":toml_data.get("layers", {})}
        for key in [x for x in toml_data.keys() if x not in ["config", "layers"]]:
            config_dict["layers"][key] = toml_data[key]
    return config_dict

def load_yml_config(file_name: str) -> dict:
    with open(file_name, "r") as file:
        yaml_data = yaml.load(file, Loader=yaml.FullLoader)
    return yaml_data

#--------------Util Functions--------------
def dict_to_config(data: dict) -> Config:
    config: Config
    if config_data := data.get("config"):
        name = config_data.get("name", "")
        exporters = []
        for exporter in config_data.get("exporters", []):
            exporters.append(get_exporter(exporter))
        if not exporters:
            exporters.append(get_exporter("googleMMaps"))
        config = Config(name, exporters)
    else:
        raise Exception("config not defined")

    if layer_data := data.get("layers"):
        for layer_name, layer_data in zip(layer_data.keys(), layer_data.values()):
            config.add_layer(dict_to_layer(layer_name, layer_data))
    else:
        raise Exception("layers are not defined")
    return config

def dict_to_layer(name:str, data:dict) -> Layer:
    layer: Layer
    processors = []
    for proc in data.get("processors", []):
        processors.append(get_processor(proc))

    layer = Layer(name, processors)
    if data:
        for datasource_name, datasource_data in zip(data.keys(), data.values()):
            if datasource_name == "processors":
                continue
            layer.add_datasource(dict_to_datasource(datasource_name, datasource_data))
    else:
        raise Exception(f"Layer {name} has no datasources defined")

    return layer

def dict_to_datasource(name:str, data:dict) -> Datasource:
    datasource: Datasource
    processors = []
    for proc in data.get("processors", []):
        processors.append(get_processor(proc))

    if query := data.get("query"):
        loader = OverpassLoader(query, data.get("geom_type"))
    elif file := data.get("file"):
        loader = GeoJsonLoader(file)
    else:
        raise Exception(f"datasource {name} not configured properly")
    return Datasource(loader, processors, name)