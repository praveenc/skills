# Diagram Generation Guide

Reference for the `diagram-generator` subagent. Contains D2 syntax primer,
heuristic rules, color palette, and example patterns.

## Contents

- [When to Generate a Diagram](#when-to-generate-a-diagram)
- [D2 Syntax Primer](#d2-syntax-primer)
- [Color Palette](#color-palette)
- [Example Patterns](#example-patterns)
- [Rendering](#rendering)
- [Naming Convention](#naming-convention)

## When to Generate a Diagram

**Generate when the report describes:**
- Architecture with 3+ interacting components
- A workflow/pipeline with sequential or branching steps
- A data flow between systems
- A tiered/layered structure (e.g., caching tiers, storage tiers)
- A comparison of approaches as a decision tree

**Skip when the report is:**
- A pricing comparison (tables are better)
- A feature overview or news roundup (prose is sufficient)
- A troubleshooting guide
- A pure cost optimization analysis
- A tool/library comparison

## D2 Syntax Primer

D2 is a diagram-as-code language. LLMs generate it easily because the syntax
is minimal and readable.

### Basics

```d2
# Nodes (auto-created on first mention)
api: API Gateway

# Connections
client -> api: HTTPS
api -> lambda: Invoke

# Shapes
db: PostgreSQL {shape: cylinder}
user: User {shape: person}
check: Valid? {shape: diamond}
start: Begin {shape: oval}
```

### Containers (grouping)

```d2
backend: Backend Services {
  auth: Auth Service
  data: Data Service
}
client -> backend.auth: Authenticate
```

### Styling

```d2
api: API Gateway {
  style.fill: "#e8f4f8"
  style.stroke: "#1971c2"
  style.border-radius: 8
}
```

### Direction

```d2
direction: right   # left-to-right flow
direction: down    # top-to-bottom (default)
```

## Color Palette

Use these consistently across diagrams for visual coherence:

| Purpose | Fill | Stroke | Usage |
|---------|------|--------|-------|
| Compute | `#fff3e0` | `#e65100` | Lambda, ECS, EC2 |
| Database | `#f3e5f5` | `#6a1b9a` | RDS, DynamoDB, Aurora |
| Storage | `#e3f2fd` | `#1565c0` | S3, EFS, EBS |
| Network | `#e8f4f8` | `#1971c2` | API GW, CloudFront, ALB |
| Cache | `#fce4ec` | `#c62828` | ElastiCache, DAX |
| ML/AI | `#e8f5e9` | `#2e7d32` | Bedrock, SageMaker |
| Security | `#fff9c4` | `#f57f17` | IAM, KMS, WAF |
| Messaging | `#f3e5f5` | `#6a1b9a` | SQS, SNS, EventBridge |
| Container | `#f8f9fa` | `#868e96` | Grouping / background |
| Start/End | `#e8f4f8` | `#1971c2` | Oval start/end nodes |
| Decision | `#fce4ec` | `#c62828` | Diamond decision nodes |

## Example Patterns

### Architecture Diagram

```d2
direction: right

user: User {shape: person}
api: API Gateway {style.fill: "#e8f4f8"; style.stroke: "#1971c2"}

backend: Backend {
  style.fill: "#f8f9fa"; style.stroke: "#868e96"
  lambda: Lambda {style.fill: "#fff3e0"; style.stroke: "#e65100"}
  cache: Redis {shape: cylinder; style.fill: "#fce4ec"; style.stroke: "#c62828"}
}

db: DynamoDB {shape: cylinder; style.fill: "#f3e5f5"; style.stroke: "#6a1b9a"}

user -> api: HTTPS
api -> backend.lambda: Invoke
backend.lambda -> backend.cache: Check
backend.lambda -> db: Query
```

### Flowchart / Decision Tree

```d2
direction: down

start: Research Query {shape: oval; style.fill: "#e8f4f8"}
classify: Classify Intent {style.fill: "#fff3e0"}
decide: Architecture? {shape: diamond; style.fill: "#fce4ec"}
yes_path: Run Full Pipeline {style.fill: "#e8f5e9"}
no_path: Docs Only {style.fill: "#f3e5f5"}
report: Generate Report {shape: oval; style.fill: "#e8f4f8"}

start -> classify -> decide
decide -> yes_path: Yes
decide -> no_path: No
yes_path -> report
no_path -> report
```

### Data Flow / Pipeline

```d2
direction: right

source: Data Source {shape: cylinder; style.fill: "#e3f2fd"}
ingest: Kinesis {style.fill: "#fff3e0"}
process: Lambda {style.fill: "#fff3e0"}
store: S3 Data Lake {shape: cylinder; style.fill: "#e3f2fd"}
query: Athena {style.fill: "#e8f5e9"}

source -> ingest: Stream
ingest -> process: Transform
process -> store: Write
store -> query: SQL
```

## Rendering

The `kroki_diagram.py` script handles rendering. The diagram-generator agent:

1. Writes D2 source to `<output-dir>/diagrams/<name>.d2`
2. Calls: `uv run $SKILL_DIR/scripts/kroki_diagram.py -i <d2-file> -o <output-dir>/diagrams/<name>.svg`
3. Injects `![<caption>](./diagrams/<name>.svg)` into the report markdown
   after the Executive Summary section

## Naming Convention

- Architecture diagrams: `<slug>-architecture.d2` → `<slug>-architecture.svg`
- Flowcharts: `<slug>-flow.d2` → `<slug>-flow.svg`
- Data flows: `<slug>-dataflow.d2` → `<slug>-dataflow.svg`
- Generic: `<slug>-diagram.d2` → `<slug>-diagram.svg`
