import requests, re, warnings, sys
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8')

url = 'https://whop.com/politics-intel/'
r = requests.get(url, verify=False, timeout=10, headers={
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'accept': 'text/html'
})

plan = 'plan_QVOSmgcqgwQN6'
idx = r.text.find(plan)
print('Context around plan_:')
print(repr(r.text[max(0, idx-300):idx+300]))
print('\n---\n')

# Search for funnel related keywords
for kw in ['funnelId', 'funnel_id', 'funnel', '"planId"', '"plan_id"', '"id":"plan']:
    idx2 = r.text.find(kw)
    if idx2 != -1:
        print(f'Context around "{kw}":')
        print(repr(r.text[max(0, idx2-50):idx2+200]))
        print()
        break
