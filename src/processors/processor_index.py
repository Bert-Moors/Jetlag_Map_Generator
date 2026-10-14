from processors.add_column import AddColumn
from processors.name_based_deduplicate import AverageStationsSameName
from processors.hiding_zones import HidingZones
from processors.mark_by_in_area_in_layer import MarkInAreaInLayer
from processors.remove_by_names import RemoveByNames
from processors.remove_overlapping_zones import RemoveOverlappingZones
from processors.rename_column import Rename
def get_processor(processor):
    mp = {
        "name_based_deduplicate": AverageStationsSameName,
        "hiding_zones": HidingZones,
        "rename_column": Rename,
        "remove_by_names": RemoveByNames,
        "remove_overlapping_zones": RemoveOverlappingZones,
        "add_column":AddColumn,
        "mark_by_in_area_in_layer": MarkInAreaInLayer,
    }

    return mp[processor.get("name")](processor)