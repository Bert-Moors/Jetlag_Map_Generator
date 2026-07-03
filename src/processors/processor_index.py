from processors.add_column import AddColumn
from processors.average_stations_same_name import AverageStationsSameName
from processors.filter_by_column import FilterByColumn
from processors.filter_by_distance_to_layer import FilterByDistanceToLayer
from processors.hiding_zones import HidingZones
from processors.lat_lon_to_points import LatLonToPoints
from processors.remove_items_by_name import RemoveByNames
from processors.remove_overlapping_zones import RemoveOverlappingZones
from processors.rename import Rename
from processors.simplified_lines import SimplifiedLines


def get_processor(processor):
    mp = {
        "name_based_deduplicate": AverageStationsSameName,
        "hiding_zones": HidingZones,
        "rename_column": Rename,
        "remove_by_names": RemoveByNames,
        "remove_overlapping_zones": RemoveOverlappingZones,
        "add_column":AddColumn,
        "filter_by_column": FilterByColumn,
        "filter_by_distance_to_layer": FilterByDistanceToLayer,
        "lat_lon_to_points": LatLonToPoints,
        "simplified_lines": SimplifiedLines,
    }

    return mp[processor.get("name")](processor)
