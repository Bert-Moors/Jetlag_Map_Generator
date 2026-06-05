import os
import sys
import tempfile
import unittest


ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from generator.generator import Generator  # noqa: E402


class LiveOverpassE2ETests(unittest.TestCase):
    def test_sample_yaml_generates_mymaps_and_hiding_zone_exports_from_live_overpass(self):
        config_path = os.path.join(ROOT, "tests", "fixtures", "live_overpass_e2e.yaml")

        with tempfile.TemporaryDirectory() as output_dir:
            Generator(config_path, output_dir).generate()

            mymaps_path = os.path.join(output_dir, "live-overpass-e2e GMM.kml")
            hiding_zones_path = os.path.join(output_dir, "live-overpass-e2e HZ.kml")

            self.assertTrue(os.path.exists(mymaps_path))
            self.assertTrue(os.path.exists(hiding_zones_path))

            with open(mymaps_path, encoding="utf-8") as file:
                mymaps = file.read()
            with open(hiding_zones_path, encoding="utf-8") as file:
                hiding_zones = file.read()

        self.assertIn("Transit", mymaps)
        self.assertIn("Arnhem Centraal", mymaps)
        self.assertIn("station", mymaps)
        self.assertIn("Hiding Zones", hiding_zones)
        self.assertIn("Arnhem Centraal", hiding_zones)


if __name__ == "__main__":
    unittest.main()
