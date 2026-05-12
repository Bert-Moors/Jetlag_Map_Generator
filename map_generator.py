import src.generator as gen
import sys
if __name__ == "__main__":
    print(sys.argv)
    path = "brussels.toml"
    if len(sys.argv) > 1:
        path = sys.argv[1]
    ext = path.split(".")[-1]
    if ext == "json":
        map_gen = gen.Generator("input/"+path, "output/"+path.split(".")[0])
    if ext == "toml":
        map_gen = gen.Generator("input/"+path, "output/"+path.split(".")[0], typ="toml")

    map_gen.generate()