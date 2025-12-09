""" test utils class """

import os
import json
from starlette.testclient import TestClient

def load_resource(path: str) -> dict:
    "load resource"
    result = {}

    with open(path, "br") as file:
        result["audio"] = file.read()

    return result