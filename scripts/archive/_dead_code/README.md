# Dead Code Archive — v1.50 Cleanup

这些文件于 v1.50 死代码清理任务（2026-07-06）中从仓库根目录移除。

所有 9 个文件在代码库中均未被任何 `import` 或 `from ... import` 语句引用（注：文档 `docs/audit_round3_code_quality.md` 和 `docs/audit_round3_data.json` 中的引用是元数据，不计入代码引用）。

## 归档文件列表

| # | 文件名 | 用途 |
|---|-------|------|
| 1 | `fix_exception_swallow.py` | 异常吞没修复工具 |
| 2 | `migration_map.py` | 迁移映射脚本 |
| 3 | `_fixer.py` | 代码修复工具 |
| 4 | `_fix_missing_as_e.py` | 补充缺少 `as e` 的 except 语句 |
| 5 | `_scan_all.py` | 全维度扫描脚本 |
| 6 | `_scan_except_pass.py` | 扫描 except...pass |
| 7 | `_scan_except_pass2.py` | 扫描 except...pass（第二版） |
| 8 | `_scan_fake_async.py` | 扫描伪异步函数 |
| 9 | `_scan_return_none.py` | 扫描 except 中 return None |

如果在未来版本中需要运行类似的代码质量扫描，可以从此目录恢复这些脚本。
