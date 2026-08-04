import { http, HttpResponse, delay } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "../../mocks/server";
import { apiGet, apiPost } from "../client";
import { ApiError } from "../errors";

describe("统一接口客户端", () => {
  it("解析 JSON 和无响应体", async () => {
    server.use(
      http.get("http://client.test/api/v1/health", () => HttpResponse.json({ ok: true })),
      http.post("http://client.test/api/v1/examples/CASE-01/run", () => new HttpResponse(null, { status: 204 })),
    );
    await expect(apiGet("/api/v1/health", { baseUrl: "http://client.test/api/v1" })).resolves.toEqual({ ok: true });
    await expect(apiPost("/api/v1/examples/{case_id}/run", undefined, {
      baseUrl: "http://client.test/api/v1",
      pathParams: { case_id: "CASE-01" },
    })).resolves.toBeUndefined();
  });

  it.each([
    [404, "CASE_NOT_FOUND", "未找到相关记录"],
    [413, "REQUEST_TOO_LARGE", "请求内容过大"],
    [500, "INTERNAL_ERROR", "系统暂时无法处理请求"],
  ])("将 %s 错误规范化为中文", async (status, code, message) => {
    server.use(http.get("http://client.test/api/v1/health", () => HttpResponse.json({ error: { code, message: "raw", details: [], retryable: false } }, { status })));
    await expect(apiGet("/api/v1/health", { baseUrl: "http://client.test/api/v1" })).rejects.toMatchObject({ status, code, message });
  });

  it("422 字段路径映射为中文且不泄漏原路径", async () => {
    server.use(http.post("http://client.test/api/v1/competency-questions/CQ-01/execute", () => HttpResponse.json({ error: { code: "INPUT_SCHEMA_ERROR", message: "bad", details: ["body.payload.evidence.billing.outstanding_amount: invalid", "body.payload.unknown: invalid"], retryable: false } }, { status: 422 })));
    try { await apiPost("/api/v1/competency-questions/{cq_id}/execute", { case_id: "CASE-03" }, { baseUrl: "http://client.test/api/v1", pathParams: { cq_id: "CQ-01" } }); throw new Error("expected rejection"); } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).fieldErrors).toEqual(["未结费用", "未识别字段"]);
      expect((error as ApiError).message).toBe("输入数据不符合要求");
    }
  });

  it("HTML 错误页不作为 JSON 或原始信息显示", async () => {
    server.use(http.get("http://client.test/api/v1/health", () => new HttpResponse("<h1>secret traceback</h1>", { status: 500, headers: { "content-type": "text/html" } })));
    await expect(apiGet("/api/v1/health", { baseUrl: "http://client.test/api/v1" })).rejects.toMatchObject({ message: "系统暂时无法处理请求" });
  });

  it("未知错误码不回显后端原始消息", async () => {
    server.use(http.get("http://client.test/api/v1/health", () => HttpResponse.json({ error: { code: "UNKNOWN_BACKEND_ERROR", message: "Python traceback and private details", details: [], retryable: false } }, { status: 418 })));
    await expect(apiGet("/api/v1/health", { baseUrl: "http://client.test/api/v1" })).rejects.toMatchObject({
      message: "系统暂时无法处理请求",
    });
  });

  it("区分超时和离线", async () => {
    server.use(http.get("http://client.test/api/v1/health", async () => { await delay(100); return HttpResponse.json({ ok: true }); }));
    await expect(apiGet("/api/v1/health", { baseUrl: "http://client.test/api/v1", timeoutMs: 5 })).rejects.toMatchObject({ code: "TIMEOUT", message: "请求超时" });
    server.use(http.get("http://client.test/api/v1/health", () => HttpResponse.error()));
    await expect(apiGet("/api/v1/health", { baseUrl: "http://client.test/api/v1" })).rejects.toMatchObject({ code: "NETWORK_ERROR", message: "无法连接后端服务" });
  });

  it("外部 AbortSignal 可取消已卸载组件的请求", async () => {
    server.use(http.get("http://client.test/api/v1/health", async () => {
      await delay(100);
      return HttpResponse.json({ status: "ok" });
    }));
    const controller = new AbortController();
    const request = apiGet("/api/v1/health", {
      baseUrl: "http://client.test/api/v1",
      signal: controller.signal,
    });
    controller.abort();

    await expect(request).rejects.toMatchObject({
      code: "REQUEST_CANCELLED",
      message: "请求已取消",
      retryable: false,
    });
  });
});
