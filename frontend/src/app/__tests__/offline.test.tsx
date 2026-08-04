import { waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "../../mocks/server";
import { renderApp } from "../../test/renderWithProviders";

describe("离线与接口错误状态", () => {
  it("health 不可用时显示非阻断中文离线提示，不回退到 mock", async () => {
    server.use(
      http.get("*/api/v1/health", () =>
        HttpResponse.json(
          { error: { code: "SERVICE_UNAVAILABLE", message: "offline", details: [], retryable: true } },
          { status: 503 },
        ),
      ),
    );
    const { container } = renderApp("/overview");
    await waitFor(() =>
      expect(container.textContent).toContain("后端服务暂时不可用，部分功能无法使用。"),
    );
    expect(container.textContent).not.toContain("模拟");
  });
});
