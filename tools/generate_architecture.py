#!/usr/bin/env python3
"""Generate an architecture-viewer JSON file from a workspace.

Only the Python standard library is used so this script can be copied with the
viewer and run in almost any development workspace.
"""

from __future__ import annotations

import argparse
import ast
from collections import defaultdict, deque
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SKIP_DIRS = {
    ".git", ".hg", ".svn", ".idea", ".vscode", ".venv", "venv",
    "node_modules", "vendor", "dist", "build", "install", "log", "logs",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "coverage",
}
SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".cpp", ".cc", ".c", ".h", ".hpp"}
CONFIG_SUFFIXES = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg"}
MANIFEST_NAMES = {"package.json", "pyproject.toml", "setup.py", "package.xml", "Cargo.toml", "go.mod", "CMakeLists.txt", "Dockerfile", "compose.yaml", "docker-compose.yml"}
JS_IMPORT = re.compile(r"(?:from\s+|require\s*\(\s*|import\s*\(\s*)['\"]([^'\"]+)['\"]")
BACKUP_NAME = re.compile(r"(?:^|[_.-])(old|bak|backup|copy)(?:[_.-]|$)", re.IGNORECASE)
GROUP_COLORS = ["#147e85", "#7559d9", "#a56b25", "#276a9b", "#6a4b8e", "#31735c", "#9a4665", "#586c9b", "#8a7135", "#346c78"]
SENSITIVE_NAME = re.compile(r"(?:secret|credential|password|private[_-]?key|access[_-]?token|api[_-]?key)", re.IGNORECASE)


def safe_id(value: str) -> str:
    result = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-").lower()
    return result or "component"


def ignored(relative: Path) -> bool:
    return any(part in SKIP_DIRS or part.startswith(".") for part in relative.parts)


def classify(path: Path, content: str = "") -> tuple[str, str]:
    text = path.as_posix().lower()
    if path.name in MANIFEST_NAMES:
        return "config", "manifest"
    if "test" in path.parts or path.name.startswith("test_") or ".test." in path.name:
        return "test", "test"
    if "docs" in path.parts or path.suffix.lower() in {".md", ".rst"}:
        return "docs", "documentation"
    if "launch" in path.parts or path.name.endswith(".launch.py"):
        return "runtime", "launcher"
    if path.suffix.lower() in CONFIG_SUFFIXES or "config" in path.parts:
        return "config", "configuration"
    if path.suffix.lower() in {".html", ".css", ".jsx", ".tsx"}:
        return "frontend", "frontend"
    stem = path.stem.lower()
    if any(word in stem for word in ("encoder", "sensor", "camera", "lidar", "imu", "odom")):
        category = "sensing"
    elif any(word in stem for word in ("controller", "control", "feedback", "follower", "planner", "navigation")):
        category = "control"
    elif any(word in stem for word in ("bridge", "adapter", "client", "server", "transport")):
        category = "integration"
    elif stem in {"main", "run", "app", "cli"}:
        category = "runtime"
    else:
        category = "source"
    if path.suffix == ".py" and ("create_publisher(" in content or "create_subscription(" in content or re.search(r"class\s+\w+\s*\([^)]*Node[^)]*\)", content)):
        return category, "ros2-node"
    return category, "source-file"


def package_group(relative: Path, package_roots: dict[Path, str]) -> str:
    matches = [(root, group) for root, group in package_roots.items() if relative == root or root in relative.parents]
    if matches:
        return max(matches, key=lambda item: len(item[0].parts))[1]
    if len(relative.parts) > 1:
        return "folder-" + safe_id(relative.parts[0])
    return "workspace"


def find_package_roots(files: list[Path]) -> dict[Path, str]:
    roots = {}
    for relative in files:
        if relative.name in {"package.xml", "package.json", "pyproject.toml", "Cargo.toml", "go.mod"}:
            root = relative.parent
            label = root.name if root.parts else "Workspace"
            roots[root] = "package-" + safe_id(label)
    return roots


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def literal_string(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def ros_topics(path: Path) -> tuple[set[str], set[str]]:
    if path.suffix != ".py":
        return set(), set()
    try:
        tree = ast.parse(read_text(path))
    except SyntaxError:
        return set(), set()
    parameters: dict[str, str] = {}
    variables: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "declare_parameter" and len(node.args) > 1:
            name, default = literal_string(node.args[0]), literal_string(node.args[1])
            if name and default:
                parameters[name] = default
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        resolved = literal_string(value)
        if not resolved:
            for child in ast.walk(value):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute) and child.func.attr == "get_parameter" and child.args:
                    parameter_name = literal_string(child.args[0])
                    if parameter_name in parameters:
                        resolved = parameters[parameter_name]
                        break
        if not resolved:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                variables[target.id] = resolved
            elif isinstance(target, ast.Attribute):
                variables[target.attr] = resolved

    def resolve_topic(expression: ast.AST) -> str | None:
        direct = literal_string(expression)
        if direct:
            return direct
        if isinstance(expression, ast.Name):
            return variables.get(expression.id)
        if isinstance(expression, ast.Attribute):
            return variables.get(expression.attr)
        return None

    publishers: set[str] = set()
    subscribers: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in {"create_publisher", "create_subscription"}:
            continue
        topic = resolve_topic(node.args[1]) if len(node.args) > 1 else None
        if not topic:
            for keyword in node.keywords:
                if keyword.arg in {"topic", "topic_name"}:
                    topic = resolve_topic(keyword.value)
        if topic:
            (publishers if node.func.attr == "create_publisher" else subscribers).add(topic)
    return publishers, subscribers


def launch_executables(path: Path) -> set[str]:
    if path.suffix != ".py" or not ("launch" in path.parts or path.name.endswith(".launch.py")):
        return set()
    try:
        tree = ast.parse(read_text(path))
    except SyntaxError:
        return set()
    result = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg == "executable":
                value = literal_string(keyword.value)
                if value:
                    result.add(value)
    return result


def python_imports(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def source_imports(path: Path) -> set[str]:
    if path.suffix == ".py":
        return python_imports(path)
    if path.suffix.lower() in {".js", ".jsx", ".ts", ".tsx"}:
        try:
            return set(JS_IMPORT.findall(path.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            return set()
    return set()


def module_aliases(relative: Path) -> set[str]:
    no_suffix = relative.with_suffix("")
    parts = list(no_suffix.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    aliases = {".".join(parts), "/".join(parts), "./" + "/".join(parts)}
    if parts:
        aliases.add(parts[-1])
    # Common src/package/module.py layout.
    if "src" in parts:
        index = parts.index("src") + 1
        aliases.add(".".join(parts[index:]))
    return {alias for alias in aliases if alias}


def collect_files(root: Path, max_nodes: int) -> list[Path]:
    candidates = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if ignored(relative):
            continue
        if BACKUP_NAME.search(path.stem):
            continue
        if path.name in MANIFEST_NAMES or path.suffix.lower() in SOURCE_SUFFIXES | CONFIG_SUFFIXES | {".md", ".rst", ".html", ".css"}:
            candidates.append(relative)
    # Manifests and executable source files are more valuable than generated-looking data.
    candidates.sort(key=lambda p: (p.name not in MANIFEST_NAMES, p.suffix.lower() not in SOURCE_SUFFIXES, len(p.parts), p.as_posix()))
    return candidates[:max_nodes]


def layout_nodes(nodes: list[dict], edges: list[dict]) -> None:
    """Place connected components in dependency lanes and group isolated files."""
    node_ids = {node["id"] for node in nodes}
    undirected: defaultdict[str, set[str]] = defaultdict(set)
    outgoing: defaultdict[str, set[str]] = defaultdict(set)
    incoming: defaultdict[str, set[str]] = defaultdict(set)
    for edge in edges:
        source, target = edge["source"], edge["target"]
        if source not in node_ids or target not in node_ids:
            continue
        undirected[source].add(target)
        undirected[target].add(source)
        outgoing[source].add(target)
        incoming[target].add(source)

    connected_ids = {node_id for node_id, adjacent in undirected.items() if adjacent}
    unseen = set(connected_ids)
    components = []
    while unseen:
        start = min(unseen)
        queue = deque([start])
        component = set()
        while queue:
            current = queue.popleft()
            if current in component:
                continue
            component.add(current)
            queue.extend(undirected[current] - component)
        unseen -= component
        components.append(component)
    components.sort(key=lambda component: (-len(component), min(component)))

    def lanes_for(component: set[str]) -> list[list[str]]:
        sources = sorted(node_id for node_id in component if not (incoming[node_id] & component))
        if not sources:
            sources = [min(component, key=lambda node_id: len(incoming[node_id] & component))]
        depth = {node_id: 0 for node_id in sources}
        queue = deque(sources)
        while queue:
            current = queue.popleft()
            for target in sorted(outgoing[current] & component):
                if target not in depth:
                    depth[target] = depth[current] + 1
                    queue.append(target)
        # Cyclic or reverse-only nodes are assigned by undirected distance.
        queue = deque(sources)
        while queue:
            current = queue.popleft()
            for adjacent in sorted(undirected[current] & component):
                if adjacent not in depth:
                    depth[adjacent] = depth[current] + 1
                    queue.append(adjacent)
        lanes: defaultdict[int, list[str]] = defaultdict(list)
        for node_id in component:
            lanes[depth.get(node_id, 0)].append(node_id)
        # Put nodes sharing neighbors next to each other to reduce crossings.
        result = []
        previous_order: dict[str, int] = {}
        for lane in sorted(lanes):
            lane_ids = list(lanes[lane])
            lane_ids.sort(key=lambda node_id: (
                sum(previous_order.get(parent, 0) for parent in incoming[node_id]) / max(1, len(incoming[node_id])),
                node_id,
            ))
            result.append(lane_ids)
            previous_order.update({node_id: index for index, node_id in enumerate(lane_ids)})
        return result

    def place(component: set[str], x: int, y: int, width: int, height: int) -> None:
        lanes = lanes_for(component)
        x_step = width / max(1, len(lanes) - 1)
        for lane_index, lane_ids in enumerate(lanes):
            lane_x = x + lane_index * x_step
            y_step = height / max(1, len(lane_ids))
            for row, node_id in enumerate(lane_ids):
                positions[node_id] = (round(lane_x), round(y + y_step * (row + 0.5)))

    positions: dict[str, tuple[int, int]] = {}
    remaining = list(components)
    if remaining and len(remaining[0]) >= 5:
        place(remaining.pop(0), 120, 105, 900, 430)

    # Smaller, unrelated systems are packed below the primary system rather
    # than extending one narrow column far beyond the initial viewport.
    for index, component in enumerate(remaining):
        column = index % 2
        row = index // 2
        place(component, 150 + column * 550, 610 + row * 190, 390, 120)

    isolated = [node for node in nodes if node["id"] not in connected_ids]
    isolated.sort(key=lambda node: (node["group"], node["source"]))
    for index, node in enumerate(isolated):
        positions[node["id"]] = (120 + (index % 5) * 220, 110 + (index // 5) * 100)

    for node in nodes:
        node["x"], node["y"] = positions.get(node["id"], (120, 110))


def generate_flows(nodes: list[dict], edges: list[dict], limit: int = 12) -> list[dict]:
    """Create traceable candidate routes without inventing business meaning."""
    labels = {node["id"]: node["label"] for node in nodes}
    outgoing: defaultdict[str, list[tuple[str, str]]] = defaultdict(list)
    incoming: defaultdict[str, set[str]] = defaultdict(set)
    connected = set()
    for edge in edges:
        outgoing[edge["source"]].append((edge["target"], edge["id"]))
        incoming[edge["target"]].add(edge["source"])
        connected.update((edge["source"], edge["target"]))
    roots = sorted(node_id for node_id in connected if not incoming[node_id])
    if not roots:
        roots = sorted(connected)
    candidates = []
    seen_paths = set()
    for root in roots:
        queue = deque([(root, [root], [])])
        best = ([root], [])
        expansions = 0
        while queue and expansions < 2000:
            expansions += 1
            current, path, edge_path = queue.popleft()
            if len(path) > len(best[0]):
                best = (path, edge_path)
            for target, edge_id in outgoing[current]:
                if target not in path:
                    queue.append((target, path + [target], edge_path + [edge_id]))
        steps, edge_ids = best
        signature = tuple(edge_ids)
        if len(steps) < 2 or signature in seen_paths:
            continue
        seen_paths.add(signature)
        candidates.append((len(steps), steps, edge_ids))
    candidates.sort(key=lambda item: (-item[0], labels.get(item[1][0], item[1][0])))
    flows = []
    for index, (_, steps, edge_ids) in enumerate(candidates[:limit], 1):
        start, end = labels.get(steps[0], steps[0]), labels.get(steps[-1], steps[-1])
        protocols = sorted({edge["protocol"] for edge in edges if edge["id"] in edge_ids})
        flows.append({
            "id": f"detected-flow-{index}",
            "name": f"{start} → {end}",
            "description": "Automatically detected route: " + ", ".join(protocols),
            "steps": steps,
            "edgeIds": edge_ids,
            "generated": True,
        })
    return flows


def collect_ai_context(root: Path, files: list[Path], max_chars: int) -> str:
    """Collect bounded, reviewable source excerpts; never include dotfiles/secrets."""
    priorities = sorted(files, key=lambda path: (
        path.name.lower() not in {"readme.md", "package.xml", "package.json", "pyproject.toml", "setup.py"},
        "launch" not in path.parts,
        "config" not in path.parts,
        path.as_posix(),
    ))
    chunks = []
    used = 0
    for relative in priorities:
        if SENSITIVE_NAME.search(relative.name):
            continue
        content = read_text(root / relative)
        if not content.strip():
            continue
        excerpt = content[:12000]
        chunk = f"\n--- FILE: {relative.as_posix()} ---\n{excerpt}\n"
        if used + len(chunk) > max_chars:
            remaining = max_chars - used
            if remaining > 300:
                chunks.append(chunk[:remaining])
            break
        chunks.append(chunk)
        used += len(chunk)
    return "".join(chunks)


def architecture_schema() -> dict:
    return {
        "type": "object",
        "required": ["repository", "groups", "nodes", "edges", "flows"],
        "additionalProperties": True,
        "properties": {
            "repository": {"type": "object"},
            "groups": {"type": "object"},
            "nodes": {"type": "array", "items": {"type": "object"}},
            "edges": {"type": "array", "items": {"type": "object"}},
            "flows": {"type": "array", "items": {"type": "object"},},
        },
    }


def ai_prompt(static_data: dict, source_context: str) -> tuple[str, str]:
    system = """You are a software architect. Produce only one valid JSON object for an interactive architecture viewer. Analyze meaning across files instead of making one node per file. Do not claim unsupported facts."""
    user = f"""Create a concise, human-readable architecture diagram from the evidence below.

Requirements:
- Consolidate related files into functional components; aim for 10-30 meaningful nodes.
- Include runtime/external actors (users, hardware, networks, services) only when supported or strongly implied. Use source='inferred external' for inferred external nodes.
- Use groups with distinct label/color objects.
- Every node requires id, label, group, type, description, source, x, y.
- Every edge requires id, source, target, label, protocol. Endpoints must reference node ids.
- Define meaningful end-to-end flows when evidence supports them. Every flow requires id, name, description, steps, edgeIds.
- Place the main system clearly within x=80..1120 and y=90..700. Prefer left-to-right data flow, keep related nodes close, separate subsystems, and reduce crossings.
- Use Japanese labels/descriptions when the evidence is primarily Japanese; otherwise use the repository language.
- Preserve important safety, fallback, and control paths.
- Do not include schema commentary or Markdown.

Static analyzer facts (use as evidence, not as the desired file-level layout):
{json.dumps(static_data, ensure_ascii=False)}

Selected workspace excerpts:
{source_context}
"""
    return system, user


def post_json(url: str, payload: dict, api_key: str | None, timeout: int) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"AI API returned HTTP {error.code}: {detail}") from error
    except (URLError, TimeoutError) as error:
        raise RuntimeError(f"Could not connect to AI API: {error}") from error


def response_text(response: dict, api_style: str) -> str:
    if api_style == "chat-completions":
        try:
            content = response["choices"][0]["message"]["content"]
            if isinstance(content, str):
                return content
        except (KeyError, IndexError, TypeError):
            pass
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    for item in response.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                return content["text"]
    raise RuntimeError("AI response did not contain text output")


def parse_ai_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"AI returned invalid JSON: {error}") from error
    if not isinstance(data, dict):
        raise RuntimeError("AI output must be a JSON object")
    return data


def validate_ai_architecture(data: dict) -> dict:
    if not isinstance(data.get("nodes"), list) or not isinstance(data.get("edges"), list):
        raise RuntimeError("AI JSON requires nodes and edges arrays")
    groups = data.get("groups") if isinstance(data.get("groups"), dict) else {}
    nodes = data["nodes"]
    ids = set()
    for index, node in enumerate(nodes):
        if not isinstance(node, dict) or not isinstance(node.get("id"), str) or not node["id"] or node["id"] in ids:
            raise RuntimeError(f"AI JSON has an invalid or duplicate node id at index {index}")
        ids.add(node["id"])
        node.setdefault("label", node["id"])
        node.setdefault("group", "system")
        node.setdefault("type", "component")
        node.setdefault("description", "")
        node.setdefault("source", "inferred")
    used_groups = sorted({node["group"] for node in nodes})
    for index, group_id in enumerate(used_groups):
        group = groups.setdefault(group_id, {})
        if not isinstance(group, dict):
            group = groups[group_id] = {"label": str(group_id)}
        group.setdefault("label", str(group_id))
        group.setdefault("color", GROUP_COLORS[index % len(GROUP_COLORS)])
    valid_edges = []
    edge_ids = set()
    for index, edge in enumerate(data["edges"]):
        if not isinstance(edge, dict) or edge.get("source") not in ids or edge.get("target") not in ids:
            continue
        edge_id = str(edge.get("id") or f"e{index + 1}")
        if edge_id in edge_ids:
            continue
        edge_ids.add(edge_id)
        edge.update(id=edge_id, label=str(edge.get("label") or "connects"), protocol=str(edge.get("protocol") or "unspecified"))
        valid_edges.append(edge)
    data["edges"] = valid_edges
    valid_flows = []
    for index, flow in enumerate(data.get("flows", [])):
        if not isinstance(flow, dict):
            continue
        steps = [step for step in flow.get("steps", []) if step in ids]
        route_edges = [edge_id for edge_id in flow.get("edgeIds", []) if edge_id in edge_ids]
        if len(steps) < 2:
            continue
        flow.update(id=str(flow.get("id") or f"flow-{index + 1}"), name=str(flow.get("name") or "Detected flow"), description=str(flow.get("description") or ""), steps=steps, edgeIds=route_edges)
        valid_flows.append(flow)
    data["flows"] = valid_flows or generate_flows(nodes, valid_edges)
    data["groups"] = groups
    data.setdefault("schemaVersion", "1.0.0")
    data.setdefault("generatedAt", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    data.setdefault("repository", {"name": "AI architecture", "primaryStack": []})
    if not all(isinstance(node.get("x"), (int, float)) and isinstance(node.get("y"), (int, float)) for node in nodes):
        layout_nodes(nodes, valid_edges)
    return data


def generate_with_ai(static_data: dict, source_context: str, base_url: str, model: str, api_key: str | None, api_style: str, timeout: int) -> dict:
    system, user = ai_prompt(static_data, source_context)
    base_url = base_url.rstrip("/")
    if api_style == "responses":
        payload = {
            "model": model,
            "input": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "reasoning": {"effort": "medium"},
            "max_output_tokens": 20000,
            "text": {"format": {"type": "json_schema", "name": "architecture", "strict": False, "schema": architecture_schema()}},
        }
        response = post_json(base_url + "/responses", payload, api_key, timeout)
    else:
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
            "max_tokens": 20000,
        }
        response = post_json(base_url + "/chat/completions", payload, api_key, timeout)
    return validate_ai_architecture(parse_ai_json(response_text(response, api_style)))


def generate(root: Path, name: str, max_nodes: int) -> dict:
    files = collect_files(root, max_nodes)
    package_roots = find_package_roots(files)
    nodes = []
    aliases: dict[str, str] = {}
    used_ids: set[str] = set()
    for index, relative in enumerate(files):
        base_id = safe_id(relative.as_posix())
        node_id = base_id
        suffix = 2
        while node_id in used_ids:
            node_id = f"{base_id}-{suffix}"
            suffix += 1
        used_ids.add(node_id)
        content = read_text(root / relative)
        category, node_type = classify(relative, content)
        base_group = package_group(relative, package_roots)
        group = f"{base_group}--{category}"
        nodes.append({
            "id": node_id,
            "label": relative.name,
            "group": group,
            "type": node_type,
            "description": f"Detected from {relative.as_posix()}",
            "source": relative.as_posix(),
            "category": category,
        })
        for alias in module_aliases(relative):
            aliases.setdefault(alias, node_id)

    edges = []
    node_by_source = {node["source"]: node for node in nodes}
    seen: set[tuple[str, str]] = set()
    for relative in files:
        source_node = node_by_source.get(relative.as_posix())
        if not source_node:
            continue
        for imported in sorted(source_imports(root / relative)):
            normalized = imported.removesuffix(".js").removesuffix(".ts").removesuffix(".py")
            target = aliases.get(normalized) or aliases.get(normalized.lstrip("./").replace("/", "."))
            if not target or target == source_node["id"] or (source_node["id"], target) in seen:
                continue
            seen.add((source_node["id"], target))
            edges.append({"id": f"e{len(edges) + 1}", "source": source_node["id"], "target": target, "label": "imports", "protocol": "source dependency"})

    # ROS 2 nodes usually communicate through topics and do not import each
    # other. Match literal publisher/subscriber topic names to expose those
    # runtime relationships.
    publishers: defaultdict[str, list[str]] = defaultdict(list)
    subscribers: defaultdict[str, list[str]] = defaultdict(list)
    for relative in files:
        node = node_by_source.get(relative.as_posix())
        if not node:
            continue
        published, subscribed = ros_topics(root / relative)
        for topic in published:
            publishers[topic].append(node["id"])
        for topic in subscribed:
            subscribers[topic].append(node["id"])
    for topic in sorted(publishers.keys() & subscribers.keys()):
        for source in publishers[topic]:
            for target in subscribers[topic]:
                if source == target or (source, target) in seen:
                    continue
                seen.add((source, target))
                edges.append({"id": f"e{len(edges) + 1}", "source": source, "target": target, "label": topic, "protocol": "ROS 2 topic"})

    # Link ROS launch files to executables when their names match source files.
    by_stem = {Path(node["source"]).stem: node["id"] for node in nodes}
    for relative in files:
        launch_node = node_by_source.get(relative.as_posix())
        if not launch_node:
            continue
        for executable in launch_executables(root / relative):
            target = by_stem.get(executable) or by_stem.get(executable.removesuffix("_node"))
            if not target or target == launch_node["id"] or (launch_node["id"], target) in seen:
                continue
            seen.add((launch_node["id"], target))
            edges.append({"id": f"e{len(edges) + 1}", "source": launch_node["id"], "target": target, "label": "launches", "protocol": "ROS 2 launch"})

    layout_nodes(nodes, edges)
    flows = generate_flows(nodes, edges)

    group_labels: dict[str, str] = {}
    for node in nodes:
        group_id = node["group"]
        base, _, category = group_id.partition("--")
        if base.startswith("package-"):
            base_label = base.removeprefix("package-").replace("-", " ").title()
        elif base.startswith("folder-"):
            base_label = base.removeprefix("folder-").replace("-", " ").title()
        else:
            base_label = "Workspace"
        group_labels[group_id] = f"{base_label} · {category.title()}"
    groups = {group_id: {"label": label, "color": GROUP_COLORS[i % len(GROUP_COLORS)]} for i, (group_id, label) in enumerate(sorted(group_labels.items()))}

    stacks = sorted({p.suffix.lstrip(".") for p in files if p.suffix})
    return {
        "schemaVersion": "1.0.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repository": {
            "name": name,
            "purpose": "Automatically generated workspace overview. Edit descriptions and flows as needed.",
            "primaryStack": stacks,
        },
        "groups": groups,
        "nodes": nodes,
        "edges": edges,
        "flows": flows,
        "constraints": [
            "This file is an automatically generated starting point.",
            "Runtime-only connections and business flows require manual review.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate JSON for docs/architecture.html")
    parser.add_argument("workspace", nargs="?", default=".", help="workspace directory (default: current directory)")
    parser.add_argument("-o", "--output", default="architecture.generated.json", help="output JSON path")
    parser.add_argument("--name", help="project name (default: workspace directory name)")
    parser.add_argument("--max-nodes", type=int, default=80, help="maximum detected files (default: 80)")
    parser.add_argument("--ai", action="store_true", help="use AI to consolidate files into a semantic architecture")
    parser.add_argument("--ai-base-url", default=os.getenv("ARCHITECTURE_AI_BASE_URL", "https://api.openai.com/v1"), help="AI API base URL")
    parser.add_argument("--ai-model", default=os.getenv("ARCHITECTURE_AI_MODEL", "gpt-5.6-terra"), help="AI model name")
    parser.add_argument("--ai-api-style", choices=("responses", "chat-completions"), default=os.getenv("ARCHITECTURE_AI_API_STYLE", "responses"), help="API protocol; local compatible servers usually use chat-completions")
    parser.add_argument("--ai-api-key-env", default="OPENAI_API_KEY", help="environment variable containing the API key")
    parser.add_argument("--ai-max-chars", type=int, default=120000, help="maximum source characters sent to AI")
    parser.add_argument("--ai-timeout", type=int, default=300, help="AI request timeout in seconds")
    parser.add_argument("--ai-fallback", action="store_true", help="write static-analysis JSON if AI generation fails")
    args = parser.parse_args()
    root = Path(args.workspace).expanduser().resolve()
    if not root.is_dir():
        parser.error(f"workspace is not a directory: {root}")
    if args.max_nodes < 1:
        parser.error("--max-nodes must be at least 1")
    if args.ai_max_chars < 1000:
        parser.error("--ai-max-chars must be at least 1000")
    output = Path(args.output).expanduser()
    data = generate(root, args.name or root.name, args.max_nodes)
    mode = "static"
    if args.ai:
        api_key = os.getenv(args.ai_api_key_env) if args.ai_api_key_env else None
        if "api.openai.com" in args.ai_base_url and not api_key:
            parser.error(f"--ai requires {args.ai_api_key_env} for api.openai.com")
        context_files = collect_files(root, max(args.max_nodes, 160))
        context = collect_ai_context(root, context_files, args.ai_max_chars)
        print(f"AI mode: sending up to {len(context):,} source characters to {args.ai_base_url} using {args.ai_model}", file=sys.stderr)
        try:
            data = generate_with_ai(data, context, args.ai_base_url, args.ai_model, api_key, args.ai_api_style, args.ai_timeout)
            mode = "ai"
        except RuntimeError as error:
            if not args.ai_fallback:
                print(f"AI generation failed: {error}", file=sys.stderr)
                return 2
            print(f"AI generation failed; using static fallback: {error}", file=sys.stderr)
            data.setdefault("generator", {})["aiError"] = str(error)
            mode = "static-fallback"
    data.setdefault("generator", {}).update({"mode": mode, "model": args.ai_model if args.ai else None})
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {output} ({len(data['nodes'])} nodes, {len(data['edges'])} edges, mode={mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
