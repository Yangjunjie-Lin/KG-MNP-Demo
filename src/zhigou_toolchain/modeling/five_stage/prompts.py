"""Read-only source catalogue. Never substitutes current templates for old requests.

AST extraction does not execute source, read fixtures, or supply model inputs.
The task strings and wrappers remain in their original execution functions.
"""
from __future__ import annotations

import ast
from pathlib import Path

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.modeling.delivery.exchange_io import digest

PACKAGE = Path(__file__).parents[2]
PROMPT_SOURCES = (
    "services/modeling_five_stage.py", "modeling/five_stage/assistance.py",
    "modeling/five_stage/tools.py", "modeling/five_stage/compatible.py",
    "ontology_io/engine.py", "ontology_io/kernel.py", "ontology_io/transport_worker.py", "ontology_io/prompt_views.py", "ontology_io/source_quotes.py", "ontology_io/vocabulary.py",
)


def source_catalogue():
    templates, wrappers, sources, builders, policies = [], [], {}, [], []
    for relative in PROMPT_SOURCES:
        path = PACKAGE / relative
        if not path.is_file():
            continue
        raw = path.read_bytes()
        # Catalogue identity is portable across Git checkout newline settings.
        # Actual runtime file BYTES are separately frozen in prompt_reference
        # and harness; never compare these two hash profiles as one object.
        source = raw.decode("utf-8").replace("\r\n", "\n")
        sources[relative] = digest(source.encode("utf-8"))
        tree = ast.parse(source)
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        def owner(node, parents=parents):
            names = []
            while node in parents:
                node = parents[node]
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    names.append(node.name)
            return ".".join(reversed(names))
        for node in ast.walk(tree):
            if (relative in {"modeling/five_stage/tools.py", "modeling/five_stage/compatible.py"}
                    and isinstance(node, ast.FunctionDef) and owner(node) in {"QwenClient", "CompatibleClient"}):
                if node.name in {"__init__", "configure_request_profile"}:
                    policies.append({"source": relative, "function": owner(node) + "." + node.name,
                        "code": ast.get_source_segment(source, node), "source_sha256": sources[relative]})
                elif node.name == "propose":
                    post = next(c for c in ast.walk(node) if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr == "_request")
                    policies.append({"source": relative, "function": owner(node) + ".propose.request_builder",
                        "code": "\n".join(source.splitlines()[node.lineno - 1:post.lineno]), "source_sha256": sources[relative]})
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in {"instruction", "schema", "body", "output_schema", "GUIDE"} for t in node.targets):
                builders.append({"source": relative, "function": owner(node), "line": node.lineno,
                    "target": ast.unparse(node.targets[0]), "expression": ast.get_source_segment(source, node.value),
                    "source_sha256": sources[relative]})
            if (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in {"system", "payload"} for t in node.targets)
                    and owner(node).endswith(".propose")):
                wrappers.append({"wrapper_id": relative + "::" + owner(node) + "." + ast.unparse(node.targets[0]),
                    "source": relative, "function": owner(node), "source_sha256": sources[relative],
                    "expression": ast.get_source_segment(source, node.value),
                    "literal_parts": [c.value for c in ast.walk(node.value) if isinstance(c, ast.Constant) and isinstance(c.value, str)]})
            if not isinstance(node, ast.Call):
                continue
            name = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else ""
            if name not in {"propose", "ask", "contextual_ask"} or not node.args:
                continue
            offset = 1 if isinstance(node.args[0], ast.Constant) and type(node.args[0].value) is int else 0
            args = node.args[offset:]
            task = args[0]
            parent = parents.get(node)
            target = ast.unparse(parent.targets[0]) if isinstance(parent, ast.Assign) else name
            identifier = relative + "::" + owner(node) + "." + target
            text = task.value if isinstance(task, ast.Constant) and isinstance(task.value, str) else None
            row = {"template_id": identifier, "source": relative, "function": owner(node),
                "line": node.lineno, "source_sha256": sources[relative],
                "group": "RESEARCH_ADAPTER" if relative.startswith("ontology_io/") else "PRODUCTION",
                "task_text": text, "task_expression": ast.get_source_segment(source, task),
                "context_expression": ast.get_source_segment(source, args[1]) if len(args) > 1 else None,
                "schema_expression": ast.get_source_segment(source, args[2]) if len(args) > 2 else None,
                "task_sha256": semantic_hash(text) if text is not None else None,
                "scope": "CURRENT_SOURCE_NOT_HISTORICAL_CAPTURE"}
            row["template_version"] = semantic_hash({k: row[k] for k in ("task_expression", "context_expression", "schema_expression")})
            templates.append(row)
    return {"format": "zhigou-prompt-catalogue/1.0.0", "templates": templates, "wrappers": wrappers,
        "source_hash_profile": "SHA256_UTF8_LF_NORMALIZED_SOURCE",
        "source_files": sources, "dynamic_builders": builders, "request_policies": policies,
        "scope": "CLIENT_TASK_WRAPPER_AND_SCHEMA_SOURCE_NOT_SERVER_TOKEN_TEMPLATE",
        "exclusions": {"recorded_providers": "Replay/import only; no physical chat request",
            "tests_and_tools": "Synthetic fixtures and explicit probes; not production templates",
            "hidden_reasoning": "Never captured"}}


def prompt_reference(task, client, schema):
    catalogue = source_catalogue()
    matches = [t for t in catalogue["templates"] if t["task_text"] == task]
    wrapper = "modeling/five_stage/compatible.py" if any(c.__name__ == "CompatibleClient" for c in type(client).__mro__) else "modeling/five_stage/tools.py"
    return {"template_refs": [{**{k: t[k] for k in ("template_id", "template_version", "source", "task_sha256")},
            "source_sha256": digest((PACKAGE / t["source"]).read_bytes()), "catalogue_source_sha256": t["source_sha256"]} for t in matches],
        "template_status": "SOURCE_MATCHED" if matches else "DYNAMIC_OR_EXTERNAL_TASK",
        "task_sha256": semantic_hash(task), "schema_sha256": semantic_hash(schema),
        "source_hash_profile": "SHA256_ACTUAL_RUNTIME_FILE_BYTES",
        "wrapper_source": wrapper, "wrapper_sha256": digest((PACKAGE / wrapper).read_bytes()),
        "configured_revision": client.lock.revision,
        "request_scope": "CLIENT_REQUEST_NOT_SERVER_TOKEN_SEQUENCE"}


def catalogue_identity():
    """Freeze source/template identity without duplicating code in every journal.

    Source code mentioning credential key names is not runtime credentials, but
    remains subject to the conservative quoted-text filter in content channels.
    """
    catalogue = source_catalogue()
    return {"catalogue_sha256": semantic_hash(catalogue), "source_hash_profile": "SHA256_ACTUAL_RUNTIME_FILE_BYTES",
        "source_files": {p: digest((PACKAGE / p).read_bytes()) for p in catalogue["source_files"]},
        "templates": [{k: t[k] for k in ("template_id", "template_version", "task_sha256", "source", "source_sha256")}
            for t in catalogue["templates"]]}


def markdown(catalogue):
    lines = ["# 当前模型调用 Prompt（同源生成）", "",
        "由 `python -m tools.generate_model_prompts` 从执行源码 AST 生成；不得手改。当前模板不是历史请求。",
        "本目录源码摘要使用 UTF-8/LF 规范化；每次实际运行另保存源码原字节摘要（不同哈希对象，不混比）。",
        "system/user、动态 Schema、参数及公开响应以授权的物理 POST 快照为准；未发送参数不补默认值。",
        "Qwen 使用 structured_outputs.json；Compatible 将 Schema 拼入 system，json_schema 模式同时传 response_format。",
        "研究适配器单列；录制 provider 不推理，tests/tools 的探针不是生产 Prompt。服务端 token 模板和私有推理不可得。", ""]
    for row in catalogue["templates"]:
        lines += ["## " + row["template_id"], "", f"分组：{row['group']}；源码 `{row['source']}::{row['function']}`。",
            f"模板版本 `{row['template_version']}`；来源 UTF-8/LF 摘要 `{row['source_sha256']}`。", "",
            "实际任务全文：" if row["task_text"] is not None else "动态任务表达式（全文只在本次调用时确定）：", "", "```text",
            row["task_text"] or row["task_expression"], "```", "", "输入变量/构造入口：", "```python",
            row["context_expression"] or "由调用方传入", "```", "动态 Schema 构造：", "```python", row["schema_expression"] or "由调用方传入", "```", ""]
    for row in catalogue["wrappers"]:
        lines += ["## " + row["wrapper_id"], "", "实际包装表达式（含参数拼装）：", "", "```python", row["expression"], "```", ""]
    for row in catalogue["dynamic_builders"]:
        lines += ["## 动态构造 " + row["source"] + "::" + row["function"] + "." + row["target"], "", "```python", row["expression"], "```", ""]
    for row in catalogue["request_policies"]:
        lines += ["## 参数与请求拼装 " + row["source"] + "::" + row["function"], "", "```python", row["code"], "```", ""]
    return "\n".join(lines).replace("\r\n", "\n")
