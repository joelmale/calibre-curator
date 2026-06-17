import type { ApiResult, IApiError } from "../types/api";

export function unwrapOr<T>(result: ApiResult<T>, fallback: T): T {
  return result.ok ? result.data : fallback;
}

export function errorMessage(error: IApiError): string {
  return error.detail ?? error.error;
}
