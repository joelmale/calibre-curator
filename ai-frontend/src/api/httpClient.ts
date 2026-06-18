import type { ApiResult, IApiError } from "../types/api";

export class HttpClient {
  public constructor(private readonly baseUrl: string) {}

  public get<TResponse>(path: string): Promise<ApiResult<TResponse>> {
    return this.request<TResponse>("GET", path);
  }

  public post<TRequest extends object, TResponse>(
    path: string,
    body: TRequest,
  ): Promise<ApiResult<TResponse>> {
    return this.request<TResponse>("POST", path, body);
  }

  private csrfToken(): string {
    return document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content ?? "";
  }

  private async request<TResponse>(
    method: "GET" | "POST",
    path: string,
    body?: object,
  ): Promise<ApiResult<TResponse>> {
    try {
      const headers: Record<string, string> = {
        "Accept": "application/json",
        "Content-Type": "application/json",
      };
      if (method === "POST") {
        const token = this.csrfToken();
        if (token) headers["X-CSRFToken"] = token;
      }
      const init: RequestInit = {
        method,
        headers,
        credentials: "same-origin",
        ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
      };
      const response = await fetch(`${this.baseUrl}${path}`, init);

      const payload: unknown = await response.json();

      if (!response.ok) {
        return { ok: false, error: this.toApiError(payload) };
      }
      return { ok: true, data: payload as TResponse };
    } catch (error: unknown) {
      return {
        ok: false,
        error: {
          error: "network_error",
          detail: error instanceof Error ? error.message : "Unknown network error",
        },
      };
    }
  }

  private toApiError(payload: unknown): IApiError {
    if (typeof payload === "object" && payload !== null && "error" in payload) {
      const p = payload as { readonly error?: unknown; readonly detail?: unknown };
      return {
        error: typeof p["error"] === "string" ? p["error"] : "api_error",
        detail: typeof p["detail"] === "string" ? p["detail"] : null,
      };
    }
    return { error: "api_error", detail: null };
  }
}
