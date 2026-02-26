#!/usr/bin/env python3
import ast
import json
import re
from datetime import date
from pathlib import Path


def stringify(node):
    if isinstance(node, ast.Constant):
        return str(node.value)
    if isinstance(node, ast.JoinedStr):
        out = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                out.append(str(value.value))
            elif isinstance(value, ast.FormattedValue):
                out.append("{expr}")
        return "".join(out)
    return None


def normalize_path(path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return path


def build_matrix(root: Path):
    api_root = root / "src/api"
    routers_dir = api_root / "routers"

    main_text = (api_root / "main.py").read_text(encoding="utf-8")
    policy = {}
    for match in re.finditer(r"app\.include_router\(([^,\n]+)(?:,\s*dependencies=([^\)]+))?\)", main_text):
        name = match.group(1).strip()
        deps = match.group(2) or ""
        if "_admin_deps" in deps:
            policy[name] = "admin_key"
        elif "_api_deps" in deps:
            policy[name] = "api_key"
        else:
            policy[name] = "none"

    policy["register_engine_chat"] = "api_key" if "register_engine_chat(app, dependencies=_api_deps)" in main_text else "none"
    policy["register_roundtable"] = "api_key" if "register_roundtable(app, dependencies=_api_deps)" in main_text else "none"

    routes = []
    for py in sorted(routers_dir.glob("*.py")):
        text = py.read_text(encoding="utf-8")
        tree = ast.parse(text)

        prefixes = {}
        for node in tree.body:
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "APIRouter"
            ):
                target = node.targets[0].id
                prefix = ""
                for kw in node.value.keywords:
                    if kw.arg == "prefix" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        prefix = kw.value.value
                prefixes[target] = prefix

        if py.name == "health.py":
            base_auth = "none"
        elif py.name == "admin.py":
            base_auth = "admin_key"
        elif py.name == "engine_chat.py":
            base_auth = policy.get("register_engine_chat", "api_key")
        elif py.name == "engine_roundtable.py":
            base_auth = policy.get("register_roundtable", "api_key")
        else:
            base_auth = policy.get(f"{py.stem}_router", "api_key")

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and isinstance(dec.func.value, ast.Name):
                    router_var = dec.func.value.id
                    method = dec.func.attr.upper()
                    if method in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                        if dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str):
                            sub = dec.args[0].value
                            prefix = prefixes.get(router_var, "")
                            full = (prefix.rstrip("/") + "/" + sub.lstrip("/")).replace("//", "/")
                            full = normalize_path(full)
                            routes.append(
                                {
                                    "file": str(py.relative_to(root)),
                                    "method": method,
                                    "path": full,
                                    "auth": base_auth,
                                }
                            )
                    elif method == "WEBSOCKET":
                        if dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str):
                            routes.append(
                                {
                                    "file": str(py.relative_to(root)),
                                    "method": "WS",
                                    "path": dec.args[0].value,
                                    "auth": "api_key_query_param",
                                }
                            )

    unique_routes = {}
    for route in routes:
        unique_routes[(route["method"], route["path"], route["auth"])] = route
    routes = sorted(unique_routes.values(), key=lambda x: (x["method"], x["path"]))

    route_index = {}
    for route in routes:
        route_index.setdefault(route["method"], []).append(route)

    regex_cache = {}

    def route_regex(path: str):
        if path not in regex_cache:
            regex_cache[path] = re.compile("^" + re.sub(r"\{[^/]+\}", r"[^/]+", path) + "$")
        return regex_cache[path]

    calls = []

    for html in (root / "src/web/templates").rglob("*.html"):
        lines = html.read_text(encoding="utf-8").splitlines()
        for idx, line in enumerate(lines, start=1):
            if "fetch(" not in line:
                continue
            match = re.search(r"fetch\(\s*['\"]([^'\"]+)['\"]", line)
            if not match:
                continue
            path = match.group(1)
            if not (path.startswith("/api") or path.startswith("/ws")):
                continue
            window = "\n".join(lines[idx - 1 : min(idx + 7, len(lines))])
            method_match = re.search(r"method\s*:\s*['\"]([A-Za-z]+)['\"]", window)
            method = method_match.group(1).upper() if method_match else "GET"
            calls.append(
                {
                    "kind": "template",
                    "file": str(html.relative_to(root)),
                    "line": idx,
                    "method": method,
                    "path": path,
                }
            )

    for base, kind in [(root / "scripts", "script"), (root / "tests", "test"), (root / "src/api/tests", "test")]:
        if not base.exists():
            continue
        for py in base.rglob("*.py"):
            try:
                tree = ast.parse(py.read_text(encoding="utf-8"))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)):
                    continue

                owner = node.func.value.id
                method = node.func.attr.lower()
                if method not in {"get", "post", "put", "patch", "delete"}:
                    continue

                if owner in {"requests", "client", "test_client", "tc"} and node.args:
                    path = stringify(node.args[0])
                    if path:
                        calls.append(
                            {
                                "kind": kind,
                                "file": str(py.relative_to(root)),
                                "line": node.lineno,
                                "method": method.upper(),
                                "path": path,
                            }
                        )

    matrix = []
    for call in calls:
        path = call["path"]
        if path.startswith("http://") or path.startswith("https://"):
            host_match = re.match(r"https?://[^/]+(/.*)$", path)
            path = host_match.group(1) if host_match else path

        path = path.split("?", 1)[0]
        method = "WS" if path.startswith("/ws") else call["method"]

        query_path = path[4:] if path.startswith("/api") else path
        query_path = normalize_path(query_path)

        found = None
        match_kind = "none"

        for route in route_index.get(method, []):
            if route["path"] == query_path:
                found = route
                match_kind = "exact"
                break

        if found is None:
            for route in route_index.get(method, []):
                if route_regex(route["path"]).match(query_path):
                    found = route
                    match_kind = "param"
                    break

        matrix.append(
            {
                **call,
                "normalized_path": path,
                "match": match_kind,
                "matched_route": found["path"] if found else None,
                "route_file": found["file"] if found else None,
                "auth": found["auth"] if found else "unresolved",
            }
        )

    matrix = sorted(matrix, key=lambda x: (x["file"], x["line"]))
    unresolved = [
        row
        for row in matrix
        if row["normalized_path"].startswith("/api") and "{expr}" not in row["normalized_path"] and row["match"] == "none"
    ]

    summary = {
        "date": str(date.today()),
        "route_count": len(routes),
        "call_count": len(matrix),
        "template_calls": sum(1 for row in matrix if row["kind"] == "template"),
        "test_calls": sum(1 for row in matrix if row["kind"] == "test"),
        "script_calls": sum(1 for row in matrix if row["kind"] == "script"),
        "unresolved_literal_api_calls": len(unresolved),
    }

    return summary, routes, matrix, unresolved


def write_outputs(root: Path, summary, routes, matrix, unresolved):
    today = date.today()
    md = root / f"ENDPOINT_CALL_MATRIX_{today}.md"
    js = root / f"endpoint_call_matrix_{today}.json"

    js.write_text(
        json.dumps(
            {
                "summary": summary,
                "routes": routes,
                "matrix": matrix,
                "unresolved": unresolved,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    lines = [f"# Endpoint Call Matrix — {today}", "", "## Summary", ""]
    for key, value in summary.items():
        lines.append(f"- {key}: {value}")

    lines += ["", "## Unresolved Literal /api Calls", ""]
    if unresolved:
        lines += ["| Kind | File | Line | Method | Path |", "|---|---|---:|---|---|"]
        for row in unresolved:
            lines.append(
                f"| {row['kind']} | {row['file']} | {row['line']} | {row['method']} | {row['normalized_path']} |"
            )
    else:
        lines.append("- None")

    lines += [
        "",
        "## Full Matrix",
        "",
        "| Kind | File | Line | Method | Call Path | Route | Auth | Match |",
        "|---|---|---:|---|---|---|---|---|",
    ]

    for row in matrix:
        lines.append(
            f"| {row['kind']} | {row['file']} | {row['line']} | {row['method']} | {row['normalized_path']} | {row['matched_route'] or ''} | {row['auth']} | {row['match']} |"
        )

    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md, js


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    summary_data, routes_data, matrix_data, unresolved_data = build_matrix(project_root)
    md_path, json_path = write_outputs(project_root, summary_data, routes_data, matrix_data, unresolved_data)
    print(md_path)
    print(json_path)
    print(json.dumps(summary_data, indent=2))
