import { fireEvent, waitFor } from "@testing-library/react";
import { useLocation } from "react-router";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { assessmentRecordFixture } from "../../mocks/fixtures/api";
import { server } from "../../mocks/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { NewAssessment } from "../pages/NewAssessment";

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="current-path">{location.pathname}</output>;
}

describe("新建评估 API 集成", () => {
  it("加载示例后提交真实 JSON，并使用响应 execution_id 导航", async () => {
    let requestBody: Record<string, unknown> | undefined;
    server.use(
      http.post("*/api/v1/assessments", async ({ request }) => {
        requestBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(assessmentRecordFixture("exec-created", "CASE-03"));
      }),
    );
    const { container, getByRole, getByTestId } = renderWithProviders(
      <>
        <NewAssessment />
        <LocationProbe />
      </>,
      { route: "/assessments/new" },
    );
    fireEvent.click(getByRole("button", { name: "加载示例（案例三）" }));
    await waitFor(() =>
      expect((getByRole("combobox", { name: /案例编号/ }) as HTMLSelectElement).value).toBe("CASE-03"),
    );
    expect(
      Array.from(container.querySelectorAll("input[required]"))
        .filter((input) => !(input as HTMLInputElement).value)
        .map((input) => input.getAttribute("type")),
    ).toEqual([]);
    for (const input of Array.from(container.querySelectorAll("input, select"))) {
      fireEvent.change(input, { target: { value: (input as HTMLInputElement).value } });
    }
    const submitButton = getByRole("button", { name: "提交真实评估" }) as HTMLButtonElement;
    const form = container.querySelector("form") as HTMLFormElement;
    Object.defineProperty(form, "checkValidity", { value: () => true });
    form.requestSubmit = () =>
      form.dispatchEvent(new SubmitEvent("submit", { bubbles: true, cancelable: true }));
    fireEvent.click(submitButton);
    await waitFor(() =>
      expect(container.textContent).not.toContain("请完整填写所有必填字段。"),
    );
    await waitFor(() => expect(requestBody).toBeDefined());
    expect(requestBody?.persist).toBe(true);
    expect(requestBody?.force_recompute).toBe(false);
    const payload = requestBody?.payload as Record<string, unknown>;
    expect(payload.case_id).toBe("CASE-03");
    const billing = (payload.evidence as Record<string, Record<string, unknown>>).billing;
    expect(typeof billing.outstanding_amount).toBe("number");
    await waitFor(() =>
      expect(getByTestId("current-path")).toHaveTextContent("/assessments/exec-created"),
    );
  });
});
