from processors.average_stations_same_name import AverageStationsSameName
from processors.hiding_zones import HidingZones
from processors.multi_line_to_polygon import MultiLineToPolygon
from processors.rename import Rename


def get_processor(processor_name):
    mp = {
        "name_based_deduplicate": AverageStationsSameName,
        "hiding_zones": HidingZones,
        "rename_column": Rename,
        "to_poly": MultiLineToPolygon,
    }
    return mp[processor_name]