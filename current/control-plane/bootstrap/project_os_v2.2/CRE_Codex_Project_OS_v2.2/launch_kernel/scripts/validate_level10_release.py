from pathlib import Path
import json, hashlib, sys
ROOT=Path(__file__).resolve().parents[1]
errors=[]
required=[
 'standards/BENCHMARK_STANDARD_REGISTRY.json','standards/BENCHMARK_CROSSWALK.md',
 'control/LEVEL10_DOMAIN_DEFINITIONS.json','control/PRE_CODEX_LEVEL10_POLICY.md',
 'evals/LEVEL10_BENCHMARKS.json','scripts/run_level10_simulation.py',
 'scripts/run_level10_campaign.py','artifacts/level10/full_system_simulation.json',
 'artifacts/level10/campaign.json'
]
for r in required:
    if not (ROOT/r).exists(): errors.append('missing:'+r)
sim=json.loads((ROOT/'artifacts/level10/full_system_simulation.json').read_text())
if not sim['summary']['all_scenarios_passed']: errors.append('simulation-failed')
if not sim['summary']['all_domains_pre_codex_design_score_10']: errors.append('domain-design-not-10')
if sim['summary']['empirical_claims_proven'] is not False: errors.append('empirical-overclaim')
if len(sim['domain_scores'])!=24: errors.append('expected-24-domains')
if len(json.loads((ROOT/'standards/BENCHMARK_STANDARD_REGISTRY.json').read_text())['standards'])<15: errors.append('standards-under-15')
result={'passed':not errors,'errors':errors,'domains':len(sim['domain_scores']),'scenarios':sim['summary']['scenario_count'],'design_level_10_domains':sum(x['design_and_evaluator_readiness_score']==10 for x in sim['domain_scores']),'empirical_claims_proven':False}
out=ROOT/'artifacts/level10/release_validation.json'; out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2)); sys.exit(0 if not errors else 1)
