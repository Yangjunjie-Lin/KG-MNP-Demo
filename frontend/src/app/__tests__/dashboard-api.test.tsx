import { waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { dashboardFixture } from "../../mocks/fixtures/api";
import { server } from "../../mocks/server";
import { renderApp } from "../../test/renderWithProviders";

describe("Dashboard API 集成", () => {
  it("从真实 dashboard/cases HTTP 响应显示统计与九个案例", async () => {
    let dashboardCalls = 0;
    server.use(
      http.get("*/api/v1/views/dashboard", () => {
        dashboardCalls += 1;
        return HttpResponse.json(dashboardFixture);
      }),
    );
    const { container } = renderApp("/overview");
    await waitFor(() => expect(container.textContent).toContain("真实数据统计"));
    expect(container.textContent).toContain("61");
    expect(container.textContent).toContain("案例九");
    expect(dashboardCalls).toBeGreaterThan(0);
    expect(container.textContent).not.toContain("CASE-09");
  });
});
