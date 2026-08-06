---
name: generate-architecture
description: Analyze a software workspace with Codex and create or update a semantic interactive architecture diagram. Use when the user asks to generate, refresh, improve, or explain architecture.html or architecture.json, map components and runtime relationships, consolidate files into functional nodes, or create meaningful end-to-end flows without manually authoring JSON.
---

# Generate Architecture

Use Codex's repository understanding as the semantic analysis layer. Do not call an external model API and do not ask the user for API keys, model names, endpoints, or long generator arguments.

## Workflow

1. Treat the current workspace root as the target unless the user names another directory.
2. Read repository instructions first. Inspect README files, manifests, launch/deployment files, configuration, entry points, and the source files needed to trace runtime behavior.
3. If `tools/generate_architecture.py` exists, run its short static mode to a temporary file for factual hints:

   ```bash
   python3 tools/generate_architecture.py . -o /tmp/architecture-facts.json
   ```

   Do not use `--ai`; Codex itself performs the semantic analysis.
4. Build `docs/architecture.json`. If the repository already has this file, preserve verified hand-authored details and update stale parts instead of replacing them mechanically.
5. Use functional components, not one node per file. Consolidate related implementation files behind one node and list relevant paths in `source`.
6. Include supported external actors, hardware, networks, data stores, and services. Mark inferred repository-external elements clearly.
7. Trace meaningful end-to-end flows from evidence. Use domain names such as manual control, autonomous navigation, request processing, data ingestion, safety fallback, or video delivery—not filenames—when supported.
8. Arrange the main flow left-to-right within the `1200 x 760` viewport. Keep related subsystems together, put secondary systems below the main system, and minimize crossings.
9. Validate every edge endpoint, flow step, and flow edge ID. Keep node IDs unique. Remove unsupported claims.
10. Open or headlessly render `docs/architecture.html` when available and visually verify labels, overlaps, crossings, colors, tabs, search, and flow highlighting. Adjust JSON coordinates when needed.

## Output contract

Write a JSON object containing:

- `schemaVersion`, `generatedAt`, and `repository`
- `groups`: objects with `label` and distinct `color`
- `nodes`: `id`, `label`, `group`, `type`, `description`, `source`, `x`, `y`
- `edges`: `id`, `source`, `target`, `label`, `protocol`
- `flows`: `id`, `name`, `description`, `steps`, `edgeIds`
- optional `deployments` and `constraints`

Keep descriptions in the repository's primary language. Prefer 10–30 meaningful nodes for an overview. Put file-level details in descriptions or sources rather than expanding them into isolated nodes.

## Completion

Report the output path, component/connection/flow counts, the major inferred relationships, and validation performed. Distinguish evidence-backed facts from important inferences.
