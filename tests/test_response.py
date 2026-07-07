"""
Tests for src.api.response — Unified API Response Format v1.50
"""
import json
import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from src.api.response import (
    success, error, paginated,
    ok, not_found, unauthorized, forbidden, bad_request, server_error,
    backward_compatible,
    STATUS_SUCCESS, STATUS_ERROR,
)


class TestSuccessResponse:
    def test_basic_success(self):
        r = success({"name": "伏羲"})
        body = json.loads(r.body)
        assert body["status"] == STATUS_SUCCESS
        assert body["message"] == "ok"
        assert body["data"] == {"name": "伏羲"}
        assert r.status_code == 200

    def test_success_with_message(self):
        r = success(None, message="操作成功", status_code=201)
        body = json.loads(r.body)
        assert body["message"] == "操作成功"
        assert body["data"] is None
        assert r.status_code == 201

    def test_success_with_extra(self):
        r = success({"id": 1}, extra={"trace_id": "abc123"})
        body = json.loads(r.body)
        assert body["trace_id"] == "abc123"
        assert body["data"] == {"id": 1}

    def test_success_extra_does_not_overwrite_core(self):
        r = success({"x": 1}, extra={"status": "hacked"})
        body = json.loads(r.body)
        # extra should not overwrite status
        assert body["status"] == STATUS_SUCCESS


class TestErrorResponse:
    def test_basic_error(self):
        r = error("参数错误")
        body = json.loads(r.body)
        assert body["status"] == STATUS_ERROR
        assert body["message"] == "参数错误"
        assert "detail" not in body
        assert r.status_code == 400

    def test_error_with_detail(self):
        r = error("认证失败", status_code=401, detail="token has expired")
        body = json.loads(r.body)
        assert body["status"] == STATUS_ERROR
        assert body["message"] == "认证失败"
        assert body["detail"] == "token has expired"
        assert r.status_code == 401

    def test_error_with_data(self):
        r = error("验证失败", status_code=422, data={"fields": ["email"]})
        body = json.loads(r.body)
        assert body["data"] == {"fields": ["email"]}

    def test_error_with_extra(self):
        r = error("服务器错误", status_code=500, extra={"request_id": "req-1"})
        body = json.loads(r.body)
        assert body["request_id"] == "req-1"


class TestPaginatedResponse:
    def test_basic_paginated(self):
        items = [{"id": i} for i in range(3)]
        r = paginated(items=items, total=95, page=2, page_size=20)
        body = json.loads(r.body)
        assert body["status"] == STATUS_SUCCESS
        assert body["data"]["items"] == items
        assert body["data"]["total"] == 95
        assert body["data"]["page"] == 2
        assert body["data"]["page_size"] == 20
        assert body["data"]["total_pages"] == 5  # ceil(95/20)

    def test_paginated_single_page(self):
        r = paginated(items=[], total=0, page=1, page_size=20)
        body = json.loads(r.body)
        assert body["data"]["total_pages"] == 1

    def test_paginated_large_total(self):
        r = paginated(items=[], total=1000, page=1, page_size=50)
        body = json.loads(r.body)
        assert body["data"]["total_pages"] == 20

    def test_paginated_zero_page_size(self):
        r = paginated(items=[], total=10, page=1, page_size=0)
        body = json.loads(r.body)
        assert body["data"]["total_pages"] == 1  # safe fallback

    def test_paginated_with_extra(self):
        r = paginated(items=[], total=10, page=1, page_size=10, extra={"filters": {"status": "active"}})
        body = json.loads(r.body)
        assert body["filters"] == {"status": "active"}


class TestConvenienceAliases:
    def test_ok_alias(self):
        r = ok({"hello": "world"})
        body = json.loads(r.body)
        assert body["status"] == STATUS_SUCCESS
        assert body["data"] == {"hello": "world"}

    def test_not_found(self):
        r = not_found()
        assert r.status_code == 404
        body = json.loads(r.body)
        assert body["status"] == STATUS_ERROR

    def test_unauthorized(self):
        r = unauthorized(detail="token expired")
        assert r.status_code == 401

    def test_forbidden(self):
        r = forbidden()
        assert r.status_code == 403

    def test_bad_request(self):
        r = bad_request(detail="missing field")
        assert r.status_code == 400

    def test_server_error(self):
        r = server_error()
        assert r.status_code == 500


class TestBackwardCompatible:
    @pytest.mark.asyncio
    async def test_v1_no_wrapping(self):
        mock_req = MagicMock(spec=Request)
        mock_req.query_params.get.return_value = None
        mock_req.headers.get.return_value = ""

        @backward_compatible()
        async def my_api(request: Request):
            return {"results": [1, 2], "total": 2}

        result = await my_api(mock_req)
        assert result == {"results": [1, 2], "total": 2}

    @pytest.mark.asyncio
    async def test_v2_query_param(self):
        mock_req = MagicMock(spec=Request)
        mock_req.query_params.get.return_value = "v2"
        mock_req.headers.get.return_value = ""

        @backward_compatible()
        async def my_api(request: Request):
            return {"results": [1, 2], "total": 2}

        result = await my_api(mock_req)
        body = json.loads(result.body)
        assert body["status"] == STATUS_SUCCESS
        assert body["data"] == {"results": [1, 2], "total": 2}

    @pytest.mark.asyncio
    async def test_v2_header(self):
        mock_req = MagicMock(spec=Request)
        mock_req.query_params.get.return_value = None
        mock_req.headers.get.return_value = "v2"

        @backward_compatible()
        async def my_api(request: Request):
            return {"results": []}

        result = await my_api(mock_req)
        body = json.loads(result.body)
        assert body["status"] == STATUS_SUCCESS

    @pytest.mark.asyncio
    async def test_jsonresponse_pass_through(self):
        mock_req = MagicMock(spec=Request)
        mock_req.query_params.get.return_value = "v2"
        mock_req.headers.get.return_value = ""

        @backward_compatible()
        async def my_api(request: Request):
            return success({"x": 1})

        result = await my_api(mock_req)
        body = json.loads(result.body)
        assert body["data"] == {"x": 1}

    @pytest.mark.asyncio
    async def test_no_request_present(self):
        @backward_compatible()
        async def my_api():
            return {"hello": "world"}

        result = await my_api()
        assert result == {"hello": "world"}


class TestIntegrationWithFastAPI:
    """Test that response utilities work correctly with FastAPI TestClient"""

    def test_success_integration(self):
        from fastapi import FastAPI
        app = FastAPI()

        @app.get("/api/test-success")
        async def test_success():
            return success({"name": "伏羲"}, message="测试成功")

        client = TestClient(app)
        resp = client.get("/api/test-success")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["data"]["name"] == "伏羲"

    def test_error_integration(self):
        from fastapi import FastAPI
        app = FastAPI()

        @app.get("/api/test-error")
        async def test_error():
            return error("未找到", status_code=404, detail="ID=999 不存在")

        client = TestClient(app)
        resp = client.get("/api/test-error")
        assert resp.status_code == 404
        body = resp.json()
        assert body["status"] == "error"
        assert body["message"] == "未找到"

    def test_backward_compat_integration(self):
        from fastapi import FastAPI
        app = FastAPI()

        @app.get("/api/test-legacy")
        async def test_legacy(request: Request):
            _wants_v2 = request.query_params.get("format") == "v2"
            if _wants_v2:
                return success(data={"items": [1, 2, 3]})
            return {"items": [1, 2, 3]}

        client = TestClient(app)

        # v1 format (default)
        resp = client.get("/api/test-legacy")
        assert resp.json() == {"items": [1, 2, 3]}

        # v2 format
        resp = client.get("/api/test-legacy?format=v2")
        body = resp.json()
        assert body["status"] == "success"
        assert body["data"]["items"] == [1, 2, 3]
