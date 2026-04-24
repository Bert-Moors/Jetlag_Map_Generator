import json
import os
from _sha2 import sha256
from typing import Dict
import requests
from pyogrio._io import Path

#---------------Globals---------------
overpass_mirrors = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter"
]
#--------------Functions--------------
def overpass_query(query: str) -> Dict:
    tries = 0
    # retry request with different interpreters until you get 200 response
    while True:
        try:
            response = requests.get(
                overpass_mirrors[tries % len(overpass_mirrors)],
                data=query,
                timeout=10,
                headers={"User-Agent": "mapgenerator/1.0"})
            print(response.status_code)
            tries += 1
            if response.status_code == 200:
                break
        except requests.exceptions.Timeout:
            print("timed out")
            tries += 1

    print(f"Gathered data in {tries} tries.")
    return json.loads(response.text)

def overpass_query_with_cache(query:str):
    ky = sha256(query.encode("utf-8"))
    if not os.path.isdir("_cache"):
        os.mkdir("_cache")
    my_file = Path("_cache/" + ky.hexdigest() + ".json")
    try:
        my_abs_path = my_file.resolve(strict=True)
        with open(my_abs_path, encoding="utf-8") as file:
            print("reloaded from file")
            return json.load(file)
    except FileNotFoundError:
        json_data = overpass_query(query)
        my_file.write_text(json.dumps(json_data))
        return json_data