"""
config_validation.py — 配置验证
启动时验证配置
"""
import os
import logging
from typing import Dict

logger = logging.getLogger("infra.config_validation")


class ConfigValidator:
    """配置验证器"""

    def __init__(self):
        self._errors = []
        self._warnings = []

    def validate(self) -> Dict:
        """验证配置"""
        self._errors = []
        self._warnings = []

        # 检查必需的环境变量
        self._check_required_env_vars()

        # 检查数据库路径
        self._check_database_paths()

        # 检查LLM配置
        self._check_llm_config()

        return {
            "valid": len(self._errors) == 0,
            "errors": self._errors,
            "warnings": self._warnings,
        }

    def _check_required_env_vars(self):
        """检查必需的环境变量"""
        required = ["MIMO_API_KEY"]
        for var in required:
            if not os.getenv(var):
                self._warnings.append(f"环境变量 {var} 未设置")

    def _check_database_paths(self):
        """检查数据库路径"""
        from src.config import DB_PATH
        db_dir = os.path.dirname(DB_PATH)
        if not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
            except Exception as e:  # TODO: Narrow exception type
                self._errors.append(f"无法创建数据库目录: {e}")

    def _check_llm_config(self):
        """检查LLM配置"""
        from src.config import MIMO_API_KEY, MIMO_BASE_URL
        if not MIMO_API_KEY:
            self._warnings.append("MIMO_API_KEY 未设置，LLM功能将不可用")
        if not MIMO_BASE_URL:
            self._warnings.append("MIMO_BASE_URL 未设置")


# 全局配置验证器
_config_validator: ConfigValidator = None


def get_config_validator() -> ConfigValidator:
    """获取全局配置验证器"""
    global _config_validator
    if _config_validator is None:
        _config_validator = ConfigValidator()
    return _config_validator
