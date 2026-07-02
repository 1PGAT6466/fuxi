"""
H2: Query Routing 意图路由 — 根据查询类型分流到不同策略
手册 3.2.4: 语义路由，复用 LangChain Router 思路
"""
import re

# 路由规则定义
ROUTES = [
    # 规则1: 闲聊/问候 → 直回模式（不检索）
    {
        "name": "chat",
        "patterns": [
            r"^(你好|hi|hello|早上好|下午好|晚上好)",
            r"^(谢谢|感谢|thank)",
            r"^(再见|拜拜|bye)",
            r"^你是谁",
            r"^(今天|最近|昨天).*(怎么样|如何|好吗)",
        ],
        "action": "direct",    # 直接回复，不检索
        "strategy": None,
    },
    # 规则2: 网络设备查询 → 检索 + 图谱
    {
        "name": "network",
        "patterns": [
            r"(VLAN|Vlan|vlan)\s*\d+",
            r"(交换机|路由器|端口|AP|AC|网关|子网|DHCP|IP\s*地址|mac|MAC)",
            r"(LSW\d+|AR\d+|拓扑|路由表|ACL|NAT|防火墙)",
            r"(网段|子接口|trunk|access|hybrid|stp)",
            r"172\.25\.\d+",
        ],
        "action": "search",
        "strategy": {"use_graph": True, "category": "网络建设", "vector_boost": True},
    },
    # 规则3: 机械设计/标准件 → 精确检索 + 分类偏好
    {
        "name": "mechanical",
        "patterns": [
            r"(齿轮|轴承|轴|弹簧|螺栓|螺钉|螺母|键|销|联轴器)",
            r"(模数|齿数|压力角|节圆|分度圆|齿顶|齿根)",
            r"(立柱|底座|气缸|液压|伺服|电机|丝杠|导轨|滑块)",
            r"(米思米|misumi|供应商|规格|型号|尺寸|公差)",
            r"(标准件|手册|设计|机械|加工|工艺|材料)",
        ],
        "action": "search",
        "strategy": {"use_graph": False, "exact_first": True},
    },
    # 规则4: IT/软件/代码 → 精确检索
    {
        "name": "it",
        "patterns": [
            r"(代码|程序|脚本|Python|Java|SQL|API|接口|函数|类|模块)",
            r"(服务器|数据库|备份|部署|端口|服务|进程)",
            r"(软件|授权|版本|安装|配置|运维)",
            r"(bug|错误|异常|日志|监控|告警)",
        ],
        "action": "search",
        "strategy": {"use_graph": False, "category_weight": "技术文档", "exact_first": True},
    },
    # 规则5: 人事/行政/财务 → 精确检索
    {
        "name": "hr",
        "patterns": [
            r"(考勤|请假|报销|薪资|社保|公积金|合同|入职|离职)",
            r"(部门|老板|财务|行政|人事|车间|质检|生产|研发)",
            r"(会议|纪要|通知|公告|制度|流程)",
        ],
        "action": "search",
        "strategy": {"use_graph": False, "category_weight": "规章制度"},
    },
]


def route_query(query: str) -> dict:
    """路由查询 -> 返回 {action, strategy}"""
    query_stripped = query.strip()
    
    # 检查所有路由规则
    for route in ROUTES:
        for pat in route["patterns"]:
            if re.search(pat, query_stripped, re.IGNORECASE):
                return {
                    "route": route["name"],
                    "action": route["action"],
                    "strategy": route.get("strategy") or {},
                }
    
    # 默认路由: 普通知识问答
    return {
        "route": "default",
        "action": "search",
        "strategy": {"use_graph": False, "vector_boost": True},
    }


# 直接回复模板（闲聊类）
DIRECT_REPLIES = {
    "chat": "你好！我是伏羲知识库助手。你可以问我关于网络配置、机械设计、标准件规格、IT运维等任何问题。",
    "thanks": "不客气！有需要随时问我。",
    "bye": "再见！有问题随时找我。",
    "who": "我是伏羲知识库助手 v8.0，专门服务于公司的技术文档、网络配置和标准件查询。",
}
