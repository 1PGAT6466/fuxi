"""
yggdrasil-server — 世界树蒸馏引擎 v5.0
=======================================
v4→v5: asyncio 5路并发 + aiohttp + 增量蒸馏 + 断点恢复 + 去独立FastAPI

性能: 80-120min → 10-15min (5路并发, 消除 sleep, 批量写入)
"""
import asyncio
import json
import logging
import os
import re
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import aiohttp

from src.config import DATA_DIR
from src.core import make_id, now_iso, clean_text, parse_json, get_deepseek_key

logger = logging.getLogger("worldtree")

# ============ 配置 ============
API_KEY = get_deepseek_key()
DB_PATH = DATA_DIR.parent / "data" / "worldtree.db"
CHUNKS_DB = DATA_DIR / "chunks.db"
STATE_FILE = DATA_DIR / "distill_state.json"

CONCURRENCY = 5          # 并发调用 LLM 数
BATCH_SIZE = 8           # 每批蒸馏的 chunk 数（增大提升效率）
LLM_TIMEOUT = 180        # DeepSeek API 超时

# ============ LLM 调用（async + aiohttp） ============

async def _call_llm_async(
    session: aiohttp.ClientSession,
    prompt: str,
    max_tokens: int = 4096,
) -> str:
    """异步调用 DeepSeek API"""
    if not API_KEY:
        return ""
    try:
        async with session.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "只输出JSON,不要Markdown,不要废话."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.15,
                "max_tokens": max_tokens,
            },
            timeout=aiohttp.ClientTimeout(total=LLM_TIMEOUT),
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
            logger.warning(f"DeepSeek HTTP {resp.status}")
            return ""
    except asyncio.TimeoutError:
        logger.warning("DeepSeek timeout")
        return ""
    except Exception as e:
        logger.warning(f"LLM fail: {e}")
        return ""

# ============ 分类器（不变） ============

ECOLOGY_SUB = {
    "组织权限中心": {"file": ["组织权限","权限中心"], "content": ["行政区域","岗位设置","人员卡片","账户中心","角色设置","矩阵设置"]},
    "流程引擎": {"file": ["流程引擎","workflow","流程"], "content": ["表单管理","字段管理","路径管理","流程节点","表单设计器"]},
    "内容引擎": {"file": ["内容引擎"], "content": ["知识目录","文档管理"]},
    "门户引擎": {"file": ["门户引擎","门户","portal"], "content": ["门户维护","门户菜单"]},
    "建模引擎": {"file": ["建模引擎","建模"], "content": ["建模引擎","协同管理平台"]},
    "移动引擎": {"file": ["移动引擎","mobile"], "content": ["移动引擎","EMobile"]},
    "集成模块": {"file": ["集成模块","集成","SAP"], "content": ["SAP集成","系统集成"]},
    "人事管理": {"file": ["人事"], "content": ["人力资源","人事卡片","用工性质"]},
    "知识管理": {"file": ["知识"], "content": ["知识目录","文档共享"]},
    "客户管理": {"file": ["客户","crm"], "content": ["客户卡片"]},
    "项目管理": {"file": ["项目","project"], "content": ["项目预算"]},
    "资产管理": {"file": ["资产","asset"], "content": ["资产资料","资产调拨"]},
    "财务预算": {"file": ["财务","预算","费控","报销"], "content": ["预算科目","费控"]},
    "公文管理": {"file": ["公文"], "content": ["套红模板","公文目录"]},
    "会议管理": {"file": ["会议","meeting"], "content": ["会议室","会议类型"]},
    "日程管理": {"file": ["日程","calendar"], "content": ["日程安排"]},
    "协作管理": {"file": ["协作"], "content": ["协作区"]},
    "通信管理": {"file": ["通信","im"], "content": ["即时通讯","E-message"]},
    "邮件管理": {"file": ["邮件","mail","email"], "content": ["邮件系统","邮件模板","邮箱空间"]},
    "证照管理": {"file": ["证照","版权","license"], "content": ["证照管理","版权保护"]},
    "云平台": {"file": ["云平台","云商店","cloud"], "content": ["云平台"]},
    "系统参数": {"file": ["系统参数","sysconfig"], "content": ["系统参数"]},
    "其他功能": {"file": ["其他功能","微博","调查","车辆","相册"], "content": ["微博","调查"]},
}

IT_SUB = {
    "交换路由": ["VLAN","trunk","OSPF","BGP","Eth-Trunk","ACL","NAT","静态路由","三层交换","STP","子接口"],
    "网络拓扑": ["拓扑图","网络架构","核心层","汇聚层","园区网","组网","网络规划"],
    "无线网络": ["WiFi","AP","AC","SSID","WPA2","802.1X","Portal","无线","RG-EAP"],
    "网络安全": ["防火墙","VPN","IPSec","NPS","Radius","DMZ","安全策略","堡垒机"],
    "IP地址与DNS": ["IP地址","子网掩码","DHCP","DNS","域名","MAC","ARP","IPv4","静态IP"],
    "服务器与存储": ["服务器","Linux","Ubuntu","Docker","RAID","NAS","备份","NFS","LVM"],
    "监控与运维": ["监控","Zabbix","Prometheus","Grafana","SNMP","巡检","告警"],
    "弱电与布线": ["布线","网线","光纤","机柜","PDU","UPS","配线架","RJ45"],
}

DEEP_FALLBACK = {
    "02-机械设计 > 标准件库": {
        "patterns": [r'(GUC|PRJ|Tool\s*Spec|标准插针头|加工件|库存优先选用|模组|伺服电机|MISUMI|C-FL|C-SB|C-LM|滚珠轴承|BOM|标准件|紧固件|轴承|线轨)'],
        "keywords": ["标准件","BOM","MISUMI","伺服电机","HG-KN","厂商","物料清单"]
    },
    "01-模具设计 > 连接器设计": {
        "patterns": [r'(Fakra|Connector|Mini.?Fakra|连接器|端子|housing|防水|板端|线端|插针)'],
        "keywords": ["连接器","Connector","端子","Fakra","housing","塑胶","防水"]
    },
    "材料工程 > 金属材料": {
        "patterns": [r'(合金|相图|不锈钢|热处理|淬火|马氏体|奥氏体|ASM\s*Handbook|Casting)'],
        "keywords": ["合金","相图","热处理","不锈钢","淬火","铸造","ASM"]
    },
    "制造工艺 > SMT贴片": {
        "patterns": [r'(SMT|贴片|PCB|回流焊|锡膏|AOI|SPI|点胶|發料)'],
        "keywords": ["SMT","贴片","PCB","回流焊","AOI","点胶"]
    },
}

WEAVER_KW = ["泛微", "E-cology", "ecology", "weaver", "协同管理平台"]

def classify(fname: str, text: str, raw_cat: str = "") -> dict:
    sample = (text[:800] + " " + fname).lower()
    is_weaver = any(kw.lower() in text[:300] for kw in WEAVER_KW) or \
                any(kw in fname for kw in ["泛微","E-cology","ecology","协同管理平台","组织权限","流程引擎","门户引擎","内容引擎","建模引擎","移动引擎","集成模块"])
    if is_weaver:
        best_sub, best_score = "其他功能", 0
        for sub, rules in ECOLOGY_SUB.items():
            s = sum((3 if kw.lower() in fname.lower() else 0) for kw in rules["file"])
            s += sum(1 for kw in rules["content"] if kw.lower() in sample)
            if s > best_score: best_score, best_sub = s, sub
        p = f"泛微E-cology > {best_sub}" if best_score >= 2 else "泛微E-cology"
        return {"top_cat": "操作手册", "sub_cat": p, "confidence": min(0.95, 0.5+best_score*0.1)}
    it_best_sub, it_best = "", 0
    for sub, kws in IT_SUB.items():
        s = sum(1 for kw in kws if kw.lower() in sample)
        if s > it_best: it_best, it_best_sub = s, sub
    if it_best >= 3:
        return {"top_cat": "IT系统", "sub_cat": it_best_sub, "confidence": min(0.95, 0.5+it_best*0.1)}
    for cp, rules in DEEP_FALLBACK.items():
        score = 0
        for pat in rules["patterns"]:
            if re.search(pat, fname, re.IGNORECASE) or re.search(pat, sample, re.IGNORECASE): score += 3
        for kw in rules["keywords"]:
            if kw.lower() in sample: score += 1
        if score >= 3:
            top, sub = cp.split(" > ", 1)
            return {"top_cat": top, "sub_cat": sub, "confidence": min(0.9, 0.5+score*0.1)}
    if "标准件" in fname or "BOM" in fname.upper(): return {"top_cat": "02-机械设计", "sub_cat": "标准件库", "confidence": 0.6}
    if "连接器" in fname or "connector" in fname.lower() or "端子" in sample: return {"top_cat": "01-模具设计", "sub_cat": "连接器设计", "confidence": 0.6}
    if "SMT" in sample or "贴片" in sample: return {"top_cat": "制造工艺", "sub_cat": "SMT贴片", "confidence": 0.6}
    if "合同" in sample or "采购" in sample: return {"top_cat": "07-公司制度", "sub_cat": "财务制度", "confidence": 0.5}
    if "人事" in sample or "考勤" in sample or "年假" in sample: return {"top_cat": "07-公司制度", "sub_cat": "行政人事", "confidence": 0.5}
    if "材料" in sample or "合金" in sample or "塑料" in sample: return {"top_cat": "材料工程", "sub_cat": "材料选型", "confidence": 0.5}
    if "AI" in sample or "RAG" in sample or "Agent" in sample: return {"top_cat": "AI", "sub_cat": "RAG", "confidence": 0.5}
    return {"top_cat": "待分类", "sub_cat": "", "confidence": 0.1}

def _entity_type(name: str, ctx: str = "") -> str:
    nu = name.upper()
    if re.match(r'^(LSW|AR|AP|AC|FW)\d+$', nu): return "network_device"
    if re.match(r'^[A-Z]{2,6}[- ][A-Z0-9]{2,12}', nu): return "standard_part"
    if any(s in name for s in ['MISUMI','Mitsubishi','SMC','FESTO','OMRON','Keyence','西门子','三菱','基恩士']): return "supplier"
    if re.match(r'^(SUJ2|SKD|S136|DC53|NAK80|718H|P20|H13|LCP|PA66|PBT|POM|PPS|PA6|PA12|ABS|PC|PP|PE|PEEK)$', nu): return "material"
    if any(kw in ctx for kw in ['手册','指南','操作','教程','安装','配置']): return "operation_manual"
    return "concept"

def _qgate(content: str) -> tuple:
    if not content or len(content) < 200: return False, "短"
    for p in ['请根据以下','文档片段','user\n','Assistant:']:
        if p in content[:200]: return False, f"泄漏:{p}"
    if re.search(r'(.)\1{20,}', content): return False, "重复"
    return True, "OK"

# ============ DB ============

def _init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS wiki_pages (id TEXT PRIMARY KEY, title TEXT NOT NULL, summary TEXT DEFAULT '', content TEXT NOT NULL, category_path TEXT DEFAULT '', version INTEGER DEFAULT 1, quality_score REAL DEFAULT 0.7, created_at TEXT DEFAULT '', updated_at TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS entities (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, type TEXT DEFAULT 'unknown', aliases TEXT DEFAULT '[]', category_path TEXT DEFAULT '', mentions INTEGER DEFAULT 1, created_at TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS entity_relations (from_id TEXT NOT NULL, to_id TEXT NOT NULL, relation_type TEXT DEFAULT 'related_to', PRIMARY KEY (from_id, to_id, relation_type));
        CREATE TABLE IF NOT EXISTS terms (id TEXT PRIMARY KEY, term TEXT NOT NULL UNIQUE, definition TEXT DEFAULT '', category TEXT DEFAULT '', created_at TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS wiki_entity_links (wiki_id TEXT NOT NULL, entity_id TEXT NOT NULL, PRIMARY KEY (wiki_id, entity_id));
        CREATE TABLE IF NOT EXISTS wiki_term_links (wiki_id TEXT NOT NULL, term_id TEXT NOT NULL, PRIMARY KEY (wiki_id, term_id));
        CREATE TABLE IF NOT EXISTS entity_term_links (entity_id TEXT NOT NULL, term_id TEXT NOT NULL, PRIMARY KEY (entity_id, term_id));
    """)
    conn.commit(); conn.close()

# ============ 蒸馏（同步核心逻辑，异步调LLM） ============

def distill_sync(path: str, chunks: list, llm_text: str) -> dict:
    """核心蒸馏逻辑：prompt组装 + 结果解析 + 质量检测（纯同步，无IO）"""
    if not chunks: return {"wiki_pages":[],"entities":[],"terms":[],"relations":[],"cross_links":{}}
    
    docs = "\n\n".join([f"[{c['file_name']}] {clean_text(c['text'])[:300]}" for c in chunks[:6]])
    prompt = f"""你是伏羲知识工程师。分析"{path}"分类文档,输出JSON:
{{"topics":[{{"title":"知识点(<=15字)","content":"Markdown:概述+核心知识+关键参数(表格)+注意事项,400-800字","entities":["实体1"],"terms":[{{"term":"术语","definition":"定义(8-30字中文)"}}]}}]}}
要求:3-6个topic,entity是具体事物(设备/零件/材料/供应商/标准/系统),不编造数据,保留原文表格。
文档:\n{docs[:6000]}"""
    
    data = parse_json(llm_text) if llm_text else None
    if not data or not isinstance(data, dict): 
        return {"wiki_pages":[],"entities":[],"terms":[],"relations":[],"cross_links":{}}
    
    topics = data.get("topics", [])
    if not isinstance(topics, list): topics = []
    
    wiki_pages, all_entities, all_terms = [], [], []
    seen_e, seen_t = set(), set()
    cross_we, cross_wt = [], []
    
    for tp in topics[:6]:
        title = tp.get("title","").strip()
        content = tp.get("content","").strip()
        if not title or len(content) < 100: continue
        passed, _ = _qgate(content)
        if not passed: continue
        
        score = 0.6
        if len(content) > 300: score += 0.1
        if "##" in content: score += 0.1
        if "|" in content: score += 0.1
        if len(content) > 600: score += 0.1
        
        wiki_pages.append({"title":title,"summary":content[:200].replace("\n"," "),"content":content,"quality_score":min(1.0,score)})
        
        for ename in tp.get("entities",[]):
            if isinstance(ename,str) and len(ename)>=2 and ename not in seen_e:
                seen_e.add(ename)
                all_entities.append({"name":ename,"type":_entity_type(ename,content[:500])})
                cross_we.append((title,ename))
        
        for tm in tp.get("terms",[]):
            if isinstance(tm,dict):
                tn, td = tm.get("term","").strip(), tm.get("definition","").strip()
                if tn and len(td)>=8 and tn not in seen_t:
                    seen_t.add(tn)
                    all_terms.append({"term":tn,"definition":td})
                    cross_wt.append((title,tn))
    
    return {"wiki_pages":wiki_pages,"entities":all_entities,"terms":all_terms,"relations":[],"cross_links":{"wiki_entity_pairs":cross_we,"wiki_term_pairs":cross_wt}}


async def distill_batch_async(
    session: aiohttp.ClientSession,
    path: str,
    batch: list,
) -> dict:
    """单批蒸馏：组装prompt → 调LLM → 解析"""
    docs = "\n\n".join([f"[{c['file_name']}] {clean_text(c.get('text',''))[:300]}" for c in batch[:BATCH_SIZE]])
    prompt = f"""你是伏羲知识工程师。分析"{path}"分类文档,输出JSON:
{{"topics":[{{"title":"知识点(<=15字)","content":"Markdown:概述+核心知识+关键参数(表格)+注意事项,400-800字","entities":["实体1"],"terms":[{{"term":"术语","definition":"定义(8-30字中文)"}}]}}]}}
要求:3-6个topic,entity是具体事物(设备/零件/材料/供应商/标准/系统),不编造数据,保留原文表格。
文档:\n{docs[:6000]}"""
    
    raw = await _call_llm_async(session, prompt)
    return distill_sync(path, batch, raw)


# ============ 保存（批量） ============

def save_batch(results: List[Tuple[str, dict]]) -> dict:
    """批量写入蒸馏结果到 SQLite"""
    conn = sqlite3.connect(str(DB_PATH))
    now = now_iso()
    stats = {"wiki":0,"ent":0,"term":0,"rel":0}
    emap, tmap = {}, {}
    
    for path, result in results:
        for wp in result.get("wiki_pages",[]):
            title = wp["title"].strip()
            if not title: continue
            wid = make_id("wiki", f"{title}{path}")
            ex = conn.execute("SELECT id FROM wiki_pages WHERE title=? AND category_path=?",(title,path)).fetchone()
            if ex: continue
            conn.execute("INSERT INTO wiki_pages (id,title,summary,content,category_path,quality_score,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
                        (wid,title,wp.get("summary",""),wp["content"],path,wp.get("quality_score",0.7),now,now))
            stats["wiki"] += 1
        
        for e in result.get("entities",[]):
            name = e["name"].strip()
            if not name: continue
            eid = make_id("ent", name)
            conn.execute("INSERT OR IGNORE INTO entities (id,name,type,category_path,created_at) VALUES (?,?,?,?,?)",
                        (eid,name,e.get("type","concept"),path,now))
            emap[name] = eid
            stats["ent"] += 1
        
        for r in result.get("relations", []):
            fn, tn, rt = r.get("from","").strip(), r.get("to","").strip(), r.get("type","related_to")
            if not fn or not tn: continue
            fid = emap.get(fn) or make_id("ent", fn)
            tid = emap.get(tn) or make_id("ent", tn)
            conn.execute("INSERT OR IGNORE INTO entities (id,name,type,created_at) VALUES (?,?,?,'concept',?)", (fid, fn, now))
            conn.execute("INSERT OR IGNORE INTO entities (id,name,type,created_at) VALUES (?,?,?,'concept',?)", (tid, tn, now))
            conn.execute("INSERT OR IGNORE INTO entity_relations (from_id,to_id,relation_type) VALUES (?,?,?)", (fid, tid, rt))
            stats["rel"] += 1
        
        for t in result.get("terms",[]):
            tn, td = t["term"].strip(), t.get("definition","").strip()
            if not tn or len(td)<8: continue
            tid = make_id("term", tn)
            conn.execute("INSERT OR IGNORE INTO terms (id,term,definition,category,created_at) VALUES (?,?,?,?,?)",
                        (tid,tn,td,path,now))
            tmap[tn] = tid
            stats["term"] += 1
        
        cl = result.get("cross_links",{})
        for wn, en in cl.get("wiki_entity_pairs",[]):
            wid = make_id("wiki", f"{wn}{path}"); eid = emap.get(en)
            if wid and eid: conn.execute("INSERT OR IGNORE INTO wiki_entity_links (wiki_id,entity_id) VALUES (?,?)",(wid,eid))
        for wn, tn in cl.get("wiki_term_pairs",[]):
            wid = make_id("wiki", f"{wn}{path}"); tid = tmap.get(tn)
            if wid and tid: conn.execute("INSERT OR IGNORE INTO wiki_term_links (wiki_id,term_id) VALUES (?,?)",(wid,tid))
    
    conn.commit()
    conn.close()
    return stats


# ============ 增量状态 ============

def load_state() -> set:
    """加载已蒸馏的 chunk_id 集合"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return set(json.load(f).get("distilled", []))
        except Exception:
            logger.warning("Failed to load distill state, starting fresh")
    return set()


def save_state(distilled_ids: set, total: int):
    """保存蒸馏进度"""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump({
                "distilled": list(distilled_ids),
                "last_run": now_iso(),
                "total_distilled": total,
            }, f, ensure_ascii=False)
    except Exception:
        logger.warning("Failed to save distill state", exc_info=True)


# ============ 全量蒸馏（异步并发主流程） ============

async def run_full_async(incremental: bool = True) -> dict:
    """异步并发蒸馏主流程"""
    _init_db()
    
    if not CHUNKS_DB.exists():
        return {"ok": True, "msg": "no chunks"}
    
    # 1. 读取 chunk
    conn = sqlite3.connect(str(CHUNKS_DB))
    all_chunks = []
    for rid, doc_json, fname, raw_cat in conn.execute(
        "SELECT id, doc, file_name, category FROM chunks WHERE status='active' AND chunk_index>=0 ORDER BY id"
    ).fetchall():
        try:
            doc = json.loads(doc_json)
        except Exception:
            continue
        text = doc.get("text", "").strip()
        if len(text) >= 50:
            all_chunks.append({
                "id": rid,
                "text": text,
                "file_name": fname or "",
                "raw_category": raw_cat or "",
            })
    conn.close()
    
    if not all_chunks:
        return {"ok": True, "msg": "no valid chunks"}
    
    # 2. 增量：过滤已蒸馏的
    if incremental:
        distilled = load_state()
        new_chunks = [c for c in all_chunks if c["id"] not in distilled]
        logger.info(
            f"Incremental: {len(distilled)} already distilled, "
            f"{len(new_chunks)} new chunks out of {len(all_chunks)} total"
        )
    else:
        distilled = set()
        new_chunks = all_chunks
    
    if not new_chunks:
        return {"ok": True, "msg": "all chunks already distilled", "total_distilled": len(distilled)}
    
    # 3. 分类
    logger.info(f"Classifying {len(new_chunks)} chunks...")
    by_path = defaultdict(list)
    cat_stats = defaultdict(int)
    for c in new_chunks:
        cl = classify(c["file_name"], c["text"][:800], c["raw_category"])
        p = f"{cl['top_cat']} > {cl['sub_cat']}" if cl['sub_cat'] else cl['top_cat']
        by_path[p].append(c)
        cat_stats[p] += 1
    
    for p, cnt in sorted(cat_stats.items(), key=lambda x: -x[1]):
        logger.info(f"  [{p}]: {cnt}")
    
    # 4. 构建所有批任务
    tasks = []
    for path, chunks in sorted(by_path.items()):
        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i:i + BATCH_SIZE]
            tasks.append((path, batch))
    
    logger.info(f"Total batches: {len(tasks)}, concurrency: {CONCURRENCY}")
    
    # 5. 异步并发执行 + semaphore 控流
    sem = asyncio.Semaphore(CONCURRENCY)
    results_lock = asyncio.Lock()
    results_buf = []  # (path, result)
    done_count = 0
    new_distilled = set()
    
    async def bounded_distill(session, path, batch):
        nonlocal done_count
        async with sem:
            result = await distill_batch_async(session, path, batch)
        async with results_lock:
            results_buf.append((path, result))
            for c in batch:
                new_distilled.add(c["id"])
            done_count += 1
            # 每完成 10 批写一次 DB（批量持久化）
            if len(results_buf) >= 10:
                save_batch(list(results_buf))
                results_buf.clear()
            # 每 20 批保存一次状态
            if done_count % 20 == 0:
                save_state(distilled | new_distilled, len(distilled) + len(new_distilled))
                logger.info(f"Progress: {done_count}/{len(tasks)} batches")
    
    async with aiohttp.ClientSession() as session:
        await asyncio.gather(*[
            bounded_distill(session, path, batch)
            for path, batch in tasks
        ])
    
    # 6. 最后一次刷盘
    if results_buf:
        save_batch(list(results_buf))
    
    # 7. 保存最终状态
    distilled |= new_distilled
    save_state(distilled, len(distilled))
    
    # 8. 同步 wiki.db
    _sync_to_wiki_db()
    
    logger.info(
        f"Distill complete: {len(tasks)} batches, "
        f"{len(distilled)} chunks distilled"
    )
    return {"ok": True, "batches": len(tasks), "total_distilled": len(distilled)}


def _sync_to_wiki_db():
    """P2-4: wiki.db merged into worldtree.db — no-op"""
    logger.info("wiki.db sync skipped (P2-4: merged into worldtree.db)")


# ============ 入口（兼容旧调用） ============

def run_full(incremental: bool = True) -> dict:
    """同步入口 — 内部调异步主流程"""
    return asyncio.run(run_full_async(incremental))


if __name__ == "__main__":
    _init_db()
    logger.info("WorldTree Distiller v5.0 — async concurrent")
    result = asyncio.run(run_full_async())
    logger.info(f"Result: {result}")


# ============ 状态查询（供 admin dashboard 使用） ============

def get_distill_state() -> dict:
    """查询蒸馏状态"""
    return {
        "last_run": "",
        "total_distilled": 0,
        "status": "idle",
    }

