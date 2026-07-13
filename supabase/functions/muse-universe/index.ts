import {
  ContractError,
  MAX_EVENT_PAGE_SIZE,
  MAX_REQUEST_BYTES,
  parseBoundedInteger,
  parseUniverseCommand,
  validateRealmId,
} from "../_shared/universe-contract.ts";

type AuthUser = Readonly<{ id: string }>;
type EdgeConfig = Readonly<{
  supabaseUrl: string;
  anonKey: string;
  allowedOrigins: ReadonlySet<string>;
}>;

class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly metadata: Readonly<Record<string, unknown>>;

  constructor(
    status: number,
    code: string,
    message: string,
    metadata: Readonly<Record<string, unknown>> = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.metadata = metadata;
  }
}

function loadConfig(): EdgeConfig {
  const supabaseUrl = (Deno.env.get("SUPABASE_URL") ?? "").replace(/\/$/, "");
  const anonKey = Deno.env.get("SUPABASE_ANON_KEY") ?? "";
  if (!supabaseUrl || !anonKey) {
    throw new ApiError(503, "not_configured", "universe service is not configured");
  }
  const allowedOrigins = new Set(
    (
      Deno.env.get("MUSE_UNIVERSE_ALLOWED_ORIGINS")
      ?? Deno.env.get("MUSE_FIRST_PARTY_ORIGINS")
      ?? ""
    )
      .split(",")
      .map((origin) => origin.trim())
      .filter(Boolean),
  );
  return Object.freeze({ supabaseUrl, anonKey, allowedOrigins });
}

function allowedOrigin(request: Request, config: EdgeConfig): string | null {
  const origin = request.headers.get("origin");
  if (origin === null) return null;
  if (!config.allowedOrigins.has(origin)) {
    throw new ApiError(403, "origin_forbidden", "origin is not allowed");
  }
  return origin;
}

function responseHeaders(origin: string | null): Headers {
  const headers = new Headers({
    "cache-control": "no-store",
    "content-type": "application/json; charset=utf-8",
    "vary": "Origin",
  });
  if (origin !== null) headers.set("access-control-allow-origin", origin);
  return headers;
}

function jsonResponse(
  status: number,
  body: unknown,
  origin: string | null,
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: responseHeaders(origin),
  });
}

function bearerToken(request: Request): string {
  const authorization = request.headers.get("authorization") ?? "";
  const match = /^Bearer ([^\s]+)$/.exec(authorization);
  if (!match) throw new ApiError(401, "unauthorized", "valid bearer token required");
  return match[1];
}

function postgrestHeaders(config: EdgeConfig, userToken: string): HeadersInit {
  return {
    "accept": "application/json",
    "apikey": config.anonKey,
    "authorization": `Bearer ${userToken}`,
    "content-type": "application/json",
  };
}

function authClient(config: EdgeConfig) {
  return {
    auth: {
      async getUser(userToken: string): Promise<{
        data: { user: AuthUser | null };
        error: Error | null;
      }> {
        const response = await fetch(`${config.supabaseUrl}/auth/v1/user`, {
          method: "GET",
          headers: postgrestHeaders(config, userToken),
        });
        if (!response.ok) {
          return { data: { user: null }, error: new Error("authentication failed") };
        }
        const value = await safeJson(response);
        if (!isObject(value) || typeof value.id !== "string") {
          return { data: { user: null }, error: new Error("authentication failed") };
        }
        return { data: { user: Object.freeze({ id: value.id }) }, error: null };
      },
    },
  };
}

async function authenticate(
  request: Request,
  config: EdgeConfig,
): Promise<{ user: AuthUser; userToken: string }> {
  const userToken = bearerToken(request);
  const auth = authClient(config).auth;
  const { data, error } = await auth.getUser(userToken);
  if (error || !data.user) {
    throw new ApiError(401, "unauthorized", "bearer token was not accepted");
  }
  return { user: data.user, userToken };
}

function isObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

async function safeJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

async function boundedJsonBody(request: Request): Promise<unknown> {
  const contentType = request.headers.get("content-type")?.split(";", 1)[0].trim();
  if (contentType !== "application/json") {
    throw new ApiError(415, "unsupported_media_type", "application/json required");
  }
  const declaredLength = request.headers.get("content-length");
  if (declaredLength !== null) {
    if (!/^(0|[1-9][0-9]*)$/.test(declaredLength)) {
      throw new ApiError(400, "invalid_content_length", "invalid Content-Length");
    }
    if (Number(declaredLength) > MAX_REQUEST_BYTES) {
      throw new ApiError(413, "request_too_large", "command body is too large");
    }
  }
  const text = await request.text();
  if (new TextEncoder().encode(text).byteLength > MAX_REQUEST_BYTES) {
    throw new ApiError(413, "request_too_large", "command body is too large");
  }
  try {
    return JSON.parse(text);
  } catch {
    throw new ApiError(400, "invalid_json", "command body is not valid JSON");
  }
}

function detailObject(value: unknown): Record<string, unknown> {
  if (isObject(value)) return value;
  if (typeof value !== "string") return {};
  try {
    const parsed = JSON.parse(value);
    return isObject(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

function rpcError(status: number, payload: unknown): ApiError {
  const body = isObject(payload) ? payload : {};
  const message = typeof body.message === "string" ? body.message : "";
  const details = detailObject(body.details);
  if (message === "universe_version_conflict") {
    return new ApiError(409, "version_conflict", "stream version conflict", {
      expected_version: details.expected_version,
      current_version: details.current_version,
    });
  }
  if (message === "universe_command_id_conflict") {
    return new ApiError(409, "command_id_conflict", "command id was reused");
  }
  if (message === "universe_forbidden") {
    return new ApiError(403, "forbidden", "command is not authorized");
  }
  if (message === "universe_not_found") {
    return new ApiError(404, "not_found", "realm or stream was not found");
  }
  if (message === "universe_unauthorized") {
    return new ApiError(401, "unauthorized", "authentication required");
  }
  if (message === "universe_invalid_command") {
    return new ApiError(400, "invalid_command", "command was rejected");
  }
  return new ApiError(
    status >= 500 ? 503 : 400,
    status >= 500 ? "remote_unavailable" : "invalid_command",
    status >= 500 ? "universe authority is unavailable" : "command was rejected",
  );
}

async function executeCommand(
  request: Request,
  config: EdgeConfig,
  userToken: string,
): Promise<unknown> {
  const command = parseUniverseCommand(await boundedJsonBody(request));
  const response = await fetch(
    `${config.supabaseUrl}/rest/v1/rpc/execute_universe_command`,
    {
      method: "POST",
      headers: postgrestHeaders(config, userToken),
      body: JSON.stringify({ p_command: command }),
    },
  );
  const payload = await safeJson(response);
  if (!response.ok) throw rpcError(response.status, payload);
  if (!isObject(payload)) {
    throw new ApiError(503, "invalid_remote_response", "universe authority returned an invalid response");
  }
  return payload;
}

async function restRows(
  config: EdgeConfig,
  userToken: string,
  table: string,
  parameters: URLSearchParams,
): Promise<Record<string, unknown>[]> {
  const response = await fetch(
    `${config.supabaseUrl}/rest/v1/${table}?${parameters.toString()}`,
    { method: "GET", headers: postgrestHeaders(config, userToken) },
  );
  const payload = await safeJson(response);
  if (!response.ok) {
    throw new ApiError(503, "remote_unavailable", "universe authority is unavailable");
  }
  if (!Array.isArray(payload) || !payload.every(isObject)) {
    throw new ApiError(503, "invalid_remote_response", "universe authority returned invalid rows");
  }
  return payload;
}

async function realmVersion(
  config: EdgeConfig,
  userToken: string,
  realmId: string,
): Promise<number> {
  const params = new URLSearchParams({
    select: "version",
    realm_id: `eq.${realmId}`,
    limit: "1",
  });
  const rows = await restRows(config, userToken, "universe_realms", params);
  if (rows.length !== 1 || !Number.isSafeInteger(rows[0].version)) {
    throw new ApiError(404, "not_found", "realm was not found");
  }
  return Number(rows[0].version);
}

async function readEvents(
  url: URL,
  config: EdgeConfig,
  userToken: string,
): Promise<Record<string, unknown>> {
  const realmId = validateRealmId(url.searchParams.get("realm_id"));
  const cursorValue = url.searchParams.get("since") ?? url.searchParams.get("cursor");
  const since = parseBoundedInteger(
    cursorValue,
    "since",
    0,
    Number.MAX_SAFE_INTEGER,
    0,
  );
  const limit = parseBoundedInteger(
    url.searchParams.get("limit"),
    "limit",
    1,
    MAX_EVENT_PAGE_SIZE,
    200,
  );
  const params = new URLSearchParams({
    select: "event",
    realm_id: `eq.${realmId}`,
    sequence: `gt.${since}`,
    order: "sequence.asc",
    limit: String(limit),
  });
  const [rows, version] = await Promise.all([
    restRows(config, userToken, "universe_events", params),
    realmVersion(config, userToken, realmId),
  ]);
  const events = rows.map((row) => row.event).filter(isObject);
  if (events.length !== rows.length) {
    throw new ApiError(503, "invalid_remote_response", "universe authority returned invalid events");
  }
  const last = events.at(-1);
  const cursor = last && Number.isSafeInteger(last.sequence) ? Number(last.sequence) : since;
  return {
    events,
    cursor,
    realm_version: version,
    server_time: new Date().toISOString(),
  };
}

async function readSnapshot(
  url: URL,
  config: EdgeConfig,
  userToken: string,
): Promise<Record<string, unknown>> {
  const realmId = validateRealmId(url.searchParams.get("realm_id"));
  const entityParams = new URLSearchParams({
    select: "entity_type,entity",
    realm_id: `eq.${realmId}`,
    order: "entity_type.asc,entity_id.asc",
  });
  const cursorParams = new URLSearchParams({
    select: "sequence",
    realm_id: `eq.${realmId}`,
    order: "sequence.desc",
    limit: "1",
  });
  const [entities, cursorRows, version] = await Promise.all([
    restRows(config, userToken, "universe_entities", entityParams),
    restRows(config, userToken, "universe_events", cursorParams),
    realmVersion(config, userToken, realmId),
  ]);
  const snapshot: Record<string, unknown[]> = {};
  for (const row of entities) {
    if (typeof row.entity_type !== "string" || !isObject(row.entity)) {
      throw new ApiError(503, "invalid_remote_response", "universe authority returned invalid entities");
    }
    const group = `${row.entity_type}s`;
    (snapshot[group] ??= []).push(row.entity);
  }
  const cursor = cursorRows.length === 1 && Number.isSafeInteger(cursorRows[0].sequence)
    ? Number(cursorRows[0].sequence)
    : 0;
  return {
    snapshot,
    cursor,
    realm_version: version,
    server_time: new Date().toISOString(),
  };
}

function routePath(url: URL): "commands" | "events" | "snapshot" | null {
  if (url.pathname.endsWith("/commands")) return "commands";
  if (url.pathname.endsWith("/events")) return "events";
  if (url.pathname.endsWith("/snapshot")) return "snapshot";
  return null;
}

Deno.serve(async (request: Request): Promise<Response> => {
  let origin: string | null = null;
  const correlationId = crypto.randomUUID();
  try {
    const config = loadConfig();
    origin = allowedOrigin(request, config);
    if (request.method === "OPTIONS") {
      const headers = responseHeaders(origin);
      headers.set("access-control-allow-headers", "authorization, apikey, content-type");
      headers.set("access-control-allow-methods", "GET, POST, OPTIONS");
      headers.set("access-control-max-age", "600");
      return new Response(null, { status: 204, headers });
    }

    const url = new URL(request.url);
    const route = routePath(url);
    if (route === null) throw new ApiError(404, "not_found", "route was not found");
    const { userToken } = await authenticate(request, config);
    let payload: unknown;
    if (route === "commands" && request.method === "POST") {
      payload = await executeCommand(request, config, userToken);
    } else if (route === "events" && request.method === "GET") {
      payload = await readEvents(url, config, userToken);
    } else if (route === "snapshot" && request.method === "GET") {
      payload = await readSnapshot(url, config, userToken);
    } else {
      throw new ApiError(405, "method_not_allowed", "method is not allowed");
    }
    return jsonResponse(200, payload, origin);
  } catch (error) {
    if (error instanceof ContractError) {
      return jsonResponse(400, {
        error: { code: "invalid_command", message: error.message },
        correlation_id: correlationId,
      }, origin);
    }
    if (error instanceof ApiError) {
      return jsonResponse(error.status, {
        error: { code: error.code, message: error.message, ...error.metadata },
        correlation_id: correlationId,
      }, origin);
    }
    return jsonResponse(500, {
      error: { code: "internal_error", message: "unexpected universe service error" },
      correlation_id: correlationId,
    }, origin);
  }
});
