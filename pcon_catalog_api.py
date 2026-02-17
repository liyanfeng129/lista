#!/usr/bin/env python3
"""
pCon Catalog API Discovery & Interaction Script

Discovers and interacts with the API behind https://catalogs.pcon-solutions.com/#/

Based on reverse-engineering research:
- The site is a Single Page Application (SPA) with hash-based routing (#/)
- Internal services use "arglobe" as a namespace:
  - arglobe_sidekick/v1/ — serves manufacturer content and files
  - arglobe_insight/ — admin/insight panel
- Related pCon APIs: Gatekeeper (EAIWS sessions), PI-API (product info), pCon.login (OAuth)
"""

import requests
import json
import re
import sys
import time
from urllib.parse import urljoin, urlparse

BASE_URL = "https://catalogs.pcon-solutions.com"
DEMO_URL = "https://demo.catalogs.pcon-solutions.com"
PORTAL_URL = "https://portal.pcon-catalog.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
              "image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}

API_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

# Known manufacturer org IDs discovered via search engine indexing
KNOWN_MANUFACTURERS = {
    "FDB Møbler": "o-14e76d60c01b488b9deb8887303b6601",
    "Sedus Stoll AG": "o-a91782efa59b4876b75ba63cbfcef575",
}


def log(msg, level="INFO"):
    colors = {"INFO": "\033[94m", "OK": "\033[92m", "WARN": "\033[93m",
              "ERR": "\033[91m", "RESET": "\033[0m"}
    print(f"{colors.get(level, '')}{level}: {msg}{colors['RESET']}")


class PConCatalogAPI:
    """Discover and interact with the pCon Catalog API."""

    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.discovered_endpoints = []
        self.discovered_js_files = []
        self.api_base = None

    def fetch_main_page(self):
        """Fetch the main page HTML to find JS bundles and inline config."""
        log("Fetching main page HTML...")
        try:
            resp = self.session.get(self.base_url, timeout=15)
            resp.raise_for_status()
            html = resp.text
            log(f"Got {len(html)} bytes, status {resp.status_code}", "OK")

            # Extract script tags
            scripts = re.findall(
                r'<script[^>]*(?:src=["\']([^"\']+)["\'])?[^>]*>(.*?)</script>',
                html, re.DOTALL
            )

            js_files = []
            inline_configs = []
            for src, body in scripts:
                if src:
                    full_url = urljoin(self.base_url + "/", src)
                    js_files.append(full_url)
                    log(f"  JS bundle: {full_url}")
                if body.strip():
                    inline_configs.append(body.strip())
                    # Look for config objects
                    config_patterns = [
                        r'(?:window\.__CONFIG__|config|environment)\s*=\s*({.*?});',
                        r'(?:apiUrl|apiBase|baseUrl|API_URL)\s*[:=]\s*["\']([^"\']+)["\']',
                    ]
                    for pat in config_patterns:
                        matches = re.findall(pat, body, re.DOTALL)
                        for m in matches:
                            log(f"  Config found: {m[:200]}", "OK")

            self.discovered_js_files = js_files

            # Also look for meta tags with API info
            meta_matches = re.findall(
                r'<meta[^>]*name=["\']([^"\']*api[^"\']*)["\'][^>]*content=["\']([^"\']+)["\']',
                html, re.IGNORECASE
            )
            for name, content in meta_matches:
                log(f"  Meta API config: {name}={content}", "OK")

            return html, js_files, inline_configs
        except requests.RequestException as e:
            log(f"Failed to fetch main page: {e}", "ERR")
            return None, [], []

    def analyze_js_bundles(self, js_files, max_bundles=5):
        """Download and analyze JS bundles for API endpoint patterns."""
        log(f"Analyzing up to {max_bundles} JS bundles for API patterns...")
        api_endpoints = set()

        for js_url in js_files[:max_bundles]:
            try:
                log(f"  Fetching: {js_url}")
                resp = self.session.get(js_url, timeout=15)
                if resp.status_code != 200:
                    log(f"    Status {resp.status_code}, skipping", "WARN")
                    continue

                js_code = resp.text
                log(f"    Got {len(js_code)} bytes")

                # Search for API URL patterns in the JS code
                patterns = [
                    # Direct API URL strings
                    r'["\'](/api/v\d+/[^"\']+)["\']',
                    r'["\'](/arglobe[^"\']+)["\']',
                    r'["\'](https?://[^"\']*pcon[^"\']*api[^"\']*)["\']',
                    # Fetch/XHR calls
                    r'fetch\(["\']([^"\']+)["\']',
                    r'\.(?:get|post|put|delete)\(["\']([^"\']+)["\']',
                    # API path construction
                    r'apiUrl\s*\+\s*["\']([^"\']+)["\']',
                    r'baseUrl\s*\+\s*["\']([^"\']+)["\']',
                    # Endpoint definitions
                    r'endpoint[s]?\s*[:=]\s*["\']([^"\']+)["\']',
                    r'url\s*[:=]\s*["\'](/[^"\']{5,})["\']',
                    # arglobe-specific patterns
                    r'arglobe_sidekick(/[^"\']+)',
                    r'arglobe_insight(/[^"\']+)',
                    r'arglobe(/[^"\']+)',
                ]

                for pat in patterns:
                    matches = re.findall(pat, js_code)
                    for m in matches:
                        if len(m) > 3 and not m.endswith(('.js', '.css', '.png',
                                '.jpg', '.svg', '.woff', '.ttf', '.map')):
                            api_endpoints.add(m)

                # Look for base URL / API config
                base_patterns = [
                    r'(?:API_BASE|apiBase|API_URL|apiUrl|BASE_URL|baseUrl)\s*[:=]\s*["\']([^"\']+)["\']',
                    r'(?:environment|config)\s*\.\s*(?:api|apiUrl|baseUrl)\s*[:=]\s*["\']([^"\']+)["\']',
                ]
                for pat in base_patterns:
                    matches = re.findall(pat, js_code)
                    for m in matches:
                        log(f"    API Base URL found: {m}", "OK")
                        self.api_base = m

            except requests.RequestException as e:
                log(f"    Error: {e}", "WARN")

        if api_endpoints:
            log(f"Found {len(api_endpoints)} potential API endpoints:", "OK")
            for ep in sorted(api_endpoints):
                log(f"    {ep}")
        else:
            log("No API endpoints found in JS bundles", "WARN")

        self.discovered_endpoints = list(api_endpoints)
        return api_endpoints

    def probe_common_api_patterns(self):
        """Probe common REST API patterns that the SPA might use."""
        log("Probing common API endpoint patterns...")

        # Based on research: arglobe_sidekick is a confirmed service
        # Also try standard REST patterns
        probe_paths = [
            # Known working patterns from search engine indexing
            "/arglobe_sidekick/v1/files/o-a91782efa59b4876b75ba63cbfcef575/welcome",

            # Likely arglobe API patterns
            "/arglobe_sidekick/v1/manufacturers",
            "/arglobe_sidekick/v1/catalogs",
            "/arglobe_sidekick/v1/search",
            "/arglobe_sidekick/v1/categories",
            "/arglobe_sidekick/v1/products",
            "/arglobe_sidekick/v1/organizations",
            "/arglobe_sidekick/v1/files",

            # Standard REST API patterns
            "/api/v1/manufacturers",
            "/api/v1/catalogs",
            "/api/v1/search",
            "/api/v1/categories",
            "/api/v1/products",
            "/api/v2/manufacturers",
            "/api/v2/catalogs",
            "/api/v2/search",
            "/api/manufacturers",
            "/api/catalogs",
            "/api/search",
            "/api/config",

            # GraphQL
            "/graphql",
            "/api/graphql",

            # Common SPA backend patterns
            "/rest/v1/catalogs",
            "/rest/v1/manufacturers",
            "/backend/api/catalogs",
            "/backend/api/manufacturers",
            "/data/catalogs.json",
            "/data/manufacturers.json",
            "/assets/data/catalogs.json",
            "/config.json",
            "/app-config.json",
            "/environment.json",

            # Insight API (admin panel exists, API likely nearby)
            "/arglobe_insight/api/v1/catalogs",
            "/arglobe_insight/api/v1/manufacturers",
            "/arglobe_insight/api/v1/search",
            "/arglobe_insight/api/catalogs",
            "/arglobe_insight/api/manufacturers",
        ]

        results = {}
        self.session.headers.update(API_HEADERS)

        for path in probe_paths:
            url = f"{self.base_url}{path}"
            try:
                resp = self.session.get(url, timeout=10, allow_redirects=False)
                status = resp.status_code
                content_type = resp.headers.get("Content-Type", "")
                content_length = len(resp.content)

                if status in (200, 201):
                    level = "OK"
                    icon = "[HIT]"
                elif status in (301, 302, 307, 308):
                    level = "WARN"
                    icon = "[REDIRECT]"
                    location = resp.headers.get("Location", "?")
                    log(f"  {icon} {status} {path} -> {location}", level)
                    results[path] = {
                        "status": status,
                        "redirect": location,
                        "content_type": content_type,
                    }
                    continue
                elif status == 401:
                    level = "WARN"
                    icon = "[AUTH REQUIRED]"
                elif status == 403:
                    level = "WARN"
                    icon = "[FORBIDDEN]"
                elif status == 404:
                    level = "INFO"
                    icon = "[NOT FOUND]"
                    # Don't log 404s to reduce noise
                    continue
                else:
                    level = "WARN"
                    icon = f"[{status}]"

                log(f"  {icon} {status} {path} ({content_type}, {content_length}b)", level)

                if status == 200:
                    # Try to parse JSON
                    try:
                        data = resp.json()
                        log(f"    JSON response keys: {list(data.keys()) if isinstance(data, dict) else f'array[{len(data)}]'}", "OK")
                        results[path] = {
                            "status": status,
                            "content_type": content_type,
                            "data_preview": json.dumps(data, indent=2)[:500],
                        }
                    except (json.JSONDecodeError, ValueError):
                        # Check if it's HTML (might be the SPA fallback)
                        if "text/html" in content_type:
                            if content_length < 5000:
                                results[path] = {
                                    "status": status,
                                    "content_type": content_type,
                                    "note": "HTML response (likely SPA fallback)",
                                }
                        else:
                            results[path] = {
                                "status": status,
                                "content_type": content_type,
                                "size": content_length,
                            }
                elif status in (401, 403):
                    results[path] = {
                        "status": status,
                        "content_type": content_type,
                        "note": "Endpoint exists but requires auth" if status == 401 else "Forbidden",
                    }

            except requests.RequestException as e:
                log(f"  [ERROR] {path}: {e}", "ERR")

        return results

    def get_manufacturer_welcome(self, org_id):
        """Fetch a manufacturer's welcome page via arglobe_sidekick."""
        url = f"{self.base_url}/arglobe_sidekick/v1/files/{org_id}/welcome"
        log(f"Fetching manufacturer welcome page: {org_id}")
        try:
            resp = self.session.get(url, timeout=15)
            log(f"  Status: {resp.status_code}, Content-Type: {resp.headers.get('Content-Type', '?')}",
                "OK" if resp.status_code == 200 else "WARN")
            if resp.status_code == 200:
                return resp.text
            return None
        except requests.RequestException as e:
            log(f"  Error: {e}", "ERR")
            return None

    def discover_from_manufacturer_page(self, html):
        """Parse a manufacturer welcome page to find more API endpoints."""
        if not html:
            return []

        endpoints = set()
        # Look for API calls, image URLs, data URLs
        patterns = [
            r'(?:href|src|data-src)=["\']([^"\']*arglobe[^"\']*)["\']',
            r'(?:href|src|data-src)=["\']([^"\']*api[^"\']*)["\']',
            r'(?:href|src|data-src)=["\']([^"\']*sidekick[^"\']*)["\']',
            r'["\']([^"\']*arglobe_sidekick/v1/[^"\']+)["\']',
        ]
        for pat in patterns:
            matches = re.findall(pat, html, re.IGNORECASE)
            endpoints.update(matches)

        if endpoints:
            log(f"Found {len(endpoints)} endpoints from manufacturer page:", "OK")
            for ep in sorted(endpoints):
                log(f"    {ep}")
        return list(endpoints)

    def try_search_api(self, query="chair"):
        """Try common search API patterns."""
        log(f"Trying search endpoints with query: '{query}'...")

        search_patterns = [
            ("/api/v1/search", {"q": query}),
            ("/api/v2/search", {"q": query}),
            ("/api/search", {"q": query}),
            ("/arglobe_sidekick/v1/search", {"q": query}),
            ("/search", {"q": query}),
            ("/api/v1/products", {"search": query}),
            ("/api/v1/catalogs", {"search": query}),
            ("/graphql", None),  # Will need POST
        ]

        results = {}
        for path, params in search_patterns:
            url = f"{self.base_url}{path}"
            try:
                if path == "/graphql":
                    # Try GraphQL introspection
                    gql_query = {
                        "query": '{ __schema { queryType { name fields { name } } } }'
                    }
                    resp = self.session.post(url, json=gql_query, timeout=10)
                else:
                    resp = self.session.get(url, params=params, timeout=10)

                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        log(f"  [HIT] {path} returned JSON", "OK")
                        results[path] = data
                    except (json.JSONDecodeError, ValueError):
                        if "text/html" not in resp.headers.get("Content-Type", ""):
                            log(f"  [HIT] {path} returned non-JSON ({resp.headers.get('Content-Type', '?')})", "OK")
                elif resp.status_code not in (404,):
                    log(f"  [{resp.status_code}] {path}", "WARN")
            except requests.RequestException:
                pass

        return results

    def full_discovery(self):
        """Run complete API discovery."""
        log("=" * 60)
        log("pCon Catalog API Discovery")
        log(f"Target: {self.base_url}")
        log("=" * 60)

        results = {
            "base_url": self.base_url,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "steps": {},
        }

        # Step 1: Fetch and analyze main page
        log("\n--- Step 1: Main Page Analysis ---")
        html, js_files, inline_configs = self.fetch_main_page()
        results["steps"]["main_page"] = {
            "js_files": js_files,
            "inline_configs_count": len(inline_configs),
        }

        # Step 2: Analyze JS bundles
        if js_files:
            log("\n--- Step 2: JS Bundle Analysis ---")
            api_endpoints = self.analyze_js_bundles(js_files)
            results["steps"]["js_analysis"] = {
                "endpoints_found": list(api_endpoints),
                "api_base": self.api_base,
            }

        # Step 3: Probe common API patterns
        log("\n--- Step 3: API Endpoint Probing ---")
        probe_results = self.probe_common_api_patterns()
        results["steps"]["probe"] = probe_results

        # Step 4: Fetch known manufacturer pages
        log("\n--- Step 4: Manufacturer Page Analysis ---")
        for name, org_id in KNOWN_MANUFACTURERS.items():
            log(f"\nManufacturer: {name} ({org_id})")
            mfg_html = self.get_manufacturer_welcome(org_id)
            if mfg_html:
                extra_endpoints = self.discover_from_manufacturer_page(mfg_html)
                results["steps"][f"manufacturer_{name}"] = {
                    "org_id": org_id,
                    "page_size": len(mfg_html),
                    "extra_endpoints": extra_endpoints,
                }

        # Step 5: Try search APIs
        log("\n--- Step 5: Search API Discovery ---")
        search_results = self.try_search_api("chair")
        results["steps"]["search"] = {
            "query": "chair",
            "working_endpoints": list(search_results.keys()),
        }

        # Summary
        log("\n" + "=" * 60)
        log("DISCOVERY SUMMARY")
        log("=" * 60)

        all_working = {}
        if probe_results:
            for path, info in probe_results.items():
                if info.get("status") == 200:
                    all_working[path] = info

        if search_results:
            for path, data in search_results.items():
                all_working[f"{path} (search)"] = {"data_preview": str(data)[:200]}

        if all_working:
            log(f"Found {len(all_working)} working endpoints:", "OK")
            for path, info in all_working.items():
                log(f"  {path}")
                if "data_preview" in info:
                    log(f"    Preview: {info['data_preview'][:200]}")
        else:
            log("No directly accessible REST endpoints found.", "WARN")
            log("The site likely requires authentication via pCon.login (OAuth2).", "WARN")
            log("See: https://login.pcon-solutions.com/doc/api/", "INFO")

        log("\nKnown working URL patterns:", "INFO")
        log("  /arglobe_sidekick/v1/files/{org-id}/welcome  (manufacturer pages)", "INFO")
        log("  /arglobe_insight/insight-ui/                  (admin panel)", "INFO")
        log("  /configuration/?v=2.3.4                       (product configurator)", "INFO")
        log("  /editor/                                      (catalog editor)", "INFO")

        log("\nRelated pCon APIs:", "INFO")
        log("  Gatekeeper: https://docs.pcon-solutions.com/webservice/gatekeeper/v3/", "INFO")
        log("  PI-API:     https://docs.pcon-solutions.com/webservice/PIM/PI-API/PI-API.pdf", "INFO")
        log("  Login/Auth: https://login.pcon-solutions.com/doc/api/", "INFO")
        log("  Basket:     https://integration.basket.pcon-solutions.com/doc/integration/latest/", "INFO")

        # Save results
        output_file = "pcon_api_discovery.json"
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
        log(f"\nResults saved to {output_file}", "OK")

        return results


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="pCon Catalog API Discovery & Interaction Script"
    )
    parser.add_argument(
        "--url", default=BASE_URL,
        help=f"Base URL (default: {BASE_URL})"
    )
    parser.add_argument(
        "--discover", action="store_true", default=True,
        help="Run full API discovery (default)"
    )
    parser.add_argument(
        "--manufacturer", type=str,
        help="Fetch a specific manufacturer page by org ID (e.g. o-a91782efa59b4876b75ba63cbfcef575)"
    )
    parser.add_argument(
        "--search", type=str,
        help="Try searching the API with a query string"
    )
    parser.add_argument(
        "--probe-only", action="store_true",
        help="Only probe API endpoints without fetching JS bundles"
    )

    args = parser.parse_args()
    api = PConCatalogAPI(args.url)

    if args.manufacturer:
        html = api.get_manufacturer_welcome(args.manufacturer)
        if html:
            print(html[:2000])
            api.discover_from_manufacturer_page(html)
    elif args.search:
        results = api.try_search_api(args.search)
        if results:
            print(json.dumps(results, indent=2, default=str))
        else:
            log("No search results from any endpoint", "WARN")
    elif args.probe_only:
        results = api.probe_common_api_patterns()
        print(json.dumps(results, indent=2, default=str))
    else:
        api.full_discovery()


if __name__ == "__main__":
    main()
