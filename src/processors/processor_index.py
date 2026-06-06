from processors.add_column import AddColumn
from processors.average_stations_same_name import AverageStationsSameName
from processors.hiding_zones import HidingZones
from processors.lat_lon_to_points import LatLonToPoints
from processors.remove_items_by_name import RemoveByNames
from processors.remove_overlapping_zones import RemoveOverlappingZones
from processors.rename import Rename


def get_processor(processor):
    mp = {
        "name_based_deduplicate": AverageStationsSameName,
        "hiding_zones": HidingZones,
        "rename_column": Rename,
        "remove_by_names": RemoveByNames,
        "remove_overlapping_zones": RemoveOverlappingZones,
        "add_column":AddColumn,
        "lat_lon_to_points": LatLonToPoints,
    }

    return mp[processor.get("name")](processor)