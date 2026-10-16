from processors.add_column import AddColumn
from processors.average_stations_same_name import AverageStationsSameName
from processors.filter_by_column import FilterByColumn
from processors.filter_by_distance_to_layer import FilterByDistanceToLayer
from processors.hiding_zones import HidingZones
from processors.lat_lon_to_points import LatLonToPoints
from processors.mark_by_in_area_in_layer import MarkInAreaInLayer
from processors.remove_items_by_name import RemoveByNames
from processors.remove_overlapping_zones import RemoveOverlappingZones
from processors.rename import Rename
from processors.simplified_lines import SimplifiedLines
from processors.simplify_geometry import SimplifyGeometry
from processors.transit_line_based_tags import TransitLineBasedTags


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
        "mark_by_in_area_in_layer": MarkInAreaInLayer,
        "lat_lon_to_points": LatLonToPoints,
        "transit_line_based_tags": TransitLineBasedTags,
        "simplified_lines": SimplifiedLines,
        "simplify_geometry": SimplifyGeometry,
    }

    return mp[processor.get("name")](processor)
