import sys, re
sys.stdout.reconfigure(encoding='utf-8')
from urllib.parse import urlparse, parse_qs
import requests, warnings
warnings.filterwarnings('ignore')

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

def broad_plan_id(text):
    candidates = re.findall(r'plan_([A-Za-z0-9]{8,})', text)
    for c in candidates:
        if any(ch.isupper() for ch in c):
            return f'plan_{c}'
    return None

def try_extract(text):
    funnel = plan = None
    m = re.search(r'"funnelId"\s*:\s*"(product_[0-9a-f\-]{36})"', text)
    if m: funnel = m.group(1)
    m = re.search(r'"defaultPlan"\s*:\s*\{\s*"id"\s*:\s*"(plan_[A-Za-z0-9]+)"', text)
    if m: plan = m.group(1)
    return funnel, plan

def resolve_url(product_url):
    print(f"\n=== Testing: {product_url} ===")
    parsed  = urlparse(product_url)
    qs      = parse_qs(parsed.query)
    aff     = qs.get('a', [None])[0]
    clean   = product_url.split('?')[0].rstrip('/') + '/'
    print(f"  Affiliate extracted: {aff}")

    # Same logic as fixed bot.py
    url_no_products = re.sub(r'(https://whop\.com)/[^/]+/products/([^/]+)/?$', r'\1/\2/', clean)
    path_parts = [p for p in parsed.path.strip('/').split('/') if p]
    url_no_user = f"https://whop.com/{path_parts[-1]}/" if len(path_parts) >= 2 else None
    url_checkout = re.search(r'/checkout/(plan_[A-Za-z0-9]+)', clean)

    # NEW ORDER: original first, then stripped
    candidates = list(dict.fromkeys(filter(None, [clean, url_no_products, url_no_user])))
    print(f"  Candidates: {candidates}")

    funnel = plan = page = None
    for url in candidates:
        r = requests.get(url, verify=False, timeout=12, headers={'user-agent': UA, 'accept': 'text/html'})
        print(f"  Trying {url} -> {r.status_code}")
        if r.status_code != 200:
            continue
        f, p = try_extract(r.text)
        if not p:
            p = broad_plan_id(r.text)
        if not p:
            m = re.search(r'href=["\']https://whop\.com/checkout/(plan_[A-Za-z0-9]+)', r.text)
            if m: p = m.group(1)
        if p:
            funnel, plan, page = f, p, r
            break
        elif not page:
            page = r

    if not plan and url_checkout:
        plan = url_checkout.group(1)

    print(f"  funnel_id: {funnel}")
    print(f"  plan_id:   {plan}")
    print(f"  Result: {'✅ OK' if plan else '❌ FAILED'}")

resolve_url('https://whop.com/thehoovement/products/thehoovement/')
resolve_url('https://whop.com/mire-trades/forex-mastery-bundle-a5?a=shubhamind29')
resolve_url('https://whop.com/steven/products/politics-intel/')
