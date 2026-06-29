"""
伏羲 Fuxi 配置
===============
统一配置入口，支持 .env 覆盖
"""
import os
import re
from pathlib import Path
from typing import List

# ============ 路径 ============
BASE_DIR = Path(os.path.expanduser("~/kb-server"))
DATA_DIR = BASE_DIR / "data"
FEEDBACK_DIR = BASE_DIR / "feedback_data"
UPLOAD_DIR = BASE_DIR / "uploads"
LOG_DIR = BASE_DIR / "logs"
BACKUP_DIR = BASE_DIR / "backups"
STATIC_DIR = BASE_DIR / "frontend"
ADMIN_DIR = STATIC_DIR / "admin"
CONFIG_HISTORY_DIR = DATA_DIR / "config_history"

# 数据库
CHUNKS_DB_PATH = DATA_DIR / "chunks.db"
DB_PATH = CHUNKS_DB_PATH  # legacy alias
WORLDTREE_DB_PATH = DATA_DIR / "worldtree.db"
# P2-4: wiki.db merged into worldtree.db, kept as legacy alias
WIKI_DB_PATH = WORLDTREE_DB_PATH  # legacy alias → worldtree.db

# 文件
CHUNKS_FILE = DATA_DIR / "chunks.json"
GRAPH_PATH = DATA_DIR / "knowledge_graph.json"
TERMS_FILE = DATA_DIR / "company_terms.json"
CONFIG_FILE = DATA_DIR / "config.json"
USER_PREFERENCES_FILE = DATA_DIR / "user_preferences.json"

# 图片
KB_IMAGES_DIR = BASE_DIR / "kb-images"

# 确保目录存在
for d in [DATA_DIR, UPLOAD_DIR, LOG_DIR, BACKUP_DIR, STATIC_DIR, CONFIG_HISTORY_DIR, KB_IMAGES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

(KB_IMAGES_DIR / "thumbs").mkdir(exist_ok=True)

# ============ 网络 ============
HOST = os.getenv("KB_HOST", "0.0.0.0")
PORT = int(os.getenv("KB_PORT", "8080"))
EMBEDDER_URL = os.getenv("KB_EMBEDDER_URL", "http://localhost:8081")
CORS_ORIGINS: List[str] = os.getenv(
    "KB_CORS_ORIGINS",
    "${KB_SERVER_URL:-http://localhost:8080},http://localhost:8080"
).split(",")

# ============ 安全 ============
ADMIN_TOKEN = os.getenv("KB_ADMIN_TOKEN", "")
MAX_FILE_MB = 200
UPLOAD_MAX_MB = int(os.getenv("KB_UPLOAD_MAX_MB", "200"))
LOADER_URL = os.getenv("LOADER_URL", "http://172.25.30.16:8090")
AI_TIMEOUT_SECONDS = int(os.getenv("KB_AI_TIMEOUT", "30"))

# ============ MiMo API 配置 ============
MIMO_API_KEY = os.getenv("MIMO_API_KEY", "")
MIMO_BASE_URL = os.getenv("MIMO_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")
MIMO_MODEL = os.getenv("MIMO_MODEL", "mimo-v2.5")
MIMO_TIMEOUT = int(os.getenv("MIMO_TIMEOUT", "60"))


# ============ 模型 ============

# ============ 版本 ============
VERSION = "1.43"
START_TIME = __import__("time").time()

# ============ 工具与 FAQ 默认数据 ============
TOOLS_DATA = [
    {"id":"vpn","name":"VPN 连接","icon":"\U0001f510","category":"网络","url":"#vpn","desc":"远程接入公司内网","available":False},
    {"id":"email","name":"企业邮箱","icon":"\U0001f4e7","category":"办公","url":"#email","desc":"伏羲企业邮箱入口","available":False},
    {"id":"oa","name":"OA 系统","icon":"\U0001f3e2","category":"办公","url":"#oa","desc":"审批、考勤、公告","available":False},
    {"id":"nps","name":"NPS 认证","icon":"\U0001f6e1\ufe0f","category":"网络","url":"#nps","desc":"802.1X 网络准入认证","available":False},
    {"id":"fileshare","name":"文件共享","icon":"\U0001f4c1","category":"办公","url":"#fileshare","desc":"部门共享文件夹","available":False},
    {"id":"printer","name":"网络打印","icon":"\U0001f5a8\ufe0f","category":"办公","url":"#printer","desc":"打印机驱动与配置","available":False},
    {"id":"phone","name":"通讯录","icon":"\U0001f4de","category":"办公","url":"#phone","desc":"全员通讯录查询","available":False},
    {"id":"ithelp","name":"IT 工单","icon":"\U0001f3ab","category":"IT","url":"#ithelp","desc":"报修 / 账号申请","available":False},
    {"id":"wiki","name":"IT 知识库","icon":"\U0001f4da","category":"IT","url":"#wiki","desc":"拓扑图、配置手册","available":False},
    {"id":"hr","name":"人事系统","icon":"\U0001f464","category":"HR","url":"#hr","desc":"薪资查询、假期","available":False},
    {"id":"erp","name":"ERP 系统","icon":"\U0001f4ca","category":"生产","url":"#erp","desc":"采购、库存、生产","available":False},
    {"id":"monitor","name":"网络监控","icon":"\U0001f4e1","category":"网络","url":"#monitor","desc":"设备状态、流量","available":False},
]
FAQ_DATA = []

# ============ 文件白名单 ============
ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".csv", ".docx", ".doc", ".xlsx", ".xls",
    ".pdf", ".pptx", ".ppt",
    ".cfg", ".log", ".ini", ".conf", ".json", ".xml", ".html", ".htm",
    ".zip", ".wps", ".deb", ".dwg", ".dxf", ".stp", ".step", ".igs", ".iges",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg",
    ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".sh", ".bat", ".ps1",
    ".yaml", ".yml",
    ".exe", ".msi", ".apk", ".dmg", ".pkg", ".rpm", ".7z", ".rar", ".tar", ".gz",
}

# ============ 敏感信息脱敏 ============
SENSITIVE_PATTERNS: List[re.Pattern] = [
    re.compile(r"(password|passwd|pwd)\s*[:=]\s*\S+", re.I),
    re.compile(r"(secret|token|api[_-]?key)\s*[:=]\s*\S+", re.I),
    re.compile(r"\b\d{6}(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dxX]\b"),
    re.compile(r"\b1[3-9]\d{9}\b"),
]


# ── Prompt 版本管理 ──
PROMPTS = {
    "fuxi_persona": """你是伏羲，一个企业知识认知中枢。你服务于伏羲内世界的团队成员。
你的知识涵盖以下领域：
- 制造工艺、工程材料、自动化设备、工业检测标准
- 企业OA系统操作（泛微E-cology等协同办公平台）
- 项目管理、人力资源、财务管理、供应链
- 品质体系、安全环保、法律法规
- 技术文档、办公文档、标准件选型
你的回答专业、精准、有来源。不确定时会诚实说明，绝不编造。
引用格式：[来源: 文件名]（如果有的话）。""",
}
