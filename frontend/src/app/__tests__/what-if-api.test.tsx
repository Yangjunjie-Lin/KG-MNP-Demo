import { fireEvent, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { whatIfFixture } from "../../mocks/fixtures/api";
import { server } from "../../mocks/server";
import { renderApp } from "../../test/renderWithProviders";

describe("情景推演 API 集成", () => {
  it("以持久化 execution_id 提交 changes，由后端返回差异", async () => {
    let requestBody: unknown;
    server.use(
      http.post("*/api/v1/assessments/exec-case03/what-if", async ({ request }) => {
        requestBody = await request.json();
        return HttpResponse.json(whatIfFixture);
      }),
    );
    let selects: HTMLSelectElement[];
    const { container, getByRole } = renderApp("/what-if");
    await waitFor(() => expect(container.textContent).toContain("基准评估"));
    selects = Array.from(container.querySelectorAll("select"));
    fireEvent.change(selects[1], { target: { value: "EXPIRED" } });
    fireEvent.click(getByRole("button", { name: "运行后端推演" }));
    await waitFor(() => expect(container.querySelector('[data-testid="what-if-result"]')).toBeInTheDocument());
    expect(requestBody).toEqual({
      changes: {
        evidence: {
          contract: {
            contract_status: "EXPIRED",
          },
        },
      },
    });
    expect(container.textContent).toContain("结论已改变");
    expect(container.textContent).toContain("规则四：合约限制检查");
    expect(container.textContent).not.toContain("MNP-ELIG-004");
  });
});
