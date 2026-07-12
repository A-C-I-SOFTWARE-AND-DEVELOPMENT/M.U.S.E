// ============================================================================
// Connections & credentials registry — every third-party connection that needs
// a username / password / API key / token, enterable through the app.
//
// usage:
//   'local'   — the PWA consumes it directly (applied to RuntimeConfig on save).
//   'gateway' — it belongs in the MUSE gateway's ~/.hermes/.env. The app stores
//               it and exports an exact .env snippet to paste on the gateway host
//               (MUSE keeps provider/messaging keys gateway-side, by design).
// ENV names are the canonical ones used by the MUSE codebase.
// ============================================================================

export type FieldType = 'text' | 'password' | 'url';

export interface CredField {
  env: string;
  label: string;
  type: FieldType;
  placeholder?: string;
  /** For 'local' integrations: which RuntimeConfig key this maps to. */
  configKey?: 'museBaseUrl' | 'museToken' | 'supabaseUrl' | 'supabaseAnonKey' | 'vapidPublicKey';
}

export interface Integration {
  id: string;
  label: string;
  category: string;
  blurb: string;
  usage: 'local' | 'gateway';
  fields: CredField[];
}

export const CRED_CATEGORIES = [
  'Backend',
  'Model Providers',
  'Messaging Bridges',
  'Dev Integrations',
  'Push & MCP',
] as const;

export const INTEGRATIONS: Integration[] = [
  // ---- Backend (local — applied immediately) ----
  {
    id: 'gateway', label: 'MUSE Gateway', category: 'Backend', usage: 'local',
    blurb: 'The cockpit gateway base URL + this device’s Bearer token (set by the connect wizard, editable here).',
    fields: [
      { env: 'VITE_MUSE_BASE_URL', label: 'Gateway URL', type: 'url', placeholder: 'http://127.0.0.1:8765', configKey: 'museBaseUrl' },
      { env: 'MUSE_DEVICE_TOKEN', label: 'Device token', type: 'password', placeholder: 'paired token', configKey: 'museToken' },
    ],
  },
  {
    id: 'supabase', label: 'Supabase', category: 'Backend', usage: 'local',
    blurb: 'Auth + persistence (push subscriptions). The anon key is safe in the client; never paste the service-role key here.',
    fields: [
      { env: 'VITE_SUPABASE_URL', label: 'Project URL', type: 'url', placeholder: 'https://xxxx.supabase.co', configKey: 'supabaseUrl' },
      { env: 'VITE_SUPABASE_ANON_KEY', label: 'Anon key', type: 'password', placeholder: 'eyJ…', configKey: 'supabaseAnonKey' },
    ],
  },
  {
    id: 'vapid', label: 'Web Push (VAPID)', category: 'Push & MCP', usage: 'local',
    blurb: 'Public key is used in the client; the private key lives only on the gateway.',
    fields: [
      { env: 'VITE_VAPID_PUBLIC_KEY', label: 'VAPID public key', type: 'password', placeholder: 'B…', configKey: 'vapidPublicKey' },
      { env: 'MUSE_VAPID_PRIVATE_KEY', label: 'VAPID private key (gateway)', type: 'password', placeholder: 'kept on gateway' },
    ],
  },

  // ---- Model Providers (gateway .env) ----
  {
    id: 'anthropic', label: 'Anthropic (Claude)', category: 'Model Providers', usage: 'gateway',
    blurb: 'Official Claude / Claude Code worker lane.',
    fields: [{ env: 'ANTHROPIC_API_KEY', label: 'API key', type: 'password', placeholder: 'sk-ant-…' }],
  },
  {
    id: 'openai', label: 'OpenAI / Codex', category: 'Model Providers', usage: 'gateway',
    blurb: 'OpenAI + the Codex reviewer lane.',
    fields: [{ env: 'OPENAI_API_KEY', label: 'API key', type: 'password', placeholder: 'sk-…' }],
  },
  {
    id: 'google', label: 'Google AI (Gemini / AI Studio)', category: 'Model Providers', usage: 'gateway',
    blurb: 'Gemini API + AI Studio.',
    fields: [{ env: 'GEMINI_API_KEY', label: 'API key', type: 'password', placeholder: 'AIza…' }],
  },
  {
    id: 'openrouter', label: 'OpenRouter', category: 'Model Providers', usage: 'gateway',
    blurb: 'Hosted-free + paid model aggregator.',
    fields: [{ env: 'OPENROUTER_API_KEY', label: 'API key', type: 'password', placeholder: 'sk-or-…' }],
  },
  {
    id: 'novita', label: 'NovitaAI', category: 'Model Providers', usage: 'gateway',
    blurb: 'Hosted OSS inference.',
    fields: [{ env: 'NOVITA_API_KEY', label: 'API key', type: 'password' }],
  },
  {
    id: 'nim', label: 'NVIDIA NIM', category: 'Model Providers', usage: 'gateway',
    blurb: 'NVIDIA NIM inference microservices.',
    fields: [{ env: 'NIM_API_KEY', label: 'API key', type: 'password' }],
  },

  // ---- Messaging Bridges (gateway .env) ----
  {
    id: 'telegram', label: 'Telegram', category: 'Messaging Bridges', usage: 'gateway',
    blurb: 'Bot token from @BotFather.',
    fields: [{ env: 'TELEGRAM_BOT_TOKEN', label: 'Bot token', type: 'password', placeholder: '123456:ABC…' }],
  },
  {
    id: 'discord', label: 'Discord', category: 'Messaging Bridges', usage: 'gateway',
    blurb: 'Bot token from the Discord developer portal.',
    fields: [{ env: 'DISCORD_BOT_TOKEN', label: 'Bot token', type: 'password' }],
  },
  {
    id: 'slack', label: 'Slack', category: 'Messaging Bridges', usage: 'gateway',
    blurb: 'Bot + app-level tokens.',
    fields: [
      { env: 'SLACK_BOT_TOKEN', label: 'Bot token (xoxb-)', type: 'password', placeholder: 'xoxb-…' },
      { env: 'SLACK_APP_TOKEN', label: 'App token (xapp-)', type: 'password', placeholder: 'xapp-…' },
    ],
  },
  {
    id: 'whatsapp', label: 'WhatsApp', category: 'Messaging Bridges', usage: 'gateway',
    blurb: 'Cloud API bot token + phone-number id.',
    fields: [
      { env: 'WHATSAPP_BOT_TOKEN', label: 'Bot token', type: 'password' },
      { env: 'WHATSAPP_PHONE_NUMBER_ID', label: 'Phone number id', type: 'text' },
    ],
  },
  {
    id: 'signal', label: 'Signal', category: 'Messaging Bridges', usage: 'gateway',
    blurb: 'signal-cli REST account + URL.',
    fields: [
      { env: 'SIGNAL_ACCOUNT', label: 'Account (phone)', type: 'text', placeholder: '+1555…' },
      { env: 'SIGNAL_HTTP_URL', label: 'signal-cli URL', type: 'url', placeholder: 'http://127.0.0.1:8080' },
    ],
  },
  {
    id: 'email', label: 'Email (SMTP/IMAP)', category: 'Messaging Bridges', usage: 'gateway',
    blurb: 'Mailbox user + password / app-password.',
    fields: [
      { env: 'EMAIL_USER', label: 'Email address', type: 'text', placeholder: 'you@example.com' },
      { env: 'EMAIL_PASS', label: 'Password / app-password', type: 'password' },
    ],
  },

  // ---- Dev Integrations (gateway .env) ----
  {
    id: 'github', label: 'GitHub', category: 'Dev Integrations', usage: 'gateway',
    blurb: 'Personal access token for repo/PR operations.',
    fields: [{ env: 'GITHUB_TOKEN', label: 'Personal access token', type: 'password', placeholder: 'ghp_…' }],
  },
  {
    id: 'vercel', label: 'Vercel', category: 'Dev Integrations', usage: 'gateway',
    blurb: 'Deploy token.',
    fields: [{ env: 'VERCEL_TOKEN', label: 'Token', type: 'password' }],
  },
  {
    id: 'cloudflare', label: 'Cloudflare', category: 'Dev Integrations', usage: 'gateway',
    blurb: 'API token + account id for edge/DNS.',
    fields: [
      { env: 'CLOUDFLARE_API_TOKEN', label: 'API token', type: 'password' },
      { env: 'CLOUDFLARE_ACCOUNT_ID', label: 'Account id', type: 'text' },
    ],
  },

  // ---- MCP ----
  {
    id: 'mcp', label: 'MCP Server', category: 'Push & MCP', usage: 'gateway',
    blurb: 'Connect any MCP server for extended capabilities.',
    fields: [
      { env: 'MCP_SERVER_URL', label: 'Server URL', type: 'url', placeholder: 'https://… or stdio' },
      { env: 'MCP_SERVER_TOKEN', label: 'Auth token (optional)', type: 'password' },
    ],
  },
];

export function integrationsByCategory(cat: string): Integration[] {
  return INTEGRATIONS.filter((i) => i.category === cat);
}

/** All canonical ENV keys for gateway-usage fields (for the .env snippet). */
export function gatewayEnvKeys(): string[] {
  return INTEGRATIONS.filter((i) => i.usage === 'gateway').flatMap((i) => i.fields.map((f) => f.env))
    .concat(['MUSE_VAPID_PRIVATE_KEY']); // private VAPID also belongs on the gateway
}
