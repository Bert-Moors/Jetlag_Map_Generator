from generator.exporters.exporters import GoogleMyMapsKmlExporter, FullKmlExporter, HidingZoneExporter


def get_exporter(name):
    mp = {
        "googleMMaps": GoogleMyMapsKmlExporter,
        "fullkml": FullKmlExporter,
        "kmlHidingZones": HidingZoneExporter,
    }

    return mp[name]()