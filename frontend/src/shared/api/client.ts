import {
  createFrontendLogger,
  summarizeLoggableError,
  toLoggableError,
} from "../logging/frontendLogger";

export type ApiClientOptions = {
  baseUrl: string;
  fetcher?: FetchFn;
};

export type FetchFn = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

const apiLogger = createFrontendLogger("api-client");

export class ApiClientError extends Error {
  readonly method: string;
  readonly path: string;
  readonly status: number;
  readonly responseBody: unknown;

  constructor({
    method,
    path,
    responseBody,
    status,
  }: {
    method: string;
    path: string;
    responseBody: unknown;
    status: number;
  }) {
    super(`${method} ${path} failed with ${status}`);
    this.name = "ApiClientError";
    this.method = method;
    this.path = path;
    this.responseBody = responseBody;
    this.status = status;
  }
}

export class ApiClient {
  readonly baseUrl: string;
  private readonly fetcher: FetchFn;

  constructor(options: ApiClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.fetcher = options.fetcher ?? defaultFetch;
  }

  async getJson<T>(path: string): Promise<T> {
    return this.requestJson<T>("GET", path);
  }

  async postJson<TResponse, TBody = unknown>(
    path: string,
    body: TBody,
  ): Promise<TResponse> {
    return this.requestJson<TResponse>("POST", path, body);
  }

  async patchJson<TResponse, TBody = unknown>(
    path: string,
    body: TBody,
  ): Promise<TResponse> {
    return this.requestJson<TResponse>("PATCH", path, body);
  }

  async requestJson<TResponse, TBody = unknown>(
    method: string,
    path: string,
    body?: TBody,
  ): Promise<TResponse> {
    const url = `${this.baseUrl}${path}`;
    const startedAt = now();

    apiLogger.debug("request.start", {
      method,
      path,
      url,
    });

    try {
      const response = await this.fetcher(url, {
        body: body === undefined ? undefined : JSON.stringify(body),
        headers:
          body === undefined
            ? {
                Accept: "application/json",
              }
            : {
                Accept: "application/json",
                "Content-Type": "application/json",
              },
        method,
      });
      const durationMs = elapsedMs(startedAt);

      apiLogger.debug(
        `request.response ${method} ${path} status=${response.status}`,
        {
          durationMs,
          method,
          path,
          status: response.status,
          url,
        },
      );

      const responseBody = await parseResponseBody(response, {
        method,
        path,
        startedAt,
        url,
      });

      if (!response.ok) {
        throw new ApiClientError({
          method,
          path,
          responseBody,
          status: response.status,
        });
      }

      apiLogger.debug(
        `request.success ${method} ${path} status=${response.status}`,
        {
          durationMs,
          method,
          path,
          status: response.status,
          url,
        },
      );

      return responseBody as TResponse;
    } catch (error) {
      if (error instanceof ApiClientError) {
        apiLogger.warn(
          `request.non_ok_response ${method} ${path} status=${error.status}`,
          {
            durationMs: elapsedMs(startedAt),
            method,
            path,
            responseBody: error.responseBody,
            status: error.status,
            url,
          },
        );
      } else {
        apiLogger.error(
          `request.failed ${method} ${path} -> ${summarizeLoggableError(
            error,
          )}`,
          {
            durationMs: elapsedMs(startedAt),
            error: toLoggableError(error),
            method,
            path,
            url,
          },
        );
      }

      throw error;
    }
  }
}

type ParseContext = {
  method: string;
  path: string;
  startedAt: number;
  url: string;
};

async function parseResponseBody(
  response: Response,
  context: ParseContext,
): Promise<unknown> {
  const text = await response.text();

  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text) as unknown;
  } catch (error) {
    apiLogger.error(
      `request.invalid_json ${context.method} ${context.path} status=${response.status} -> ${summarizeLoggableError(
        error,
      )}`,
      {
        durationMs: elapsedMs(context.startedAt),
        error: toLoggableError(error),
        method: context.method,
        path: context.path,
        responseText: truncate(text),
        status: response.status,
        url: context.url,
      },
    );
    throw error;
  }
}

function now(): number {
  return globalThis.performance?.now() ?? Date.now();
}

function defaultFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  return globalThis.fetch(input, init);
}

function elapsedMs(startedAt: number): number {
  return Math.round(now() - startedAt);
}

function truncate(value: string): string {
  if (value.length <= 500) {
    return value;
  }

  return `${value.slice(0, 500)}...`;
}
