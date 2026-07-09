"""
gateway.py — API 网关
将请求路由到已注册的服务
"""
import logging
from fastapi import APIRouter, HTTPException

from .registry import ServiceRegistry

logger = logging.getLogger("platform.gateway")


class ServiceGateway:
    def __init__(self, registry: ServiceRegistry):
        self._registry = registry
        self.router = APIRouter(prefix="/api/services", tags=["platform"])
        self._register_routes()

    def _register_routes(self) -> None:
        @self.router.get("/")
        def list_services():
            services = self._registry.list_services()
            return [
                {
                    "id": s.id,
                    "name": s.name,
                    "version": s.version,
                    "status": s.status.value,
                    "service_type": s.service_type,
                    "api_prefix": s.api_prefix,
                }
                for s in services
            ]

        @self.router.get("/{service_id}")
        def get_service(service_id: str):
            info = self._registry.get_service(service_id)
            if not info:
                raise HTTPException(404, f"Service not found: {service_id}")
            return {
                "id": info.id,
                "name": info.name,
                "version": info.version,
                "description": info.description,
                "service_type": info.service_type,
                "status": info.status.value,
                "api_prefix": info.api_prefix,
                "capabilities": info.capabilities,
                "registered_at": info.registered_at,
                "last_health_check": info.last_health_check,
                "error_message": info.error_message,
            }

        @self.router.post("/{service_id}/start")
        async def start_service(service_id: str):
            info = self._registry.get_service(service_id)
            if not info:
                raise HTTPException(404, f"Service not found: {service_id}")
            ok = await self._registry.start_service(service_id)
            return {"ok": ok, "service_id": service_id, "status": info.status.value}

        @self.router.post("/{service_id}/stop")
        async def stop_service(service_id: str):
            info = self._registry.get_service(service_id)
            if not info:
                raise HTTPException(404, f"Service not found: {service_id}")
            ok = await self._registry.stop_service(service_id)
            return {"ok": ok, "service_id": service_id, "status": info.status.value}

        @self.router.get("/{service_id}/health")
        def health_check(service_id: str):
            info = self._registry.get_service(service_id)
            if not info:
                raise HTTPException(404, f"Service not found: {service_id}")
            return {
                "service_id": service_id,
                "status": info.status.value,
                "last_health_check": info.last_health_check,
                "error_message": info.error_message,
            }


def get_gateway(registry: ServiceRegistry) -> ServiceGateway:
    return ServiceGateway(registry)
