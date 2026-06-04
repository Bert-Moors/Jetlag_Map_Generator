import os
import sys
import tempfile
import unittest
from unittest.mock import patch

import geopandas as gpd
import pandas as pd
import shapely


ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from generator.config.config import Config, Datasource, Layer  # noqa: E402
from generator.exporters.exporter_index import get_exporter  # noqa: E402
from generator.exporters.exporter_util import add_to_kml  # noqa: E402
from generator.exporters.exporters import (  # noqa: E402
    FullKmlExporter,
    GoogleMyMapsKmlExporter,
    HidingZoneExporter,
)
from generator.generator import Generator  # noqa: E402


def point_frame(name="A", typ="bus"):
    return gpd.GeoDataFrame(
        {"name": [name], "type": [typ], "geometry": [shapely.Point(5, 51)]}, crs="EPSG:4326"
    )


class FakeFolder:
    def __init__(self, name="root"):
        self.name = name
        self.folders = []
        self.points = []
        self.lines = []
        self.multigeometries = []
        self.styles = []

    def newfolder(self, name):
        folder = FakeFolder(name)
        self.folders.append(folder)
        return folder

    def newpoint(self, name, coords):
        item = FakeKmlItem(name, coords)
        self.points.append(item)
        return item

    def newlinestring(self, name, coords):
        item = FakeKmlItem(name, coords)
        self.lines.append(item)
        return item

    def newmultigeometry(self, name):
        item = FakeMultiGeometry(name)
        self.multigeometries.append(item)
        return item


class FakeKmlItem:
    def __init__(self, name, coords):
        self.name = name
        self.coords = coords
        self.extendeddata = FakeExtendedData()
        self.style = None


class FakeMultiGeometry:
    def __init__(self, name):
        self.name = name
        self.extendeddata = FakeExtendedData()
        self.polygons = []
        self.linestrings = []

    def newpolygon(self, name, outerboundaryis):
        self.polygons.append((name, outerboundaryis))

    def newlinestring(self, coords):
        self.linestrings.append(coords)


class FakeExtendedData:
    def __init__(self):
        self.data = []

    def newdata(self, name, value):
        self.data.append((name, value))


class ExporterUtilityTests(unittest.TestCase):
    def test_add_to_kml_serializes_supported_geometry_types(self):
        root = FakeFolder()
        frames = {
            "Layer": gpd.GeoDataFrame(
                [
                    {"name": "point", "type": "pt", "geometry": shapely.Point(1, 2)},
                    {
                        "name": "polygon",
                        "type": "poly",
                        "geometry": shapely.Polygon([(0, 0), (1, 0), (1, 1), (0, 0)]),
                    },
                    {
                        "name": "multi-line",
                        "type": "line",
                        "geometry": shapely.MultiLineString([[(0, 0), (1, 1)]]),
                    },
                    {
                        "name": "line",
                        "type": "line",
                        "color": "ff0000ff",
                        "geometry": shapely.LineString([(0, 0), (1, 1)]),
                    },
                    {
                        "name": "multi-poly",
                        "type": "poly",
                        "geometry": shapely.MultiPolygon(
                            [shapely.Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])]
                        ),
                    },
                ]
            )
        }

        add_to_kml(frames, root)

        layer = root.folders[0]
        self.assertEqual(layer.name, "Layer")
        self.assertEqual(len(layer.points), 1)
        self.assertEqual(layer.points[0].extendeddata.data, [("type", "pt")])
        self.assertEqual(len(layer.lines), 1)
        self.assertEqual(len(layer.multigeometries), 3)


class ExporterTests(unittest.TestCase):
    def test_exporter_index_constructs_exporters_and_rejects_unknown_names(self):
        self.assertIsInstance(get_exporter("googleMMaps"), GoogleMyMapsKmlExporter)
        self.assertIsInstance(get_exporter("fullkml"), FullKmlExporter)
        self.assertIsInstance(get_exporter("kmlHidingZones"), HidingZoneExporter)

        with self.assertRaises(KeyError):
            get_exporter("missing")

    def test_google_my_maps_exporter_combines_datasources_per_layer(self):
        data = {"Transit": {"bus": point_frame("Bus", "bus"), "tram": point_frame("Tram", "tram")}}
        exporter = GoogleMyMapsKmlExporter()

        with tempfile.TemporaryDirectory() as tmp:
            output_prefix = os.path.join(tmp, "map")
            exporter.export(data, output_prefix)
            output = f"{output_prefix} GMM.kml"
            self.assertTrue(os.path.exists(output))
            with open(output, encoding="utf-8") as file:
                contents = file.read()

        self.assertIn("Transit", contents)
        self.assertIn("Bus", contents)
        self.assertIn("Tram", contents)

    def test_full_kml_exporter_keeps_datasources_nested_under_layers(self):
        data = {"Transit": {"bus": point_frame("Bus", "bus")}}
        exporter = FullKmlExporter()

        with tempfile.TemporaryDirectory() as tmp:
            output_prefix = os.path.join(tmp, "map")
            exporter.export(data, output_prefix)
            output = f"{output_prefix} FULL.kml"
            self.assertTrue(os.path.exists(output))
            with open(output, encoding="utf-8") as file:
                contents = file.read()

        self.assertIn("Transit", contents)
        self.assertIn("bus", contents)
        self.assertIn("Bus", contents)

    def test_hiding_zone_exporter_exports_rows_with_hiding_size(self):
        data = {
            "Transit": {
                "bus": gpd.GeoDataFrame(
                    {
                        "name": ["Bus", "NoSize"],
                        "type": ["bus", "bus"],
                        "hiding_size": [100, 0],
                        "geometry": [shapely.Point(5, 51), shapely.Point(5.1, 51.1)],
                    },
                    crs="EPSG:4326",
                )
            }
        }
        exporter = HidingZoneExporter()

        with tempfile.TemporaryDirectory() as tmp:
            output_prefix = os.path.join(tmp, "map")
            exporter.export(data, output_prefix)
            output = f"{output_prefix} HZ.kml"
            self.assertTrue(os.path.exists(output))
            with open(output, encoding="utf-8") as file:
                contents = file.read()

        self.assertIn("Hiding Zones", contents)
        self.assertIn("Bus", contents)
        self.assertNotIn("NoSize", contents)


class FakeLoader:
    def __init__(self, rows):
        self.rows = rows

    def load(self):
        return gpd.GeoDataFrame(self.rows, crs="EPSG:4326")


class RecordingProcessor:
    def __init__(self, column, value):
        self.column = column
        self.value = value

    def process(self, frame):
        frame = frame.copy()
        frame[self.column] = self.value
        return frame


class RecordingExporter:
    def __init__(self):
        self.calls = []

    def export(self, data, output_path):
        self.calls.append((data, output_path))


class GeneratorPipelineTests(unittest.TestCase):
    def test_generator_imports_processes_splits_layer_data_and_exports(self):
        exporter = RecordingExporter()
        config = Config("map-name", [exporter])
        layer = Layer("Transit", [RecordingProcessor("layer_processed", True)])
        layer.add_datasource(
            Datasource(
                FakeLoader([{"name": "Bus", "geometry": shapely.Point(5, 51)}]),
                [RecordingProcessor("source_processed", "bus")],
                "bus",
            )
        )
        layer.add_datasource(
            Datasource(
                FakeLoader([{"name": "Tram", "geometry": shapely.Point(5.1, 51.1)}]),
                [],
                "tram",
            )
        )
        config.add_layer(layer)

        with tempfile.TemporaryDirectory() as tmp:
            with patch("generator.generator.genconfig.load_config", return_value=config):
                Generator("ignored.yaml", tmp).generate()

            self.assertTrue(os.path.isdir(tmp))

        self.assertEqual(len(exporter.calls), 1)
        exported_data, output_path = exporter.calls[0]
        self.assertTrue(output_path.endswith("/map-name"))
        self.assertEqual(set(exported_data["Transit"].keys()), {"bus", "tram"})
        bus = exported_data["Transit"]["bus"].iloc[0]
        tram = exported_data["Transit"]["tram"].iloc[0]
        self.assertEqual(bus["type"], "bus")
        self.assertEqual(tram["type"], "tram")
        self.assertEqual(bus["source_processed"], "bus")
        self.assertTrue(bus["layer_processed"])
        self.assertTrue(tram["layer_processed"])
        self.assertTrue(pd.isna(tram.get("source_processed")))


if __name__ == "__main__":
    unittest.main()
