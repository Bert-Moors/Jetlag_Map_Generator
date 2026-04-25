import src.generator as gen

if __name__ == "__main__":
    map_gen = gen.Generator("input/input.json", "output/brussels")
    map_gen.generate()