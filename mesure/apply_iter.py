import sys
import json
from camilladsp import CamillaClient

with open(sys.argv[1]) as f:
    changes = json.load(f)
c = CamillaClient('127.0.0.1', 1234)
c.connect()
for name, gain in changes.items():
    c.config.set_value(f"/filters/{name}/parameters/gain", gain)
    print(f"{name} -> {gain}")
