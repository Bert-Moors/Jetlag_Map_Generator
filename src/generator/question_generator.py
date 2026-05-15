import json
import random
from typing import Any

from config.config import Config, Layer



class QuestionGenerator:
    def __init__(self, output_path: str):
        self._output_path = output_path
        self.nums = set()

    def random(self):
        while True:
            num = random.random()
            if num not in self.nums:
                self.nums.add(num)
                return num

    def generate(self, config: Config):
        for q in config.questions:
                for folder in config.folders:
                    if folder.name != q.layer:
                        continue
                    for z in folder.layers:
                        if z.typ != q.data_field:
                            continue
                        if q.type == "matching":
                            self.generate_matching_question(z, q.name)
                        if q.type == "measuring":
                            self.generate_measuring_question(z, q.name)
                        if q.type == "tentacles":
                            self.generate_tentacle_question(z, q.name)

        pass

    @staticmethod
    def as_feature_collection(payload: dict[str, Any]) -> dict[str, Any]:
        payload_type = payload.get("type")

        if payload_type == "FeatureCollection":
            features = payload.get("features")
            if not isinstance(features, list):
                raise ValueError("FeatureCollection is missing a features array")
            return payload

        if payload_type == "Feature":
            return {"type": "FeatureCollection", "features": [payload]}

        return {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": {}, "geometry": payload}],
        }

    @staticmethod
    def polygon_parts(geometry: dict[str, Any]) -> list[list[list[list[float]]]]:
        geometry_type = geometry.get("type")
        coordinates = geometry.get("coordinates")

        if geometry_type == "Polygon":
            return [coordinates]
        if geometry_type == "MultiPolygon":
            return coordinates

        raise ValueError(f"Geometry type {geometry_type} cannot be used for matching zones")


    @staticmethod
    def build_matching_geo(feature_collection: dict[str, Any]) -> tuple[str, Any]:
        features = feature_collection["features"]
        if features is None:
            raise ValueError("Feature collection is missing a feature")
        geometry_types = {feature.get("geometry", {}).get("type") for feature in features}
        if geometry_types == {"Point"}:
            return "custom-points", features

        if geometry_types.issubset({"Polygon", "MultiPolygon", "Point"}):
            coordinates: list[list[list[list[float]]]] = []
            collected_properties: list[dict[str, Any]] = []

            for feature in features:
                coordinates.extend(QuestionGenerator.polygon_parts(feature["geometry"]))
                properties = feature.get("properties")
                if isinstance(properties, dict) and properties:
                    collected_properties.append(properties)

            return (
                "custom-zone",
                feature_collection
            )

        raise ValueError("AHI")

    def generate_matching_question(self, layer: Layer, name: str):
        print("generating", name)
        data = layer.loader.load()
        ctr = data.centroid[0]
        for proc in layer.processors:
            data = proc.process(data)
        typ, dct = self.build_matching_geo(self.as_feature_collection(data.to_geo_dict()))

        jso = {
            "question_name": name,
            "id": "matching",
            "key":self.random(),
            "data": {
                "type": typ,
                "lat": ctr.y,
                "lng": ctr.x,
                "geo": dct,
            }
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
        dct = self.as_feature_collection(data.to_geo_dict())
        ctr = data.centroid[0]
        jso = {
            "question_name": name,
            "id": "measuring",
            "key": self.random(),
            "data": {
                "type": "custom-measure",
                "lat": ctr.y,
                "lng": ctr.x,
                "geo": dct
            }
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
            "id": "tentacle",
            "key": self.random(),
            "data": data.to_json()
        }
        print(jso)

        file = open(self._output_path + "/tentacle/" + name + ".json", "w")
        file.write(json.dumps(jso))
        file.close()