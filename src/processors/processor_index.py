from processors.average_stations_same_name import AverageStationsSameName
from processors.hiding_zones import HidingZones
from processors.rename import Rename


def get_processor(processor_name):
    mp = {
        "name_collapse": AverageStationsSameName,
        "hiding_zones": HidingZones,
        "rename": Rename,
    }
    return mp[processor_name]