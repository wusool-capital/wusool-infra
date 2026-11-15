// The runtime client every Kubb-generated call goes through. Same-origin only: the Worker
// proxies /api/v1/* to the Toolkit and Cloudflare Access supplies the sign-in, so there is
// no base URL, key or cookie to manage here.

type Scalar = string | number | boolean;

export interface RequestConfig {
  method: "GET" | "PUT" | "PATCH" | "POST" | "DELETE" | "OPTIONS" | "HEAD";
  url: string;
  baseURL?: string;
  headers?: object;
  path?: object;
  query?: object;
  body?: unknown;
  contentType?: { request?: string };
  responseType?: "json" | "text" | "blob";
  signal?: AbortSignal;
  throwOnError?: boolean;
  security?: { type: string; name?: string; in?: string; scopes?: string[] }[];
  client?: typeof client;
}

interface DataShape {
  body?: unknown;
  headers?: unknown;
  path?: unknown;
  query?: unknown;
}

export type Options<TData extends DataShape, ThrowOnError extends boolean = true> = Omit<
  RequestConfig,
  keyof DataShape | "url" | "method"
> &
  TData & { throwOnError?: ThrowOnError };

type SuccessOf<TResponses> = TResponses[Extract<keyof TResponses, `2${string}`>];
interface Success<TResponses> {
  data: SuccessOf<TResponses>;
  error: undefined;
  response: Response;
}
interface Failure {
  data: undefined;
  error: ApiProblem;
  response: Response;
}

export type RequestResult<TResponses, ThrowOnError extends boolean = true> = ThrowOnError extends true
  ? Success<TResponses>
  : Success<TResponses> | Failure;

export type ResponseErrorConfig<TError = unknown> = ApiProblem & { body?: TError };

/** An RFC 9457 problem from the Toolkit; `code` is stable, so screens can branch on it. */
export class ApiProblem extends Error {
  readonly status: number;
  readonly code: string;
  readonly errors: string[];
  /** What a failed multi-step save already stored, so the person can retry the rest. */
  readonly landed: string[];

  constructor(status: number, body: ProblemBody | null) {
    super(body?.detail ?? `Request failed (${String(status)})`);
    this.name = "ApiProblem";
    this.status = status;
    this.code = body?.code ?? "unknown";
    this.errors = body?.errors ?? [];
    this.landed = body?.landed ?? [];
  }
}

interface ProblemBody {
  code?: string;
  detail?: string;
  errors?: string[];
  landed?: string[];
}

function problemBody(body: unknown): ProblemBody | null {
  return typeof body === "object" && body !== null ? (body as ProblemBody) : null;
}

export function buildUrl(config: Pick<RequestConfig, "url" | "path" | "query">): string {
  const path = (config.path ?? {}) as Record<string, Scalar>;
  const url = config.url.replace(/\{(\w+)\}/g, (_, key: string) => encodeURIComponent(String(path[key])));
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries((config.query ?? {}) as Record<string, Scalar | null | undefined>)) {
    if (value !== undefined && value !== null && value !== "") params.append(key, String(value));
  }
  const search = params.toString();
  return `${url}${search ? `?${search}` : ""}`;
}

export async function client(config: RequestConfig): Promise<{
  data: unknown;
  error: ApiProblem | undefined;
  response: Response;
}> {
  const response = await fetch(buildUrl(config), {
    method: config.method,
    headers: {
      ...(config.body === undefined ? {} : { "Content-Type": "application/json" }),
      ...(config.headers as Record<string, string> | undefined),
    },
    body: config.body === undefined ? null : JSON.stringify(config.body),
    signal: config.signal ?? null,
  });
  const body: unknown = await response.json().catch(() => undefined);
  if (response.ok) return { data: body, error: undefined, response };

  const error = new ApiProblem(response.status, problemBody(body));
  if (config.throwOnError ?? true) throw error;
  return { data: undefined, error, response };
}
