"""
文本分析器插件
提供文本分析、关键词提取、情感分析等功能
"""
import re
from collections import Counter
from typing import List, Dict, Any

# 插件配置
_config = {
    "max_text_length": 10000,
    "language": "zh"
}

def on_activate(context: dict):
    """插件激活时调用"""
    global _config
    if "config" in context:
        _config.update(context["config"])
    print(f"[文本分析器] 已激活，配置: {_config}")

def on_deactivate():
    """插件停用时调用"""
    print("[文本分析器] 已停用")

def register_routes(app):
    """注册API路由"""
    from fastapi import HTTPException
    from pydantic import BaseModel
    from typing import Optional
    
    class TextInput(BaseModel):
        text: str
        language: Optional[str] = None
    
    class KeywordInput(BaseModel):
        text: str
        top_n: int = 10
    
    @app.post("/api/plugins/text-analyzer/analyze")
    async def analyze_text(input_data: TextInput):
        """分析文本"""
        text = input_data.text
        if len(text) > _config["max_text_length"]:
            raise HTTPException(400, f"文本超过最大长度限制({_config['max_text_length']}字符)")
        
        result = {
            "char_count": len(text),
            "word_count": len(text.split()),
            "line_count": len(text.split('\n')),
            "sentence_count": len(re.split(r'[。！？.!?]+', text)) - 1,
            "paragraph_count": len([p for p in text.split('\n\n') if p.strip()]),
            "avg_sentence_length": 0,
            "keywords": _extract_keywords(text, 5),
            "sentiment": _analyze_sentiment(text)
        }
        
        if result["sentence_count"] > 0:
            result["avg_sentence_length"] = round(result["char_count"] / result["sentence_count"], 1)
        
        return {"status": "ok", "data": result}
    
    @app.post("/api/plugins/text-analyzer/keywords")
    async def extract_keywords(input_data: KeywordInput):
        """提取关键词"""
        keywords = _extract_keywords(input_data.text, input_data.top_n)
        return {"status": "ok", "data": {"keywords": keywords}}
    
    print("[文本分析器] 路由已注册: POST /api/plugins/text-analyzer/analyze, /keywords")

def _extract_keywords(text: str, top_n: int = 10) -> List[Dict[str, Any]]:
    """提取关键词（简单实现）"""
    # 移除标点符号和数字
    clean_text = re.sub(r'[^\w\s]', '', text)
    clean_text = re.sub(r'\d+', '', clean_text)
    
    # 分词（简单按空格和中文字符分割）
    words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', clean_text)
    
    # 过滤停用词
    stop_words = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
    words = [w for w in words if len(w) > 1 and w not in stop_words]
    
    # 统计词频
    word_counts = Counter(words)
    
    return [{"word": word, "count": count} for word, count in word_counts.most_common(top_n)]

def _analyze_sentiment(text: str) -> Dict[str, Any]:
    """情感分析（简单实现）"""
    positive_words = {'好', '棒', '优秀', '喜欢', '开心', '快乐', '满意', '赞', '完美', '出色'}
    negative_words = {'差', '糟', '讨厌', '失望', '难过', '生气', '不满', '坏', '失败', '问题'}
    
    pos_count = sum(1 for w in positive_words if w in text)
    neg_count = sum(1 for w in negative_words if w in text)
    
    total = pos_count + neg_count
    if total == 0:
        return {"label": "neutral", "score": 0.5}
    
    score = pos_count / total
    if score > 0.6:
        label = "positive"
    elif score < 0.4:
        label = "negative"
    else:
        label = "neutral"
    
    return {"label": label, "score": round(score, 2)}

def health_check():
    """健康检查"""
    return {"status": "ok", "plugin": "text-analyzer", "version": "1.0.0"}
