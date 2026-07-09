"""
ontology.py — 伏羲领域本体定义（v13.0）
本体 = 骨架，定义知识的组织规则和语义模型
知识图谱 = 血肉，记录具体实体和关系事实
"""

# ============================================================
# 一、实体类型定义（类/概念）
# ============================================================
ENTITY_TYPES = {
    # --- 硬件设备 ---
    "network_device": {
        "label": "网络设备",
        "subtype": ["交换机", "路由器", "AP", "AC", "防火墙"],
        "attributes": ["型号", "IP", "端口数", "固件版本", "机柜位置"],
    },
    "server": {
        "label": "服务器",
        "subtype": ["物理服务器", "虚拟机", "容器"],
        "attributes": ["主机名", "IP", "OS", "CPU", "内存", "磁盘"],
    },
    "pc_client": {
        "label": "PC/终端",
        "subtype": ["PC", "笔记本", "工控机"],
        "attributes": ["主机名", "IP", "MAC", "部门", "使用者"],
    },
    # --- 工业设备 ---
    "machine_tool": {
        "label": "加工设备",
        "subtype": ["注塑机", "CNC", "线切割", "电火花", "磨床"],
        "attributes": ["型号", "品牌", "精度", "行程"],
    },
    "measuring_device": {
        "label": "测量设备",
        "subtype": ["三坐标", "投影仪", "显微镜", "高度规"],
        "attributes": ["型号", "品牌", "精度", "量程"],
    },
    "sensor": {
        "label": "传感器",
        "subtype": ["光电", "接近", "压力", "温度", "位移"],
        "attributes": ["型号", "品牌", "检测距离", "输出方式(NPN/PNP)"],
    },
    "actuator": {
        "label": "执行器",
        "subtype": ["气缸", "电磁阀", "伺服电机", "步进电机", "变频器"],
        "attributes": ["型号", "品牌", "行程/功率", "控制方式"],
    },
    "plc": {
        "label": "PLC/控制器",
        "subtype": ["S7-1200", "S7-1500", "FX5U", "CP1H"],
        "attributes": ["型号", "品牌", "IO点数", "通讯协议"],
    },
    # --- 模具/机械 ---
    "mold": {
        "label": "模具",
        "subtype": ["注塑模", "冲压模", "压铸模"],
        "attributes": ["编号", "型腔数", "材料", "标准件"],
    },
    "standard_part": {
        "label": "标准件",
        "subtype": ["导柱", "导套", "顶针", "滑块", "浇口套", "线轨", "丝杆"],
        "attributes": ["型号", "规格", "供应商"],
    },
    "material": {
        "label": "材料",
        "subtype": ["模具钢", "工程塑料", "金属料"],
        "attributes": ["牌号", "硬度", "供应商", "MSDS"],
    },
    # --- 软件 ---
    "software": {
        "label": "软件",
        "subtype": ["操作系统", "设计软件", "测量软件", "办公软件"],
        "attributes": ["名称", "版本", "授权数", "供应商"],
    },
    "firmware": {
        "label": "固件/配置文件",
        "subtype": ["设备配置", "PLC程序", "HMI工程"],
        "attributes": ["文件名", "关联设备", "版本"],
    },
    # --- 文档 ---
    "operation_manual": {
        "label": "使用手册",
        "subtype": ["OA系统", "ERP系统", "设计软件", "设备操作", "测量软件"],
        "attributes": ["系统名称", "版本号", "功能模块", "适用范围"],
    },

    "document": {
        "label": "文档",
        "subtype": ["SOP", "技术规范", "图纸", "合同", "制度"],
        "attributes": ["文号", "版本", "作者", "审核状态"],
    },
    "project": {
        "label": "项目",
        "subtype": ["产线建设", "IT建设", "新品开发"],
        "attributes": ["编号", "名称", "周期", "预算", "状态"],
    },
    # --- 组织 ---
    "department": {
        "label": "部门",
        "attributes": ["名称", "负责人", "人数", "职责"],
    },
    "supplier": {
        "label": "供应商",
        "attributes": ["名称", "类型", "评级", "联系人"],
    },
    "person": {
        "label": "人员",
        "attributes": ["姓名", "部门", "岗位", "技能"],
    },
    # --- 网络 ---
    "vlan": {
        "label": "VLAN",
        "attributes": ["ID", "名称", "网段", "网关"],
    },
    "subnet": {
        "label": "子网",
        "attributes": ["网段", "掩码", "网关", "DHCP范围"],
    },
}

# ============================================================
# 二、关系类型定义（语义约束）
# ============================================================
RELATION_TYPES = {
    "connects_to": {
        "label": "连接",
        "domain": ["network_device", "server", "pc_client", "plc", "sensor"],
        "range": ["network_device", "server", "pc_client", "plc", "sensor"],
        "description": "设备之间的物理/网络连接",
    },
    "belongs_to": {
        "label": "归属",
        "domain": ["pc_client", "server", "firmware", "document", "person"],
        "range": ["department", "project", "vlan", "subnet"],
        "description": "实体归属于某个组织/网络/项目",
    },
    "installed_on": {
        "label": "安装于",
        "domain": ["software", "firmware"],
        "range": ["server", "pc_client", "network_device", "plc", "machine_tool"],
        "description": "软件/固件安装在设备上",
    },
    "supplied_by": {
        "label": "供应商",
        "domain": ["standard_part", "material", "sensor", "actuator", "machine_tool", "measuring_device", "software"],
        "range": ["supplier"],
        "description": "从供应商采购",
    },
    "part_of": {
        "label": "组成部分",
        "domain": ["standard_part", "sensor", "actuator"],
        "range": ["mold", "machine_tool"],
        "description": "标准件是模具/设备的一部分",
    },
    "measured_by": {
        "label": "测量",
        "domain": ["standard_part", "material", "mold"],
        "range": ["measuring_device"],
        "description": "用测量设备检测",
    },
    "controlled_by": {
        "label": "控制",
        "domain": ["sensor", "actuator", "machine_tool"],
        "range": ["plc"],
        "description": "传感器/执行器由 PLC 控制",
    },
    "authored_by": {
        "label": "作者",
        "domain": ["document", "firmware"],
        "range": ["person"],
        "description": "文档/配置的创建者",
    },
    "guides_user_on": {
        "label": "操作指引",
        "domain": ["operation_manual"],
        "range": ["software", "measuring_device", "machine_tool"],
        "description": "使用手册指导用户在特定系统/设备上的操作",
    },

    "mentions": {
        "label": "提及",
        "domain": ["document"],
        "range": [],  # 任何类型
        "description": "文档中提到某个实体",
    },
    "related_to": {
        "label": "关联",
        "domain": [], "range": [],
        "description": "通用关联（未明确分类时使用）",
    },
}

# ============================================================
# 三、属性约束（数据类型）
# ============================================================
PROPERTY_TYPES = {
    "ip": r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$',
    "mac": r'^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$',
    "vlan_id": r'^\d{1,4}$',
    "cidr": r'^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$',
    "phone": r'^\d{11}$',
    "email": r'^[\w\.-]+@[\w\.-]+\.\w+$',
}

# ============================================================
# 四、实体别名与合并规则（同义实体归一化）
# ============================================================
SYNONYMS = {
    "LSW1": ["lsw1", "核心交换机", "Core-Switch", "核心"],
    "AR1": ["ar1", "出口路由器", "Router-1", "路由器"],
    "三坐标": ["CMM", "坐标测量机", "蔡司CONTURA", "蔡司"],
    "PLC": ["可编程控制器", "可编程逻辑控制器"],
}


def get_entity_type(name: str, text_context: str = "") -> str:
    """根据实体名+上下文推断实体类型"""
    import re
    name_upper = name.upper()
    # 网络设备
    if re.match(r'^(LSW|AR|AP|AC|FW)\d+', name_upper):
        return "network_device"
    if re.search(r'(交换机|路由器|AP|AC|防火墙)', name):
        return "network_device"
    # 设备型号
    if re.match(r'^[A-Z]{2,4}[\-]?\d{2,4}', name) and not any(k in name for k in ["LSW","AR","AC","AP"]):
        if any(k in text_context.lower() for k in ["传感器","sensor","光电","接近"]):
            return "sensor"
        if any(k in text_context.lower() for k in ["气缸","电磁阀","伺服","变频"]):
            return "actuator"
        return "standard_part"
    # 材料
    if re.match(r'^(SUJ2|SKD|S136|DC53|NAK80|718H|P20|H13|LCP|PA66|PBT|POM|PPS|PA6|PA12|ABS|PC|PP|PE|PEEK)$', name_upper):
        return "material"
    # 供应商
    for s in ["米思米","盘起","天田","恒钢","翁开尔","住友","蔡司","西门子","欧姆龙","三菱","基恩士","SMC","FESTO"]:
        if s in name:
            return "supplier"
    # VLAN/IP
    if re.match(r'^VLAN\s*\d+$', name_upper):
        return "vlan"
    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(/\d{2})?$', name):
        return "subnet"
    # 使用手册
    if any(k in text_context.lower() for k in ["使用手册", "操作指南", "用户手册", "泛微", "ecology"]):
        return "operation_manual"
    return "unknown"
