"""Fix N+1 in shaoyang/distiller.py - batch inserts."""
import os
os.chdir(r'E:\easyclaw\伏羲-v1.44\repo')

with open('src/shaoyang/distiller.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: entities batch insert
old1 = '''        for e in result.get("entities",[]):
            name = e["name"].strip()
            if not name: continue
            eid = make_id("ent", name)
            conn.execute("INSERT OR IGNORE INTO entities (id,name,type,category_path,created_at) VALUES (?,?,?,?,?)",
                        (eid,name,e.get("type","concept"),path,now))
            emap[name] = eid
            stats["ent"] += 1'''

new1 = '''        # Batch: executemany \u66ff\u4ee3\u5faa\u73af INSERT
        entity_rows = []
        for e in result.get("entities",[]):
            name = e["name"].strip()
            if not name: continue
            eid = make_id("ent", name)
            entity_rows.append((eid, name, e.get("type","concept"), path, now))
            emap[name] = eid
            stats["ent"] += 1
        if entity_rows:
            conn.executemany("INSERT OR IGNORE INTO entities (id,name,type,category_path,created_at) VALUES (?,?,?,?,?)", entity_rows)'''

if old1 in content:
    content = content.replace(old1, new1)
    print('Fixed: entities batch insert')
else:
    print('SKIP: entities batch insert')

# Fix 2: terms batch insert
old2 = '''        for t in result.get("terms",[]):
            tn, td = t["term"].strip(), t.get("definition","").strip()
            if not tn or len(td)<8: continue
            tid = make_id("term", tn)
            conn.execute("INSERT OR IGNORE INTO terms (id,term,definition,category,created_at) VALUES (?,?,?,?,?)",
                        (tid,tn,td,path,now))
            tmap[tn] = tid
            stats["term"] += 1'''

new2 = '''        # Batch: executemany \u66ff\u4ee3\u5faa\u73af INSERT
        term_rows = []
        for t in result.get("terms",[]):
            tn, td = t["term"].strip(), t.get("definition","").strip()
            if not tn or len(td)<8: continue
            tid = make_id("term", tn)
            term_rows.append((tid, tn, td, path, now))
            tmap[tn] = tid
            stats["term"] += 1
        if term_rows:
            conn.executemany("INSERT OR IGNORE INTO terms (id,term,definition,category,created_at) VALUES (?,?,?,?,?)", term_rows)'''

if old2 in content:
    content = content.replace(old2, new2)
    print('Fixed: terms batch insert')
else:
    print('SKIP: terms batch insert')

# Fix 3: relations batch insert
old3 = '''        for r in result.get("relations", []):
            fn, tn, rt = r.get("from","").strip(), r.get("to","").strip(), r.get("type","related_to")
            if not fn or not tn: continue
            fid = emap.get(fn) or make_id("ent", fn)
            tid = emap.get(tn) or make_id("ent", tn)
            conn.execute("INSERT OR IGNORE INTO entities (id,name,type,created_at) VALUES (?,?,?,'concept',?)", (fid, fn, now))
            conn.execute("INSERT OR IGNORE INTO entities (id,name,type,created_at) VALUES (?,?,?,'concept',?)", (tid, tn, now))
            conn.execute("INSERT OR IGNORE INTO entity_relations (from_id,to_id,relation_type) VALUES (?,?,?)", (fid, tid, rt))
            stats["rel"] += 1'''

new3 = '''        # Batch: \u6279\u91cf\u63d2\u5165\u5173\u7cfb
        rel_ent_rows = []
        rel_rows = []
        for r in result.get("relations", []):
            fn, tn, rt = r.get("from","").strip(), r.get("to","").strip(), r.get("type","related_to")
            if not fn or not tn: continue
            fid = emap.get(fn) or make_id("ent", fn)
            tid = emap.get(tn) or make_id("ent", tn)
            rel_ent_rows.append((fid, fn, "concept", now))
            rel_ent_rows.append((tid, tn, "concept", now))
            rel_rows.append((fid, tid, rt))
            stats["rel"] += 1
        if rel_ent_rows:
            conn.executemany("INSERT OR IGNORE INTO entities (id,name,type,created_at) VALUES (?,?,?,?)", rel_ent_rows)
        if rel_rows:
            conn.executemany("INSERT OR IGNORE INTO entity_relations (from_id,to_id,relation_type) VALUES (?,?,?)", rel_rows)'''

if old3 in content:
    content = content.replace(old3, new3)
    print('Fixed: relations batch insert')
else:
    print('SKIP: relations batch insert')

# Fix 4: cross_links batch insert
old4 = '''        cl = result.get("cross_links",{})
        for wn, en in cl.get("wiki_entity_pairs",[]):
            wid = make_id("wiki", f"{wn}{path}"); eid = emap.get(en)
            if wid and eid: conn.execute("INSERT OR IGNORE INTO wiki_entity_links (wiki_id,entity_id) VALUES (?,?)",(wid,eid))
        for wn, tn in cl.get("wiki_term_pairs",[]):
            wid = make_id("wiki", f"{wn}{path}"); tid = tmap.get(tn)
            if wid and tid: conn.execute("INSERT OR IGNORE INTO wiki_term_links (wiki_id,term_id) VALUES (?,?)",(wid,tid))'''

new4 = '''        # Batch: \u6279\u91cf\u63d2\u5165 cross_links
        cl = result.get("cross_links",{})
        we_rows = []
        wt_rows = []
        for wn, en in cl.get("wiki_entity_pairs",[]):
            wid = make_id("wiki", f"{wn}{path}"); eid = emap.get(en)
            if wid and eid: we_rows.append((wid, eid))
        for wn, tn in cl.get("wiki_term_pairs",[]):
            wid = make_id("wiki", f"{wn}{path}"); tid = tmap.get(tn)
            if wid and tid: wt_rows.append((wid, tid))
        if we_rows:
            conn.executemany("INSERT OR IGNORE INTO wiki_entity_links (wiki_id,entity_id) VALUES (?,?)", we_rows)
        if wt_rows:
            conn.executemany("INSERT OR IGNORE INTO wiki_term_links (wiki_id,term_id) VALUES (?,?)", wt_rows)'''

if old4 in content:
    content = content.replace(old4, new4)
    print('Fixed: cross_links batch insert')
else:
    print('SKIP: cross_links batch insert')

with open('src/shaoyang/distiller.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done')
