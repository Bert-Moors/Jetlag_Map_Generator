from typing import List
from loaders.loaders import Loader


class Datasource:
    """
    Configures source and styling for one datasource.
    """

    def __init__(self, loader: Loader, processors, name_type):
        self.loader = loader
        self.processors = processors
        self.name_type = name_type


class Layer:
    """
    Data class that holds the config for one layer.
    Contains multiple data sources
    """

    def __init__(self, name, processors):
        self.name = name
        self.processors = processors
        self.datasources = []

    def add_datasource(self, data: Datasource):
        self.datasources.append(data)


class Config:
    """
    Data class that holds the entire config for the generator.
    Contains multiple layers.
    """

    def __init__(self, name:str, exporters):
        self.name = name
        self.location = ""
        self.exporters = exporters
        self.layers: List[Layer] = []

    def add_layer(self, layer: Layer):
        self.layers.append(layer)
