from typing import List

from loaders.loaders import Loader


class Datasource:
    """
    Configures source and styling for one datasource.
    """

    def __init__(self, loader: Loader, processors, typ):
        self.loader = loader
        self.processors = processors
        self.typ = typ


class Layer:
    """
    Data class that holds the config for one layer.
    Contains multiple data sources
    """

    def __init__(self, name):
        self.name = name
        self.datasource = []

    def add_datasource(self, data):
        self.datasource.append(data)


class Config:
    """
    Data class that holds the entire config for the generator.
    Contains multiple layers.
    """

    def __init__(self, file_name: str):
        self.location = ""
        self.metadata = {}
        self.folders: List[Layer] = []
        self.name = ""
