from generator.exporters.exporters import GoogleMyMapsKmlExporter, FullKmlExporter

def get_exporter(name):
    mp = {
        "googleMMaps": GoogleMyMapsKmlExporter,
        "fullkml": FullKmlExporter
    }

    return mp[name]()