# S-33: Embedding Cluster Explorer — t-SNE/UMAP 2D Projection of Semantic Memories
**Epic:** E18 — Visualization & Graph Execution | **Priority:** P2 | **Points:** 8 | **Phase:** 3

## Problem

Aria stores **768-dimensional embedding vectors** in the `SemanticMemory` table (`src/api/db/models.py` line 702: `embedding = Column(Vector(768))`) via pgvector. These embeddings power cosine-similarity search (`GET /memories/search` at `src/api/routers/memories.py` line 300) but are **never visualized**.

The `memory_explorer.html` (422 lines) shows a flat card grid with importance bars and similarity badges after search — but you can't see the **topology** of memory space: which memories cluster together, which are isolated, which categories form tight groups vs. spread out.

This is a significant cognitive gap for Aria v4: understanding the shape of her memory landscape. The `EngineChatMessage` table also has embeddings (`Vector(1536)`) but at a different dimensionality — this ticket focuses on SemanticMemory (768-dim).

**Missing:** A 2D scatter plot of semantic memories projected via dimensionality reduction (PCA → t-SNE or UMAP) with:
- Points colored by category
- Point size scaled by importance
- Hover tooltips showing memory content
- Click to zoom/inspect
- Cluster highlighting

## Root Cause

Dimensionality reduction (t-SNE/UMAP) requires mathematical computation that's typically done server-side (Python with scikit-learn or umap-learn). The API currently only stores and retrieves raw embeddings — it never projects them to 2D.

The frontend has no scatter plot capability beyond Chart.js (which supports scatter type but would need the projected coordinates served from the API).

## Fix

### 1. New API endpoint: `GET /api/memories/embedding-projection`

**File:** `src/api/routers/memories.py`

**⚠️ CRITICAL — Route ordering:** The `GET /memories/{key}` catch-all endpoint at line 486 will intercept this route if registered after it. This endpoint **MUST** be placed **BEFORE** line 486 in the file (e.g., around line 460–480) so that `/memories/embedding-projection` matches before the `{key}` path parameter swallows it.

**PREREQUISITE — Imports:** Ensure `numpy` is imported and models are available:
```python
import numpy as np  # At top of endpoint or module level
```
If S-31 has not been applied, add to line 16:
```python
from db.models import Memory, SemanticMemory, WorkingMemory, Thought, LessonLearned
```

This endpoint:
1. Fetches N semantic memories with their embeddings
2. Projects from 768-dim to 2D using PCA (fast, no extra dependencies) or t-SNE (if scikit-learn available)
3. Returns (x, y) coordinates with metadata for each memory

```python
@router.get("/memories/embedding-projection")
async def get_embedding_projection(
    limit: int = Query(200, ge=10, le=1000, description="Default 200; >500 may be slow due to PCA on 768-dim vectors"),
    method: str = Query("pca", pattern="^(pca|tsne)$"),
    category: Optional[str] = Query(None),
    min_importance: float = Query(0.0, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
):
    """
    Project semantic memory embeddings to 2D for scatter plot visualization.
    
    Methods:
    - pca: Principal Component Analysis (fast, deterministic, no extra deps)
    - tsne: t-SNE (better clusters, requires scikit-learn, slower)
    """
    import numpy as np
    
    # Fetch memories with embeddings
    stmt = select(SemanticMemory).where(
        SemanticMemory.embedding.isnot(None),
        SemanticMemory.importance >= min_importance,
    )
    if category:
        stmt = stmt.where(SemanticMemory.category == category)
    stmt = stmt.order_by(SemanticMemory.importance.desc()).limit(limit)
    
    result = await db.execute(stmt)
    memories = result.scalars().all()
    
    if len(memories) < 3:
        return {"points": [], "method": method, "error": "Need at least 3 memories with embeddings"}
    
    # Extract embedding matrix
    embeddings = []
    valid_memories = []
    for m in memories:
        emb = m.embedding
        if emb is not None and len(emb) > 0:
            embeddings.append(emb)
            valid_memories.append(m)
    
    if len(embeddings) < 3:
        return {"points": [], "method": method, "error": "Not enough valid embeddings"}
    
    X = np.array(embeddings, dtype=np.float32)
    
    # Dimensionality reduction
    if method == "tsne":
        try:
            from sklearn.manifold import TSNE
            perplexity = min(30, len(X) - 1)
            reducer = TSNE(n_components=2, perplexity=perplexity, random_state=42, n_iter=500)
            coords = reducer.fit_transform(X)
        except ImportError:
            # Fallback to PCA if scikit-learn not installed
            method = "pca"
    
    if method == "pca":
        # PCA using numpy only (no sklearn needed)
        X_centered = X - X.mean(axis=0)
        cov = np.cov(X_centered, rowvar=False)
        eigenvalues, eigenvectors = np.linalg.eigh(cov)
        # Take top 2 eigenvectors (largest eigenvalues are last)
        idx = np.argsort(eigenvalues)[::-1][:2]
        coords = X_centered @ eigenvectors[:, idx]
    
    # Normalize to [-1, 1] range for frontend
    coords_min = coords.min(axis=0)
    coords_max = coords.max(axis=0)
    coords_range = coords_max - coords_min
    coords_range[coords_range == 0] = 1
    coords_normalized = 2 * (coords - coords_min) / coords_range - 1
    
    # Build points with metadata
    points = []
    for i, m in enumerate(valid_memories):
        points.append({
            "id": str(m.id),
            "x": round(float(coords_normalized[i][0]), 4),
            "y": round(float(coords_normalized[i][1]), 4),
            "label": (m.summary or m.content or "")[:80],
            "category": m.category,
            "importance": m.importance,
            "source": m.source,
            "access_count": m.access_count,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })
    
    # Category stats
    categories = {}
    for p in points:
        cat = p["category"]
        categories.setdefault(cat, {"count": 0, "avg_x": 0, "avg_y": 0})
        categories[cat]["count"] += 1
        categories[cat]["avg_x"] += p["x"]
        categories[cat]["avg_y"] += p["y"]
    for cat in categories:
        n = categories[cat]["count"]
        categories[cat]["avg_x"] = round(categories[cat]["avg_x"] / n, 4)
        categories[cat]["avg_y"] = round(categories[cat]["avg_y"] / n, 4)
    
    return {
        "points": points,
        "method": method,
        "total": len(points),
        "categories": categories,
    }
```

### 2. New template: `src/web/templates/embedding_explorer.html`

Chart.js scatter plot with:
- **Scatter dataset** per category (different colors)
- **Point radius** scaled by importance (min 4, max 16)
- **Hover tooltip**: shows memory label, category, importance, source
- **Click handler**: populates inspector panel with full content
- **Category legend**: click to toggle visibility
- **Method toggle**: PCA vs t-SNE radio buttons
- **Controls**: limit slider (50–500), min importance slider, category filter

Reference: Chart.js scatter type is supported natively. Use `type: 'scatter'` with `pointRadius` function.

### 3. New route in `src/web/app.py`

```python
    @app.route('/embedding-explorer')
    def embedding_explorer():
        return render_template('embedding_explorer.html')
```

### 4. Nav menu update

Add `/embedding-explorer` to 💾 Memory dropdown in `base.html`.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | API endpoint reads SemanticMemory via ORM. Uses numpy (already in Docker image) for PCA. Optional scikit-learn for t-SNE. |
| 2 | .env for secrets (zero in code) | ❌ | No secrets involved. |
| 3 | models.yaml single source of truth | ❌ | No model references. |
| 4 | Docker-first testing | ✅ | Must verify numpy available in Docker. PCA fallback ensures no hard scikit-learn dependency. |
| 5 | aria_memories only writable path | ❌ | Read-only endpoint — no writes. |
| 6 | No soul modification | ❌ | No soul files touched. |

## Dependencies
- **S-31** — shares nav menu changes (Memory dropdown). Non-blocking.
- **numpy** must be available in the Docker image (check `pyproject.toml` or `requirements.txt`).

## Verification
```bash
# 1. Verify numpy is available in Docker:
docker compose exec aria-api python -c "import numpy; print(numpy.__version__)"
# EXPECTED: version number (e.g., 1.24.x)

# 2. API endpoint returns projection:
curl -s "http://localhost:8000/api/memories/embedding-projection?limit=50&method=pca" | python3 -m json.tool | head -20
# EXPECTED: JSON with "points" array (each with x, y, label, category, importance)

# 3. Route registered:
grep -n "embedding.explorer\|embedding_explorer" src/web/app.py
# EXPECTED: route definition

# 4. Template uses Chart.js scatter:
grep -c "scatter\|type.*scatter" src/web/templates/embedding_explorer.html
# EXPECTED: >= 1

# 5. Category coloring works:
curl -s "http://localhost:8000/api/memories/embedding-projection?limit=100" | python3 -c "
import json, sys
d = json.load(sys.stdin)
cats = set(p['category'] for p in d['points'])
print(f'{len(d[\"points\"])} points, {len(cats)} categories: {cats}')
"
# EXPECTED: N points, M categories: {category names}
```

## Prompt for Agent
```
You are implementing S-33: Embedding Cluster Explorer for the Aria project.

FILES TO READ FIRST:
- src/web/templates/memory_explorer.html (lines 1-422) — existing memory page (extend pattern)
- src/api/routers/memories.py (lines 300-370) — existing search endpoint (embedding access pattern)
- src/api/db/models.py (lines 694-714) — SemanticMemory model with Vector(768) column
- src/web/templates/sentiment.html (lines 1-658) — REFERENCE for Chart.js dashboard pattern
- pyproject.toml — check if numpy is a dependency

CONSTRAINTS:
1. Use ORM for DB access (SemanticMemory model)
2. PCA must work with numpy only (no scikit-learn hard requirement)
3. t-SNE is optional (graceful fallback to PCA if sklearn missing)
4. Template extends base.html, uses Chart.js CDN for scatter plot
5. Point radius must scale with importance (min 4px, max 16px)

STEPS:
1. Add GET /memories/embedding-projection endpoint to src/api/routers/memories.py
2. Create src/web/templates/embedding_explorer.html with:
   - Chart.js scatter plot (one dataset per category, colored)
   - Point size = 4 + importance * 12
   - Hover tooltip: label, category, importance
   - Click: populate inspector sidebar with full content
   - Controls: method toggle (PCA/t-SNE), limit slider, category filter
3. Add /embedding-explorer route to src/web/app.py
4. Add nav link in base.html Memory dropdown
5. Test with verification commands
```
