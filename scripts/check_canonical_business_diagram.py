#!/usr/bin/env python3
"""Validate the fixed KG-MNP canonical business diagram v2 stage gate."""

from __future__ import annotations

import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "canonical_business_diagram_v2.json"
SCHEMA_PATH = ROOT / "schemas" / "canonical_business_diagram_v2.schema.json"
ENDPOINT_TOLERANCE = 2.0
CANVAS_WIDTH = 1664
CANVAS_HEIGHT = 900

EXPECTED_LAYERS: dict[str, tuple[int, str, tuple[str, str], int, int, int, int]] = {
    "USER_IDENTITY": (
        1,
        "1. 用户与身份层",
        ("(User & Identity", "Layer)"),
        8,
        10,
        1648,
        180,
    ),
    "ACCOUNT_BILLING": (
        2,
        "2. 账户与计费层",
        ("(Account & Billing", "Layer)"),
        8,
        208,
        1648,
        114,
    ),
    "SERVICE_OFFERING": (
        3,
        "3. 业务与服务层",
        ("(Service & Offering", "Layer)"),
        8,
        338,
        1648,
        122,
    ),
    "PORTABILITY_PROCESS": (
        4,
        "4. 携号转网流程层",
        ("(Number Portability", "Process Layer)"),
        8,
        475,
        1648,
        160,
    ),
    "QUALIFICATION_COMPLIANCE": (
        5,
        "5. 资格与合规层",
        ("(Qualification &", "Compliance Layer)"),
        8,
        652,
        1648,
        235,
    ),
}

# layer, Chinese label, approved English subtitle, x, y, width, height, style key
EXPECTED_NODES: dict[str, tuple[str, str, str, int, int, int, int, str]] = {
    "USER": ("USER_IDENTITY", "用户", "User", 266, 42, 120, 72, "ordinary"),
    "VERIFICATION": (
        "USER_IDENTITY",
        "实名认证记录",
        "Verification",
        610,
        42,
        198,
        72,
        "ordinary",
    ),
    "MOBILE_NUMBER_IDENTITY": (
        "USER_IDENTITY",
        "手机号码",
        "Mobile Number",
        969,
        42,
        195,
        72,
        "ordinary",
    ),
    "OPERATOR_CURRENT": (
        "USER_IDENTITY",
        "运营商",
        "Operator",
        1378,
        43,
        157,
        72,
        "ordinary",
    ),
    "ACCOUNT": ("ACCOUNT_BILLING", "账户", "Account", 409, 241, 157, 62, "ordinary"),
    "BILL": ("ACCOUNT_BILLING", "账单", "Bill", 799, 241, 177, 62, "ordinary"),
    "PAYMENT": (
        "ACCOUNT_BILLING",
        "缴费记录",
        "Payment",
        1275,
        241,
        157,
        62,
        "ordinary",
    ),
    "TARIFF_PLAN": (
        "SERVICE_OFFERING",
        "套餐",
        "Tariff Plan",
        290,
        379,
        153,
        62,
        "ordinary",
    ),
    "CONTRACT": (
        "SERVICE_OFFERING",
        "合同",
        "Contract",
        535,
        379,
        153,
        62,
        "ordinary",
    ),
    "BROADBAND": (
        "SERVICE_OFFERING",
        "宽带",
        "Broadband",
        806,
        379,
        153,
        62,
        "ordinary",
    ),
    "VALUE_ADDED_SERVICE": (
        "SERVICE_OFFERING",
        "增值业务",
        "Value Added Service",
        1067,
        379,
        191,
        62,
        "ordinary",
    ),
    "USER_RIGHT": (
        "SERVICE_OFFERING",
        "用户权益",
        "User Right",
        1381,
        379,
        151,
        62,
        "ordinary",
    ),
    "PORT_REQUEST": (
        "PORTABILITY_PROCESS",
        "携转申请",
        "Port Request",
        333,
        527,
        139,
        61,
        "ordinary",
    ),
    "MOBILE_NUMBER_PORT": (
        "PORTABILITY_PROCESS",
        "手机号码",
        "Mobile Number",
        640,
        482,
        160,
        48,
        "ordinary",
    ),
    "OPERATOR_DONOR": (
        "PORTABILITY_PROCESS",
        "运营商（携出方）",
        "Operator - Donor",
        640,
        532,
        168,
        52,
        "ordinary",
    ),
    "OPERATOR_RECIPIENT": (
        "PORTABILITY_PROCESS",
        "运营商（携入方）",
        "Operator - Recipient",
        640,
        584,
        168,
        52,
        "ordinary",
    ),
    "PORT_STEP": (
        "PORTABILITY_PROCESS",
        "办理步骤",
        "Port Step",
        887,
        529,
        139,
        58,
        "ordinary",
    ),
    "AUTH_CODE": (
        "PORTABILITY_PROCESS",
        "授权码",
        "Auth Code",
        1100,
        529,
        120,
        58,
        "ordinary",
    ),
    "EXCEPTION_EVENT": (
        "PORTABILITY_PROCESS",
        "异常事件",
        "Exception Event",
        1301,
        529,
        142,
        58,
        "ordinary",
    ),
    "IMPACT": (
        "PORTABILITY_PROCESS",
        "影响结果",
        "Impact",
        1512,
        529,
        103,
        58,
        "ordinary",
    ),
    "ELIGIBILITY_CONDITION": (
        "QUALIFICATION_COMPLIANCE",
        "资格条件",
        "Eligibility Condition",
        287,
        673,
        180,
        67,
        "ordinary",
    ),
    "REGULATION_RULE": (
        "QUALIFICATION_COMPLIANCE",
        "监管规则",
        "Regulation Rule",
        286,
        796,
        180,
        62,
        "ordinary",
    ),
    "SAFETY_CHECK": (
        "QUALIFICATION_COMPLIANCE",
        "安全检查",
        "Safety Check",
        630,
        672,
        247,
        99,
        "safety_check",
    ),
    "BLOCK_REASON": (
        "QUALIFICATION_COMPLIANCE",
        "阻塞原因",
        "Block Reason",
        1050,
        674,
        175,
        64,
        "ordinary",
    ),
    "REMEDIATION_ACTION": (
        "QUALIFICATION_COMPLIANCE",
        "处理措施",
        "Remediation Action",
        1375,
        674,
        205,
        64,
        "ordinary",
    ),
    "EVIDENCE": (
        "QUALIFICATION_COMPLIANCE",
        "证据",
        "Evidence",
        1050,
        796,
        179,
        61,
        "ordinary",
    ),
    "OPERATOR_EVIDENCE": (
        "QUALIFICATION_COMPLIANCE",
        "运营商",
        "Operator",
        1380,
        796,
        176,
        61,
        "ordinary",
    ),
}

# from, to, source port, target port, label, path, label x, label y, bends, bus id
EXPECTED_EDGES: dict[
    str, tuple[str, str, str, str, str, str, int, int, int, str | None]
] = {
    "struct-user-verification": (
        "USER", "VERIFICATION", "RIGHT", "LEFT", "具有实名记录",
        "M 386 78 H 610", 490, 64, 0, None,
    ),
    "struct-verification-number": (
        "VERIFICATION", "MOBILE_NUMBER_IDENTITY", "RIGHT", "LEFT", "验证",
        "M 808 78 H 969", 883, 64, 0, None,
    ),
    # The supplied one-bend path ended 39 px below the target. This two-bend
    # variant preserves the reference under-node rail and reaches its bottom port.
    "struct-user-number": (
        "USER", "MOBILE_NUMBER_IDENTITY", "BOTTOM", "BOTTOM", "持有／使用",
        "M 326 114 V 153 H 969 V 114", 604, 145, 2, None,
    ),
    "struct-number-operator-service": (
        "MOBILE_NUMBER_IDENTITY", "OPERATOR_CURRENT", "RIGHT", "LEFT", "当前服务",
        "M 1164 68 H 1378", 1268, 56, 0, None,
    ),
    "struct-number-operator-alloc": (
        "MOBILE_NUMBER_IDENTITY", "OPERATOR_CURRENT", "RIGHT", "LEFT", "初始分配",
        "M 1164 94 H 1378", 1268, 118, 0, None,
    ),
    "struct-user-account": (
        "USER", "ACCOUNT", "BOTTOM", "LEFT", "拥有",
        "M 326 114 V 272 H 409", 348, 229, 1, None,
    ),
    "struct-account-bill": (
        "ACCOUNT", "BILL", "RIGHT", "LEFT", "生成",
        "M 566 272 H 799", 611, 260, 0, None,
    ),
    "struct-bill-payment": (
        "BILL", "PAYMENT", "RIGHT", "LEFT", "结清",
        "M 976 272 H 1275", 1122, 260, 0, None,
    ),
    "struct-number-plan": (
        "MOBILE_NUMBER_IDENTITY", "TARIFF_PLAN", "BOTTOM", "TOP", "订购",
        "M 366 350 V 379", 382, 371, 0, "service-offering-bus",
    ),
    "struct-number-contract": (
        "MOBILE_NUMBER_IDENTITY", "CONTRACT", "BOTTOM", "TOP", "受约束于",
        "M 611 350 V 379", 630, 371, 0, "service-offering-bus",
    ),
    "struct-number-broadband": (
        "MOBILE_NUMBER_IDENTITY", "BROADBAND", "BOTTOM", "TOP", "关联",
        "M 883 350 V 379", 899, 371, 0, "service-offering-bus",
    ),
    "struct-number-vas": (
        "MOBILE_NUMBER_IDENTITY", "VALUE_ADDED_SERVICE", "BOTTOM", "TOP", "使用",
        "M 1163 350 V 379", 1179, 371, 0, "service-offering-bus",
    ),
    "struct-number-right": (
        "MOBILE_NUMBER_IDENTITY", "USER_RIGHT", "BOTTOM", "TOP", "享有",
        "M 1456 350 V 379", 1472, 371, 0, "service-offering-bus",
    ),
    # The supplied vertical at x=302 crossed TARIFF_PLAN. The two-bend route
    # uses the clear left corridor while retaining both requested endpoints.
    "struct-user-port": (
        "USER", "PORT_REQUEST", "BOTTOM", "LEFT", "提交",
        "M 302 114 H 278 V 558 H 333", 276, 505, 2, None,
    ),
    "struct-port-number": (
        "PORT_REQUEST", "MOBILE_NUMBER_PORT", "RIGHT", "LEFT", "申请携转号码",
        "M 472 543 H 551 V 506 H 640", 556, 497, 2, None,
    ),
    "struct-port-donor": (
        "PORT_REQUEST", "OPERATOR_DONOR", "RIGHT", "LEFT", "携出自",
        "M 472 557 H 640", 548, 545, 0, None,
    ),
    "struct-port-recipient": (
        "PORT_REQUEST", "OPERATOR_RECIPIENT", "RIGHT", "LEFT", "携入至",
        "M 472 572 H 551 V 610 H 640", 548, 601, 2, None,
    ),
    "struct-donor-step": (
        "OPERATOR_DONOR", "PORT_STEP", "RIGHT", "LEFT", "包含",
        "M 808 558 H 887", 847, 545, 0, None,
    ),
    "struct-step-auth": (
        "PORT_STEP", "AUTH_CODE", "RIGHT", "LEFT", "获得",
        "M 1026 558 H 1100", 1062, 545, 0, None,
    ),
    "struct-auth-exception": (
        "AUTH_CODE", "EXCEPTION_EVENT", "RIGHT", "LEFT", "发生",
        "M 1220 558 H 1301", 1260, 545, 0, None,
    ),
    "struct-exception-impact": (
        "EXCEPTION_EVENT", "IMPACT", "RIGHT", "LEFT", "产生",
        "M 1443 558 H 1512", 1477, 545, 0, None,
    ),
    "struct-port-eligibility": (
        "PORT_REQUEST", "ELIGIBILITY_CONDITION", "BOTTOM", "TOP", "触发",
        "M 402 588 V 673", 421, 647, 0, None,
    ),
    "struct-safety-condition": (
        "SAFETY_CHECK", "ELIGIBILITY_CONDITION", "LEFT", "RIGHT", "检查",
        "M 630 706 H 467", 544, 693, 0, None,
    ),
    "struct-condition-rule": (
        "ELIGIBILITY_CONDITION", "REGULATION_RULE", "BOTTOM", "TOP", "依据",
        "M 377 740 V 796", 397, 774, 0, None,
    ),
    "struct-safety-block": (
        "SAFETY_CHECK", "BLOCK_REASON", "RIGHT", "LEFT", "识别",
        "M 877 706 H 1050", 958, 693, 0, None,
    ),
    "struct-block-remediation": (
        "BLOCK_REASON", "REMEDIATION_ACTION", "RIGHT", "LEFT", "建议",
        "M 1225 706 H 1375", 1298, 693, 0, None,
    ),
    "struct-block-evidence": (
        "BLOCK_REASON", "EVIDENCE", "BOTTOM", "TOP", "证明",
        "M 1137 738 V 796", 1156, 773, 0, None,
    ),
    "struct-safety-evidence": (
        "SAFETY_CHECK", "EVIDENCE", "BOTTOM", "LEFT", "引用",
        "M 753 771 V 826 H 1050", 894, 818, 1, None,
    ),
    "struct-evidence-operator": (
        "EVIDENCE", "OPERATOR_EVIDENCE", "RIGHT", "LEFT", "来源于",
        "M 1229 826 H 1380", 1303, 813, 0, None,
    ),
}

EXPECTED_ZERO_BEND_EDGES = {
    "struct-user-verification",
    "struct-verification-number",
    "struct-number-operator-service",
    "struct-number-operator-alloc",
    "struct-account-bill",
    "struct-bill-payment",
    "struct-port-donor",
    "struct-donor-step",
    "struct-step-auth",
    "struct-auth-exception",
    "struct-exception-impact",
    "struct-safety-condition",
    "struct-safety-block",
    "struct-block-remediation",
    "struct-block-evidence",
    "struct-evidence-operator",
}

PATH_TOKEN = re.compile(r"[MHV]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)")
CHINESE = re.compile(r"[\u3400-\u9fff]")


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class Segment:
    start: Point
    end: Point

    @property
    def direction(self) -> str:
        return "H" if self.start.y == self.end.y else "V"


@dataclass(frozen=True)
class ParsedPath:
    subpaths: tuple[tuple[Point, ...], ...]
    segments: tuple[Segment, ...]

    @property
    def points(self) -> tuple[Point, ...]:
        return tuple(point for subpath in self.subpaths for point in subpath)


@dataclass(frozen=True)
class EndpointResult:
    edge_id: str
    source_connected: bool
    target_connected: bool
    source_distance: float
    target_distance: float


def _number(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"non-finite coordinate {value!r}")
    return result


def parse_canonical_path(path: str) -> ParsedPath:
    """Parse the canonical absolute M/H/V subset and reject all other syntax."""

    tokens = PATH_TOKEN.findall(path)
    remainder = PATH_TOKEN.sub("", path)
    if not tokens or tokens[0] != "M" or remainder.strip():
        raise ValueError("path must start with M and contain only absolute M/H/V commands")
    if len(tokens) < 4:
        raise ValueError("path must contain M x y and at least one segment")

    index = 0
    subpaths: list[tuple[Point, ...]] = []
    current_points: list[Point] = []
    while index < len(tokens):
        command = tokens[index]
        index += 1
        if command == "M":
            if current_points:
                if len(current_points) < 2:
                    raise ValueError("each M subpath must contain at least one segment")
                subpaths.append(tuple(current_points))
            try:
                x = _number(tokens[index])
                y = _number(tokens[index + 1])
            except (IndexError, ValueError) as exc:
                raise ValueError("M must be followed by two coordinates") from exc
            index += 2
            current_points = [Point(x, y)]
            continue
        if command not in {"H", "V"} or not current_points:
            raise ValueError(f"expected M, H, or V, got {command!r}")
        try:
            coordinate = _number(tokens[index])
        except (IndexError, ValueError) as exc:
            raise ValueError(f"{command} must be followed by one coordinate") from exc
        index += 1
        if command == "H":
            next_point = Point(coordinate, y)
            x = coordinate
        else:
            next_point = Point(x, coordinate)
            y = coordinate
        if next_point == current_points[-1]:
            raise ValueError("zero-length path segment")
        current_points.append(next_point)

    if len(current_points) < 2:
        raise ValueError("each M subpath must contain at least one segment")
    subpaths.append(tuple(current_points))
    segments: list[Segment] = []
    for subpath in subpaths:
        path_segments = [Segment(a, b) for a, b in zip(subpath, subpath[1:])]
        for previous, current in zip(path_segments, path_segments[1:]):
            if previous.direction == current.direction:
                raise ValueError("consecutive collinear segments must be merged")
        if len(set(subpath)) != len(subpath):
            raise ValueError("path folds back to a previously visited point")
        segments.extend(path_segments)
    return ParsedPath(tuple(subpaths), tuple(segments))


def count_path_bends(parsed: ParsedPath) -> int:
    bends = 0
    for subpath in parsed.subpaths:
        directions = [
            "H" if start.y == end.y else "V"
            for start, end in zip(subpath, subpath[1:])
        ]
        bends += sum(
            previous != current
            for previous, current in zip(directions, directions[1:])
        )
    return bends


def _fmt_number(value: float) -> str:
    return str(int(value)) if value.is_integer() else format(value, "g")


def normalize_canonical_path(parsed: ParsedPath) -> str:
    parts: list[str] = []
    for subpath in parsed.subpaths:
        first = subpath[0]
        parts.extend(["M", _fmt_number(first.x), _fmt_number(first.y)])
        for start, end in zip(subpath, subpath[1:]):
            direction = "H" if start.y == end.y else "V"
            parts.extend(
                [
                    direction,
                    _fmt_number(end.x if direction == "H" else end.y),
                ]
            )
    return " ".join(parts)


def _rect(node: dict[str, Any]) -> tuple[float, float, float, float]:
    return (
        float(node["x"]),
        float(node["y"]),
        float(node["x"] + node["width"]),
        float(node["y"] + node["height"]),
    )


def _distance_to_port(point: Point, node: dict[str, Any], port: str) -> float:
    left, top, right, bottom = _rect(node)
    if port in {"LEFT", "RIGHT"}:
        x = left if port == "LEFT" else right
        nearest_y = min(max(point.y, top), bottom)
        return math.hypot(point.x - x, point.y - nearest_y)
    y = top if port == "TOP" else bottom
    nearest_x = min(max(point.x, left), right)
    return math.hypot(point.x - nearest_x, point.y - y)


def _distance_to_segment(point: Point, segment: Segment) -> float:
    if segment.direction == "H":
        low, high = sorted((segment.start.x, segment.end.x))
        nearest_x = min(max(point.x, low), high)
        return math.hypot(point.x - nearest_x, point.y - segment.start.y)
    low, high = sorted((segment.start.y, segment.end.y))
    nearest_y = min(max(point.y, low), high)
    return math.hypot(point.x - segment.start.x, point.y - nearest_y)


def _distance_to_path(point: Point, parsed: ParsedPath) -> float:
    return min(_distance_to_segment(point, segment) for segment in parsed.segments)


def validate_edge_endpoints(
    edge: dict[str, Any],
    parsed: ParsedPath,
    nodes: dict[str, dict[str, Any]],
    buses: dict[str, tuple[dict[str, Any], ParsedPath]],
) -> EndpointResult:
    source_node = nodes[edge["sourceRole"]]
    target_node = nodes[edge["targetRole"]]
    bus_id = edge.get("busId")
    if bus_id:
        source_distance = _distance_to_path(parsed.points[0], buses[bus_id][1])
    else:
        source_distance = _distance_to_port(
            parsed.points[0], source_node, edge["sourcePort"]
        )
    target_distance = _distance_to_port(
        parsed.points[-1], target_node, edge["targetPort"]
    )
    return EndpointResult(
        edge_id=edge["id"],
        source_connected=source_distance <= ENDPOINT_TOLERANCE,
        target_connected=target_distance <= ENDPOINT_TOLERANCE,
        source_distance=source_distance,
        target_distance=target_distance,
    )


def _strictly_inside(point: Point, node: dict[str, Any]) -> bool:
    left, top, right, bottom = _rect(node)
    return left < point.x < right and top < point.y < bottom


def _segment_crosses_node_interior(segment: Segment, node: dict[str, Any]) -> bool:
    left, top, right, bottom = _rect(node)
    if segment.direction == "H":
        if not top < segment.start.y < bottom:
            return False
        low, high = sorted((segment.start.x, segment.end.x))
        return max(low, left) < min(high, right)
    if not left < segment.start.x < right:
        return False
    low, high = sorted((segment.start.y, segment.end.y))
    return max(low, top) < min(high, bottom)


def _overlap_length(first: Segment, second: Segment) -> float:
    if first.direction != second.direction:
        return 0.0
    if first.direction == "H":
        if first.start.y != second.start.y:
            return 0.0
        a0, a1 = sorted((first.start.x, first.end.x))
        b0, b1 = sorted((second.start.x, second.end.x))
    else:
        if first.start.x != second.start.x:
            return 0.0
        a0, a1 = sorted((first.start.y, first.end.y))
        b0, b1 = sorted((second.start.y, second.end.y))
    return max(0.0, min(a1, b1) - max(a0, b0))


def _rects_overlap(first: dict[str, Any], second: dict[str, Any]) -> bool:
    a_left, a_top, a_right, a_bottom = _rect(first)
    b_left, b_top, b_right, b_bottom = _rect(second)
    return max(a_left, b_left) < min(a_right, b_right) and max(
        a_top, b_top
    ) < min(a_bottom, b_bottom)


def _inside_canvas(item: dict[str, Any]) -> bool:
    return (
        item["x"] >= 0
        and item["y"] >= 0
        and item["x"] + item["width"] <= CANVAS_WIDTH
        and item["y"] + item["height"] <= CANVAS_HEIGHT
    )


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _unique_by_id(items: Iterable[dict[str, Any]], label: str, errors: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        item_id = item["id"]
        if item_id in result:
            errors.append(f"duplicate {label} id {item_id}")
        result[item_id] = item
    return result


def _edge_diagnostic(
    edge: dict[str, Any], actual_bends: int | None, endpoint: EndpointResult | None
) -> str:
    source_distance = endpoint.source_distance if endpoint else math.inf
    target_distance = endpoint.target_distance if endpoint else math.inf
    return (
        f"edge id={edge.get('id')} source role={edge.get('sourceRole')} "
        f"target role={edge.get('targetRole')} path={edge.get('path')!r} "
        f"bend count={actual_bends!r} source distance={source_distance:.2f} "
        f"target distance={target_distance:.2f}"
    )


def validate() -> tuple[dict[str, int], list[str]]:
    errors: list[str] = []
    geometry_errors: list[str] = []
    disconnected_sources = 0
    disconnected_targets = 0
    excessive_bends = 0

    try:
        schema = _load_json(SCHEMA_PATH)
        data = _load_json(CONFIG_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [str(exc)]

    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:  # pragma: no cover - library supplies detailed reason
        return {}, [f"invalid JSON Schema: {exc}"]
    schema_errors = sorted(
        Draft202012Validator(schema).iter_errors(data),
        key=lambda error: [str(part) for part in error.absolute_path],
    )
    errors.extend(
        "schema "
        + "/".join(str(part) for part in error.absolute_path)
        + f": {error.message}"
        for error in schema_errors
    )
    if schema_errors:
        return {}, errors

    if data["canvas"] != {
        "width": 1664,
        "height": 900,
        "view_box": "0 0 1664 900",
        "preserve_aspect_ratio": "xMidYMid meet",
    }:
        errors.append("canvas must be the canonical 1664x900 view box")

    expected_style = {
        "canvas_background": "#ffffff",
        "layer_background": "#ffffff",
        "layer_border": "#111111",
        "layer_border_width": 1.5,
        "layer_separator_width": 1.5,
        "node_background": "#ffffff",
        "node_border": "#111111",
        "node_border_width": 1.5,
        "node_radius": 0,
        "primary_text": "#111111",
        "secondary_text": "#111111",
        "edge": "#111111",
        "edge_width": 1.5,
        "arrow_fill": "#111111",
        "label_background": "#ffffff",
        "label_border": "none",
        "shadow": "none",
        "gradient": "none",
    }
    for key, expected in expected_style.items():
        if data["style"].get(key) != expected:
            errors.append(f"style {key} must be {expected!r}")
    if data["style"]["safety_check"] != {
        "node_border_width": 3.5,
        "font_weight": 700,
        "zh_font_size": 24,
        "en_font_size": 19,
    }:
        errors.append("safety-check style does not match the canonical emphasis")

    layers = _unique_by_id(data["layers"], "layer", errors)
    if set(layers) != set(EXPECTED_LAYERS):
        errors.append(
            f"layer ids differ: expected {sorted(EXPECTED_LAYERS)}, got {sorted(layers)}"
        )
    for layer_id, expected in EXPECTED_LAYERS.items():
        layer = layers.get(layer_id)
        if not layer:
            continue
        actual = (
            layer["order"],
            layer["titleZh"],
            tuple(layer["subtitleLines"]),
            layer["x"],
            layer["y"],
            layer["width"],
            layer["height"],
        )
        if actual != expected:
            errors.append(f"layer {layer_id} differs: expected {expected}, got {actual}")
        if layer["titleArea"] != {"x": 8, "width": 214} or layer["contentX"] != 222:
            errors.append(f"layer {layer_id} has an invalid fixed title area")
        if not _inside_canvas(layer):
            geometry_errors.append(f"layer {layer_id} is outside the canvas")

    nodes = _unique_by_id(data["nodes"], "node", errors)
    if set(nodes) != set(EXPECTED_NODES):
        errors.append(
            f"core node ids differ: expected {sorted(EXPECTED_NODES)}, got {sorted(nodes)}"
        )
    for node_id, expected in EXPECTED_NODES.items():
        node = nodes.get(node_id)
        if not node:
            continue
        actual = (
            node["layerId"],
            node["labelZh"],
            node["labelEn"],
            node["x"],
            node["y"],
            node["width"],
            node["height"],
            node["styleKey"],
        )
        if actual != expected:
            errors.append(f"node {node_id} differs: expected {expected}, got {actual}")
        if not CHINESE.search(node["labelZh"]):
            errors.append(f"node {node_id} is missing its Chinese primary label")
        if "(" in node["labelEn"] or ")" in node["labelEn"]:
            errors.append(f"node {node_id} labelEn must not contain display parentheses")
        if not _inside_canvas(node):
            geometry_errors.append(f"node {node_id} is outside the canvas")
        layer = layers.get(node["layerId"])
        if layer:
            if not (
                node["x"] >= layer["contentX"]
                and node["y"] >= layer["y"]
                and node["x"] + node["width"] <= layer["x"] + layer["width"]
                and node["y"] + node["height"]
                <= layer["y"] + layer["height"] + 4
            ):
                geometry_errors.append(
                    f"node {node_id} is outside content area of {node['layerId']}"
                )

    if nodes.get("SAFETY_CHECK", {}).get("styleKey") != "safety_check":
        errors.append("SAFETY_CHECK must use the safety_check style key")
    for node_id, node in nodes.items():
        if node_id != "SAFETY_CHECK" and node.get("styleKey") != "ordinary":
            errors.append(f"ordinary node {node_id} has non-ordinary style")

    node_items = list(nodes.values())
    for index, first in enumerate(node_items):
        for second in node_items[index + 1 :]:
            if _rects_overlap(first, second):
                geometry_errors.append(f"nodes {first['id']} and {second['id']} overlap")

    raw_buses = _unique_by_id(data["buses"], "bus", errors)
    if set(raw_buses) != {"service-offering-bus"}:
        errors.append("exactly one service-offering-bus is required")
    parsed_buses: dict[str, tuple[dict[str, Any], ParsedPath]] = {}
    for bus_id, bus in raw_buses.items():
        try:
            parsed = parse_canonical_path(bus["path"])
            actual_bends = count_path_bends(parsed)
            if normalize_canonical_path(parsed) != bus["path"]:
                errors.append(f"bus {bus_id} path is not normalized")
            if actual_bends != bus["bendCount"] or actual_bends > 1:
                errors.append(
                    f"bus {bus_id} bend count {actual_bends} != declared {bus['bendCount']}"
                )
            parsed_buses[bus_id] = (bus, parsed)
        except ValueError as exc:
            errors.append(f"bus {bus_id} invalid path: {exc}")
            continue
        source = nodes.get(bus["sourceRole"])
        if source:
            distance = _distance_to_port(parsed.points[0], source, bus["sourcePort"])
            if distance > ENDPOINT_TOLERANCE:
                disconnected_sources += 1
                errors.append(
                    f"bus {bus_id} source is disconnected from {bus['sourceRole']}: "
                    f"distance={distance:.2f}"
                )
        for node_id, node in nodes.items():
            if node_id == bus["sourceRole"]:
                continue
            for segment in parsed.segments:
                if _segment_crosses_node_interior(segment, node):
                    geometry_errors.append(f"bus {bus_id} crosses node {node_id}")
                    break

    service_bus = raw_buses.get("service-offering-bus", {})
    if service_bus:
        expected_bus = {
            "sourceRole": "MOBILE_NUMBER_IDENTITY",
            "sourcePort": "BOTTOM",
            "path": "M 1066 114 V 350 H 366 M 366 350 H 1456",
            "bendCount": 1,
            "edgeIds": [
                "struct-number-plan",
                "struct-number-contract",
                "struct-number-broadband",
                "struct-number-vas",
                "struct-number-right",
            ],
        }
        for key, expected in expected_bus.items():
            if service_bus.get(key) != expected:
                errors.append(f"service-offering-bus {key} differs from canonical value")

    edges = _unique_by_id(data["edges"], "edge", errors)
    if set(edges) != set(EXPECTED_EDGES):
        errors.append(
            f"structural edge ids differ: expected {sorted(EXPECTED_EDGES)}, got {sorted(edges)}"
        )

    parsed_edges: dict[str, ParsedPath] = {}
    endpoints: dict[str, EndpointResult] = {}
    for edge_id, edge in edges.items():
        if edge["fromRole"] != edge["sourceRole"]:
            errors.append(f"edge {edge_id} fromRole and sourceRole differ")
        if edge["toRole"] != edge["targetRole"]:
            errors.append(f"edge {edge_id} toRole and targetRole differ")
        if edge["sourceRole"] not in nodes or edge["targetRole"] not in nodes:
            errors.append(f"edge {edge_id} references a missing endpoint role")
            continue
        bus_id = edge.get("busId")
        if bus_id and bus_id not in parsed_buses:
            errors.append(f"edge {edge_id} references missing bus {bus_id}")
            continue
        try:
            parsed = parse_canonical_path(edge["path"])
            actual_bends = count_path_bends(parsed)
            parsed_edges[edge_id] = parsed
            if normalize_canonical_path(parsed) != edge["path"]:
                errors.append(f"edge {edge_id} path is not normalized")
        except ValueError as exc:
            errors.append(f"edge {edge_id} invalid path: {exc}")
            continue

        endpoint = validate_edge_endpoints(edge, parsed, nodes, parsed_buses)
        endpoints[edge_id] = endpoint
        if not endpoint.source_connected:
            disconnected_sources += 1
        if not endpoint.target_connected:
            disconnected_targets += 1
        if not endpoint.source_connected or not endpoint.target_connected:
            errors.append(_edge_diagnostic(edge, actual_bends, endpoint))
        if actual_bends != edge["bendCount"] or actual_bends > 3:
            excessive_bends += 1
            errors.append(_edge_diagnostic(edge, actual_bends, endpoint))
        if edge_id in EXPECTED_ZERO_BEND_EDGES and actual_bends != 0:
            errors.append(f"edge {edge_id} must have zero bends")

        expected = EXPECTED_EDGES.get(edge_id)
        if expected:
            actual = (
                edge["fromRole"],
                edge["toRole"],
                edge["sourcePort"],
                edge["targetPort"],
                edge["labelZh"],
                edge["path"],
                edge["labelX"],
                edge["labelY"],
                edge["bendCount"],
                edge.get("busId"),
            )
            if actual != expected:
                errors.append(f"edge {edge_id} differs from canonical specification")

        for node_id, node in nodes.items():
            if node_id in {edge["sourceRole"], edge["targetRole"]}:
                continue
            for segment in parsed.segments:
                if _segment_crosses_node_interior(segment, node):
                    geometry_errors.append(f"edge {edge_id} crosses node {node_id}")
                    break
        label = Point(float(edge["labelX"]), float(edge["labelY"]))
        for node_id, node in nodes.items():
            if _strictly_inside(label, node):
                geometry_errors.append(f"label of edge {edge_id} is inside node {node_id}")
        if _distance_to_path(label, parsed) > 64:
            geometry_errors.append(f"label of edge {edge_id} is too far from its path")

    if service_bus:
        bus_edge_ids = [
            edge_id
            for edge_id, edge in edges.items()
            if edge.get("busId") == "service-offering-bus"
        ]
        if bus_edge_ids != service_bus["edgeIds"]:
            errors.append("service bus edgeIds do not match bus-linked edges in render order")
        for edge_id in service_bus["edgeIds"]:
            if edge_id not in edges:
                errors.append(f"service bus references missing edge {edge_id}")

    edge_items = list(edges.values())
    for index, first in enumerate(edge_items):
        first_path = parsed_edges.get(first["id"])
        if not first_path:
            continue
        for second in edge_items[index + 1 :]:
            second_path = parsed_edges.get(second["id"])
            if not second_path:
                continue
            # Shared role endpoints may intentionally share the initial boundary rail.
            if {
                first["sourceRole"],
                first["targetRole"],
            } & {second["sourceRole"], second["targetRole"]}:
                continue
            if first.get("busId") and first.get("busId") == second.get("busId"):
                continue
            if any(
                _overlap_length(a, b) > ENDPOINT_TOLERANCE
                for a in first_path.segments
                for b in second_path.segments
            ):
                geometry_errors.append(
                    f"edges {first['id']} and {second['id']} have unexpected overlap"
                )

    markers = _unique_by_id(data["markers"], "marker", errors)
    marker = markers.get("primary-secondary-card-association")
    if set(markers) != {"primary-secondary-card-association"} or not marker:
        errors.append("exactly one primary-secondary-card-association marker is required")
    else:
        expected_marker_fields = {
            "type": "PRIMARY_SECONDARY_CARD",
            "anchorRole": "MOBILE_NUMBER_IDENTITY",
            "rect": {"x": 1045, "y": 126, "width": 48, "height": 42},
            "labelZh": "主副卡关联",
            "labelX": 1120,
            "labelY": 153,
            "style": {
                "stroke": "#111111",
                "strokeWidth": 1.5,
                "strokeDasharray": "7 5",
                "fill": "none",
            },
        }
        for key, expected in expected_marker_fields.items():
            if marker.get(key) != expected:
                errors.append(f"primary/secondary-card marker {key} differs")
        expected_arrow_paths = ["M 1057 126 V 114", "M 1081 126 V 114"]
        if [arrow["path"] for arrow in marker["arrows"]] != expected_arrow_paths:
            errors.append("primary/secondary-card marker arrow paths differ")
        for arrow in marker["arrows"]:
            try:
                parsed = parse_canonical_path(arrow["path"])
            except ValueError as exc:
                errors.append(f"marker arrow {arrow['id']} invalid path: {exc}")
                continue
            target = nodes.get(arrow["targetRole"])
            if target:
                distance = _distance_to_port(
                    parsed.points[-1], target, arrow["targetPort"]
                )
                if distance > ENDPOINT_TOLERANCE:
                    errors.append(
                        f"marker arrow {arrow['id']} target disconnected: {distance:.2f}"
                    )
        if not _inside_canvas(marker["rect"]):
            geometry_errors.append("primary/secondary-card marker is outside the canvas")

    # Deduplicate geometry messages so the summary is a count of distinct violations.
    geometry_errors = list(dict.fromkeys(geometry_errors))
    errors.extend(f"geometry: {message}" for message in geometry_errors)
    summary = {
        "layers": len(data["layers"]),
        "nodes": len(data["nodes"]),
        "edges": len(data["edges"]),
        "buses": len(data["buses"]),
        "markers": len(data["markers"]),
        "disconnected_sources": disconnected_sources,
        "disconnected_targets": disconnected_targets,
        "excessive_bends": excessive_bends,
        "geometry_violations": len(geometry_errors),
    }
    return summary, errors


def main() -> int:
    summary, errors = validate()
    if errors:
        print("Canonical business diagram FAILED:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Canonical business diagram passed:")
    print(f"canvas: {CANVAS_WIDTH}x{CANVAS_HEIGHT}")
    print(f"layers: {summary['layers']}")
    print(f"core nodes: {summary['nodes']}")
    print(f"disconnected sources: {summary['disconnected_sources']}")
    print(f"disconnected targets: {summary['disconnected_targets']}")
    print(f"excessive bends: {summary['excessive_bends']}")
    print(f"geometry violations: {summary['geometry_violations']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
