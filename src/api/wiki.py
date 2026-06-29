"""routers/wiki.py — LLM-Wiki API 路由 (v18 — worldtree fallback)"""
import json, time, os, sqlite3
from fastapi import APIRouter, Query, Request, HTTPException, File, UploadFile, Form
from fastapi.responses import JSONResponse

router = APIRouter(tags=["wiki"])
from collections import defaultdict
from pathlib import Path


# 9 大一级分类 — 覆盖清洗程序17类 + AI + IT系统
CATEGORY_MAP = {
    "模具设计":     ["模具设计", "模具", "连接器设计", "连接器", "端子", "注塑", "成型", "型腔", "分模", "滑块"],
    "机械设计":     ["机械设计", "机械", "材料", "标准件", "标准件库", "公差", "轴承", "齿轮", "紧固件", "GB/T", "PA66", "工程塑料", "联轴器", "丝杆", "导轨"],
    "电气自动化":   ["电气自动化", "电气", "PLC", "传感器", "伺服", "电机", "变频", "HMI", "SCADA", "继电器", "断路器", "配电"],
    "自动化产线":   ["自动化产线", "自动化", "产线", "装配线", "流水线", "机器人", "AGV", "机械手", "倍速链", "视觉"],
    "网络建设":     ["网络建设", "网络", "VLAN", "路由", "交换", "DHCP", "DNS", "防火墙", "AC", "AP", "拓扑", "子网", "ACL", "VPN", "IP"],
    "工程技术规范": ["工程技术规范", "规范", "标准", "ISO", "GB", "工艺", "SOP", "技术要求", "验收", "规程", "ASTM", "DIN", "JIS", "品质管理", "品质", "SPC", "FMEA"],
    "公司制度":     ["公司制度", "制度", "人事", "财务", "行政", "培训", "安全", "供应商管理", "采购", "项目管理", "会议", "周报", "办公文档", "合同", "报价"],
    "IT系统与操作手册": ["IT系统", "操作手册", "使用手册", "维护手册", "前端使用", "系统维护", "泛微", "E-cology", "E-c", "SAP", "OA系统", "ERP", "MES", "PLM", "WMS", "协同办公", "管理员指南", "建模引擎", "移动引擎", "流程引擎", "门户引擎", "内容引擎", "集成模块", "组织权限", "系统参数"],
    "AI":           ["RAG", "AI", "LLM", "机器学习", "深度学习", "NLP", "检索", "分块", "Embedding",
                     "Agent", "Chunk", "幻觉", "评测", "召回", "Rerank", "Prompt", "蒸馏", "Wiki上传", "技术文档"],
}


def _get_wt_db():
    """Get worldtree.db connection — uses core/db context manager pattern."""
    from src.core.db import connect, get_db_path
    conn = sqlite3.connect(str(get_db_path("worldtree")))
    conn.row_factory = sqlite3.Row
    return conn


def _try_engine(func_name: str):
    """Try loading wiki_engine, return None if missing."""
    try:
        from src.services.wiki_engine import get_wiki_engine
        return get_wiki_engine()
    except ModuleNotFoundError:
        return None


def _safe_json(val, default=None):
    """Safely parse JSON, returning default on failure."""
    if val is None:
        return default
    if isinstance(val, (list, dict)):
        return val
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return default
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return default
    return default


def _get_page_dict(row) -> dict:
    """Row → dict, normalize field names."""
    r = dict(row)
    return {
        "id": r.get("id", ""),
        "title": r.get("title", ""),
        "content": r.get("content", r.get("summary", "")),
        "summary": r.get("summary", ""),
        "category": r.get("category_path", r.get("category", "")),
        "tags": _safe_json(r.get("tags"), []),
        "quality_score": r.get("quality_score", 0),
        "created_at": r.get("created_at", ""),
    }


def map_category(raw_cat: str) -> tuple:
    """将原始 category (来自 ingest.py/清洗程序 约17类) 映射为 8大一级分类"""
    if not raw_cat or raw_cat == "未分类":
        return ("未分类", raw_cat)
    
    if " > " in raw_cat:
        parts = raw_cat.split(" > ", 1)
        parent = parts[0].strip()
        child = parts[1].strip() if len(parts) > 1 else ""
    else:
        parent = raw_cat.strip()
        child = raw_cat.strip()
    
    # 直接匹配（old ingest 分类名 → 9大分类）
    DIRECT_MAP = {
        "IT网络": ("网络建设", "IT网络"),
        "供应商管理": ("公司制度", "供应商管理"),
        "品质测量": ("工程技术规范", "品质测量"),
        "行政人事": ("公司制度", "行政人事"),
        "财务文档": ("公司制度", "财务文档"),
        "通用办公": ("公司制度", "通用办公"),
        "模具设计": ("模具设计", "模具设计"),
        "连接器设计": ("模具设计", "连接器设计"),
        "机械设计": ("机械设计", "机械设计"),
        "标准件库": ("机械设计", "标准件库"),
        "电气自动化": ("电气自动化", "电气自动化"),
        "自动化产线": ("自动化产线", "自动化产线"),
        "网络建设": ("网络建设", "网络建设"),
        "工程技术规范": ("工程技术规范", "工程技术规范"),
        "品质管理": ("工程技术规范", "品质管理"),
        "公司制度": ("公司制度", "公司制度"),
        "项目管理": ("公司制度", "项目管理"),
        "办公文档": ("公司制度", "办公文档"),
        "技术文档": ("AI", "技术文档"),
        "元数据": ("未分类", "元数据"),
        "IT系统与操作手册": ("IT系统与操作手册", "IT系统与操作手册"),
        "操作手册": ("IT系统与操作手册", "操作手册"),
        "系统维护": ("IT系统与操作手册", "系统维护"),
    }
    if parent in DIRECT_MAP:
        return DIRECT_MAP[parent]
    
    # 关键词匹配（兜底）
    for top_cat, keywords in CATEGORY_MAP.items():
        for kw in keywords:
            if kw.lower() in parent.lower() or kw.lower() in child.lower():
                return (top_cat, child or parent)
    
    return (parent, child or parent)


def _list_pages_from_db(category: str = "", limit: int = 500) -> list:
    """Fallback: list pages from worldtree.db wiki_pages table."""
    db = _get_wt_db()
    try:
        if category:
            rows = db.execute(
                "SELECT * FROM wiki_pages WHERE category_path LIKE ? ORDER BY created_at DESC LIMIT ?",
                (f"{category}%", limit)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM wiki_pages ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [_get_page_dict(r) for r in rows]
    finally:
        db.close()


def _get_page_from_db(page_id: str) -> dict | None:
    """Fallback: get single page from worldtree.db."""
    db = _get_wt_db()
    try:
        row = db.execute("SELECT * FROM wiki_pages WHERE id = ?", (page_id,)).fetchone()
        return _get_page_dict(row) if row else None
    finally:
        db.close()


def _search_pages_from_db(q: str, limit: int = 20) -> list:
    """Fallback: search pages by title/content from worldtree.db."""
    db = _get_wt_db()
    try:
        rows = db.execute(
            "SELECT * FROM wiki_pages WHERE title LIKE ? OR summary LIKE ? LIMIT ?",
            (f"%{q}%", f"%{q}%", limit)
        ).fetchall()
        return [_get_page_dict(r) for r in rows]
    finally:
        db.close()


@router.get("/api/wiki/tree")
async def wiki_tree():
    """返回 WIKI 四级树结构: 大类 > 子分类 > 系统 > 页面"""
    engine = _try_engine("wiki_tree")
    pages = engine.list_pages(limit=500) if engine else _list_pages_from_db(limit=500)
    
    tree_root = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    
    for p in pages:
        raw_cat = p.get("category", "未分类")
        title = p.get("title", "")
        page_id = p.get("id", "")
        
        if " > " in raw_cat:
            parts = [x.strip() for x in raw_cat.split(" > ")]
        else:
            level1, level2 = map_category(raw_cat)
            parts = [level1, level2]
        
        if len(parts) >= 4:
            top, sub, sys, topic = parts[0], parts[1], parts[2], parts[3]
            tree_root[top][sub][sys].append({"id": page_id, "name": title})
        elif len(parts) == 3:
            top, sub, sys = parts
            tree_root[top][sub][sys].append({"id": page_id, "name": title})
        elif len(parts) == 2:
            top, sub = parts
            tree_root[top][sub]["_direct"].append({"id": page_id, "name": title})
        else:
            tree_root[parts[0]]["_direct"]["_direct"].append({"id": page_id, "name": title})
    
    category_order = list(CATEGORY_MAP.keys())
    tree = []
    
    for top_cat in category_order:
        if top_cat not in tree_root:
            continue
        
        top_children = []
        for sub_cat in sorted(tree_root[top_cat]):
            sys_dict = tree_root[top_cat][sub_cat]
            sub_children = []
            
            for sys_name in sorted(sys_dict):
                page_list = sys_dict[sys_name]
                if sys_name == "_direct":
                    for leaf in page_list:
                        sub_children.append(leaf)
                else:
                    sub_children.append({
                        "name": sys_name,
                        "children": page_list,
                        "count": len(page_list),
                    })
            
            if sub_cat == "_direct":
                top_children.extend(sub_children)
            else:
                top_children.append({
                    "name": sub_cat,
                    "children": sub_children,
                    "count": sum(
                        (c.get("count", 1) if isinstance(c, dict) else 1)
                        for c in sub_children
                    ),
                })
        
        tree.append({
            "name": top_cat,
            "children": top_children,
            "count": sum(c.get("count", 0) for c in top_children if isinstance(c, dict)),
        })
    
    for top_cat in sorted(tree_root):
        if top_cat in category_order:
            continue
        top_children = []
        for sub_cat in sorted(tree_root[top_cat]):
            sys_dict = tree_root[top_cat][sub_cat]
            for sys_name in sorted(sys_dict):
                page_list = sys_dict[sys_name]
                if sys_name == "_direct":
                    for leaf in page_list:
                        top_children.append(leaf)
                else:
                    top_children.append({
                        "name": sys_name,
                        "children": page_list,
                        "count": len(page_list),
                    })
        tree.append({
            "name": top_cat,
            "children": top_children,
            "count": len(top_children),
        })
    
    return {"tree": tree, "total": len(pages), "version": "v18-fallback"}


@router.get("/api/wiki/search")
async def search_wiki(q: str = Query(""), limit: int = Query(5)):
    engine = _try_engine("search_wiki")
    if engine:
        pages = engine.search_by_title(q, limit=limit)
        if not pages:
            pages = engine.search_content(q, limit=limit)
        return {"pages": pages, "total": len(pages)}
    if not q:
        return {"pages": [], "total": 0}
    pages = _search_pages_from_db(q, limit)
    return {"pages": pages, "total": len(pages)}


@router.get("/api/wiki/pages")
async def list_wiki_pages(category: str = Query(""), limit: int = Query(50)):
    engine = _try_engine("list_pages")
    pages = engine.list_pages(category=category, limit=limit) if engine else _list_pages_from_db(category=category, limit=limit)
    return {"pages": pages, "total": len(pages)}


@router.get("/api/wiki/page/{page_id}")
async def get_wiki_page(page_id: str):
    engine = _try_engine("get_page")
    if engine:
        page = engine.get_page(page_id)
        if not page:
            return JSONResponse({"error": "not found", "page_id": page_id}, status_code=404)
        linked = engine.get_linked_pages(page_id)
        page["linked_pages"] = linked
        return page
    
    page = _get_page_from_db(page_id)
    if not page:
        return JSONResponse({"error": "not found", "page_id": page_id}, status_code=404)
    page["linked_pages"] = []
    return page


@router.delete("/api/wiki/page/{page_id}")
async def delete_wiki_page(page_id: str):
    engine = _try_engine("delete_page")
    if engine:
        ok = engine.delete_page(page_id)
        return {"ok": ok, "deleted": page_id if ok else None}
    
    db = _get_wt_db()
    try:
        db.execute("DELETE FROM wiki_pages WHERE id = ?", (page_id,))
        db.commit()
        return {"ok": True, "deleted": page_id}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


@router.post("/api/wiki/page")
async def create_wiki_page(request: Request):
    engine = _try_engine("create_page")
    body = await request.json()
    title = body.get("title", "")
    content = body.get("content", "")
    category = body.get("category", "")
    tags = body.get("tags", [])
    sources = body.get("sources", [])
    
    if not title or not content:
        return JSONResponse({"error": "title and content are required"}, status_code=400)
    
    if engine:
        try:
            page_id = engine.create_page(title=title, content=content, category=category, tags=tags, sources=sources)
            return {"ok": True, "page_id": page_id, "title": title}
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
    
    # Fallback: insert into worldtree.db
    import uuid
    page_id = body.get("id", f"wiki_{uuid.uuid4().hex[:12]}")
    db = _get_wt_db()
    try:
        db.execute(
            "INSERT OR REPLACE INTO wiki_pages (id, title, content, summary, category_path, tags, quality_score, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (page_id, title, content, content[:200], category, json.dumps(tags), body.get("quality_score", 0), time.strftime("%Y-%m-%d %H:%M:%S"))
        )
        db.commit()
        return {"ok": True, "page_id": page_id, "title": title}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        db.close()


@router.post("/api/wiki/batch")
async def batch_create_wiki(request: Request):
    engine = _try_engine("batch_create")
    body = await request.json()
    pages = body.get("pages", [])
    
    if engine:
        results = []
        for p in pages:
            try:
                page_id = engine.create_page(
                    title=p.get("title", ""), content=p.get("content", ""),
                    category=p.get("category", ""), tags=p.get("tags", []),
                    sources=p.get("sources", [])
                )
                results.append({"ok": True, "page_id": page_id})
            except Exception as e:
                results.append({"ok": False, "error": str(e)})
        return {"results": results}
    
    # Fallback
    import uuid
    results = []
    db = _get_wt_db()
    try:
        for p in pages:
            try:
                page_id = p.get("id", f"wiki_{uuid.uuid4().hex[:12]}")
                db.execute(
                    "INSERT OR REPLACE INTO wiki_pages (id, title, content, summary, category_path, tags, quality_score, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (page_id, p.get("title", ""), p.get("content", ""), p.get("content", "")[:200],
                     p.get("category", ""), json.dumps(p.get("tags", [])), p.get("quality_score", 0),
                     time.strftime("%Y-%m-%d %H:%M:%S"))
                )
                results.append({"ok": True, "page_id": page_id})
            except Exception as e:
                results.append({"ok": False, "error": str(e)})
        db.commit()
    finally:
        db.close()
    return {"results": results}


@router.post("/api/wiki/sync-vectors")
async def sync_wiki_vectors():
    engine = _try_engine("sync_vectors")
    if engine:
        return engine.sync_vectors()
    # No-op fallback
    return {"synced": 0, "message": "wiki_engine not available, no sync performed"}


@router.post("/api/wiki/upload")
async def wiki_upload(file: UploadFile = File(...), source: str = Form("wiki_upload")):
    """Upload a file to be processed into a Wiki page."""
    engine = _try_engine("wiki_upload")
    if engine:
        try:
            content = await file.read()
            result = engine.upload_file(file.filename, content, source)
            return {"ok": True, "page_id": result.get("page_id", "")}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    # Fallback: save to uploads dir and insert as wiki page
    try:
        import uuid
        content_bytes = await file.read()
        content = content_bytes.decode("utf-8", errors="ignore")
        page_id = f"wiki_{uuid.uuid4().hex[:12]}"
        db = _get_wt_db()
        db.execute(
            "INSERT OR REPLACE INTO wiki_pages (id, title, content, summary, category_path, tags, quality_score, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (page_id, file.filename, content, content[:200], source, "[]", 0.5, time.strftime("%Y-%m-%d %H:%M:%S"))
        )
        db.commit()
        db.close()
        return {"ok": True, "page_id": page_id}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/api/wiki/export")
async def export_wiki():
    engine = _try_engine("export")
    pages = engine.list_pages(limit=500) if engine else _list_pages_from_db(limit=500)
    return {"exported_at": time.strftime("%Y-%m-%d %H:%M"), "total": len(pages), "pages": pages}


@router.get("/api/wiki/stats")
async def wiki_stats():
    engine = _try_engine("stats")
    pages = engine.list_pages(limit=500) if engine else _list_pages_from_db(limit=500)
    total = len(pages)
    tags_counter = defaultdict(int)
    cat_counts = defaultdict(int)
    
    for p in pages:
        for tag in p.get("tags", []):
            tags_counter[tag] += 1
        level1, _ = map_category(p.get("category", ""))
        cat_counts[level1] += 1
    
    return {
        "total_pages": total,
        "top_tags": dict(sorted(tags_counter.items(), key=lambda x: -x[1])[:20]),
        "category_distribution": {k: cat_counts.get(k, 0) for k in CATEGORY_MAP},
    }
"""v1.42 Wiki API 路由 — 知识页数据接口"""
from typing import Dict, Any, Optional


@router.get("/list")
async def wiki_list(search: Optional[str] = None) -> Dict[str, Any]:
    """获取 Wiki 页面列表"""
    try:
        from src.services.wiki import get_wiki_engine
        engine = get_wiki_engine()
        pages = engine.list_pages()
        if search:
            pages = [p for p in pages if search.lower() in p.get("title", "").lower()]
        
        return {"ok": True, "pages": pages, "total": len(pages)}
    except ImportError:
        return {"ok": True, "pages": [], "total": 0, "message": "wiki service not available"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@router.get("/{wiki_id}")
async def wiki_detail(wiki_id: str) -> Dict[str, Any]:
    """获取单个 Wiki 页面详情"""
    try:
        import sys
        sys.path.insert(0, '/home/feng-shaoxuan/伏羲·内世界')
        from src.services.wiki import get_wiki_page
        
        page = await get_wiki_page(wiki_id)
        if page:
            return {"ok": True, "page": page}
        return {"ok": False, "error": "not found"}
    except ImportError:
        return {"ok": False, "error": "wiki service not available"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
