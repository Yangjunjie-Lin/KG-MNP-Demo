import { translateValidationDetail } from "./fieldLabels";

export interface ApiErrorOptions {
  status?: number;
  code?: string;
  message?: string;
  details?: unknown[];
  retryable?: boolean;
  cause?: unknown;
}

const statusMessages: Record<number, string> = {
  400: "请求数据不符合要求",
  401: "无权访问该内容",
  403: "无权访问该内容",
  404: "未找到相关记录",
  413: "请求内容过大",
  422: "输入数据不符合要求",
  500: "系统暂时无法处理请求",
  502: "无法连接后端服务",
  503: "系统暂时无法处理请求",
  504: "请求超时",
};

const codeMessages: Record<string, string> = {
  INPUT_SCHEMA_ERROR: "输入数据不符合要求",
  REQUEST_TOO_LARGE: "请求内容过大",
  CASE_NOT_FOUND: "未找到相关记录",
  EXECUTION_NOT_FOUND: "未找到相关记录",
  QUERY_NOT_FOUND: "未找到相关记录",
  EXAMPLE_NOT_FOUND: "未找到相关记录",
  RULE_NOT_FOUND: "未找到相关记录",
  ONTOLOGY_MODULE_NOT_FOUND: "未找到相关记录",
  INTERNAL_ERROR: "系统暂时无法处理请求",
  STORAGE_ERROR: "系统暂时无法处理请求",
  NETWORK_ERROR: "无法连接后端服务",
  TIMEOUT: "请求超时",
  INVALID_RESPONSE: "系统暂时无法处理请求",
  INVALID_REQUEST: "请求数据不符合要求",
  REQUEST_CANCELLED: "请求已取消",
};

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown[];
  readonly retryable: boolean;
  readonly cause?: unknown;

  constructor(options: ApiErrorOptions = {}) {
    const status = options.status ?? 0;
    const code = options.code ?? (status ? `HTTP_${status}` : "NETWORK_ERROR");
    const safeMessage =
      codeMessages[code] ?? statusMessages[status] ?? "系统暂时无法处理请求";
    super(safeMessage);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = options.details ?? [];
    this.retryable = options.retryable ?? (status === 0 || status >= 500);
    this.cause = options.cause;
  }

  get fieldErrors(): string[] {
    if (this.status !== 422 && this.code !== "INPUT_SCHEMA_ERROR") return [];
    return [...new Set(this.details.map(translateValidationDetail).filter(Boolean))];
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

export function errorMessage(error: unknown): string {
  return isApiError(error) ? error.message : "系统暂时无法处理请求";
}
