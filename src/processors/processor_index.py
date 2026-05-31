from processors.average_stations_same_name import AverageStationsSameName
from processors.hiding_zones import HidingZones
from processors.remove_overlapping_zones import RemoveOverlappingZones
from processors.rename import Rename


def get_processor(processor):
    mp = {
        "name_based_deduplicate": AverageStationsSameName,
        "hiding_zones": HidingZones,
        "rename_column": Rename,
        "remove_overlapping_zones": RemoveOverlappingZones,
    }

    return mp[processor.get("name")](processor)