#!/usr/bin/env python3
import ast
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "src" / "api"
ROUTERS_DIR = API_DIR / "routers"


def normalize_path(path: str) -> str:
    clean = path.split("?")[0]
    if clean.startswith("/api/"):
        clean = clean[4:]
    if clean == "/api":
        clean = "/"
    if clean != "/" and clean.endswith("/"):
        clean = clean.rstrip("/")
    return clean


def parse_main_auth():
    main_src = (API_DIR / "main.py").read_text(encoding="utf-8")
    main_ast = ast.parse(main_src)

    router_auth = {}
    for node in ast.walk(main_ast):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "include_router":
            if not node.args or not isinstance(node.args[0], ast.Name):
                continue
            name = node.args[0].id
            auth = "public"
            for kw in node.keywords or []:
                if kw.arg == "dependencies":
                    txt = ast.get_source_segment(main_src, kw.value) or ""
                    if "_admin_deps" in txt or "require_admin_key" in txt:
                        auth = "admin"
                    elif "_api_deps" in txt or "require_api_key" in txt:
                        auth = "api"
            router_auth[name] = auth

    router_alias_to_file = {}
    for node in main_ast.body:
        if isinstance(node, ast.Try):
            for stmt in node.body:
                if isinstance(stmt, ast.ImportFrom) and stmt.module and ".routers." in stmt.module:
                    mod = stmt.module.split(".")[-1]
                    for alias in stmt.names:
                        if alias.name == "router" and alias.asname:
                            router_alias_to_file[alias.asname] = mod + ".py"
            break

    return main_src, router_auth, router_alias_to_file


def parse_router_routes():
    routes = []
    for rf in ROUTERS_DIR.glob("*.py"):
        src = rf.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src)
        except Exception:
            continue

        prefix = ""
        for n in ast.walk(tree):
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call):
                fn = n.value.func
                if isinstance(fn, ast.Name) and fn.id == "APIRouter":
                    for kw in n.value.keywords or []:
                        if kw.arg == "prefix" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                            prefix = kw.value.value

        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in n.decorator_list:
                    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                        if not (isinstance(dec.func.value, ast.Name) and dec.func.value.id == "router"):
                            continue
                        m = dec.func.attr.lower()
                        methods = []
                        if m in {"get", "post", "put", "patch", "delete", "options", "head"}:
                            methods = [m.upper()]
                        elif m == "api_route":
                            for kw in dec.keywords or []:
                                if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
                                    for e in kw.value.elts:
                                        if isinstance(e, ast.Constant) and isinstance(e.value, str):
                                            methods.append(e.value.upper())
                            if not methods:
                                methods = ["GET"]

                        if not methods:
                            continue

                        path = ""
                        if dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str):
                            path = dec.args[0].value

                        full = (prefix.rstrip("/") + "/" + path.lstrip("/")).replace("//", "/")
                        if not full.startswith("/"):
                            full = "/" + full

                        routes.append({"router_file": rf.name, "path": full, "methods": methods})
    return routes


def parse_app_routes():
    routes = []
    for p in [API_DIR / "main.py", ROUTERS_DIR / "engine_chat.py", ROUTERS_DIR / "engine_roundtable.py"]:
        if not p.exists():
            continue
        src = p.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src)
        except Exception:
            continue
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in n.decorator_list:
                    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                        if not (isinstance(dec.func.value, ast.Name) and dec.func.value.id == "app"):
                            continue
                        m = dec.func.attr.lower()
                        if m not in {"get", "post", "put", "patch", "delete", "options", "head"}:
                            continue
                        path = ""
                        if dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str):
                            path = dec.args[0].value
                        routes.append({"router_file": p.name, "path": normalize_path(path), "methods": [m.upper()]})
    return routes


def extract_calls():
    calls = []

    def add_call(source_type, file, line, method, path):
        if not path.startswith("/"):
            return
        clean_path = normalize_path(path)
        calls.append(
            {
                "source_type": source_type,
                "file": str(file.relative_to(ROOT)),
                "line": line,
                "method": method.upper(),
                "path": clean_path,
            }
        )

    for f in (ROOT / "src/web/templates").glob("*.html"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        api_vars = {
            m.group(1): m.group(2)
            for m in re.finditer(r"const\s+([A-Za-z_]\w*)\s*=\s*['\"](/api[^'\"]*)['\"]", text)
        }

        fetch_re = re.compile(r"fetch\((['\"])(/api/[^'\"]*)\1", re.I)
        for m in fetch_re.finditer(text):
            line = text[: m.start()].count("\n") + 1
            method = "GET"
            window = text[m.end() : m.end() + 220]
            m2 = re.search(r"method\s*:\s*['\"](GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)['\"]", window, re.I)
            if m2:
                method = m2.group(1).upper()
            add_call("template", f, line, method, m.group(2))

        fetch_tpl_re = re.compile(r"fetch\(\s*`\$\{([A-Za-z_]\w*)\}([^`]*)`", re.I)
        for m in fetch_tpl_re.finditer(text):
            var_name = m.group(1)
            base = api_vars.get(var_name)
            if not base:
                continue
            line = text[: m.start()].count("\n") + 1
            method = "GET"
            window = text[m.end() : m.end() + 220]
            m2 = re.search(r"method\s*:\s*['\"](GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)['\"]", window, re.I)
            if m2:
                method = m2.group(1).upper()
            add_call("template", f, line, method, f"{base}{m.group(2)}")

    for f in (ROOT / "scripts").glob("*.py"):
        lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
        for i, line in enumerate(lines, start=1):
            for m in re.finditer(r"requests\.(get|post|put|patch|delete)\(\s*f?['\"](https?://[^/'\"]+)?([^'\"\)]+)", line, re.I):
                add_call("script", f, i, m.group(1), m.group(3))
            for m in re.finditer(r"urllib\.request\.urlopen\((?:urllib\.request\.Request\()?[f]?['\"](https?://[^/'\"]+)?([^'\"\)]+)", line):
                add_call("script", f, i, "GET", m.group(2))

    for base in [ROOT / "tests", ROOT / "src/api/tests"]:
        if not base.exists():
            continue
        for f in base.rglob("*.py"):
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
            for i, line in enumerate(lines, start=1):
                for m in re.finditer(r"client\.(get|post|put|patch|delete)\(\s*[f]?['\"]([^'\"]+)", line, re.I):
                    path = m.group(2)
                    if path.startswith(("/api/", "/engine/", "/graphql", "/health", "/status", "/heartbeat", "/host-stats")):
                        add_call("test", f, i, m.group(1), path)
                for m in re.finditer(r"requests\.(get|post|put|patch|delete)\(\s*[f]?['\"](https?://[^/'\"]+)?([^'\"]+)", line, re.I):
                    path = m.group(3)
                    if path.startswith(("/api/", "/engine/", "/graphql", "/health", "/status", "/heartbeat", "/host-stats")):
                        add_call("test", f, i, m.group(1), path)

    return calls


def main():
    _, router_auth, router_alias_to_file = parse_main_auth()
    routes = parse_router_routes() + parse_app_routes()

    file_to_auth = {fname: router_auth.get(alias, "unknown") for alias, fname in router_alias_to_file.items()}

    for route in routes:
        if route["router_file"] in {"main.py", "engine_chat.py", "engine_roundtable.py"}:
            p = route["path"]
            if p.startswith("/health") or p.startswith("/status") or p.startswith("/heartbeat") or p.startswith("/host-stats") or p.startswith("/api/metrics"):
                route["auth"] = "public"
            else:
                route["auth"] = "api"
        else:
            route["auth"] = file_to_auth.get(route["router_file"], "unknown")

    index = []
    for route in routes:
        route_path = normalize_path(route["path"])
        pattern = "^" + re.escape(route_path) + "$"
        pattern = pattern.replace("\\{", "{").replace("\\}", "}")
        pattern = re.sub(r"\{[^/]+\}", r"[^/]+", pattern)
        index.append((re.compile(pattern), {**route, "path": route_path}))

    rows = []
    calls = extract_calls()
    for call in calls:
        matched = None
        for rgx, route in index:
            if call["method"] in route["methods"] and rgx.match(call["path"]):
                matched = route
                break
        if not matched:
            for rgx, route in index:
                if rgx.match(call["path"]):
                    matched = route
                    break

        rows.append(
            {
                **call,
                "status": "matched" if matched else "unmatched",
                "api_route": matched["path"] if matched else "",
                "api_methods": ",".join(matched["methods"]) if matched else "",
                "auth": matched.get("auth", "") if matched else "",
                "router_file": matched.get("router_file", "") if matched else "",
            }
        )

    out_dir = ROOT / "aria_souvenirs" / "docs"
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "endpoint_call_matrix_2026-02-26.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["source_type", "file", "line", "method", "path", "status", "api_route", "api_methods", "auth", "router_file"],
        )
        writer.writeheader()
        writer.writerows(rows)

    unmatched = [r for r in rows if r["status"] == "unmatched"]
    summary = {
        "routes_total": len(routes),
        "calls_total": len(rows),
        "matched": len(rows) - len(unmatched),
        "unmatched": len(unmatched),
        "unmatched_by_type": {
            "template": sum(1 for r in unmatched if r["source_type"] == "template"),
            "test": sum(1 for r in unmatched if r["source_type"] == "test"),
            "script": sum(1 for r in unmatched if r["source_type"] == "script"),
        },
    }

    json_path = out_dir / "endpoint_call_matrix_summary_2026-02-26.json"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"matrix={csv_path}")
    print(f"summary={json_path}")
    print(json.dumps(summary))
    print("top_unmatched:")
    for row in unmatched[:50]:
        print(f"{row['source_type']} {row['file']}:{row['line']} {row['method']} {row['path']}")


if __name__ == "__main__":
    main()
