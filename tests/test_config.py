import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.yaml_config import load_string_mapping


class ConfigMappingTest(unittest.TestCase):
    def test_gics_sector_mapping_loads_from_yaml(self):
        mapping = load_string_mapping(ROOT_DIR / "config" / "gics_sectors.yaml", "gics_sectors")
        self.assertEqual(mapping["Information Technology"], "Information_Technology")
        self.assertEqual(len(mapping), 11)


if __name__ == "__main__":
    unittest.main()
