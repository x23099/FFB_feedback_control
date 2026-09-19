---
name: generate-architecture
description: Create or update a semantic interactive architecture diagram when the user requests generation or modification of architecture.json, architecture.html, or an equivalent diagram artifact. Do not activate for architecture explanations, code reviews, or component questions that do not request a diagram artifact change.
---

# Generate Architecture

Use Codex's repository understanding as the semantic analysis layer. Do not call an external model API and do not ask the user for API keys, model names, endpoints, or long generator arguments.

## Scope

Create or update only the requested diagram artifacts. If explicitly invoked for explanation or review only, read the relevant evidence and answer without generating files, running the generator, or rendering the diagram. Follow applicable repository authorization rules; diagram work does not authorize deployment, external transmission, or hardware operation.

## Workflow

1. Treat the current workspace root as the target unless the user names another directory.
2. Use applicable repository instructions already in context; read missing instructions as needed. Inspect only documentation, configuration, entry points, and source paths relevant to the requested components and runtime flows. For a new diagram, establish the overall structure; for a partial update, trace changed components and their affected relationships. Reuse evidence while its sources remain unchanged.
3. If static facts are needed and `tools/generate_architecture.py` exists, inspect its behavior before running it in static mode. Reuse current facts when available; otherwise use a unique temporary output:

   ```bash
   architecture_facts=$(mktemp /tmp/architecture-facts.XXXXXX.json)
   python3 tools/generate_architecture.py . -o "$architecture_facts"
   ```

   Do not use `--ai`; Codex itself performs the semantic analysis.
4. Build `docs/architecture.json`. If the repository already has this file, preserve verified hand-authored details and update stale parts instead of replacing them mechanically.
5. Use functional components, not one node per file. Consolidate related implementation files behind one node and list relevant paths in `source`.
6. Include supported external actors, hardware, networks, data stores, and services. Mark inferred repository-external elements clearly.
7. Trace meaningful end-to-end flows from evidence. Use domain names such as manual control, autonomous navigation, request processing, data ingestion, safety fallback, or video delivery—not filenames—when supported.
8. Arrange the main flow left-to-right within the `1200 x 760` viewport. Keep related subsystems together, put secondary systems below the main system, and minimize crossings.
9. Validate the final JSON structure, unique node IDs, every edge endpoint, flow step, and flow edge ID after edits. Check changed claims and affected relationships against evidence and remove unsupported claims. Reuse successful checks for unchanged inputs; rerun or broaden checks after relevant changes, failures, or unresolved concerns.
10. When `docs/architecture.html` and rendering tools are available, visually check the affected labels, layout, or flows. Check the full layout on initial generation or broad layout changes; test tabs, search, and flow highlighting when their behavior or relevant data changes. Adjust coordinates when needed and recheck the affected display. Report unavailable validation rather than claiming it passed.

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
