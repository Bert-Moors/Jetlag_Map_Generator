import json

from config.config import Config, Layer
from generator.random_unique import RandomUnique


class QuestionGenerator:
    def __init__(self, output_path: str):
        self._output_path = output_path


    def generate(self, config: Config):
        for q in config.questions:
                for folder in config.folders:
                    if folder.name != q.layer:
                        continue
                    for z in folder.layers:
                        if z.typ != q.data_field:
                            continue
                        if q.type == "matching":
                            self.generate_measuring_question(z, q.name)
                        if q.type == "measuring":
                            self.generate_measuring_question(z, q.name)
                        if q.type == "tentacles":
                            self.generate_tentacle_question(z, q.name)

        pass

    def generate_matching_question(self, layer: Layer, name: str):
        print("generating", name)
        data = layer.loader.load()
        for proc in layer.processors:
            data = proc.process(data)

        jso = {
            "question_name": name,
            "id":RandomUnique.singleton().random(),
            "bla": data.to_json()
        }
        print(jso)

        file = open(self._output_path + "/matching/" + name + ".json", "w")
        file.write(json.dumps(jso))
        file.close()

    def generate_measuring_question(self, layer: Layer, name: str):
        print("generating", name)
        data = layer.loader.load()
        for proc in layer.processors:
            data = proc.process(data)

        jso = {
            "question_name": name,
            "id":RandomUnique.singleton().random(),
            "bla": data.to_json()
        }
        print(jso)

        file = open(self._output_path + "/measuring/" + name + ".json", "w")
        file.write(json.dumps(jso))
        file.close()


    def generate_tentacle_question(self, layer: Layer, name: str):
        print("generating", name)
        data = layer.loader.load()
        for proc in layer.processors:
            data = proc.process(data)

        jso = {
            "question_name": name,
            "id":RandomUnique.singleton().random(),
            "bla": data.to_json()
        }
        print(jso)

        file = open(self._output_path + "/tentacle/" + name + ".json", "w")
        file.write(json.dumps(jso))
        file.close()