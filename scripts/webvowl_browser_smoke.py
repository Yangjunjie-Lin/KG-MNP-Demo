#!/usr/bin/env python3
"""Fail-closed browser smoke test for the loopback WebVOWL runtime.

The test deliberately records semantic/UI signals only; screenshots and DOM
coordinates are not part of any acceptance hash.
"""

from __future__ import annotations

import argparse
import http.client
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse

EXPECTED_BROWSER_NAME = "chromium"
EXPECTED_BROWSER_VERSION = "131.0.6778.33"
EXPECTED_BROWSER_REVISION = "1148"
EXPECTED_PLAYWRIGHT_VERSION = "1.49.1"
NETWORK_SCHEMES = {"http", "https", "ws", "wss"}
HTTP_EGRESS_PROBE = "https://example.invalid/kg-mnp-browser-egress-probe"
WEBSOCKET_EGRESS_PROBE = "wss://example.invalid/kg-mnp-browser-egress-probe"


def _expected_ontology(vowl_path: str | None) -> dict[str, str | None]:
    if not vowl_path:
        return {"title": None, "iri": None, "version": None}
    try:
        value = json.loads(Path(vowl_path).read_text(encoding="utf-8"))
        header = value["header"]
        titles = header["title"]
        if not isinstance(header, dict) or not isinstance(titles, dict):
            raise TypeError("VOWL header/title is not an object")
        title = titles.get("en") or next(
            (item for item in titles.values() if isinstance(item, str) and item), None
        )
        iri = header.get("iri")
        version = header.get("version")
        if not all(isinstance(item, str) and item for item in (title, iri)):
            raise ValueError("VOWL header has no title or ontology IRI")
        if version is not None and not isinstance(version, str):
            raise TypeError("VOWL ontology version is not text")
        return {"title": title, "iri": iri, "version": version}
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"cannot read expected VOWL ontology identity: {exc}"
        ) from exc


def _security_expectations(vowl_path: str | None) -> dict[str, list[str]]:
    """Discover tracked malicious-fixture signals without weakening normal smoke."""
    if not vowl_path:
        return {"labels": [], "encoded_iris": []}
    try:
        value = json.loads(Path(vowl_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read VOWL browser-security signals: {exc}") from exc
    labels: set[str] = set()
    encoded_iris: set[str] = set()
    for collection in ("classAttribute", "propertyAttribute"):
        records = value.get(collection, [])
        if not isinstance(records, list):
            raise TypeError(f"VOWL {collection} is not an array")
        for record in records:
            if not isinstance(record, dict):
                raise TypeError(f"VOWL {collection} contains a non-object")
            iri = record.get("iri")
            if isinstance(iri, str) and re.search(r"%[0-9A-Fa-f]{2}", iri):
                encoded_iris.add(iri)
            label = record.get("label", {})
            if isinstance(label, dict):
                for text in label.values():
                    if isinstance(text, str) and (
                        "<script" in text.casefold()
                        or "onerror=" in text.casefold()
                        or ("quotes" in text.casefold() and "\n" in text)
                    ):
                        labels.add(text)
    return {"labels": sorted(labels), "encoded_iris": sorted(encoded_iris)}


def _origin(url: str) -> tuple[str, str, int | None]:
    parsed = urlparse(url)
    return parsed.scheme.casefold(), (parsed.hostname or "").casefold(), parsed.port


def _allowed_network_target(
    url: str, allowed_origin: tuple[str, str, int | None]
) -> bool:
    scheme, host, port = _origin(url)
    base_scheme, base_host, base_port = allowed_origin
    allowed_schemes = {base_scheme, "ws" if base_scheme == "http" else "wss"}
    return scheme in allowed_schemes and host == base_host and port == base_port


def _proxy_request_status(
    base_url: str,
    method: str,
    target: str,
    *,
    host_header: str | None = None,
    extra_headers: dict[str, str] | None = None,
) -> int:
    parsed = urlparse(base_url)
    if parsed.scheme != "http" or not parsed.hostname:
        raise RuntimeError("proxy probe requires an HTTP loopback URL")
    port = parsed.port or 80
    connection = http.client.HTTPConnection(parsed.hostname, port, timeout=5)
    try:
        connection.putrequest(
            method,
            target,
            skip_host=True,
            skip_accept_encoding=True,
        )
        connection.putheader("Host", host_header or f"{parsed.hostname}:{port}")
        headers = extra_headers or {"Connection": "close"}
        for name, value in headers.items():
            connection.putheader(name, value)
        connection.endheaders()
        response = connection.getresponse()
        response.read()
        return response.status
    finally:
        connection.close()


def _probe_fixed_loopback_proxy(base_url: str) -> dict[str, int | str]:
    """Prove that the published relay rejects all forward-proxy forms."""

    absolute_status = _proxy_request_status(
        base_url,
        "GET",
        "http://example.invalid/kg-mnp-proxy-egress-probe",
    )
    connect_status = _proxy_request_status(
        base_url,
        "CONNECT",
        "example.invalid:443",
    )
    foreign_host_status = _proxy_request_status(
        base_url,
        "GET",
        "/kg-mnp-proxy-host-probe",
        host_header="example.invalid",
    )
    upgrade_status = _proxy_request_status(
        base_url,
        "GET",
        "/kg-mnp-proxy-upgrade-probe",
        extra_headers={"Connection": "Upgrade", "Upgrade": "websocket"},
    )
    result: dict[str, int | str] = {
        "status": "PASS",
        "absolute_form_status": absolute_status,
        "connect_status": connect_status,
        "foreign_host_status": foreign_host_status,
        "upgrade_status": upgrade_status,
    }
    if (absolute_status, connect_status, foreign_host_status, upgrade_status) != (
        403,
        403,
        421,
        403,
    ):
        result["status"] = "FAILED"
    return result


def run(
    base_url: str,
    vowl_path: str | None = None,
    timeout_ms: int = 30_000,
    *,
    require_security_expectations: bool = False,
) -> dict:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        return {
            "status": "FAILED",
            "error": f"Playwright is not installed: {exc}",
            "external_requests": [],
        }
    allowed_origin = _origin(base_url.rstrip("/") + "/")
    if allowed_origin != ("http", "127.0.0.1", 8080):
        return {
            "status": "FAILED",
            "error": "browser smoke requires http://127.0.0.1:8080",
            "external_requests": [],
        }
    external: list[str] = []
    blocked_external: list[str] = []
    js_errors: list[str] = []
    console_errors: list[str] = []
    expected = _expected_ontology(vowl_path)
    security_expectations = _security_expectations(vowl_path)
    if require_security_expectations and (
        len(security_expectations["labels"]) < 3
        or len(security_expectations["encoded_iris"]) < 1
    ):
        return {
            "status": "FAILED",
            "error": "malicious fixture security expectations are incomplete",
            "security_label_count": len(security_expectations["labels"]),
            "encoded_iri_count": len(security_expectations["encoded_iris"]),
            "external_requests": [],
        }
    ontology_title = None
    ontology_iri = None
    ontology_version = None
    input_loaded = vowl_path is None
    http_probe_blocked = False
    websocket_probe_blocked = False
    security_labels_rendered_as_text = not security_expectations["labels"]
    encoded_iris_loaded = not security_expectations["encoded_iris"]
    proxy_probe: dict[str, int | str]
    try:
        proxy_probe = _probe_fixed_loopback_proxy(base_url)
    except (OSError, RuntimeError, http.client.HTTPException) as exc:
        proxy_probe = {"status": "FAILED", "error": str(exc)}
    started = time.monotonic()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        browser_version = browser.version
        playwright_version = None
        try:
            from importlib.metadata import PackageNotFoundError, version

            playwright_version = version("playwright")
        except PackageNotFoundError:
            playwright_version = None
        executable_path = p.chromium.executable_path
        browser_revision_match = re.search(r"chromium-(\d+)", executable_path)
        browser_revision = (
            browser_revision_match.group(1) if browser_revision_match else None
        )
        for actual, expected_value, label in (
            (browser_version, EXPECTED_BROWSER_VERSION, "Chromium version"),
            (browser_revision, EXPECTED_BROWSER_REVISION, "Chromium revision"),
            (playwright_version, EXPECTED_PLAYWRIGHT_VERSION, "Playwright version"),
        ):
            if actual != expected_value:
                js_errors.append(
                    f"{label} mismatch: expected {expected_value}, got {actual}"
                )
        # Every non-bypassed protocol is forced through the fixed relay, whose
        # absolute-form/CONNECT/Upgrade contract rejects arbitrary forwarding.
        # Request routing below is an independent browser-level fail-closed gate.
        context = browser.new_context(
            proxy={"server": base_url.rstrip("/"), "bypass": "127.0.0.1"},
            service_workers="block",
        )

        def route_network(route) -> None:
            nonlocal http_probe_blocked
            url = route.request.url
            parsed = urlparse(url)
            if (
                parsed.scheme.casefold() in NETWORK_SCHEMES
                and not _allowed_network_target(url, allowed_origin)
            ):
                blocked_external.append(url)
                if url == HTTP_EGRESS_PROBE:
                    http_probe_blocked = True
                else:
                    external.append(url)
                route.abort("blockedbyclient")
                return
            route.continue_()

        def route_web_socket(route) -> None:
            url = route.url
            if not _allowed_network_target(url, allowed_origin):
                blocked_external.append(url)
                if url != WEBSOCKET_EGRESS_PROBE:
                    external.append(url)
                # A routed socket reaches the network only after
                # connect_to_server(). Returning here keeps it fully local.
                return
            route.connect_to_server()

        context.route("**/*", route_network)
        context.route_web_socket("**/*", route_web_socket)
        # This guard must be registered after Playwright's WebSocket router so
        # it remains the outermost constructor in every document.
        context.add_init_script(
            script=f"""
            (() => {{
                const allowed = new URL({json.dumps(base_url.rstrip("/") + "/")});
                const NativeWebSocket = globalThis.WebSocket;
                function GuardedWebSocket(url, protocols) {{
                    const target = new URL(String(url), globalThis.location.href);
                    const sameEndpoint = target.hostname === allowed.hostname
                        && target.port === allowed.port
                        && target.protocol === 'ws:';
                    if (!sameEndpoint) {{
                        globalThis.__kgMnpBlockedWebSockets =
                            globalThis.__kgMnpBlockedWebSockets || [];
                        globalThis.__kgMnpBlockedWebSockets.push(target.href);
                        throw new DOMException(
                            'External WebSocket forbidden', 'SecurityError'
                        );
                    }}
                    return protocols === undefined
                        ? new NativeWebSocket(url)
                        : new NativeWebSocket(url, protocols);
                }}
                GuardedWebSocket.prototype = NativeWebSocket.prototype;
                Object.setPrototypeOf(GuardedWebSocket, NativeWebSocket);
                globalThis.WebSocket = GuardedWebSocket;
            }})();
            """
        )
        page = context.new_page()
        try:
            page.evaluate(
                "url => fetch(url).then(() => false).catch(() => true)",
                HTTP_EGRESS_PROBE,
            )
            websocket_probe_blocked = page.evaluate(
                """url => {
                    try {
                        new WebSocket(url);
                        return false;
                    } catch (error) {
                        return error && error.name === 'SecurityError';
                    }
                }""",
                WEBSOCKET_EGRESS_PROBE,
            )
            if websocket_probe_blocked:
                blocked_external.append(WEBSOCKET_EGRESS_PROBE)
            if not http_probe_blocked or not websocket_probe_blocked:
                raise RuntimeError("browser external-network interception probe failed")
            page.on("pageerror", lambda exc: js_errors.append(str(exc)))
            page.on(
                "console",
                lambda msg: (
                    console_errors.append(msg.text) if msg.type == "error" else None
                ),
            )
            response = page.goto(
                base_url.rstrip("/") + "/", wait_until="networkidle", timeout=timeout_ms
            )
            root_status = response.status if response else None
            if root_status != 200:
                raise RuntimeError(f"WebVOWL root returned HTTP {root_status}")
            if vowl_path:
                # WebVOWL's file input is intentionally used only with a local
                # generated artifact; no remote IRI/import is supplied.
                chooser = page.locator("#file-converter-input")
                if chooser.count() != 1:
                    raise RuntimeError(
                        "WebVOWL canonical VOWL file input is unavailable"
                    )
                chooser.set_input_files(vowl_path)
                page.wait_for_function(
                    """expected => {
                        const title = document.querySelector('#title');
                        const about = document.querySelector('#about');
                        const version = document.querySelector('#version');
                        return title && title.textContent.trim() === expected.title
                            && about && about.textContent.trim() === expected.iri
                            && (!expected.version || (version
                                && version.textContent.trim() === expected.version));
                    }""",
                    arg=expected,
                    timeout=timeout_ms,
                )
                input_loaded = True
            ontology_title = page.locator("#title").inner_text().strip()
            ontology_iri = page.locator("#about").inner_text().strip()
            ontology_version = page.locator("#version").inner_text().strip()
            if vowl_path and (
                ontology_title != expected["title"]
                or ontology_iri != expected["iri"]
                or (
                    expected["version"] is not None
                    and ontology_version != expected["version"]
                )
            ):
                raise RuntimeError(
                    "loaded ontology identity does not match canonical VOWL"
                )
            body_text = page.locator("body").inner_text(timeout=timeout_ms)
            svg_count = page.locator("svg").count()
            class_nodes = page.locator(".nodeContainer .node").count()
            property_nodes = page.locator(".linkContainer .link").count()
            script_executed = bool(page.evaluate("Boolean(window.__kgMnpInjected)"))
            injected_html_nodes = page.locator("img[src='x']").count()
            guarded_websockets = page.evaluate(
                "globalThis.__kgMnpBlockedWebSockets || []"
            )
            security_labels_rendered_as_text = page.evaluate(
                """labels => labels.every(expectedLabel =>
                    Array.from(document.querySelectorAll('.nodeContainer .node'))
                        .some(element => {
                            const datum = element.__data__;
                            const loadedLabel = datum
                                && typeof datum.labelForCurrentLanguage === 'function'
                                && datum.labelForCurrentLanguage() === expectedLabel;
                            const renderedAsText = Array.from(
                                element.querySelectorAll('text, title')
                            ).some(text => text.textContent.includes(expectedLabel));
                            return loadedLabel && renderedAsText;
                        }))""",
                security_expectations["labels"],
            )
            encoded_iris_loaded = page.evaluate(
                """iris => iris.every(expectedIri =>
                    Array.from(document.querySelectorAll('.linkContainer .link'))
                        .some(element => {
                            const link = element.__data__;
                            const property = link
                                && typeof link.property === 'function'
                                && link.property();
                            return property
                                && typeof property.iri === 'function'
                                && property.iri() === expectedIri;
                        }))""",
                security_expectations["encoded_iris"],
            )
            external.extend(
                url for url in guarded_websockets if url != WEBSOCKET_EGRESS_PROBE
            )
            blocked_external.extend(guarded_websockets)
            if svg_count < 1:
                raise RuntimeError("no SVG visualization was rendered")
            if class_nodes < 1 or property_nodes < 1:
                raise RuntimeError(
                    "WebVOWL graph has no rendered class nodes or property edges"
                )
            if script_executed or injected_html_nodes:
                raise RuntimeError(
                    "ontology label content was interpreted as executable HTML"
                )
            if not security_labels_rendered_as_text:
                raise RuntimeError(
                    "malicious ontology labels were not rendered as text"
                )
            if not encoded_iris_loaded:
                raise RuntimeError("encoded unusual ontology IRI was not loaded")
            if not re.search(r"KG-MNP|ontology|WebVOWL", body_text, re.IGNORECASE):
                raise RuntimeError("ontology title/IRI was not visible")
        except (OSError, RuntimeError, ValueError, PlaywrightError) as exc:
            js_errors.append(str(exc))
            root_status = locals().get("root_status")
            svg_count = locals().get("svg_count", 0)
            class_nodes = locals().get("class_nodes", 0)
            property_nodes = locals().get("property_nodes", 0)
            script_executed = locals().get("script_executed", False)
            injected_html_nodes = locals().get("injected_html_nodes", 0)
            guarded_websockets = locals().get("guarded_websockets", [])
            security_labels_rendered_as_text = locals().get(
                "security_labels_rendered_as_text", False
            )
            encoded_iris_loaded = locals().get("encoded_iris_loaded", False)
        finally:
            context.close()
            browser.close()
    status = (
        "PASS"
        if root_status == 200
        and svg_count > 0
        and class_nodes > 0
        and property_nodes > 0
        and not script_executed
        and injected_html_nodes == 0
        and security_labels_rendered_as_text
        and encoded_iris_loaded
        and not js_errors
        and not console_errors
        and not external
        and http_probe_blocked
        and websocket_probe_blocked
        and proxy_probe.get("status") == "PASS"
        else "FAILED"
    )
    return {
        "status": status,
        "browser_name": EXPECTED_BROWSER_NAME,
        "browser_version": browser_version,
        "browser_revision": browser_revision,
        "playwright_version": playwright_version,
        "root_status": root_status,
        "canonical_vowl_loaded": input_loaded,
        "ontology_title": ontology_title,
        "ontology_iri": ontology_iri,
        "ontology_version": ontology_version,
        "svg_count": svg_count,
        "class_nodes": class_nodes,
        "property_nodes": property_nodes,
        "script_executed": script_executed,
        "injected_html_nodes": injected_html_nodes,
        "security_label_count": len(security_expectations["labels"]),
        "security_labels_rendered_as_text": security_labels_rendered_as_text,
        "encoded_iri_count": len(security_expectations["encoded_iris"]),
        "encoded_iris_loaded": encoded_iris_loaded,
        "javascript_errors": js_errors,
        "console_errors": console_errors,
        "external_requests": sorted(set(external)),
        "blocked_external_requests": sorted(set(blocked_external)),
        "browser_http_egress_probe_blocked": http_probe_blocked,
        "browser_websocket_egress_probe_blocked": websocket_probe_blocked,
        "loopback_proxy_egress_probe": proxy_probe,
        "duration_seconds": round(time.monotonic() - started, 3),
        "screenshot_hash_used_as_gate": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--vowl-path")
    parser.add_argument("--output")
    parser.add_argument("--require-security-expectations", action="store_true")
    args = parser.parse_args()
    result = run(
        args.base_url,
        args.vowl_path,
        require_security_expectations=args.require_security_expectations,
    )
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8", newline="\n")
    print(payload, end="")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
