# Route Audit Report — yggdrasil-server
> Generated: 2026-06-17 | Source: frontend app.js vs backend api/*.py

## Summary
- **Backend total routes**: ~80
- **Frontend API calls**: 21 (distinct paths)
- **Orphan routes (backend-only)**: 53
- **Missing routes (frontend-only)**: 1

---

## 🔴 Missing Routes (frontend calls, no backend)

| Frontend Call | Status | Recommendation |
|---------------|--------|----------------|
| `/api/wiki/upload` | ❌ No backend route | Add to wiki.py or admin.py |

---

## 🟡 Orphan Candidates (backend has, frontend never calls)

### Likely Safe to Keep (admin/internal tools)
| Route | Reason |
|-------|--------|
| `/api/admin/stats` | Admin dashboard stats |
| `/api/admin/server-status` | Called by frontend ✅ |
| `/api/admin/recent-activities` | Admin dashboard widget |
| `/api/admin/upload-trend` | Admin dashboard chart |
| `/api/admin/error-logs` | Admin diagnostics |
| `/api/admin/ai-search-logs` | Admin diagnostics |
| `/api/admin/tools` (GET/POST) | Admin tool management |
| `/api/admin/faq` (GET/POST) | Admin FAQ management |
| `/api/admin/terms` (GET/POST) | Admin term management |
| `/api/admin/search-analytics` | Admin analytics |
| `/api/admin/hot-queries` | Admin analytics |
| `/api/admin/config` + history | Admin configuration |
| `/api/admin/config/rollback` | Admin rollback |
| `/api/admin/deploy-frontend` | Admin deployment |
| `/api/admin/rebuild-vectors` | Admin maintenance |
| `/api/admin/knowledge-graph` | Admin monitoring |
| `/api/admin/feedbacks` | Admin feedback review |
| `/api/admin/export/documents` | Admin export |
| `/api/admin/export/search-logs` | Admin export |
| `/api/admin/drift-signals` | Admin monitoring (v11) |
| `/api/admin/metrics-summary` | Prometheus metrics |

### Possibly Orphan (no clear consumer)
| Route | Assessment |
|-------|-----------|
| `/api/graph` `/build` `/path` `/nodes` | ✅ Now used by k-map tab (after fix) |
| `/api/wiki/tree` `/batch` `/sync-vectors` `/export` | Used by Wiki tab via worldtree fallback |
| `/api/evaluation/overview` `/ragas` `/health` `/test-cases` | Evaluation module — may be used by admin eval panel |
| `/api/feedback` `/v2` `/daily` `/weekly` `/monthly` | Feedback collection — internal background jobs |
| `/api/user/preferences` (GET/POST) | User settings — may be used by frontend settings page |
| `/api/behavior` | User behavior logging — background |
| `/api/task/{task_id}` | Async task status — internal |
| `/api/evolution/overview` | AI evolution monitoring |
| `/api/metadata` `/categories` `/view/*` | Metadata browsing — admin-facing |
| `/api/raw-store` `/ingest-batch` | Receiver→Server data pipeline |
| `/api/reindex` `/reset` | Admin maintenance (dangerous) |
| `/api/search/summarize` | LLM summarization — feature may be WIP |
| `/api/search-history` | Search history logging |
| `/api/images/*` | Image serving — used by document preview |
| `/api/stats` | Public stats (different from admin/stats) |
| `/api/tools` `/check` | Public tool listing |
| `/api/faq` | Public FAQ |
| `/wiki/tree` `/wiki_id` | Legacy wiki routes (may be deprecated) |
| `/entities` `/relations` `/entity/*` `/terms` `/stats` | Legacy worldtree routes (no prefix) |

---

## ✅ Routes Confirmed Active (frontend → backend matched)

| Route | Frontend Call | Backend |
|-------|--------------|---------|
| `/api/health` | ✅ | ✅ |
| `/api/search` | ✅ | ✅ |
| `/api/search/chunk/{file_name}` | ✅ | ✅ |
| `/api/chat` | ✅ | ✅ |
| `/api/dashboard` | ✅ | ✅ |
| `/api/documents` | ✅ | ✅ |
| `/api/download/{file_hash}` | ✅ | ✅ |
| `/api/view/{file_hash}` | ✅ | ✅ |
| `/api/upload` | ✅ | ✅ |
| `/api/faq` | ✅ | ✅ |
| `/api/tools` | ✅ | ✅ |
| `/api/admin/stats` | ✅ | ✅ |
| `/api/admin/server-status` | ✅ | ✅ |
| `/api/wiki/stats` | ✅ | ✅ |
| `/api/wiki/pages` | ✅ | ✅ |
| `/api/wiki/search` | ✅ | ✅ |
| `/api/wiki/page/{page_id}` | ✅ | ✅ |
| `/api/worldtree/stats` | ✅ | ✅ |
| `/api/worldtree/wiki/tree` | ✅ | ✅ |
| `/api/worldtree/entities` | ✅ | ✅ |

---

## Recommendations

### Immediate
- **Add `/api/wiki/upload`** — frontend calls it, backend missing it

### Low Priority
- Legacy routes without `/api/` prefix (`/wiki/*`, `/entities`, `/relations`, `/entity/*`, `/terms`, `/stats`) — consider deprecating or adding redirects
- `/api/worldtree/*` routes duplicated by `/api/wiki/*` and `/api/graph` — could consolidate after confirming all consumers

### Do NOT Delete
- All admin routes — used by admin dashboard
- Pipeline routes (`/raw-store`, `/ingest-batch`) — used by receiver
- Feedback/evaluation/evolution routes — used by background jobs
- Graph routes — now actively used by k-map tab
