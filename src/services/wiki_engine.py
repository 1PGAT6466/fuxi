"""
wiki_engine.py — Wiki引擎核心
LLM蒸馏知识库
"""
import json
import logging
import time
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger("services.wiki_engine")

WIKI_DIR = Path("data/wiki")


class WikiEngine:
    """Wiki引擎"""

    def __init__(self):
        WIKI_DIR.mkdir(parents=True, exist_ok=True)

    async def distill(self, text: str, source: str = "") -> Dict:
        """蒸馏Wiki摘要"""
        try:
            from src.infra.llm import call_llm_by_task
            prompt = f"请从以下文本中提取关键信息，生成Wiki摘要（不超过200字）：\n\n{text[:3000]}"
            summary = await call_llm_by_task(task="distillation", prompt=prompt)

            result = {
                "summary": summary or "",
                "source": source,
                "timestamp": time.time(),
            }

            # 保存
            self._save_wiki(result)
            return result
        except Exception as e:
            logger.warning(f"[Wiki] 蒸馏失败: {e}")
            return {"summary": "", "source": source, "error": str(e)}

    async def search(self, query: str, limit: int = 5) -> List[Dict]:
        """搜索Wiki"""
        wiki_file = WIKI_DIR / "wiki_entries.jsonl"
        if not wiki_file.exists():
            return []

        results = []
        try:
            with open(wiki_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        if query.lower() in entry.get("summary", "").lower():
                            results.append(entry)
                    except:
                        pass
        except Exception:
            pass

        return results[-limit:]

    def _save_wiki(self, result: Dict):
        """保存Wiki条目"""
        try:
            wiki_file = WIKI_DIR / "wiki_entries.jsonl"
            with open(wiki_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"[Wiki] 保存失败: {e}")

    def get_stats(self) -> Dict:
        """获取Wiki统计"""
        wiki_file = WIKI_DIR / "wiki_entries.jsonl"
        if not wiki_file.exists():
            return {"count": 0}

        count = 0
        try:
            with open(wiki_file, "r", encoding="utf-8") as f:
                count = sum(1 for _ in f)
        except Exception:
            pass

        return {"count": count}
