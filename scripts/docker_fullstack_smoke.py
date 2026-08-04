#!/usr/bin/env python3
"""运行中的 Docker Compose 全栈冒烟检查。

先直连后端检查 health/ready，再通过前端 Nginx 入口检查同源代理、
CASE-03 和追溯链路，避免部署问题被直连后端的测试掩盖。
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from collections.abc import Callable
from typing import Any, TypeVar


FRONTEND_URL = os.environ.get("KG_MNP_FRONTEND_URL", "http://localhost:8080").rstrip("/")
BACKEND_URL = os.environ.get("KG_MNP_BACKEND_URL", "http://localhost:8000").rstrip("/")

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")


@dataclass
class SmokeError(RuntimeError):
    message: str

    def __str__(self) -> str:
        return self.message


T = TypeVar("T")


def retry_request(operation: Callable[[], T], label: str, *, attempts: int = 10) -> T:
    last_error: SmokeError | None = None
    for attempt in range(attempts):
        try:
            return operation()
        except SmokeError as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2)
    assert last_error is not None
    raise SmokeError(f"{label}重试 {attempts} 次后仍失败：{last_error}") from last_error


def request_json(base_url: str, path: str, *, method: str = "GET") -> Any:
    url = f"{base_url}{path}"
    body = b"" if method == "POST" else None
    request = urllib.request.Request(url, data=body, method=method)
    request.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status < 200 or response.status >= 300:
                raise SmokeError(f"请求失败：{method} {path} 返回 HTTP {response.status}")
            raw = response.read()
    except SmokeError:
        raise
    except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        raise SmokeError(f"请求失败：{method} {path}：{exc}") from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SmokeError(f"响应不是有效 JSON：{method} {path}") from exc


def request_text(base_url: str, path: str) -> str:
    url = f"{base_url}{path}"
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            if response.status < 200 or response.status >= 300:
                raise SmokeError(f"页面请求失败：GET {path} 返回 HTTP {response.status}")
            return response.read().decode("utf-8")
    except SmokeError:
        raise
    except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        raise SmokeError(f"页面请求失败：GET {path}：{exc}") from exc


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeError(message)


def main() -> int:
    try:
        health = retry_request(
            lambda: request_json(BACKEND_URL, "/api/v1/health"),
            "后端 health",
        )
        require(isinstance(health, dict) and health.get("status") == "ok", "后端 health 未返回 ok")
        print("后端 health：通过")

        ready = retry_request(
            lambda: request_json(BACKEND_URL, "/api/v1/ready"),
            "后端 ready",
        )
        require(
            isinstance(ready, dict)
            and ready.get("status") == "ready"
            and ready.get("sqlite") is True,
            "后端 ready 未达到 ready/sqlite=true",
        )
        print("后端 ready：通过")

        homepage = retry_request(
            lambda: request_text(FRONTEND_URL, "/"),
            "前端首页",
        )
        require("<html" in homepage.lower(), "前端首页未返回 HTML")
        print("前端首页：通过")

        proxy_health = retry_request(
            lambda: request_json(FRONTEND_URL, "/api/v1/health"),
            "前端 API 代理",
        )
        require(proxy_health.get("status") == "ok", "前端 API 代理不可用")
        print("前端 API 代理：通过")

        route = retry_request(
            lambda: request_text(FRONTEND_URL, "/assessments/new"),
            "SPA 路由",
        )
        require("<html" in route.lower(), "SPA 路由回退未返回首页")
        print("SPA 路由：通过")

        result = request_json(FRONTEND_URL, "/api/v1/examples/CASE-03/run", method="POST")
        execution_id = result.get("execution_id") if isinstance(result, dict) else None
        require(isinstance(execution_id, str) and bool(execution_id), "CASE-03 未返回 execution_id")
        require(result.get("case_id") == "CASE-03", "CASE-03 返回的 case_id 不正确")
        decision = result.get("decision")
        if decision is None and isinstance(result.get("result"), dict):
            decision = result["result"].get("decision")
        require(decision == "BLOCKED", "CASE-03 结果不是 BLOCKED")
        print(f"CASE-03：通过（execution_id={execution_id}）")

        encoded = urllib.parse.quote(execution_id, safe="")
        detail = request_json(FRONTEND_URL, f"/api/v1/assessments/{encoded}")
        require(detail.get("execution_id") == execution_id, "评估详情 execution_id 不一致")
        print("评估详情：通过")

        view = request_json(FRONTEND_URL, f"/api/v1/views/assessments/{encoded}")
        require(isinstance(view, dict), "评估视图响应无效")
        print("评估视图：通过")

        trace = request_json(FRONTEND_URL, f"/api/v1/views/assessments/{encoded}/trace")
        node_count = trace.get("node_count") if isinstance(trace, dict) else 0
        edge_count = trace.get("edge_count") if isinstance(trace, dict) else 0
        require(isinstance(node_count, int) and node_count > 0, "追溯图节点为空")
        require(isinstance(edge_count, int) and edge_count > 0, "追溯图关系为空")
        print(f"追溯图：通过（{node_count} 个节点，{edge_count} 条关系）")
        return 0
    except SmokeError as exc:
        print(f"Docker 全栈冒烟失败：{exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - protects the CI entry point
        print(f"Docker 全栈冒烟失败：未预期错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
