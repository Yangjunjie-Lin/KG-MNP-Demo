import { adaptDashboard } from "../../api/adapters/systemAdapter";
import { apiGet } from "../../api/client";

export async function getDashboard(signal?: AbortSignal) {
  const [dashboard, examples] = await Promise.all([
    apiGet("/api/v1/views/dashboard", { signal }),
    apiGet("/api/v1/examples", { signal }),
  ]);
  return adaptDashboard(dashboard, examples);
}
