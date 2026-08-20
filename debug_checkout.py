"""
Debug Checkout Test — tests URL resolution + session creation only.
Does NOT submit a real payment. Stops after checkout session is created.
Run: python debug_checkout.py
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')

# Add bot.py to path so we can import its classes
sys.path.insert(0, os.path.dirname(__file__))

# Import directly from bot.py
import importlib.util
spec = importlib.util.spec_from_file_location("bot", "bot.py")
bot_mod = importlib.util.load_from_spec = None

# Inline the needed pieces rather than importing bot.py (which starts the bot)
import re, requests, random, string, json, base64, warnings
from urllib.parse import urlparse, parse_qs
warnings.filterwarnings('ignore')

# ─── SSL Adapter (copied from bot.py) ──────────────────────────────────────
import ssl
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

class SSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.set_ciphers('DEFAULT:@SECLEVEL=1')
        kwargs['ssl_context'] = ctx
        super().init_poolmanager(*args, **kwargs)

# ─── Minimal BrowserProfile ─────────────────────────────────────────────────
class BrowserProfile:
    def __init__(self):
        self.user_agent = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/131.0.0.0 Safari/537.36")
        self.accept_language = "en-US,en;q=0.9"
        self.sec_ch_ua = '"Not=A?Brand";v="99", "Google Chrome";v="131", "Chromium";v="131"'
        self.platform_name = "Windows"

def rstr(n): return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))
def uuid(): return f"{rstr(8)}-{rstr(4)}-{rstr(4)}-{rstr(4)}-{rstr(12)}"

def broad_plan_id(text):
    candidates = re.findall(r'plan_([A-Za-z0-9]{8,})', text)
    for c in candidates:
        if any(ch.isupper() for ch in c):
            return f'plan_{c}'
    return None

def resolve_url(session, product_url):
    """Resolve any Whop URL to (funnel_id, plan_id)."""
    parsed    = urlparse(product_url)
    qs        = parse_qs(parsed.query)
    aff       = qs.get('a', [None])[0]
    clean     = product_url.split('?')[0].rstrip('/') + '/'
    affiliate = aff or "arnobrip69"

    def try_extract(text):
        f = p = None
        m = re.search(r'"funnelId"\s*:\s*"(product_[0-9a-f\-]{36})"', text)
        if m: f = m.group(1)
        m = re.search(r'"defaultPlan"\s*:\s*\{\s*"id"\s*:\s*"(plan_[A-Za-z0-9]+)"', text)
        if m: p = m.group(1)
        return f, p

    url_no_products = re.sub(r'(https://whop\.com)/[^/]+/products/([^/]+)/?$', r'\1/\2/', clean)
    path_parts      = [p for p in parsed.path.strip('/').split('/') if p]
    url_no_user     = f"https://whop.com/{path_parts[-1]}/" if len(path_parts) >= 2 else None
    url_co_in_url   = re.search(r'/checkout/(plan_[A-Za-z0-9]+)', clean)

    candidates = list(dict.fromkeys(filter(None, [clean, url_no_products, url_no_user])))
    print(f"  Trying candidates: {candidates}")

    funnel = plan = page = None
    for url in candidates:
        r = session.get(url)
        print(f"  {url} → {r.status_code}")
        if r.status_code != 200:
            continue
        f, p = try_extract(r.text)
        if not p: p = broad_plan_id(r.text)
        if not p:
            m = re.search(r'href=["\']https://whop\.com/checkout/(plan_[A-Za-z0-9]+)', r.text)
            if m: p = m.group(1)
        if p:
            funnel, plan, page = f, p, r
            break
        elif not page:
            page = r

    if not plan and url_co_in_url:
        plan = url_co_in_url.group(1)

    return funnel, plan, affiliate


def test_checkout_session(product_url):
    print(f"\n{'='*60}")
    print(f"Testing: {product_url}")
    print('='*60)

    profile   = BrowserProfile()
    csrf      = uuid()
    aff_code  = "arnobrip69"  # default, will be overridden if URL has ?a=

    session = requests.Session()
    session.verify = False
    session.mount('https://', SSLAdapter())
    session.headers.update({
        'accept':                    'text/html,application/xhtml+xml,*/*',
        'accept-language':           profile.accept_language,
        'user-agent':                profile.user_agent,
        'sec-ch-ua':                 profile.sec_ch_ua,
        'sec-ch-ua-mobile':          '?0',
        'sec-ch-ua-platform':        f'"{profile.platform_name}"',
    })
    # Set cookies
    wuid = f"wuid_{rstr(20)}"
    ssk  = uuid()
    for k, v in {
        '__Host-whop-core.csrf-token':   csrf,
        'whop-core.ssk':                 ssk,
        'affiliate_code':                aff_code,
        'whop-core.affiliate-toolsuite': aff_code,
        'whop-frosted-theme':            'appearance:light',
        'whop-theme-resolved':           'light',
        '_wuid':                         wuid,
    }.items():
        session.cookies.set(k, v, domain='.whop.com')

    # Step 1: Resolve URL
    print("\n[1] Resolving URL...")
    funnel_id, plan_id, aff_used = resolve_url(session, product_url)
    print(f"  funnel_id:  {funnel_id}")
    print(f"  plan_id:    {plan_id}")
    print(f"  affiliate:  {aff_used}")

    if not plan_id:
        print("  ❌ FAILED: no plan_id found — cannot proceed")
        return

    # Step 2: Create checkout session
    print("\n[2] Creating checkout session...")
    payload = {
        "plan_id":          plan_id,
        "amount":           1,
        "d2c":              True,
        "return_to":        "/",
        "referring_plan_id": None,
        "tracking_link_id": None,
        "utm": {
            "utm_source":   "whop",
            "utm_medium":   "affiliate",
            "utm_campaign": aff_used,
        },
        "user_agent":       profile.user_agent,
        "source":           "product_page_direct",
        "funnel_id":        funnel_id or None,
    }
    referer = product_url.split('?')[0].rstrip('/') + f'/?a={aff_used}'
    headers = {
        'content-type': 'text/plain;charset=UTF-8',
        'x-csrf':       csrf,
        'origin':       'https://whop.com',
        'referer':      referer,
        'priority':     'u=1, i',
    }
    r = session.post('https://whop.com/checkout/api/', json=payload, headers=headers)
    print(f"  Response: {r.status_code}")

    try:
        data = r.json()
    except Exception:
        print(f"  Raw response: {r.text[:500]}")
        return

    if r.status_code in [200, 201]:
        checkout_id = data.get('id')
        secret      = data.get('secret')
        print(f"  ✅ Checkout session created!")
        print(f"  checkout_id: {checkout_id}")
        print(f"  secret:      {secret[:20]}..." if secret else "  secret: None")
        processors = data.get('processors', [])
        if processors:
            public_key = processors[0].get('processor_config', {}).get('tokenization', {}).get('public_key')
            print(f"  public_key:  {public_key}")
        else:
            print(f"  processors:  {data.get('processors')}")
        print(f"\n  ✅ SUCCESS — can proceed to card tokenization + payment")
    else:
        print(f"  ❌ FAILED: {r.status_code}")
        print(f"  Response: {json.dumps(data, indent=2)[:600]}")


# Test all 3 URLs
test_checkout_session("https://whop.com/thehoovement/products/thehoovement/")
test_checkout_session("https://whop.com/mire-trades/forex-mastery-bundle-a5?a=shubhamind29")
test_checkout_session("https://whop.com/politics-intel/")
