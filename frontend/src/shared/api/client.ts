export type ApiClientOptions = {
  baseUrl: string;
  fetcher?: FetchFn;
};

export type FetchFn = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

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
    this.fetcher = options.fetcher ?? fetch;
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
    const response = await this.fetcher(`${this.baseUrl}${path}`, {
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

    const responseBody = await parseResponseBody(response);

    if (!response.ok) {
      throw new ApiClientError({
        method,
        path,
        responseBody,
        status: response.status,
      });
    }

    return responseBody as TResponse;
  }
}

async function parseResponseBody(response: Response): Promise<unknown> {
  const text = await response.text();

  if (!text) {
    return null;
  }

  return JSON.parse(text) as unknown;
}
