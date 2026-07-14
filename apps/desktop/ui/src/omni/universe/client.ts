import type {
  ApiProblemKind,
  CommandResult,
  UniverseCatalogSnapshot,
  UniverseCommand,
  UniverseEventPage,
  UniverseSnapshot,
} from './types.ts';

type FetchLike = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;
type HeaderFactory = () => Record<string, string>;

interface ErrorPayload {
  error?: string | {
    code?: string;
    message?: string;
    correlation_id?: string;
    current_version?: number;
    retry_after_ms?: number;
  };
  detail?: string;
  message?: string;
  correlation_id?: string;
  current_version?: number;
  retry_after_ms?: number;
}

export class UniverseApiError extends Error {
  readonly kind: ApiProblemKind;
  readonly status: number | null;
  readonly correlationId: string | null;
  readonly currentVersion: number | null;
  readonly retryAfterMs: number | null;

  constructor(
    kind: ApiProblemKind,
    message: string,
    options: {
      status?: number | null;
      correlationId?: string | null;
      currentVersion?: number | null;
      retryAfterMs?: number | null;
      cause?: unknown;
    } = {},
  ) {
    super(message, { cause: options.cause });
    this.name = 'UniverseApiError';
    this.kind = kind;
    this.status = options.status ?? null;
    this.correlationId = options.correlationId ?? null;
    this.currentVersion = options.currentVersion ?? null;
    this.retryAfterMs = options.retryAfterMs ?? null;
  }
}

function kindForStatus(status: number): ApiProblemKind {
  if (status === 401) return 'unauthenticated';
  if (status === 403) return 'denied';
  if (status === 409) return 'conflict';
  if (status === 429) return 'rate-limited';
  if (status === 404 || status === 501) return 'unavailable';
  if (status >= 500) return 'server';
  return 'invalid-response';
}

async function readJson(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type')?.toLowerCase() ?? '';
  if (!contentType.includes('application/json') && !contentType.includes('+json')) {
    if (response.status === 204) return null;
    const text = await response.text();
    return text ? { message: text.slice(0, 500) } : null;
  }
  try {
    return await response.json();
  } catch (cause) {
    throw new UniverseApiError('invalid-response', 'Universe service returned invalid JSON.', {
      status: response.status,
      cause,
    });
  }
}

function payloadObject(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

export class UniverseClient {
  readonly baseUrl: string;
  readonly actorId: string;
  private readonly headers: HeaderFactory;
  private readonly fetcher: FetchLike;

  constructor(
    baseUrl: string,
    headers: HeaderFactory,
    fetcher?: FetchLike,
    actorId = 'ply_owner',
  ) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.headers = headers;
    // Wrap the global fetch instead of storing the bare reference: calling
    // `this.fetcher(...)` with an unbound `fetch` rebinds `this` to the client
    // and throws "Illegal invocation" in Chromium — which surfaced as a
    // permanent "Atlas stale" badge because the error was classified as a
    // network failure before any request left the page.
    this.fetcher = fetcher ?? ((input, init) => fetch(input, init));
    this.actorId = actorId;
  }

  private async request<T>(
    path: string,
    options: { method?: 'GET' | 'POST'; body?: unknown; signal?: AbortSignal } = {},
  ): Promise<T> {
    const suppliedHeaders = this.headers();
    const authorization = suppliedHeaders.Authorization ?? suppliedHeaders.authorization;
    const requestHeaders: Record<string, string> = authorization
      ? { Authorization: authorization }
      : {};
    if (options.body !== undefined) requestHeaders['Content-Type'] = 'application/json';

    let response: Response;
    try {
      response = await this.fetcher(`${this.baseUrl}/v1/plugins/muse-universe${path}`, {
        method: options.method ?? 'GET',
        headers: requestHeaders,
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
        credentials: 'omit',
        cache: 'no-store',
        signal: options.signal,
      });
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === 'AbortError') throw cause;
      throw new UniverseApiError('network', 'Universe service could not be reached.', { cause });
    }

    const body = await readJson(response);
    if (!response.ok) {
      const payload = payloadObject(body) as ErrorPayload;
      const nested = payloadObject(payload.error);
      const retryHeader = response.headers.get('retry-after');
      const retryAfterMs =
        typeof (nested.retry_after_ms ?? payload.retry_after_ms) === 'number'
          ? Number(nested.retry_after_ms ?? payload.retry_after_ms)
          : retryHeader && Number.isFinite(Number(retryHeader))
            ? Number(retryHeader) * 1000
            : null;
      throw new UniverseApiError(
        kindForStatus(response.status),
        (typeof nested.message === 'string' ? nested.message : null)
          ?? payload.detail
          ?? payload.message
          ?? (typeof payload.error === 'string' ? payload.error : null)
          ?? `Universe request failed (${response.status}).`,
        {
          status: response.status,
          correlationId:
            (typeof nested.correlation_id === 'string' ? nested.correlation_id : null)
            ?? payload.correlation_id
            ?? null,
          currentVersion:
            typeof (nested.current_version ?? payload.current_version) === 'number'
              ? Number(nested.current_version ?? payload.current_version)
              : null,
          retryAfterMs,
        },
      );
    }
    return body as T;
  }

  async catalog(signal?: AbortSignal): Promise<UniverseCatalogSnapshot> {
    const body = await this.request<unknown>('/catalog', { signal });
    const record = payloadObject(body);
    return (record.catalog ?? record) as UniverseCatalogSnapshot;
  }

  async snapshot(realmId: string, signal?: AbortSignal): Promise<UniverseSnapshot> {
    const body = await this.request<unknown>(
      `/snapshot?realm_id=${encodeURIComponent(realmId)}&actor_id=${encodeURIComponent(this.actorId)}`,
      { signal },
    );
    const record = payloadObject(body);
    const snapshot = (record.snapshot ?? record) as UniverseSnapshot;
    if (!snapshot || typeof snapshot !== 'object') {
      throw new UniverseApiError('invalid-response', 'Universe snapshot was not an object.');
    }
    return snapshot;
  }

  async events(
    realmId: string,
    cursor: number,
    signal?: AbortSignal,
    limit = 128,
  ): Promise<UniverseEventPage> {
    const boundedLimit = Math.max(1, Math.min(256, Math.trunc(limit)));
    const body = await this.request<UniverseEventPage>(
      `/events?realm_id=${encodeURIComponent(realmId)}&since=${Math.max(0, Math.trunc(cursor))}&limit=${boundedLimit}`,
      { signal },
    );
    return {
      events: Array.isArray(body.events) ? body.events : [],
      cursor: Number.isFinite(body.cursor) ? body.cursor : cursor,
      realm_version: Number.isFinite(body.realm_version) ? body.realm_version : 0,
    };
  }

  command(command: UniverseCommand, signal?: AbortSignal): Promise<CommandResult> {
    return this.request<CommandResult>('/commands', {
      method: 'POST',
      body: this.commandEnvelope(command),
      signal,
    });
  }

  validate(command: UniverseCommand, signal?: AbortSignal): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/validate', {
      method: 'POST',
      body: this.commandEnvelope(command),
      signal,
    });
  }

  private commandEnvelope(command: UniverseCommand): Record<string, unknown> {
    return {
      command_id: command.command_id,
      command_type: command.command_type,
      realm_id: command.realm_id,
      actor_id: command.actor_id,
      expected_version: command.expected_version,
      payload: command.payload,
      simulation: command.simulation,
      ...(command.approval_id ? { approval_id: command.approval_id } : {}),
    };
  }
}
