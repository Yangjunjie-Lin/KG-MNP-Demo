import type { paths } from "./generated/schema";
import { resolveApiUrl } from "./config";
import { ApiError } from "./errors";

type HttpMethod = "get" | "post";
type JsonRecord = Record<string, unknown>;
type Operation<Path extends keyof paths, Method extends HttpMethod> = NonNullable<
  paths[Path][Method]
>;
type PathFor<Method extends HttpMethod> = {
  [Path in keyof paths]: Operation<Path, Method> extends never ? never : Path;
}[keyof paths];
type OperationParameters<OperationType, Kind extends "path" | "query"> =
  OperationType extends { parameters: infer Parameters }
    ? Kind extends keyof Parameters
      ? NonNullable<Parameters[Kind]>
      : never
    : never;
type JsonContent<ResponseType> = ResponseType extends {
  content: { "application/json": infer Body };
}
  ? Body
  : undefined;
type SuccessResponse<OperationType> = OperationType extends {
  responses: { 200: infer ResponseType };
}
  ? JsonContent<ResponseType>
  : undefined;
type RequestBody<OperationType> = OperationType extends {
  requestBody: { content: { "application/json": infer Body } };
}
  ? Body
  : undefined;

export type ApiGetPath = PathFor<"get">;
export type ApiPostPath = PathFor<"post">;

export interface ApiTransportOptions extends Omit<RequestInit, "body" | "method" | "signal"> {
  baseUrl?: string;
  timeoutMs?: number;
  signal?: AbortSignal;
}

export interface ApiRequestOptions extends ApiTransportOptions {
  method?: string;
  body?: unknown;
  pathParams?: Record<string, string | number>;
  query?: Record<string, unknown>;
}

type ParameterOptions<OperationType> =
  ([OperationParameters<OperationType, "path">] extends [never]
    ? { pathParams?: never }
    : { pathParams: OperationParameters<OperationType, "path"> }) &
  ([OperationParameters<OperationType, "query">] extends [never]
    ? { query?: never }
    : Record<string, never> extends OperationParameters<OperationType, "query">
      ? { query?: OperationParameters<OperationType, "query"> }
      : { query: OperationParameters<OperationType, "query"> });

export type ApiGetOptions<Path extends ApiGetPath> = ApiTransportOptions &
  ParameterOptions<Operation<Path, "get">>;
export type ApiPostOptions<Path extends ApiPostPath> = ApiTransportOptions &
  ParameterOptions<Operation<Path, "post">>;
type OptionArguments<Options, Parameters> = Record<string, never> extends Parameters
  ? [options?: Options]
  : [options: Options];

function composeAbortSignal(
  externalSignal: AbortSignal | null | undefined,
  controller: AbortController,
): () => void {
  if (!externalSignal) return () => undefined;
  if (externalSignal.aborted) controller.abort(externalSignal.reason);
  const abort = () => controller.abort(externalSignal.reason);
  externalSignal.addEventListener("abort", abort, { once: true });
  return () => externalSignal.removeEventListener("abort", abort);
}

function asErrorPayload(value: unknown): JsonRecord | null {
  if (!value || typeof value !== "object") return null;
  const error = (value as JsonRecord).error;
  return error && typeof error === "object" ? (error as JsonRecord) : null;
}

function interpolatePath(
  path: string,
  parameters: Record<string, string | number> | undefined,
): string {
  return path.replace(/\{([^}]+)\}/gu, (_match, name: string) => {
    const value = parameters?.[name];
    if (value === undefined || value === null || value === "") {
      throw new ApiError({ code: "INVALID_REQUEST" });
    }
    return encodeURIComponent(String(value));
  });
}

function appendQuery(path: string, query: Record<string, unknown> | undefined): string {
  if (!query) return path;
  const search = new URLSearchParams();
  for (const [key, rawValue] of Object.entries(query)) {
    if (rawValue === undefined || rawValue === null) continue;
    const values = Array.isArray(rawValue) ? rawValue : [rawValue];
    for (const value of values) search.append(key, String(value));
  }
  const suffix = search.toString();
  return suffix ? `${path}?${suffix}` : path;
}

function isJsonContentType(contentType: string): boolean {
  return /(?:^|\s|;)application\/(?:[\w.+-]+\+)?json(?:\s|;|$)/iu.test(contentType);
}

/**
 * Low-level transport used by the OpenAPI-bound apiGet/apiPost helpers.
 * Callers that know a response outside the checked-in contract may inject T here;
 * application services should use apiGet/apiPost so path, method, body and response stay linked.
 */
export async function apiRequest<T = unknown>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const {
    baseUrl,
    timeoutMs = 15_000,
    signal: externalSignal,
    body: requestBody,
    pathParams,
    query,
    headers: initialHeaders,
    ...requestInit
  } = options;
  const controller = new AbortController();
  const detach = composeAbortSignal(externalSignal, controller);
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort(new DOMException("timeout", "TimeoutError"));
  }, timeoutMs);
  const headers = new Headers(initialHeaders);
  let body: BodyInit | undefined;

  try {
    if (requestBody !== undefined) {
      headers.set("Content-Type", "application/json");
      body = JSON.stringify(requestBody);
    }
    headers.set("Accept", "application/json");
    const expandedPath = appendQuery(interpolatePath(path, pathParams), query);
    const relativePath = expandedPath.replace(/^\/api\/v1(?=\/|\?|$)/u, "");
    const response = await fetch(resolveApiUrl(relativePath, baseUrl), {
      ...requestInit,
      body,
      headers,
      signal: controller.signal,
    });
    const contentType = response.headers.get("content-type") ?? "";
    const rawBody = response.status === 204 || response.status === 205
      ? ""
      : await response.text();
    let payload: unknown;
    if (rawBody.trim()) {
      if (isJsonContentType(contentType)) {
        try {
          payload = JSON.parse(rawBody) as unknown;
        } catch (error) {
          throw new ApiError({
            status: response.ok ? 502 : response.status,
            code: "INVALID_RESPONSE",
            cause: error,
          });
        }
      } else if (response.ok) {
        throw new ApiError({ status: 502, code: "INVALID_RESPONSE" });
      }
    }
    if (!response.ok) {
      const error = asErrorPayload(payload);
      throw new ApiError({
        status: response.status,
        code: typeof error?.code === "string" ? error.code : undefined,
        message: typeof error?.message === "string" ? error.message : undefined,
        details: Array.isArray(error?.details) ? error.details : [],
        retryable: typeof error?.retryable === "boolean" ? error.retryable : undefined,
      });
    }
    return payload as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (controller.signal.aborted) {
      throw new ApiError({
        code: timedOut ? "TIMEOUT" : "REQUEST_CANCELLED",
        retryable: timedOut,
        cause: error,
      });
    }
    throw new ApiError({ code: "NETWORK_ERROR", retryable: true, cause: error });
  } finally {
    clearTimeout(timer);
    detach();
  }
}

export function apiGet<Path extends ApiGetPath>(
  path: Path,
  ...args: OptionArguments<ApiGetOptions<Path>, ParameterOptions<Operation<Path, "get">>>
): Promise<SuccessResponse<Operation<Path, "get">>>;
export function apiGet(
  path: string,
  options: ApiRequestOptions = {},
): Promise<unknown> {
  return apiRequest(path, { ...options, method: "GET" });
}

export function apiPost<Path extends ApiPostPath>(
  path: Path,
  body: RequestBody<Operation<Path, "post">>,
  ...args: OptionArguments<ApiPostOptions<Path>, ParameterOptions<Operation<Path, "post">>>
): Promise<SuccessResponse<Operation<Path, "post">>>;
export function apiPost(
  path: string,
  body: unknown,
  options: ApiRequestOptions = {},
): Promise<unknown> {
  return apiRequest(path, { ...options, method: "POST", body });
}
