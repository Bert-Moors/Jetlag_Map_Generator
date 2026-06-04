import os
import sys
import unittest

import geopandas as gpd
import shapely


ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from processors.add_column import AddColumn  # noqa: E402
from processors.average_stations_same_name import AverageStationsSameName  # noqa: E402
from processors.hiding_zones import HidingZones, calculate_epsg  # noqa: E402
from processors.processor_index import get_processor  # noqa: E402
from processors.remove_items_by_name import RemoveByNames  # noqa: E402
from processors.remove_overlapping_zones import RemoveOverlappingZones  # noqa: E402
from processors.rename import Rename  # noqa: E402


def frame(rows):
    return gpd.GeoDataFrame(rows, crs="EPSG:4326")


class ProcessorTests(unittest.TestCase):
    def test_get_processor_constructs_known_processors(self):
        self.assertIsInstance(get_processor({"name": "add_column"}), AddColumn)
        self.assertIsInstance(get_processor({"name": "rename_column"}), Rename)
        self.assertIsInstance(get_processor({"name": "remove_by_names", "name_list": []}), RemoveByNames)

        with self.assertRaises(KeyError):
            get_processor({"name": "unknown"})

    def test_add_column_mutates_frame_with_configured_values(self):
        df = frame([{"name": "A", "geometry": shapely.Point(0, 0)}])

        result = AddColumn({"columns": {"color": "red", "size": 5}}).process(df)

        self.assertIs(result, df)
        self.assertEqual(result["color"].tolist(), ["red"])
        self.assertEqual(result["size"].tolist(), [5])

    def test_rename_returns_frame_with_renamed_columns(self):
        df = frame([{"old": "A", "geometry": shapely.Point(0, 0)}])

        result = Rename({"columns": {"old": "name"}}).process(df)

        self.assertIn("name", result.columns)
        self.assertNotIn("old", result.columns)

    def test_remove_by_names_drops_exact_name_matches(self):
        df = frame(
            [
                {"name": "Keep", "geometry": shapely.Point(0, 0)},
                {"name": "Drop", "geometry": shapely.Point(1, 1)},
            ]
        )

        result = RemoveByNames({"name_list": ["Drop"]}).process(df)

        self.assertEqual(result["name"].tolist(), ["Keep"])
        self.assertEqual(df["name"].tolist(), ["Keep", "Drop"])

    def test_average_stations_same_name_uppercases_and_removes_prefixes_before_dissolve(self):
        df = frame(
            [
                {"name": "City, Central", "type": "bus", "geometry": shapely.Point(0, 0)},
                {"name": "Central", "type": "bus", "geometry": shapely.Point(2, 0)},
                {"name": "Other", "type": "tram", "geometry": shapely.Point(10, 0)},
            ]
        )

        result = AverageStationsSameName({"prefix_ignores": ["City, "]}).process(df)

        self.assertEqual(set(result["name"]), {"City, Central", "Other"})
        central = result[result["name"] == "City, Central"].iloc[0]
        self.assertAlmostEqual(central.geometry.x, 1.0)
        self.assertAlmostEqual(central.geometry.y, 0.0)
        self.assertEqual(central["type"], "bus")

    def test_calculate_epsg_returns_utm_codes_for_hemispheres(self):
        self.assertEqual(calculate_epsg({"geometry": shapely.Point(5, 51)}), 32631)
        self.assertEqual(calculate_epsg({"geometry": shapely.Point(5, -51)}), 32731)

    def test_hiding_zones_creates_multilinestring_boundaries_by_default(self):
        df = frame([{"name": "A", "type": "bus", "geometry": shapely.Point(5, 51)}])

        result = HidingZones({"size": 100}).process(df)

        self.assertEqual(result.crs.to_epsg(), 4326)
        self.assertEqual(result.geometry.iloc[0].geom_type, "MultiLineString")
        self.assertIn("epsg", result.columns)

    def test_hiding_zones_can_create_polygons(self):
        df = frame([{"name": "A", "type": "bus", "geometry": shapely.Point(5, 51)}])

        result = HidingZones({"size": 100, "draw_polygons": True}).process(df)

        self.assertEqual(result.geometry.iloc[0].geom_type, "Polygon")

    def test_remove_overlapping_zones_prefers_more_important_types(self):
        df = frame(
            [
                {"name": "bus", "type": "bus", "geometry": shapely.Point(5, 51)},
                {"name": "train", "type": "train", "geometry": shapely.Point(5.0001, 51.0001)},
            ]
        )

        result = RemoveOverlappingZones(
            {
                "size": 500,
                "allowed_intrusion": 0,
                "config": {"train": {"importance": 2}, "bus": {"importance": 1}},
            }
        ).process(df)

        self.assertEqual(result["name"].tolist(), ["train"])
        self.assertEqual(result.crs.to_epsg(), 4326)

    def test_remove_overlapping_zones_uses_hiding_size_overrides(self):
        df = frame(
            [
                {"name": "small", "type": "stop", "hiding_size": 1, "geometry": shapely.Point(5, 51)},
                {"name": "small2", "type": "stop", "hiding_size": 1, "geometry": shapely.Point(5.001, 51.001)},
            ]
        )

        result = RemoveOverlappingZones({"size": 500, "allowed_intrusion": 0}).process(df)

        self.assertEqual(set(result["name"]), {"small", "small2"})


if __name__ == "__main__":
    unittest.main()
