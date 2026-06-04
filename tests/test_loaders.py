import os
import sys
import tempfile
import unittest
from unittest.mock import patch

import geopandas as gpd
import shapely


ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from loaders.loaders import GeoJsonLoader, OverpassLoader  # noqa: E402
from loaders.overpass import overpass_query_with_cache  # noqa: E402
from loaders.util import order_lines  # noqa: E402


class OverpassLoaderTests(unittest.TestCase):
    def test_parse_points_supports_nodes_centers_and_bounds(self):
        loader = OverpassLoader("query", "points")

        frame = loader._OverpassLoader__parse_json(
            {
                "elements": [
                    {"type": "node", "lon": 1.0, "lat": 2.0, "tags": {"name": "node"}},
                    {
                        "type": "way",
                        "center": {"lon": 3.0, "lat": 4.0},
                        "tags": {"name": "way-center"},
                    },
                    {
                        "type": "relation",
                        "bounds": {"minlon": 4.0, "maxlon": 6.0, "minlat": 8.0, "maxlat": 10.0},
                        "tags": {"name": "relation-bounds"},
                    },
                ]
            },
            "points",
        )

        self.assertEqual(list(frame["name"]), ["node", "way-center", "relation-bounds"])
        self.assertEqual(frame.geometry.iloc[0], shapely.Point(1.0, 2.0))
        self.assertEqual(frame.geometry.iloc[1], shapely.Point(3.0, 4.0))
        self.assertEqual(frame.geometry.iloc[2], shapely.Point(5.0, 9.0))

    def test_parse_points_rejects_missing_point_geometry_and_empty_responses(self):
        loader = OverpassLoader("query", "points")

        with self.assertRaisesRegex(Exception, "Point has no valid data"):
            loader._OverpassLoader__parse_json(
                {"elements": [{"type": "way", "tags": {"name": "bad"}}]}, "points"
            )

        with self.assertRaisesRegex(Exception, "Response is empty"):
            loader._OverpassLoader__parse_json({"elements": []}, "points")

    def test_parse_border_routes_and_polygons(self):
        loader = OverpassLoader("query", "border")
        border = loader._OverpassLoader__parse_json(
            {
                "elements": [
                    {
                        "members": [
                            {
                                "type": "way",
                                "geometry": [{"lon": 0, "lat": 0}, {"lon": 1, "lat": 1}],
                            }
                        ]
                    }
                ]
            },
            "border",
        )
        self.assertEqual(border.geometry.iloc[0].geom_type, "MultiLineString")
        self.assertEqual(border["name"].iloc[0], "border")

        routes = loader._OverpassLoader__parse_json(
            {
                "elements": [
                    {
                        "tags": {"name": "route"},
                        "members": [
                            {
                                "type": "way",
                                "role": "",
                                "geometry": [{"lon": 0, "lat": 0}, {"lon": 1, "lat": 1}],
                            },
                            {
                                "type": "way",
                                "role": "platform",
                                "geometry": [{"lon": 2, "lat": 2}, {"lon": 3, "lat": 3}],
                            },
                        ],
                    }
                ]
            },
            "routes",
        )
        self.assertEqual(len(routes.geometry.iloc[0].geoms), 1)

        polygons = loader._OverpassLoader__parse_json(
            {
                "elements": [
                    {
                        "tags": {"name": "poly"},
                        "members": [
                            {
                                "type": "way",
                                "geometry": [{"lon": 0, "lat": 0}, {"lon": 1, "lat": 0}],
                            },
                            {
                                "type": "way",
                                "geometry": [{"lon": 1, "lat": 0}, {"lon": 1, "lat": 1}],
                            },
                            {
                                "type": "way",
                                "geometry": [{"lon": 1, "lat": 1}, {"lon": 0, "lat": 0}],
                            },
                        ],
                    }
                ]
            },
            "polygons",
        )
        self.assertEqual(polygons.geometry.iloc[0].geom_type, "MultiPolygon")
        self.assertEqual(len(polygons.geometry.iloc[0].geoms), 1)

    def test_parse_json_rejects_unimplemented_geom_type(self):
        loader = OverpassLoader("query", "lines")

        with self.assertRaisesRegex(Exception, "geom type not supported"):
            loader._OverpassLoader__parse_json({"elements": [{"type": "node"}]}, "lines")

    def test_load_uses_overpass_cache_and_configured_geom_type(self):
        with patch("loaders.loaders.overpass_query_with_cache") as query:
            query.return_value = {
                "elements": [
                    {"type": "node", "lon": 1.0, "lat": 2.0, "tags": {"name": "node"}}
                ]
            }

            frame = OverpassLoader("query-text", "points").load()

        query.assert_called_once_with("query-text")
        self.assertEqual(frame["name"].iloc[0], "node")


class GeoJsonLoaderTests(unittest.TestCase):
    def test_geojson_loader_reads_file_at_construction_and_returns_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "data.geojson")
            source = gpd.GeoDataFrame(
                {"name": ["A"], "geometry": [shapely.Point(1, 2)]}, crs="EPSG:4326"
            )
            source.to_file(path, driver="GeoJSON")

            loader = GeoJsonLoader(path)
            loaded = loader.load()

        self.assertEqual(list(loaded["name"]), ["A"])
        self.assertEqual(loaded.geometry.iloc[0], shapely.Point(1, 2))

    def test_geojson_loader_rejects_missing_file_name(self):
        with self.assertRaisesRegex(Exception, "file_name cannot be None"):
            GeoJsonLoader()


class LoaderUtilityTests(unittest.TestCase):
    def test_order_lines_returns_closed_shapes(self):
        shape = order_lines(
            [
                [[0, 0], [1, 0]],
                [[1, 0], [1, 1]],
                [[1, 1], [0, 0]],
            ]
        )

        self.assertEqual(shape, [[[0, 0], [1, 0], [1, 1], [0, 0]]])

    def test_overpass_query_with_cache_uses_sha_file_and_avoids_network_on_hit(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                with patch("loaders.overpass.overpass_query") as query:
                    query.return_value = {"elements": [{"id": 1}]}
                    first = overpass_query_with_cache("query")
                    second = overpass_query_with_cache("query")
            finally:
                os.chdir(cwd)

        self.assertEqual(first, {"elements": [{"id": 1}]})
        self.assertEqual(second, {"elements": [{"id": 1}]})
        query.assert_called_once_with("query")


if __name__ == "__main__":
    unittest.main()
