from generator.exporters.exporters import FullKmlExporter, GoogleMyMapsKmlExporter, HidingZoneExporter, OpenStreetMapA3PdfExporter


def get_exporter(name):
    mp = {
        "googleMMaps": GoogleMyMapsKmlExporter,
        "osmA3Pdf": OpenStreetMapA3PdfExporter,
        "fullkml": FullKmlExporter,
        "kmlHidingZones": HidingZoneExporter,
    }

    return mp[name]()
