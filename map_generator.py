import src.generator as gen
import sys

if __name__ == "__main__":
    path = "arnhem.yaml"
    if len(sys.argv) > 1:
        path = sys.argv[1]
    ext = path.split(".")[-1]

    map_gen = gen.Generator("input/"+path, "output/"+path.split(".")[0])
    map_gen.generate()