"""Confirm that the Lean export includes both PROBATIO theorems and their proof terms."""
import json
import sys

targets = {"Probatio.verifier_correct", "Probatio.verifierCle_correct"}
found = set()
names = {0: ""}
with open(sys.argv[1], encoding="utf-8") as source:
    for line in source:
        record = json.loads(line)
        if "in" in record:
            if "str" in record:
                field = record["str"]
                part = field["str"]
            else:
                field = record["num"]
                part = str(field["i"])
            prefix = names[field["pre"]]
            names[record["in"]] = f"{prefix}.{part}" if prefix else part
        if "thm" in record:
            decl = record["thm"]
            name = names[decl["name"]]
            if name in targets:
                if name in found or not isinstance(decl.get("value"), int):
                    sys.exit(f"Missing or duplicate proof term: {name}")
                found.add(name)
if found != targets:
    sys.exit(f"Theorem declarations missing from export: {sorted(targets - found)}")
for name in sorted(found):
    print(f"Export contains theorem and proof term: {name}")
