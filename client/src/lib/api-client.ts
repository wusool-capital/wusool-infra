// The runtime client every Kubb-generated call goes through: base URL, the
// API key, and Zod validation of every response before it reaches a component.
import { getApiKey, setApiKey } from "@/lib/api-key";

type ValidationResult =
  { value: unknown; issues?: undefined } | { issues: readonly unknown[] };
interface StandardSchema {
  "~standard": {
    validate: (value: unknown) => ValidationResult | Promise<ValidationResult>;
  };
}

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
  validator?: {
    request?: StandardSchema;
    response?: StandardSchema;
    error?: StandardSchema;
  };
  client?: typeof client;
}

interface DataShape {
  body?: unknown;
  headers?: unknown;
  path?: unknown;
  query?: unknown;
}

export type Options<
  TData extends DataShape,
  ThrowOnError extends boolean = true,
> = Omit<RequestConfig, keyof DataShape | "url" | "method"> &
  TData & { throwOnError?: ThrowOnError };

type SuccessOf<TResponses> = TResponses[Extract<
  keyof TResponses,
  `2${string}`
>];
interface Success<TResponses> {
  data: SuccessOf<TResponses>;
  error: undefined;
  response: Response;
}
interface Failure {
  data: undefined;
  error: ApiRequestError;
  response: Response;
}

export type RequestResult<
  TResponses,
  ThrowOnError extends boolean = true,
> = ThrowOnError extends true
  ? Success<TResponses>
  : Success<TResponses> | Failure;

export type ResponseErrorConfig<TError = unknown> = ApiRequestError & {
  body?: TError;
};

export interface ApiErrorBody {
  code: string;
  message: string;
  existing_deals?: {
    attio_id: string;
    name: string;
    stage: string | null;
    web_url: string | null;
  }[];
}

export class ApiRequestError extends Error {
  readonly status: number;
  readonly detail: ApiErrorBody | null;

  constructor(status: number, detail: ApiErrorBody | null, message?: string) {
    super(message ?? detail?.message ?? `Request failed (${String(status)})`);
    this.name = "ApiRequestError";
    this.status = status;
    this.detail = detail;
  }
}

const BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function errorDetail(body: unknown): ApiErrorBody | null {
  if (!isRecord(body) || !isRecord(body.detail)) return null;
  const { code, message } = body.detail;
  if (typeof code !== "string" || typeof message !== "string") return null;
  return body.detail as unknown as ApiErrorBody;
}

export function buildUrl(
  config: Pick<RequestConfig, "url" | "path" | "query" | "baseURL">,
): string {
  const path = (config.path ?? {}) as Record<string, Scalar>;
  const url = config.url.replace(/\{(\w+)\}/g, (_, key: string) =>
    encodeURIComponent(String(path[key])),
  );
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(
    (config.query ?? {}) as Record<string, Scalar | null | undefined>,
  )) {
    if (value !== undefined && value !== null) params.set(key, String(value));
  }
  const search = params.toString();
  return `${config.baseURL ?? BASE_URL}${url}${search ? `?${search}` : ""}`;
}

export function authHeaders(): Record<string, string> {
  const key = getApiKey();
  return key === null ? {} : { Authorization: `Bearer ${key}` };
}

export async function client(config: RequestConfig): Promise<{
  data: unknown;
  error: ApiRequestError | undefined;
  response: Response;
}> {
  const response = await fetch(buildUrl(config), {
    method: config.method,
    headers: {
      ...authHeaders(),
      ...(config.body === undefined
        ? {}
        : { "Content-Type": "application/json" }),
      ...(config.headers as Record<string, string> | undefined),
    },
    body: config.body === undefined ? null : JSON.stringify(config.body),
    signal: config.signal ?? null,
  });
  const body: unknown = await response.json().catch(() => undefined);

  if (response.ok) {
    const result =
      await config.validator?.response?.["~standard"].validate(body);
    if (result?.issues) {
      throw new ApiRequestError(
        response.status,
        null,
        "The server sent data in an unexpected shape.",
      );
    }
    return { data: result ? result.value : body, error: undefined, response };
  }

  // A rejected key means the stored one is wrong: drop it so the key prompt shows.
  if (response.status === 401) setApiKey(null);
  const error = new ApiRequestError(response.status, errorDetail(body));
  if (config.throwOnError ?? true) throw error;
  return { data: undefined, error, response };
}
