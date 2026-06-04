import json
import os
import sys
import tempfile
import unittest


ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from generator.config.config_loaders import (  # noqa: E402
    dict_to_config,
    load_config,
    load_toml_config,
)
from generator.exporters.exporters import GoogleMyMapsKmlExporter, FullKmlExporter  # noqa: E402
from loaders.loaders import OverpassLoader  # noqa: E402
from processors.add_column import AddColumn  # noqa: E402
from processors.rename import Rename  # noqa: E402


class ConfigLoaderTests(unittest.TestCase):
    def test_dict_to_config_builds_default_exporter_layers_datasources_and_processors(self):
        config = dict_to_config(
            {
                "config": {"name": "sample"},
                "layers": {
                    "Transit": {
                        "processors": [{"name": "rename_column", "columns": {"old": "new"}}],
                        "bus": {
                            "query": "[out:json][timeout:1];node(1);out;",
                            "geom_type": "points",
                            "processors": [
                                {"name": "add_column", "columns": {"source": "test"}}
                            ],
                        },
                    }
                },
            }
        )

        self.assertEqual(config.name, "sample")
        self.assertEqual(len(config.exporters), 1)
        self.assertIsInstance(config.exporters[0], GoogleMyMapsKmlExporter)
        self.assertEqual(len(config.layers), 1)
        self.assertEqual(config.layers[0].name, "Transit")
        self.assertIsInstance(config.layers[0].processors[0], Rename)
        self.assertEqual(len(config.layers[0].datasources), 1)
        self.assertEqual(config.layers[0].datasources[0].name_type, "bus")
        self.assertIsInstance(config.layers[0].datasources[0].loader, OverpassLoader)
        self.assertIsInstance(config.layers[0].datasources[0].processors[0], AddColumn)

    def test_dict_to_config_uses_explicit_exporters(self):
        config = dict_to_config(
            {
                "config": {"name": "sample", "exporters": ["fullkml"]},
                "layers": {"Layer": {"source": {"query": "q", "geom_type": "points"}}},
            }
        )

        self.assertEqual(len(config.exporters), 1)
        self.assertIsInstance(config.exporters[0], FullKmlExporter)

    def test_dict_to_config_rejects_missing_required_sections(self):
        with self.assertRaisesRegex(Exception, "config not defined"):
            dict_to_config({"layers": {}})

        with self.assertRaisesRegex(Exception, "layers are not defined"):
            dict_to_config({"config": {"name": "configured"}})

    def test_dict_to_config_rejects_datasource_without_loader(self):
        with self.assertRaisesRegex(Exception, "datasource source not configured properly"):
            dict_to_config({"config": {"name": "configured"}, "layers": {"Layer": {"source": {}}}})

    def test_load_config_dispatches_json_yaml_and_rejects_unknown_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            json_path = os.path.join(tmp, "config.json")
            yaml_path = os.path.join(tmp, "config.yaml")
            payload = {
                "config": {"name": "from-file"},
                "layers": {"Layer": {"source": {"query": "q", "geom_type": "points"}}},
            }
            with open(json_path, "w", encoding="utf-8") as file:
                json.dump(payload, file)
            with open(yaml_path, "w", encoding="utf-8") as file:
                file.write(
                    "config:\n"
                    "  name: from-yaml\n"
                    "layers:\n"
                    "  Layer:\n"
                    "    source:\n"
                    "      query: q\n"
                    "      geom_type: points\n"
                )

            self.assertEqual(load_config(json_path).name, "from-file")
            self.assertEqual(load_config(yaml_path).name, "from-yaml")

            with self.assertRaisesRegex(Exception, "Wrong config loading format"):
                load_config(os.path.join(tmp, "config.txt"))

        with self.assertRaisesRegex(Exception, "file_name cannot be None"):
            load_config(None)

    def test_load_toml_config_merges_extra_top_level_tables_into_layers(self):
        with tempfile.TemporaryDirectory() as tmp:
            toml_path = os.path.join(tmp, "config.toml")
            with open(toml_path, "w", encoding="utf-8") as file:
                file.write(
                    '[config]\nname = "toml-map"\n\n'
                    '[Extra.source]\nquery = "q"\ngeom_type = "points"\n'
                )

            data = load_toml_config(toml_path)

        self.assertEqual(data["config"]["name"], "toml-map")
        self.assertIn("Extra", data["layers"])
        self.assertEqual(data["layers"]["Extra"]["source"]["geom_type"], "points")


if __name__ == "__main__":
    unittest.main()
