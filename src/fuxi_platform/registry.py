"""
registry.py — 服务注册中心
管理服务生命周期：注册、启动、停止、健康检查
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("platform.registry")


class ServiceStatus(str, Enum):
    UNKNOWN = "unknown"
    REGISTERED = "registered"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ServiceInfo:
    id: str
    name: str
    version: str = "0.0.0"
    description: str = ""
    service_type: str = "generic"
    status: ServiceStatus = ServiceStatus.UNKNOWN
    api_prefix: str = ""
    health_endpoint: str = ""
    capabilities: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    registered_at: float = field(default_factory=time.time)
    last_health_check: float = 0.0
    error_message: str = ""


class ServiceRegistry:
    def __init__(self, services_dir: Optional[str] = None):
        self._services: Dict[str, ServiceInfo] = {}
        self._instances: Dict[str, Any] = {}
        self._services_dir = Path(services_dir) if services_dir else None
        self._health_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        self._running = True
        if self._services_dir and self._services_dir.exists():
            await self._discover_services()
        self._health_task = asyncio.create_task(self._health_check_loop())
        logger.info("Service registry started")

    async def stop(self) -> None:
        self._running = False
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
        for service_id in list(self._services.keys()):
            await self.stop_service(service_id)
        logger.info("Service registry stopped")

    def register_service(self, service_dir: str) -> Optional[ServiceInfo]:
        svc_path = Path(service_dir)
        manifest = svc_path / "service.json"
        if not manifest.exists():
            logger.warning(f"No service.json in {service_dir}")
            return None

        import json
        data = json.loads(manifest.read_text(encoding="utf-8"))
        info = ServiceInfo(
            id=data.get("id", svc_path.name),
            name=data.get("name", svc_path.name),
            version=data.get("version", "0.0.0"),
            description=data.get("description", ""),
            service_type=data.get("service_type", "generic"),
            api_prefix=data.get("api_prefix", ""),
            health_endpoint=data.get("health_endpoint", ""),
            capabilities=data.get("capabilities", []),
            config=data.get("config", {}),
            status=ServiceStatus.REGISTERED,
        )
        self._services[info.id] = info
        logger.info(f"Registered service: {info.id} ({info.name})")
        return info

    async def start_service(self, service_id: str) -> bool:
        info = self._services.get(service_id)
        if not info:
            logger.error(f"Service not found: {service_id}")
            return False

        info.status = ServiceStatus.STARTING
        try:
            mod_path = f"src.services.{service_id}"
            import importlib
            mod = importlib.import_module(mod_path)
            if hasattr(mod, "create_service"):
                instance = mod.create_service(info.config)
                if hasattr(instance, "start"):
                    await instance.start()
                self._instances[service_id] = instance
            info.status = ServiceStatus.RUNNING
            info.last_health_check = time.time()
            logger.info(f"Service started: {service_id}")
            return True
        except Exception as e:  # TODO: Narrow exception type
            info.status = ServiceStatus.ERROR
            info.error_message = str(e)
            logger.error(f"Failed to start service {service_id}: {e}")
            return False

    async def stop_service(self, service_id: str) -> bool:
        info = self._services.get(service_id)
        if not info:
            return False

        info.status = ServiceStatus.STOPPING
        try:
            instance = self._instances.pop(service_id, None)
            if instance and hasattr(instance, "stop"):
                await instance.stop()
            info.status = ServiceStatus.STOPPED
            logger.info(f"Service stopped: {service_id}")
            return True
        except Exception as e:  # TODO: Narrow exception type
            info.status = ServiceStatus.ERROR
            info.error_message = str(e)
            logger.error(f"Failed to stop service {service_id}: {e}")
            return False

    def get_service(self, service_id: str) -> Optional[ServiceInfo]:
        return self._services.get(service_id)

    def list_services(
        self,
        service_type: Optional[str] = None,
        status: Optional[ServiceStatus] = None,
    ) -> List[ServiceInfo]:
        result = list(self._services.values())
        if service_type:
            result = [s for s in result if s.service_type == service_type]
        if status:
            result = [s for s in result if s.status == status]
        return result

    async def _discover_services(self) -> None:
        if not self._services_dir:
            return
        for child in sorted(self._services_dir.iterdir()):
            if child.is_dir() and (child / "service.json").exists():
                await self.register_service(str(child))

    async def _health_check_loop(self) -> None:
        while self._running:
            try:
                for sid, info in list(self._services.items()):
                    if info.status != ServiceStatus.RUNNING:
                        continue
                    try:
                        from src.core.http_client import get_http_session
                        url = f"http://localhost{info.api_prefix}{info.health_endpoint}"
                        session = await get_http_session()
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                            if resp.status == 200:
                                info.last_health_check = time.time()
                                info.error_message = ""
                            else:
                                info.error_message = f"HTTP {resp.status}"
                    except Exception as e:  # TODO: Narrow exception type
                        info.error_message = str(e)
            except Exception as e:  # TODO: Narrow exception type
                logger.error(f"Health check loop error: {e}")
            await asyncio.sleep(30)


_registry: Optional[ServiceRegistry] = None


def get_registry(services_dir: Optional[str] = None) -> ServiceRegistry:
    global _registry
    if _registry is None:
        _registry = ServiceRegistry(services_dir)
    return _registry
