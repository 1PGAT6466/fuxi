"""
统一分类注册表 — 全系统唯一分类定义 v1.43
========================================
所有模块必须从这里导入分类信息，禁止自行定义。
"""
from typing import List, Dict, Optional

# ============================================================
# 主分类定义 — 唯一事实来源
# ============================================================

CATEGORIES: Dict[str, Dict] = {
    "模具设计": {
        "priority": 10,
        "keywords": [
            "模具", "导柱", "导套", "顶针", "滑块", "浇口", "分型面", "模架",
            "型腔", "注塑模具", "塑胶模具", "双色模具", "压铸模具", "冲压模具",
            "锻模", "吹塑", "模具设计大典", "热流道", "冷流道", "脱模", "排气槽"
        ],
        "domain": "mold_design",
        "desc": "模具设计、模架、标准件、浇注系统"
    },
    "标准件": {
        "priority": 8,
        "keywords": [
            "标准件", "螺丝", "螺母", "轴承", "弹簧", "垫圈", "销", "键",
            "O型圈", "密封圈", "导柱", "导套", "顶针", "滑块", "紧固件",
            "螺栓", "螺钉", "铆钉", "卡簧", "挡圈", "六角", "内六角"
        ],
        "domain": "standard_parts",
        "desc": "标准件、紧固件、密封件、轴承等"
    },
    "品质测量": {
        "priority": 8,
        "keywords": [
            "测量", "检测", "量具", "卡尺", "千分尺", "三坐标", "粗糙度",
            "硬度", "公差", "形位公差", "GD&T", "CMM", "投影仪", "高度仪",
            "圆度", "同心度", "平行度", "垂直度", "平面度"
        ],
        "domain": "quality_measure",
        "desc": "品质检测、量具、公差、形位公差"
    },
    "品质体系": {
        "priority": 6,
        "keywords": [
            "ISO9001", "IATF16949", "ISO14001", "体系", "审核", "内审",
            "外审", "管理评审", "纠正措施", "预防措施", "FMEA", "PPAP",
            "APQP", "SPC", "MSA", "质量手册", "程序文件"
        ],
        "domain": "quality_system",
        "desc": "品质体系、审核、五大工具"
    },
    "供应链": {
        "priority": 6,
        "keywords": [
            "采购", "供应商", "物流", "库存", "仓储", "ERP", "BOM",
            "物料", "交期", "订单", "送货", "验收", "入库", "出库",
            "供应链", "VMI", "JIT", "安全库存"
        ],
        "domain": "supply_chain",
        "desc": "采购、供应商、物流、库存管理"
    },
    "安全环保": {
        "priority": 7,
        "keywords": [
            "安全", "环保", "消防", "应急", "事故", "隐患", "EHS",
            "危废", "废水", "废气", "噪音", "PPE", "劳保", "安全培训",
            "危险源", "风险评估", "安全生产"
        ],
        "domain": "safety",
        "desc": "安全环保、消防、EHS"
    },
    "项目管理": {
        "priority": 5,
        "keywords": [
            "项目", "进度", "里程碑", "甘特图", "WBS", "项目计划",
            "风险管理", "变更管理", "验收", "交付", "预算", "成本"
        ],
        "domain": "project_mgmt",
        "desc": "项目管理、进度、成本"
    },
    "人力资源": {
        "priority": 5,
        "keywords": [
            "人力", "招聘", "培训", "考核", "薪酬", "绩效", "考勤",
            "入职", "离职", "劳动合同", "社保", "公积金", "面试"
        ],
        "domain": "hr",
        "desc": "人力资源、招聘、培训、考核"
    },
    "IT网络": {
        "priority": 4,
        "keywords": [
            "网络", "服务器", "防火墙", "交换机", "路由器", "VLAN",
            "IP", "DNS", "VPN", "运维", "数据库", "OA", "邮箱", "权限", "账号"
        ],
        "domain": "it_network",
        "desc": "IT基础设施、网络、服务器、安全"
    },
    "研发设计": {
        "priority": 6,
        "keywords": [
            "研发", "设计", "CAD", "CAE", "仿真", "3D", "2D",
            "SolidWorks", "UG", "ProE", "CATIA", "AutoCAD", "有限元",
            "模流分析", "热分析", "结构分析"
        ],
        "domain": "rd_design",
        "desc": "研发设计、CAD/CAE、仿真分析"
    },
    "元数据": {
        "priority": 2,
        "keywords": [
            "清单", "BOM", "明细", "汇总", "台账", "目录", "索引",
            "对照表", "配置表", "参数表", "说明", "手册"
        ],
        "domain": "metadata",
        "desc": "清单、BOM、台账、目录类文档"
    },
    "技术文档": {
        "priority": 3,
        "keywords": [
            "技术", "规范", "标准", "工艺", "流程", "参数", "规格",
            "说明书", "图纸", "SOP", "SIP", "作业指导书", "检验标准"
        ],
        "domain": "technical",
        "desc": "技术规范、工艺、SOP、图纸"
    },
    "办公文档": {
        "priority": 2,
        "keywords": [
            "报告", "总结", "计划", "通知", "会议", "纪要", "申请",
            "审批", "函", "公告", "制度", "规章", "合同"
        ],
        "domain": "office",
        "desc": "报告、总结、通知、制度等办公文档"
    },
    "财务": {
        "priority": 5,
        "keywords": [
            "财务", "会计", "税务", "发票", "报销", "预算", "成本",
            "利润", "资产负债", "现金流量", "审计", "核算"
        ],
        "domain": "finance",
        "desc": "财务、会计、税务、审计"
    },
    "销售市场": {
        "priority": 5,
        "keywords": [
            "销售", "客户", "市场", "营销", "报价", "合同", "订单",
            "CRM", "线索", "商机", "成交", "回款"
        ],
        "domain": "sales",
        "desc": "销售、客户、市场营销"
    },
    "法律法规": {
        "priority": 6,
        "keywords": [
            "法律", "法规", "合规", "知识产权", "专利", "商标", "著作权",
            "诉讼", "仲裁", "合同法", "劳动法", "环保法"
        ],
        "domain": "legal",
        "desc": "法律法规、合规、知识产权"
    },
    "通用办公": {
        "priority": 1,
        "keywords": [
            "Excel", "Word", "PPT", "表格", "文档", "幻灯片",
            "邮件", "日程", "任务", "笔记", "通讯录"
        ],
        "domain": "default",
        "desc": "兜底分类 — 无法归入以上任何类的文件",
    },
    # ── 操作手册类 ──
    "操作手册_泛微OA": {
        "keywords": [
            "流程引擎", "审批", "表单", "门户", "公文", "人事管理",
            "后台维护", "前台使用", "功能模块", "E-cology", "泛微",
            "协同办公", "组织架构", "权限设置", "模块配置", "考勤",
            "合同", "招聘", "培训", "报表", "资产", "客户", "预算"
        ],
        "priority": 8,
        "domain": "oa_manual",
        "desc": "泛微OA系统各模块的后台维护和前端使用手册"
    },
}

# ============================================================
# 领域 Prompt 映射
# ============================================================

DOMAIN_PROMPTS: Dict[str, str] = {
    "mold_design": "你是模具设计专家，回答时注重导柱导套配合、分型面、浇注系统等专业细节。",
    "standard_parts": "你是标准件专家，熟悉各类紧固件、密封件、轴承的型号规格和选用。",
    "quality_measure": "你是品质测量专家，精通GD&T、量具选用、测量方案设计。",
    "quality_system": "你是品质体系专家，熟悉ISO/IATF体系要求、五大工具应用。",
    "supply_chain": "你是供应链管理专家，擅长采购、库存、供应商管理。",
    "safety": "你是安全环保专家，熟悉EHS管理体系、消防、危废处理。",
    "project_mgmt": "你是项目管理专家，擅长进度管控、风险管理、成本控制。",
    "hr": "你是人力资源专家，熟悉招聘、培训、绩效、劳动法规。",
    "it_network": "你是IT运维专家，熟悉网络架构、服务器、信息安全。",
    "rd_design": "你是研发设计专家，精通CAD/CAE、仿真分析、产品开发。",
    "metadata": "你是数据管理专家，擅长BOM、台账、数据结构化管理。",
    "technical": "你是技术文档专家，擅长SOP、工艺规范、技术标准编写。",
    "office": "你是办公文档专家，擅长公文写作、报告编制。",
    "finance": "你是财务专家，熟悉会计核算、税务筹划、成本分析。",
    "sales": "你是销售专家，擅长客户管理、报价策略、商务谈判。",
    "legal": "你是法务专家，熟悉合同法、知识产权、合规管理。",
    "default": "你是通用知识库助手，根据文档内容提供准确回答。",
    "oa_manual": "你是企业OA系统专家，熟悉泛微E-cology等协同办公平台的配置和使用。",
}

# ============================================================
# 实体类型 → 分类映射（图谱路由用）
# ============================================================

ENTITY_TYPE_TO_CATEGORY: Dict[str, str] = {
    "模具": "模具设计",
    "标准件": "标准件",
    "量具": "品质测量",
    "检测设备": "品质测量",
    "供应商": "供应链",
    "物料": "供应链",
    "设备": "技术文档",
    "工艺": "技术文档",
    "人员": "人力资源",
    "部门": "人力资源",
    "系统": "IT网络",
    "网络": "IT网络",
}

# ============================================================
# 同义词映射 — 统一化处理
# ============================================================

SYNONYM_MAP: Dict[str, str] = {
    "plc": "PLC",
    "可编程控制器": "PLC",
    "cad": "CAD",
    "计算机辅助设计": "CAD",
    "cae": "CAE",
    "计算机辅助工程": "CAE",
    "erp": "ERP",
    "企业资源计划": "ERP",
    "bom": "BOM",
    "物料清单": "BOM",
    "crm": "CRM",
    "客户关系管理": "CRM",
    "iso9001": "ISO9001",
    "iatf16949": "IATF16949",
    "fmea": "FMEA",
    "ppap": "PPAP",
    "apqp": "APQP",
    "spc": "SPC",
    "msa": "MSA",
    "gd&t": "GD&T",
    "gdt": "GD&T",
    "cmm": "CMM",
    "三坐标测量机": "CMM",
    "solidworks": "SolidWorks",
    "ug": "UG",
    "nx": "UG",
    "proe": "ProE",
    "creo": "ProE",
    "catia": "CATIA",
    "autocad": "AutoCAD",
}

# ============================================================
# 匹配配置
# ============================================================

MATCH_CONFIG = {
    "max_text_len": 5000,
    "min_confidence": 0.15,
    "high_score_threshold": 15,
    "high_score_min_keywords": 3,
    "ext_boost": 2,
}

# ============================================================
# 工具函数
# ============================================================

def normalize_category(raw: str) -> str:
    """归一化分类名"""
    if not raw:
        return "通用办公"
    r = raw.strip().lower()
    for cat_name in CATEGORIES:
        if cat_name.lower() == r:
            return cat_name
    for cat_name, cat_info in CATEGORIES.items():
        aliases = cat_info.get("aliases", [])
        for alias in aliases:
            if alias.lower() == r:
                return cat_name
    return "通用办公"


def match_category(text: str, file_ext: str = "", max_len: int = 5000, file_name: str = "") -> Optional[str]:
    """
    从文档文本中推断分类（margin-based 置信度）。

    返回: 分类名 或 None（不确定，调用方决定 fallback）
    """
    # 文件名模式匹配：操作手册类直接命中
    if file_name:
        _fn_lower = file_name.lower()
        if '泛微' in _fn_lower or 'e-cology' in _fn_lower or 'ecology' in _fn_lower:
            return '操作手册_泛微OA'

    if not text or len(text) < 5:
        return None

    if len(text) > max_len:
        text = text[:max_len]

    scores: Dict[str, float] = {}
    text_lower = text.lower()

    for cat_name, cat_info in CATEGORIES.items():
        priority = cat_info.get("priority", 1)
        matched_count = 0
        for kw in cat_info.get("keywords", []):
            if kw.lower() in text_lower:
                matched_count += 1

        if matched_count > 0:
            score = priority * matched_count
            scores[cat_name] = score

    if not scores:
        return None

    sorted_scores = sorted(scores.values(), reverse=True)
    if len(sorted_scores) >= 2:
        confidence = (sorted_scores[0] - sorted_scores[1]) / sorted_scores[0] if sorted_scores[0] > 0 else 0
    else:
        confidence = 1.0

    best = max(scores, key=scores.get)
    best_count = 0
    for kw in CATEGORIES.get(best, {}).get("keywords", []):
        if kw.lower() in text_lower:
            best_count += 1

    # 高绝对分兜底
    if sorted_scores[0] > MATCH_CONFIG["high_score_threshold"] and best_count >= MATCH_CONFIG["high_score_min_keywords"]:
        return best

    if confidence < MATCH_CONFIG["min_confidence"]:
        return None

    return best


def match_categories_multi(text: str, top_k: int = 3) -> List[Dict]:
    """
    返回多个候选分类及其置信度。
    """
    if not text:
        return [{"category": "通用办公", "confidence": 1.0, "matched_keywords": []}]

    if len(text) > MATCH_CONFIG["max_text_len"]:
        text = text[:MATCH_CONFIG["max_text_len"]]

    scores = {}
    text_lower = text.lower()

    for cat_name, cat_info in CATEGORIES.items():
        priority = cat_info.get("priority", 1)
        matched = []
        for kw in cat_info.get("keywords", []):
            if kw.lower() in text_lower:
                matched.append(kw)
        if matched:
            scores[cat_name] = {"score": priority * len(matched), "keywords": matched}

    if not scores:
        return [{"category": "通用办公", "confidence": 1.0, "matched_keywords": []}]

    total = sum(v["score"] for v in scores.values())
    results = []
    for cat_name, info in sorted(scores.items(), key=lambda x: -x[1]["score"])[:top_k]:
        results.append({
            "category": cat_name,
            "confidence": round(info["score"] / total, 3),
            "matched_keywords": info["keywords"]
        })
    return results


def get_domain(cat_name: str) -> str:
    return CATEGORIES.get(cat_name, {}).get("domain", "default")


def get_domain_prompt(domain: str) -> str:
    return DOMAIN_PROMPTS.get(domain, "")


def get_entity_type_category(entity_type: str) -> str:
    return ENTITY_TYPE_TO_CATEGORY.get(entity_type, "")


def get_keywords(cat_name: str) -> List[str]:
    return CATEGORIES.get(cat_name, {}).get("keywords", [])


def llm_classify(text: str) -> str:
    """1.5.12 LLM 辅助分类（三级管线兜底）"""
    try:
        import requests
        r = requests.post(
            "https://token-plan-cn.xiaomimimo.com/v1/chat/completions",
            json={
                "model": "mimo-v2.5",
                "messages": [
                    {"role": "system", "content": "只输出分类名"},
                    {"role": "user", "content": f"分类：机械设计/电气自动化/IT系统/质量管理/项目管理/通用办公\n文档：{text[:500]}"}
                ],
                "max_tokens": 20,
                "temperature": 0.1
            },
            headers={"Authorization": "Bearer {os.getenv('MIMO_API_KEY', '')}"},
            timeout=10
        )
        return r.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    except:
        return ""
