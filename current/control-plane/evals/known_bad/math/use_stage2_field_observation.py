import json
from _support import issue, load

problem = load()
rows = sorted(problem["candidates"], key=lambda row: -(row["business_value_units"] or 0))[:10]
print(json.dumps(issue(problem, rows)))
