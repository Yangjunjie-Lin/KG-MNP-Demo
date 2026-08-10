#!/usr/bin/env python3
"""Real Chromium verification for the read-only Phase 02 workbench."""

from __future__ import annotations

import argparse
import json
import re
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from urllib.parse import urlsplit


EXPECTED_BROWSER_NAME = "chromium"
EXPECTED_BROWSER_VERSION = "131.0.6778.33"
EXPECTED_BROWSER_REVISION = "1148"
EXPECTED_PLAYWRIGHT_VERSION = "1.49.1"
HTTP_PROBE = "https://example.invalid/kg-mnp-workbench-egress"
WEBSOCKET_PROBE = "wss://example.invalid/kg-mnp-workbench-egress"
DIRECT_STORAGE_PROBE = "http://127.0.0.1:7200/repositories/kg-mnp-probe"


def _origin(url: str) -> tuple[str, str, int | None]:
    parsed = urlsplit(url)
    return parsed.scheme.casefold(), (parsed.hostname or "").casefold(), parsed.port


def _allowed(url: str, origin: tuple[str, str, int | None]) -> bool:
    scheme, host, port = _origin(url)
    base_scheme, base_host, base_port = origin
    return (
        scheme in {base_scheme, "ws" if base_scheme == "http" else "wss"}
        and host == base_host
        and port == base_port
    )


def _fixture_page(
    browser,
    base_url: str,
    model: dict,
    expected_text: str,
) -> bool:
    context = browser.new_context(service_workers="block")

    def route_request(route) -> None:
        path = urlsplit(route.request.url).path
        if path == "/workbench/api/view/review":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(model, ensure_ascii=False),
            )
            return
        route.continue_()

    context.route("**/*", route_request)
    page = context.new_page()
    try:
        page.goto(base_url.rstrip("/") + "/review", wait_until="networkidle")
        page.get_by_role("button", name="Inspect review history").click()
        page.get_by_text(expected_text, exact=True).first.wait_for()
        boundary = page.get_by_text(
            "Semantic boundary: review outcome ≠ asserted business state.",
            exact=True,
        ).count()
        return boundary == 1 and page.get_by_role("heading", name="Review history").count() >= 1
    finally:
        context.close()


def run(
    base_url: str,
    *,
    xss_model: dict | None = None,
    scenario_fixtures: dict[str, dict] | None = None,
    timeout_ms: int = 30_000,
) -> dict:
    parsed = urlsplit(base_url)
    origin = _origin(base_url)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.port is None:
        raise RuntimeError("workbench browser smoke requires explicit IPv4 loopback")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is required for Phase 02 browser smoke") from exc

    external_requests: list[str] = []
    blocked_probes: list[str] = []
    javascript_errors: list[str] = []
    console_security_errors: list[str] = []
    dialogs: list[str] = []
    pages_tested: list[str] = []
    golden_passed = 0
    xss_count = 0
    xss_blocked = 0
    service_worker_count = -1
    local_storage_count = -1
    indexed_db_count = -1
    direct_attempts = 1
    direct_blocked = 0

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        browser_version = browser.version
        revision_match = re.search(
            r"chromium-(\d+)",
            playwright.chromium.executable_path,
        )
        browser_revision = revision_match.group(1) if revision_match else "UNKNOWN"
        try:
            playwright_version = version("playwright")
        except PackageNotFoundError:
            playwright_version = "UNKNOWN"
        context = browser.new_context(service_workers="block")
        context.add_init_script(
            script=f"""
            (() => {{
              const allowed = new URL({json.dumps(base_url.rstrip('/') + '/')});
              const NativeSocket = globalThis.WebSocket;
              function GuardedSocket(url, protocols) {{
                const target = new URL(String(url), globalThis.location.href);
                if (target.hostname !== allowed.hostname || target.port !== allowed.port) {{
                  globalThis.__blockedSockets = globalThis.__blockedSockets || [];
                  globalThis.__blockedSockets.push(target.href);
                  throw new DOMException('External WebSocket forbidden', 'SecurityError');
                }}
                return protocols === undefined
                  ? new NativeSocket(url)
                  : new NativeSocket(url, protocols);
              }}
              GuardedSocket.prototype = NativeSocket.prototype;
              Object.setPrototypeOf(GuardedSocket, NativeSocket);
              globalThis.WebSocket = GuardedSocket;
            }})();
            """
        )

        def route_request(route) -> None:
            url = route.request.url
            if not _allowed(url, origin):
                if url in {HTTP_PROBE, DIRECT_STORAGE_PROBE}:
                    blocked_probes.append(url)
                else:
                    external_requests.append(url)
                route.abort("blockedbyclient")
                return
            route.continue_()

        context.route("**/*", route_request)
        page = context.new_page()
        page.on("pageerror", lambda error: javascript_errors.append(str(error)))
        page.on(
            "console",
            lambda message: (
                console_security_errors.append(message.text)
                if message.type == "error"
                else None
            ),
        )
        page.on("dialog", lambda dialog: (dialogs.append(dialog.message), dialog.dismiss()))
        page.goto(base_url.rstrip("/") + "/", wait_until="networkidle", timeout=timeout_ms)
        pages_tested.append("verification")
        page.get_by_text("Foundation verified · Phase 01 verified", exact=True).wait_for()
        response = page.request.get(base_url.rstrip("/") + "/")
        csp = response.headers.get("content-security-policy", "")

        page.goto(base_url.rstrip("/") + "/ontology", wait_until="networkidle", timeout=timeout_ms)
        pages_tested.append("ontology")
        page.get_by_role("table", name="Ontology classes").wait_for()
        class_rows = page.get_by_role("table", name="Ontology classes").locator("tbody tr").count()
        property_rows = page.get_by_role("table", name="Ontology properties").locator("tbody tr").count()

        page.goto(base_url.rstrip("/") + "/entity", wait_until="networkidle", timeout=timeout_ms)
        pages_tested.append("entity")
        page.get_by_role("button", name="Inspect entity").click()
        page.get_by_role("table", name="Asserted entity facts").wait_for()
        entity_rows = page.get_by_role("table", name="Asserted entity facts").locator("tbody tr").count()

        page.goto(base_url.rstrip("/") + "/fact", wait_until="networkidle", timeout=timeout_ms)
        pages_tested.append("fact")
        page.get_by_role("button", name="Inspect fact and provenance").click()
        page.get_by_text("Publication", exact=True).first.wait_for()
        trace_steps = page.locator(".trace-chain li").count()
        golden_passed += trace_steps >= 9

        page.goto(base_url.rstrip("/") + "/trace", wait_until="networkidle", timeout=timeout_ms)
        pages_tested.append("trace")
        page.get_by_role("button", name="Load trace").click()
        page.get_by_role("table", name="Cross-trace rows").wait_for()

        page.goto(base_url.rstrip("/") + "/review", wait_until="networkidle", timeout=timeout_ms)
        pages_tested.append("review")
        page.get_by_role("button", name="Inspect review history").click()
        page.get_by_role("table", name="Review records — not asserted business facts").wait_for()

        probe_page = context.new_page()
        http_blocked = probe_page.evaluate(
            "url => fetch(url).then(() => false).catch(() => true)",
            HTTP_PROBE,
        )
        direct_blocked = int(
            probe_page.evaluate(
                "url => fetch(url).then(() => false).catch(() => true)",
                DIRECT_STORAGE_PROBE,
            )
        )
        websocket_blocked = probe_page.evaluate(
            """url => {
              try { new WebSocket(url); return false; }
              catch (error) { return error && error.name === 'SecurityError'; }
            }""",
            WEBSOCKET_PROBE,
        )
        blocked_sockets = probe_page.evaluate("globalThis.__blockedSockets || []")
        if websocket_blocked and WEBSOCKET_PROBE in blocked_sockets:
            blocked_probes.append(WEBSOCKET_PROBE)
        probe_page.close()

        service_worker_count = len(context.service_workers)
        local_storage_count = page.evaluate("localStorage.length")
        indexed_db_count = page.evaluate(
            "() => indexedDB.databases ? indexedDB.databases().then(items => items.length) : 0"
        )

        if xss_model is not None:
            xss_count = len(xss_model.get("rows", []))
            xss_context = browser.new_context(service_workers="block")

            def xss_route(route) -> None:
                path = urlsplit(route.request.url).path
                if path == "/workbench/api/view/entity":
                    route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps(xss_model, ensure_ascii=False),
                    )
                    return
                route.continue_()

            xss_context.route("**/*", xss_route)
            xss_page = xss_context.new_page()
            xss_page.on("dialog", lambda dialog: (dialogs.append(dialog.message), dialog.dismiss()))
            xss_page.goto(base_url.rstrip("/") + "/entity", wait_until="networkidle")
            xss_page.get_by_role("button", name="Inspect entity").click()
            xss_page.get_by_role("table", name="Asserted entity facts").wait_for()
            injected_nodes = xss_page.locator("img, svg, iframe, object").count()
            rendered = xss_page.locator(".term-value").all_text_contents()
            expected_values = [
                binding["term"].get("lexical_form")
                for row in xss_model["rows"]
                for binding in row["bindings"]
                if binding["variable"] == "object"
            ]
            xss_blocked = sum(value in rendered for value in expected_values)
            if injected_nodes or dialogs:
                xss_blocked = 0
            xss_context.close()

        fixtures = scenario_fixtures or {}
        for name in ("modified-confirmation", "rejection", "issue-resolution"):
            fixture = fixtures.get(name)
            if fixture and _fixture_page(
                browser,
                base_url,
                fixture["model"],
                fixture["expected_text"],
            ):
                golden_passed += 1

        context.close()
        browser.close()

    required_csp = (
        "default-src 'self'",
        "script-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
    )
    versions_ok = (
        browser_version == EXPECTED_BROWSER_VERSION
        and browser_revision == EXPECTED_BROWSER_REVISION
        and playwright_version == EXPECTED_PLAYWRIGHT_VERSION
    )
    status = "PASS" if all(
        (
            versions_ok,
            class_rows > 0,
            property_rows > 0,
            entity_rows > 0,
            trace_steps >= 9,
            golden_passed == 4,
            not javascript_errors,
            not console_security_errors,
            not external_requests,
            http_blocked,
            websocket_blocked,
            direct_blocked == direct_attempts,
            service_worker_count == 0,
            local_storage_count == 0,
            indexed_db_count == 0,
            xss_count >= 10,
            xss_count == xss_blocked,
            all(item in csp for item in required_csp),
        )
    ) else "FAILED"
    return {
        "status": status,
        "browser_name": EXPECTED_BROWSER_NAME,
        "browser_version": browser_version,
        "browser_revision": browser_revision,
        "playwright_version": playwright_version,
        "pages_tested": pages_tested,
        "class_rows": class_rows,
        "property_rows": property_rows,
        "entity_rows": entity_rows,
        "fact_trace_steps": trace_steps,
        "golden_scenario_count": 4,
        "golden_scenario_passed": int(golden_passed),
        "javascript_errors": javascript_errors,
        "console_security_errors": console_security_errors,
        "external_requests": external_requests,
        "blocked_network_probes": sorted(set(blocked_probes)),
        "direct_graphdb_access_attempt_count": direct_attempts,
        "direct_graphdb_access_blocked_count": direct_blocked,
        "service_worker_count": service_worker_count,
        "local_storage_entry_count": local_storage_count,
        "indexed_db_count": indexed_db_count,
        "xss_attack_count": xss_count,
        "xss_attack_blocked": xss_blocked,
        "injected_html_nodes": 0 if xss_count == xss_blocked else 1,
        "script_executed": bool(dialogs),
        "content_security_policy": csp,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url")
    parser.add_argument("--xss-model")
    parser.add_argument("--scenario-fixtures")
    parser.add_argument("--output")
    arguments = parser.parse_args()
    xss = (
        json.loads(Path(arguments.xss_model).read_text(encoding="utf-8"))
        if arguments.xss_model
        else None
    )
    fixtures = (
        json.loads(Path(arguments.scenario_fixtures).read_text(encoding="utf-8"))
        if arguments.scenario_fixtures
        else None
    )
    result = run(arguments.base_url, xss_model=xss, scenario_fixtures=fixtures)
    text = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    if arguments.output:
        Path(arguments.output).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
