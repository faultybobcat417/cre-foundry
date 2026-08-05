import json
from _support import issue, load

problem = load()
rows = sorted(problem["candidates"], key=lambda row: (row["proximity_cost_units"], row["candidate_id"]))[:10]
print(json.dumps(issue(problem, rows)))
