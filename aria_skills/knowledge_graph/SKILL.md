---
name: aria-knowledgegraph
description: Build and query Aria's knowledge graph. Store entities and relationships.
metadata: {"aria": {"emoji": "🕸️", "requires": {"env": ["DATABASE_URL"]}}}
---

# aria-knowledgegraph

Build and query Aria's knowledge graph. Store entities (people, places, concepts) and their relationships.

## Usage

```bash
exec python3 /app/skills/run_skill.py knowledge_graph <function> '<json_args>'
```

## Functions

### add_entity
Create or update an entity in the knowledge graph.

```bash
exec python3 /app/skills/run_skill.py knowledge_graph add_entity '{"name": "Najia", "type": "person", "properties": {"role": "creator", "relationship": "guardian"}}'
```

**Parameters:**
- `name` (required): Entity name
- `type` (required): Entity type (person, place, concept, event, etc.)
- `properties`: Optional JSON object with additional attributes

### add_relation
Create a relationship between two entities.

```bash
exec python3 /app/skills/run_skill.py knowledge_graph add_relation '{"from_entity": "Najia", "to_entity": "Aria", "relation_type": "created", "properties": {"date": "2024"}}'
```

**Relation types:**
- `created`, `owns`, `uses`
- `knows`, `works_with`, `friends_with`
- `located_in`, `part_of`, `belongs_to`
- `related_to`, `interested_in`, `learned_about`

### query_related
Find entities related to a given entity.

```bash
exec python3 /app/skills/run_skill.py knowledge_graph query_related '{"entity_name": "Najia", "depth": 2}'
```

### search
Search entities by name, type, or properties.

```bash
exec python3 /app/skills/run_skill.py knowledge_graph search '{"query": "python"}'
```

## Database Schema

**knowledge_entities:**
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| name | TEXT | Entity name |
| type | TEXT | Entity type |
| properties | JSONB | Additional data |
| created_at | TIMESTAMP | Creation time |
| updated_at | TIMESTAMP | Last update |

**knowledge_relations:**
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| from_entity | UUID | Source entity |
| to_entity | UUID | Target entity |
| relation_type | TEXT | Relationship type |
| properties | JSONB | Relation metadata |

## Example: Building a Knowledge Graph

```bash
# Add people
exec python3 /app/skills/run_skill.py knowledge_graph add_entity '{"name": "Najia", "type": "person"}'
exec python3 /app/skills/run_skill.py knowledge_graph add_entity '{"name": "Aria", "type": "ai_agent"}'

# Add relationship
exec python3 /app/skills/run_skill.py knowledge_graph add_relation '{"from_entity": "Najia", "to_entity": "Aria", "relation_type": "created"}'

# Query
exec python3 /app/skills/run_skill.py knowledge_graph query_related '{"entity_name": "Najia"}'
```

## Python Module

This skill wraps `/app/skills/aria_skills/knowledge_graph.py`
