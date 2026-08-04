import { apiGet } from "../../api/client";
import { adaptSystemStatus } from "../../api/adapters/systemAdapter";

export async function getSystemStatus(signal?: AbortSignal) {
  const [health, ready, meta] = await Promise.all([
    apiGet("/api/v1/health", { signal }),
    apiGet("/api/v1/ready", { signal }),
    apiGet("/api/v1/meta", { signal }),
  ]);
  return adaptSystemStatus(health, ready, meta);
}
