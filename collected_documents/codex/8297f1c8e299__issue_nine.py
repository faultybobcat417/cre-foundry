import json
from _support import issue, load

problem = load()
print(json.dumps(issue(problem, problem["candidates"][:9])))
