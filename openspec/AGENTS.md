# OpenSpec Workflow

## Schema: spec-driven

Active schema defined in `config.yaml`. Schema controls artifact types, build order, and CLI behavior.

## Directory Structure

```
openspec/
├── config.yaml          # Schema: spec-driven
├── specs/               # 31 active capability specs (normative: must/shall)
├── changes/             # Active changes → archive/YYYY-MM-DD-<name>/
└── doc/                 # Reference docs (descriptive, not normative)
```

Specs are normative truth. Docs are descriptive reference. Never generate docs from specs.

## CLI: openspec-cn

```bash
openspec-cn list --json                         # Active changes with schema/status
openspec-cn status --change "<name>" --json     # Artifact graph, applyRequires
openspec-cn instructions <artifact> --change "<name>" --json  # Template + context
openspec-cn new change "<name>"                 # Scaffold change directory
```

Parse JSON for `schemaName`, `artifacts[]`, `applyRequires`, `contextFiles`.

## Claude Integration

**Commands** (`.claude/commands/opsx/`) — user-facing shortcuts, Chinese-localized:
- `/opsx:apply` ("OPSX: 应用") — implement tasks
- `/opsx:archive` ("OPSX: 归档") — archive completed change
- `/opsx:explore` ("OPSX: 探索") — thinking mode, no code
- `/opsx:propose` ("OPSX: 提案") — create change with all artifacts

**Skills** (`.claude/skills/openspec-*/`) — programmatic, load via `load_skills`:
```
load_skills=['openspec-apply-change', 'openspec-archive-change', ...]
```

## Workflow Lifecycle

1. **Explore** — think freely, no code. Capture insights to artifacts if useful.
2. **Propose** — creates change with proposal.md, design.md, tasks.md.
3. **Apply** — implement tasks sequentially, mark `- [ ]` → `- [x]`.
4. **Archive** — move to `changes/archive/YYYY-MM-DD-<name>/`.

## Authoring Conventions

**Spec format** (`specs/<capability>/spec.md`):
- Header: `# <capability> 规范`
- Sections: `## 目的`, `## 需求`
- Requirements: `### 需求: <description>`
- Scenarios:
  ```
  #### 场景:<description>
  - **当** <condition>
  - **那么** <outcome>
  ```
- Constraint language: `必须` (must), `禁止` (must not), `应该` (should)

**Change artifacts**: proposal.md (what/why), design.md (how), tasks.md (checkbox list).

## Doc Directory

`openspec/doc/` — reference docs (ask.md, rag.md, bare.txt, typst.txt). Descriptive, not normative.

## Common Failure Modes

**Guessing change names** — Never assume. Run `openspec-cn list --json` and prompt user.
**Skipping context files** — Always read `contextFiles` from `openspec-cn instructions apply --json`.
**Schema ignorance** — Check `schemaName` from status output. Behavior adapts to schema.
**Writing code in explore mode** — Explore is for thinking only, not implementation.
**Batching task completions** — Mark each task `- [x]` immediately after completing.
**Assuming artifact names** — Use `openspec-cn status --json` to discover artifacts.
