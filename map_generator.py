from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / "src"))

import generator as gen

if __name__ == "__main__":
    path = Path("rotterdam.yaml")
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])

    input_path = path if path.parent != Path(".") else Path("input") / path
    output_path = Path("output") / input_path.stem
    map_gen = gen.Generator(str(input_path), str(output_path))
    map_gen.generate()
