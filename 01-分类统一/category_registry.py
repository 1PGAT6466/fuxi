"""
统一分类注册表 — 全系统唯一分类定义
====================================
所有模块必须从这里导入分类信息，禁止自行定义。

用法：
    from src.category_registry import CATEGORIES, normalize_category, match_category, get_keywords

迁移步骤：
    1. 将此文件放入 src/ 目录
    2. 删除 graph_router.py 中的 CATEGORY_ALIAS、INTENT_KEYWORDS、ENTITY_TYPE_TO_CATEGORY
    3. 删除 fusion.py 中的 CAT_KW
    4. 删除 chat.py 中的 DOMAIN_KEYWORDS
    5. 全局替换：from src.category_registry import ...
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
        "ext_match": [".stp", ".step", ".dwg", ".dxf", ".prt", ".asm"],
        "aliases": [],
        "domain": "mechanical",
        "description": "模具设计相关的设计标准、结构、图样、工艺",
    },
    "连接器设计": {
        "priority": 9,
        "keywords": [
            "连接器", "Connector", "Fakra", "Mini-Fakra", "端子", "housing",
            "板端", "线端", "插针", "防水"
        ],
        "ext_match": [],
        "aliases": [],
        "domain": "mechanical",
        "description": "连接器产品设计文档、规范、工艺流程",
    },
    "机械设计": {
        "priority": 8,
        "keywords": [
            "机械", "公差", "配合", "轴承", "齿轮", "弹簧", "键槽", "花键",
            "螺纹", "联轴器", "热处理", "硬度", "表面粗糙度", "凸轮", "蜗杆",
            "蜗轮", "形位公差"
        ],
        "ext_match": [],
        "aliases": [],
        "domain": "mechanical",
        "description": "通用机械设计手册、标准、设计过程",
    },
    "标准件库": {
        "priority": 7,
        "keywords": [
            "标准件", "BOM", "MISUMI", "米思米", "选型手册", "库存优先选用",
            "厂商", "物料清单", "伺服电机", "HG-KN", "GUC", "PRJ",
            "标准插针头", "加工件", "滚珠轴承"
        ],
        "ext_match": [],
        "aliases": [],
        "domain": "mechanical",
        "description": "标准件选型、BOM、厂商清单",
    },
    "电气自动化": {
        "priority": 8,
        "keywords": [
            "PLC", "传感器", "伺服", "变频", "电磁阀", "气缸", "自动化产线",
            "电气", "PROFINET", "NPN", "PNP", "HMI", "触摸屏", "电气柜",
            "接线", "断路器", "熔断器", "光电开关", "接近开关", "西门子",
            "欧姆龙", "三菱", "基恩士", "SMC"
        ],
        "ext_match": [".awl", ".scl"],
        "aliases": [],
        "domain": "electrical",
        "description": "电气设计、PLC、自动化产线",
    },
    "IT网络": {
        "priority": 8,
        "keywords": [
            "VLAN", "交换机", "路由", "子网", "DHCP", "ACL", "防火墙", "WiFi",
            "IP", "拓扑", "interface", "trunk", "OSPF", "BGP", "NAT",
            "静态路由", "STP", "Eth-Trunk", "无线", "AP", "AC", "SSID",
            "WPA2", "WPA3", "802.1X", "NPS"
        ],
        "ext_match": [".cfg", ".conf", ".ini"],
        "aliases": ["网络建设"],  # 旧名称兼容
        "domain": "network",
        "description": "网络建设、拓扑、设备配置",
        "sub_categories": [
            "交换路由", "网络拓扑", "无线网络", "网络安全",
            "IP地址与DNS", "服务器与存储", "监控与运维", "弱电与布线"
        ],
    },
    "工程技术规范": {
        "priority": 7,
        "keywords": [
            "注塑", "成型", "工艺", "材料", "表面处理", "塑料", "模温",
            "料筒", "干燥", "收缩率", "SOP", "作业指导", "验收", "检查",
            "LCP", "PA66", "PBT", "POM", "PPS", "PA6"
        ],
        "ext_match": [],
        "aliases": [],
        "domain": "process",
        "description": "注塑成型、材料、工艺标准",
    },
    "品质测量": {
        "priority": 7,
        "keywords": [
            "三坐标", "蔡司", "品质", "测量", "质量", "CPK", "GRR", "检测",
            "CONTURA", "CALYPSO", "位置度", "平面度", "GR&R", "SPC",
            "不良", "8D", "纠正", "检具", "圆度", "轮廓度"
        ],
        "ext_match": [],
        "aliases": ["品质管理"],  # 旧名称兼容
        "domain": "quality",
        "description": "品质测量、三坐标、GR&R",
    },
    "供应商管理": {
        "priority": 6,
        "keywords": ["采购", "报价", "合同", "供应商", "交货", "付款", "RFQ"],
        "ext_match": [".xlsx", ".xls"],
        "aliases": [],
        "domain": "business",
        "description": "采购、合同、供应商",
    },
    "行政人事": {
        "priority": 5,
        "keywords": ["考勤", "请假", "薪资", "人事", "报销", "制度", "行政", "组织架构", "社保", "入职", "离职"],
        "ext_match": [],
        "aliases": [],
        "domain": "admin",
        "description": "公司制度、人事行政",
    },
    "财务文档": {
        "priority": 5,
        "keywords": ["财务", "预算", "税务", "审计", "发票", "费控", "对账", "报表"],
        "ext_match": [],
        "aliases": [],
        "domain": "business",
        "description": "财务、预算、税务",
    },
    "项目管理": {
        "priority": 5,
        "keywords": ["项目", "甘特", "里程碑", "WBS", "进度", "计划", "APQP", "PPAP", "DFMEA", "PFMEA"],
        "ext_match": [],
        "aliases": [],
        "domain": "management",
        "description": "项目文档、进度、甘特图",
    },
    "操作手册": {
        "priority": 6,
        "keywords": [
            "泛微", "E-cology", "ecology", "weaver", "协同管理平台",
            "操作手册", "使用手册", "流程引擎", "建模引擎", "门户引擎",
            "组织权限", "系统参数", "公文", "人事", "资产", "会议", "日程", "协作"
        ],
        "ext_match": [],
        "aliases": ["公司制度"],  # 旧名称兼容
        "domain": "admin",
        "description": "软件操作手册、系统使用说明",
    },
    "技术文档": {
        "priority": 4,
        "keywords": ["手册", "指南", "教程", "说明", "PROE", "Creo", "SolidWorks", "设计规则"],
        "ext_match": [],
        "aliases": [],
        "domain": "technical",
        "description": "通用技术资料、培训材料",
    },
    "办公文档": {
        "priority": 3,
        "keywords": ["PPT", "课件", "报告", "总结", "表格"],
        "ext_match": [],
        "aliases": [],
        "domain": "admin",
        "description": "通用办公文件、PPT、Word",
    },
    "元数据": {
        "priority": 2,
        "keywords": [".rar", ".7z", ".zip", ".pkg", ".exe", ".dll", ".cnsldb"],
        "ext_match": [],
        "aliases": [],
        "domain": "meta",
        "description": "归档文件、大型工具包、非文本资源",
    },
    "通用办公": {
        "priority": 1,
        "keywords": [],
        "ext_match": [],
        "aliases": [],
        "domain": "default",
        "description": "兜底分类 — 无法归入以上任何类的文件",
    },
}

# ============================================================
# 领域 Prompt 映射 — 用于 chat.py 生成回答
# ============================================================

DOMAIN_PROMPTS: Dict[str, str] = {
    "network": (
        "你是宝利根 IT 网络工程师 AI 助手。\n"
        "专长: VLAN 划分、交换路由配置、ACL 策略、无线网络部署、DHCP/NPS 认证。\n"
        "回答时使用网络专业术语（如 trunk/access/STP/OSPF），引用具体设备型号和端口号。\n"
        "涉及 IP 规划时自动检查网段冲突。"
    ),
    "mechanical": (
        "你是宝利根模具/机械设计 AI 助手。\n"
        "专长: 注塑模具设计（导柱导套/滑块/浇口/冷却系统）、连接器模具、标准件选型。\n"
        "回答时标注材料牌号（如 SKD61/SUJ2/S136）、HRC 硬度、尺寸公差。\n"
        "涉及标准件时注明供应商替代方案（米思米/盘起/国产）。"
    ),
    "electrical": (
        "你是宝利根电气自动化 AI 助手。\n"
        "专长: PLC 控制（西门子 S7-1200）、传感器选型与安装、电气柜布线、伺服驱动。\n"
        "回答时注明传感器型号（欧姆龙/SMC/基恩士）、接线方式（NPN/PNP）、防护等级。"
    ),
    "quality": (
        "你是宝利根品质检测 AI 助手。\n"
        "专长: 三坐标测量（蔡司 CONTURA）、GD&T 公差分析、GR&R 评估、CPK 计算。\n"
        "回答时标注测量标准（ISO 2768/GB/T 1184）、公差等级、采样策略。"
    ),
    "process": (
        "你是宝利根工程技术 AI 助手。\n"
        "专长: 注塑工艺参数优化、材料选型、表面处理、成型缺陷分析。\n"
        "回答时注明材料牌号、工艺参数范围、常见不良及对策。"
    ),
    "business": (
        "你是宝利根商务管理 AI 助手。\n"
        "专长: 采购流程、供应商管理、合同审核、财务报销。\n"
        "回答时引用公司制度条款，注明审批流程。"
    ),
    "admin": (
        "你是宝利根行政管理 AI 助手。\n"
        "专长: OA 系统操作（泛微 E-cology）、人事制度、考勤管理。\n"
        "回答时提供具体操作步骤，注明菜单路径。"
    ),
}

# ============================================================
# 实体类型 → 分类映射（用于图谱路由）
# ============================================================

ENTITY_TYPE_TO_CATEGORY: Dict[str, str] = {
    "network_device": "IT网络",
    "vlan": "IT网络",
    "subnet": "IT网络",
    "ip": "IT网络",
    "ssid": "IT网络",
    "protocol": "IT网络",
    "standard_part": "标准件库",
    "material": "模具设计",
    "plastic": "工程技术规范",
    "sensor": "电气自动化",
    "sensor_or_actuator": "电气自动化",
    "plc": "电气自动化",
    "supplier": "供应商管理",
    "standard": "工程技术规范",
    "model": "电气自动化",
    "document_ref": "技术文档",
}

# ============================================================
# 同义词表 — 用于查询扩展
# ============================================================

SYNONYM_MAP: Dict[str, List[str]] = {
    "plc": ["可编程控制器", "可编程逻辑控制器"],
    "lcp": ["液晶聚合物", "液晶高分子"],
    "pa66": ["尼龙66", "聚酰胺66"],
    "pbt": ["聚对苯二甲酸丁二醇酯"],
    "pom": ["聚甲醛", "赛钢"],
    "pps": ["聚苯硫醚"],
    "grr": ["量具重复性", "测量系统分析"],
    "cpk": ["过程能力指数"],
    "spc": ["统计过程控制"],
    "sop": ["标准作业程序", "标准操作流程"],
    "msds": ["安全数据表", "化学品安全说明书"],
    "vlan": ["虚拟局域网"],
    "dhcp": ["动态主机配置"],
    "acl": ["访问控制列表"],
    "nat": ["网络地址转换"],
    "wpa2": ["无线保护接入2"],
    "wpa3": ["无线保护接入3"],
    "sql": ["数据库查询"],
}

# ============================================================
# 意图关键词 — 用于快速分类判断
# ============================================================

INTENT_KEYWORDS: Dict[str, List[str]] = {}
for _cat_name, _cat_info in CATEGORIES.items():
    if _cat_info["keywords"]:
        INTENT_KEYWORDS[_cat_name] = _cat_info["keywords"]

# ============================================================
# 工具函数
# ============================================================

# 反向别名映射：旧名 → 新名
_ALIAS_MAP: Dict[str, str] = {}
for _cat_name, _cat_info in CATEGORIES.items():
    for _alias in _cat_info.get("aliases", []):
        _ALIAS_MAP[_alias] = _cat_name


def normalize_category(name: str) -> str:
    """将旧分类名映射到统一名称
    
    Examples:
        >>> normalize_category("网络建设")
        "IT网络"
        >>> normalize_category("品质管理")
        "品质测量"
        >>> normalize_category("模具设计")
        "模具设计"
    """
    return _ALIAS_MAP.get(name, name)


def get_keywords(category: str) -> List[str]:
    """获取分类关键词列表"""
    cat = CATEGORIES.get(category, {})
    return cat.get("keywords", [])


def get_all_categories() -> List[str]:
    """获取所有分类名（按优先级降序）"""
    return sorted(CATEGORIES.keys(), key=lambda x: CATEGORIES[x]["priority"], reverse=True)


def get_domain(category: str) -> str:
    """获取分类对应的领域标识"""
    cat = CATEGORIES.get(category, {})
    return cat.get("domain", "default")


def get_domain_prompt(category: str) -> str:
    """获取分类对应的领域 Prompt"""
    domain = get_domain(category)
    return DOMAIN_PROMPTS.get(domain, "")


def match_category(query: str, threshold: int = 1) -> str:
    """根据查询内容匹配最可能的分类
    
    Args:
        query: 用户查询文本
        threshold: 最低命中关键词数
        
    Returns:
        匹配到的分类名，无匹配返回空字符串
    """
    scores = {}
    q_lower = query.lower()
    for cat_name, cat_info in CATEGORIES.items():
        score = sum(1 for kw in cat_info["keywords"] if kw.lower() in q_lower)
        if score >= threshold:
            scores[cat_name] = score
    if not scores:
        return ""
    return max(scores, key=scores.get)


def match_categories_multi(query: str, top_n: int = 3) -> List[str]:
    """匹配多个可能的分类（按得分降序）"""
    scores = {}
    q_lower = query.lower()
    for cat_name, cat_info in CATEGORIES.items():
        score = sum(1 for kw in cat_info["keywords"] if kw.lower() in q_lower)
        if score > 0:
            scores[cat_name] = score
    sorted_cats = sorted(scores.items(), key=lambda x: -x[1])
    return [c for c, _ in sorted_cats[:top_n]]


def detect_exact_patterns(query: str) -> bool:
    """检测查询中是否包含型号/编号等精确匹配模式"""
    import re
    patterns = [
        r'[A-Z]{2,5}[-\s]?\d{2,6}([-\s]?\w+)?',  # GP-20-150, S7-1200
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}',     # IP 地址
        r'VLAN\s*\d+',                                # VLAN 80
        r'GB/T\s*\d+',                                # 标准号
        r'SOP-[\w-]+',                                # SOP 编号
    ]
    for pat in patterns:
        if re.search(pat, query, re.IGNORECASE):
            return True
    return False


def get_entity_type_category(entity_type: str) -> str:
    """根据实体类型获取对应分类"""
    return ENTITY_TYPE_TO_CATEGORY.get(entity_type, "")
