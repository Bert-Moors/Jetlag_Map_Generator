import src.generator as gen
import sys

from config.config import Config
from generator.matching_generator import QuestionGenerator

if __name__ == "__main__":
    print(sys.argv)
    path = "brussels.toml"
    if len(sys.argv) > 1:
        path = sys.argv[1]
    ext = path.split(".")[-1]
    cfg = Config("input/"+path)

    map_gen = gen.Generator("output/"+path.split(".")[0])
    map_gen.generate(cfg)

    QuestionGenerator("output/" + path.split(".")[0]).generate(cfg)