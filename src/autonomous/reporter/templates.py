"""
报告模板 (Report Templates)
============================
日报和周报的 Markdown / HTML 模板。
支持变量替换和可扩展模板。
"""

from datetime import datetime
from typing import Any, Dict, Optional

from .aggregator import AggregatedData
from .config import TEMPLATE_VARS

# ───────────────────────────────────────────────────
# 模板注册表
# ───────────────────────────────────────────────────

_TEMPLATE_REGISTRY: Dict[str, "ReportTemplate"] = {}


def register_template(name: str, template: "ReportTemplate"):
    """注册报告模板"""
    _TEMPLATE_REGISTRY[name] = template


def get_template(name: str) -> Optional["ReportTemplate"]:
    """获取报告模板"""
    return _TEMPLATE_REGISTRY.get(name)


def list_templates() -> Dict[str, str]:
    """列出所有已注册模板"""
    return {name: tpl.description for name, tpl in _TEMPLATE_REGISTRY.items()}


# ───────────────────────────────────────────────────
# 模板基类
# ───────────────────────────────────────────────────


class ReportTemplate:
    """报告模板基类"""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description

    def render_markdown(self, data: AggregatedData) -> str:
        """渲染 Markdown 格式报告"""
        raise NotImplementedError

    def render_html(self, data: AggregatedData) -> str:
        """渲染 HTML 格式报告"""
        md = self.render_markdown(data)
        return self._markdown_to_html(md, data)

    def _render_variables(self, text: str, data: AggregatedData) -> str:
        """替换模板变量"""
        variables = {
            **TEMPLATE_VARS,
            "report_type": "日报" if data.report_type == "daily" else "周报",
            "start_time": data.start_time.strftime("%Y-%m-%d %H:%M"),
            "end_time": data.end_time.strftime("%Y-%m-%d %H:%M"),
            "generated_at": data.generated_at.strftime("%Y-%m-%d %H:%M:%S"),
            "date": data.end_time.strftime("%Y-%m-%d"),
        }
        for key, value in variables.items():
            text = text.replace(f"{{{{{key}}}}}", str(value))
        return text

    def _markdown_to_html(self, md: str, data: AggregatedData) -> str:
        """将 Markdown 转换为 HTML（轻量级实现）"""
        html = md
        # 标题
        html = html.replace("# ", "<h1>").replace("\n<h1>", "\n<h1>")
        for i in range(6, 0, -1):
            prefix = "#" * i + " "
            html = html.replace(f"\n{prefix}", f"\n<h{i}>")
        # 粗体
        import re

        html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
        # 换行
        html = html.replace("\n", "<br>\n")
        # 水平线
        html = html.replace("---", "<hr>")

        report_label = "日报" if data.report_type == "daily" else "周报"
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>伏羲·内世界 {report_label} - {data.end_time.strftime('%Y-%m-%d')}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; color: #333; line-height: 1.6; }}
        h1 {{ color: #1a1a2e; border-bottom: 2px solid #16213e; padding-bottom: 10px; }}
        h2 {{ color: #16213e; margin-top: 30px; }}
        h3 {{ color: #0f3460; }}
        table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
        th {{ background-color: #16213e; color: white; }}
        tr:nth-child(even) {{ background-color: #f5f5f5; }}
        .status-good {{ color: #27ae60; font-weight: bold; }}
        .status-warn {{ color: #f39c12; font-weight: bold; }}
        .status-bad {{ color: #e74c3c; font-weight: bold; }}
        .metric {{ background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 10px 0; }}
        .trend-up {{ color: #e74c3c; }}
        .trend-down {{ color: #27ae60; }}
        .trend-stable {{ color: #7f8c8d; }}
        hr {{ border: none; border-top: 1px solid #eee; margin: 20px 0; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; color: #999; font-size: 0.9em; }}
    </style>
</head>
<body>
{html}
<div class="footer">
    <p>由 {TEMPLATE_VARS.get('system_name', '伏羲')} {TEMPLATE_VARS.get('version', '')} 自动生成</p>
</div>
</body>
</html>"""


# ───────────────────────────────────────────────────
# 趋势辅助
# ───────────────────────────────────────────────────


def _trend_str(current: float, prev: Optional[float], unit: str = "", higher_is_bad: bool = True) -> str:
    """生成趋势描述字符串"""
    if prev is None or prev == 0:
        return ""
    change = ((current - prev) / prev) * 100
    if abs(change) < 1:
        return "（持平）"
    arrow = "↑" if change > 0 else "↓"
    if higher_is_bad:
        label = "⚠️ 恶化" if change > 0 else "✅ 改善"
    else:
        label = "✅ 提升" if change > 0 else "⚠️ 下降"
    return f"（{arrow} {abs(change):.1f}% {label}）"


def _health_status_str(ratio: float) -> str:
    """健康率文字描述"""
    if ratio >= 0.99:
        return "✅ 优秀"
    elif ratio >= 0.95:
        return "🟢 良好"
    elif ratio >= 0.90:
        return "🟡 一般"
    else:
        return "🔴 较差"


def _bar(value: float, max_val: float = 100, width: int = 20) -> str:
    """生成文本进度条"""
    filled = int(value / max_val * width) if max_val > 0 else 0
    filled = min(filled, width)
    return "█" * filled + "░" * (width - filled)


# ───────────────────────────────────────────────────
# 日报模板
# ───────────────────────────────────────────────────


class DailyReportTemplate(ReportTemplate):
    """日报模板"""

    def __init__(self):
        super().__init__("daily", "伏羲·内世界系统日报")

    def render_markdown(self, data: AggregatedData) -> str:
        d = data
        h = d.health
        r = d.requests
        e = d.errors
        res = d.resources
        k = d.knowledge
        rep = d.repairs
        a = d.alerts

        md = f"""# 📊 伏羲·内世界 系统日报

**报告周期**: {d.start_time.strftime('%Y-%m-%d %H:%M')} ~ {d.end_time.strftime('%Y-%m-%d %H:%M')}
**生成时间**: {d.generated_at.strftime('%Y-%m-%d %H:%M:%S')}

---

## 1. 系统健康

| 指标 | 数值 |
|------|------|
| 健康检查次数 | {h.total_checks} |
| 健康率 | {h.healthy_ratio*100:.1f}% {_health_status_str(h.healthy_ratio)} {_trend_str(h.healthy_ratio, d.prev_health_ratio, '%')} |
| 正常/降级/异常 | {h.healthy_count}/{h.degraded_count}/{h.unhealthy_count} |
| 平均响应时间 | {h.avg_response_time:.3f}s |

## 2. 请求统计

| 指标 | 数值 |
|------|------|
| 总请求量 | {r.total_requests} {_trend_str(r.total_requests, d.prev_request_count)} |
| 成功率 | {r.success_rate:.1f}% |
| 平均延迟 | {r.avg_latency:.3f}s |
| P95 延迟 | {r.p95_latency:.3f}s |
| P99 延迟 | {r.p99_latency:.3f}s |

## 3. 错误统计

| 指标 | 数值 |
|------|------|
| 总错误数 | {e.total_errors} {_trend_str(e.total_errors, d.prev_error_count)} |
| 趋势 | {e.error_trend} ({e.trend_change_pct:+.1f}%) |

"""
        if e.error_types:
            md += "| 错误类型 | 数量 |\n|----------|------|\n"
            for etype, count in sorted(e.error_types.items(), key=lambda x: -x[1]):
                md += f"| {etype} | {count} |\n"
            md += "\n"

        md += f"""## 4. 资源使用

| 资源 | 平均值 | 峰值 | 状态 |
|------|--------|------|------|
| CPU | {res.cpu_avg:.1f}% {_trend_str(res.cpu_avg, d.prev_cpu_avg, '%')} | {res.cpu_peak:.1f}% | {_bar(res.cpu_avg)} |
| 内存 | {res.memory_avg:.1f}% | {res.memory_peak:.1f}% | {_bar(res.memory_avg)} |
| 磁盘 | {res.disk_avg:.1f}% | {res.disk_peak:.1f}% | {_bar(res.disk_avg)} |

磁盘已用: **{res.disk_used_gb:.1f} GB**

## 5. 知识库统计

| 指标 | 数值 |
|------|------|
| 文档数 | {k.document_count} |
| 向量数 | {k.vector_count} |
| 查询次数 | {k.query_count} |
| 平均查询延迟 | {k.avg_query_latency:.3f}s |

## 6. 自修复统计

| 指标 | 数值 |
|------|------|
| 总修复次数 | {rep.total_repairs} |
| 成功/失败/回滚 | {rep.success_count}/{rep.failed_count}/{rep.rolled_back_count} |
| 成功率 | {rep.success_rate*100:.1f}% |

"""
        if rep.action_summary:
            md += "| 修复动作 | 执行次数 |\n|----------|----------|\n"
            for action, count in sorted(rep.action_summary.items(), key=lambda x: -x[1]):
                md += f"| {action} | {count} |\n"
            md += "\n"

        md += f"""## 7. 告警统计

| 级别 | 数量 |
|------|------|
| P0（紧急） | {a.p0_count} |
| P1（重要） | {a.p1_count} |
| P2（警告） | {a.p2_count} |
| P3（信息） | {a.p3_count} |
| **总计** | **{a.total_alerts}** {_trend_str(a.total_alerts, d.prev_alert_count)} |

已解决: {a.resolved_count} | 活跃: {a.active_count}

---

## 📋 总结

"""
        # 自动生成总结
        summary_items = []
        if h.healthy_ratio >= 0.99:
            summary_items.append("系统运行稳定，健康率优秀。")
        elif h.healthy_ratio >= 0.90:
            summary_items.append(f"系统基本正常，健康率 {h.healthy_ratio*100:.1f}%，需关注降级情况。")
        else:
            summary_items.append(f"⚠️ 系统健康率偏低 ({h.healthy_ratio*100:.1f}%)，需要重点关注。")

        if a.p0_count > 0:
            summary_items.append(f"🔴 发生 {a.p0_count} 次 P0 紧急告警，需立即排查。")

        if e.error_trend == "rising":
            summary_items.append(f"⚠️ 错误数量呈上升趋势 (+{e.trend_change_pct:.1f}%)。")

        if rep.total_repairs > 0 and rep.success_rate < 0.8:
            summary_items.append(f"⚠️ 自修复成功率偏低 ({rep.success_rate*100:.1f}%)，需检查修复动作。")

        if not summary_items:
            summary_items.append("系统运行正常，各项指标均在预期范围内。")

        for item in summary_items:
            md += f"- {item}\n"

        md += f"\n---\n*报告由 {TEMPLATE_VARS.get('system_name', '伏羲')} 自动生成*\n"
        return md


# ───────────────────────────────────────────────────
# 周报模板
# ───────────────────────────────────────────────────


class WeeklyReportTemplate(ReportTemplate):
    """周报模板"""

    def __init__(self):
        super().__init__("weekly", "伏羲·内世界系统周报")

    def render_markdown(self, data: AggregatedData) -> str:
        d = data
        h = d.health
        r = d.requests
        e = d.errors
        res = d.resources
        k = d.knowledge
        rep = d.repairs
        a = d.alerts

        md = f"""# 📊 伏羲·内世界 系统周报

**报告周期**: {d.start_time.strftime('%Y-%m-%d')} ~ {d.end_time.strftime('%Y-%m-%d')}（共 {(d.end_time - d.start_time).days} 天）
**生成时间**: {d.generated_at.strftime('%Y-%m-%d %H:%M:%S')}

---

## 📈 本周概览

| 维度 | 关键指标 | 状态 |
|------|----------|------|
| 系统健康 | 健康率 {h.healthy_ratio*100:.1f}% | {_health_status_str(h.healthy_ratio)} |
| 请求处理 | {r.total_requests} 次请求 | 成功率 {r.success_rate:.1f}% |
| 错误情况 | {e.total_errors} 个错误 | 趋势: {e.error_trend} |
| 资源使用 | CPU {res.cpu_avg:.1f}% / 内存 {res.memory_avg:.1f}% | {'正常' if res.cpu_avg < 80 else '偏高'} |
| 自修复 | {rep.total_repairs} 次修复 | 成功率 {rep.success_rate*100:.1f}% |
| 告警 | {a.total_alerts} 次告警 | P0: {a.p0_count}, P1: {a.p1_count} |

---

## 1. 系统健康详情

| 指标 | 本周数值 | 对比上周 |
|------|----------|----------|
| 健康检查次数 | {h.total_checks} | — |
| 健康率 | {h.healthy_ratio*100:.1f}% | {_trend_str(h.healthy_ratio, d.prev_health_ratio, '%')} |
| 正常/降级/异常 | {h.healthy_count}/{h.degraded_count}/{h.unhealthy_count} | — |
| 平均响应时间 | {h.avg_response_time:.3f}s | — |

## 2. 请求统计详情

| 指标 | 本周数值 | 对比上周 |
|------|----------|----------|
| 总请求量 | {r.total_requests} | {_trend_str(r.total_requests, d.prev_request_count)} |
| 日均请求 | {r.total_requests // 7} | — |
| 成功率 | {r.success_rate:.1f}% | — |
| 平均延迟 | {r.avg_latency:.3f}s | — |
| P95 延迟 | {r.p95_latency:.3f}s | — |
| P99 延迟 | {r.p99_latency:.3f}s | — |

## 3. 错误统计详情

| 指标 | 本周数值 | 对比上周 |
|------|----------|----------|
| 总错误数 | {e.total_errors} | {_trend_str(e.total_errors, d.prev_error_count)} |
| 日均错误 | {e.total_errors // 7} | — |
| 趋势 | {e.error_trend} ({e.trend_change_pct:+.1f}%) | — |

"""
        if e.error_types:
            md += "**错误类型分布**:\n\n"
            md += "| 错误类型 | 数量 | 占比 |\n|----------|------|------|\n"
            for etype, count in sorted(e.error_types.items(), key=lambda x: -x[1]):
                pct = count / e.total_errors * 100 if e.total_errors > 0 else 0
                md += f"| {etype} | {count} | {pct:.1f}% |\n"
            md += "\n"

        md += f"""## 4. 资源使用详情

| 资源 | 平均值 | 峰值 | 对比上周 |
|------|--------|------|----------|
| CPU | {res.cpu_avg:.1f}% | {res.cpu_peak:.1f}% | {_trend_str(res.cpu_avg, d.prev_cpu_avg, '%')} |
| 内存 | {res.memory_avg:.1f}% | {res.memory_peak:.1f}% | — |
| 磁盘 | {res.disk_avg:.1f}% | {res.disk_peak:.1f}% | — |

磁盘已用: **{res.disk_used_gb:.1f} GB**

## 5. 知识库统计详情

| 指标 | 数值 |
|------|------|
| 文档数 | {k.document_count} |
| 向量数 | {k.vector_count} |
| 查询次数 | {k.query_count} |
| 日均查询 | {k.query_count // 7} |
| 平均查询延迟 | {k.avg_query_latency:.3f}s |

## 6. 自修复统计详情

| 指标 | 数值 |
|------|------|
| 总修复次数 | {rep.total_repairs} |
| 成功 | {rep.success_count} |
| 失败 | {rep.failed_count} |
| 回滚 | {rep.rolled_back_count} |
| 成功率 | {rep.success_rate*100:.1f}% |

"""
        if rep.action_summary:
            md += "**修复动作分布**:\n\n"
            md += "| 修复动作 | 执行次数 |\n|----------|----------|\n"
            for action, count in sorted(rep.action_summary.items(), key=lambda x: -x[1]):
                md += f"| {action} | {count} |\n"
            md += "\n"

        md += f"""## 7. 告警统计详情

| 级别 | 数量 | 对比上周 |
|------|------|----------|
| P0（紧急） | {a.p0_count} | — |
| P1（重要） | {a.p1_count} | — |
| P2（警告） | {a.p2_count} | — |
| P3（信息） | {a.p3_count} | — |
| **总计** | **{a.total_alerts}** | {_trend_str(a.total_alerts, d.prev_alert_count)} |

已解决: {a.resolved_count} | 活跃: {a.active_count}

---

## 📋 本周总结

"""
        summary_items = []

        # 健康总结
        if h.healthy_ratio >= 0.99:
            summary_items.append("🟢 **系统健康**: 本周运行极为稳定，健康率接近 100%。")
        elif h.healthy_ratio >= 0.95:
            summary_items.append(f"🟢 **系统健康**: 本周整体良好，健康率 {h.healthy_ratio*100:.1f}%。")
        elif h.healthy_ratio >= 0.90:
            summary_items.append(f"🟡 **系统健康**: 健康率 {h.healthy_ratio*100:.1f}%，存在降级情况，建议排查。")
        else:
            summary_items.append(f"🔴 **系统健康**: 健康率仅 {h.healthy_ratio*100:.1f}%，需重点关注！")

        # 请求总结
        summary_items.append(f"📊 **请求处理**: 本周共处理 {r.total_requests} 次请求，成功率 {r.success_rate:.1f}%。")

        # 错误总结
        if e.error_trend == "rising":
            summary_items.append(f"⚠️ **错误趋势**: 错误数量呈上升趋势 (+{e.trend_change_pct:.1f}%)，建议排查根因。")
        elif e.error_trend == "falling":
            summary_items.append(f"✅ **错误趋势**: 错误数量呈下降趋势 ({e.trend_change_pct:.1f}%)，持续改善中。")
        else:
            summary_items.append(f"📊 **错误趋势**: 错误数量基本稳定，共 {e.total_errors} 个。")

        # 告警总结
        if a.p0_count > 0:
            summary_items.append(f"🔴 **告警**: 发生 {a.p0_count} 次 P0 紧急告警，需复盘处理流程。")
        elif a.total_alerts > 0:
            summary_items.append(f"📊 **告警**: 本周共 {a.total_alerts} 次告警，已解决 {a.resolved_count} 次。")
        else:
            summary_items.append("✅ **告警**: 本周零告警，运行平稳。")

        # 自修复总结
        if rep.total_repairs > 0:
            summary_items.append(
                f"🔧 **自修复**: 本周执行 {rep.total_repairs} 次自动修复，成功率 {rep.success_rate*100:.1f}%。"
            )

        for item in summary_items:
            md += f"- {item}\n"

        md += f"\n---\n*报告由 {TEMPLATE_VARS.get('system_name', '伏羲')} 自动生成*\n"
        return md


# ───────────────────────────────────────────────────
# 注册默认模板
# ───────────────────────────────────────────────────

register_template("daily", DailyReportTemplate())
register_template("weekly", WeeklyReportTemplate())
