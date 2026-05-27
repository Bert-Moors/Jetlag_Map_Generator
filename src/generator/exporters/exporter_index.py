from generator.exporters.exporters import GoogleMyMapsKmlExporter

def get_exporter(name):
    mp = {
        "googleMMaps": GoogleMyMapsKmlExporter,
    }

    return mp[name]()