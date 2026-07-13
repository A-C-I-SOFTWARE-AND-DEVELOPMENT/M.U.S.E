import assert from 'node:assert/strict';
import test from 'node:test';
import { UniverseApiError, UniverseClient } from './client.ts';

test('command preserves authoritative conflict evidence', async () => {
  const client = new UniverseClient(
    'http://127.0.0.1:8765',
    () => ({ Authorization: 'Bearer test' }),
    async () =>
      new Response(
        JSON.stringify({
          error: 'version_conflict',
          current_version: 4,
          correlation_id: 'corr_1',
        }),
        { status: 409, headers: { 'content-type': 'application/json' } },
      ),
  );

  await assert.rejects(
    client.command({ command_id: 'cmd_1' } as never),
    (error: unknown) =>
      error instanceof UniverseApiError &&
      error.kind === 'conflict' &&
      error.currentVersion === 4 &&
      error.correlationId === 'corr_1',
  );
});

test('event polling resumes after the acknowledged cursor', async () => {
  const urls: string[] = [];
  const client = new UniverseClient('http://muse', () => ({}), async (input) => {
    urls.push(String(input));
    return Response.json({ events: [], cursor: 91, realm_version: 7 });
  });

  const page = await client.events('rlm_local', 90);
  assert.equal(page.cursor, 91);
  assert.match(urls[0] ?? '', /since=90/);
});

test('requests omit ambient credentials and preserve only supplied bearer headers', async () => {
  const urls: string[] = [];
  const requests: RequestInit[] = [];
  const client = new UniverseClient(
    'http://muse',
    () => ({ Authorization: 'Bearer paired-device' }),
    async (input, init) => {
      urls.push(String(input));
      requests.push(init ?? {});
      return Response.json({ realms: [], cursor: 0, realm_version: 0 });
    },
  );

  await client.snapshot('rlm_local');
  assert.equal(requests[0]?.credentials, 'omit');
  assert.equal((requests[0]?.headers as Record<string, string>).Authorization, 'Bearer paired-device');
  assert.match(urls[0] ?? '', /actor_id=ply_owner/);
});

test('commands use the authoritative plural route and strip server-owned envelope fields', async () => {
  let url = '';
  let body: Record<string, unknown> = {};
  const client = new UniverseClient('http://muse', () => ({ Authorization: 'Bearer test' }), async (input, init) => {
    url = String(input);
    body = JSON.parse(String(init?.body)) as Record<string, unknown>;
    return Response.json({ event: {}, entity: {}, idempotent_replay: false });
  });

  await client.command({
    command_id: 'cmd_1', command_type: 'mission.create', realm_id: 'rlm_local', actor_id: 'ply_owner',
    stream_type: 'mission', stream_id: 'msn_1', expected_version: 0, payload: { id: 'msn_1' },
    authorization: { allowed: false, reason: 'server-owned', scopes: [], owner_gate: 'server-owned' },
    provenance: { source: 'client-draft', evidence: [], confidence: 1, signature: null },
    causation_id: 'cmd_1', correlation_id: 'cmd_1', simulation: true,
  });

  assert.match(url, /\/v1\/plugins\/muse-universe\/commands$/);
  assert.equal(body.command_id, 'cmd_1');
  assert.equal(body.simulation, true);
  assert.equal('authorization' in body, false);
  assert.equal('provenance' in body, false);
  assert.equal('stream_type' in body, false);
});
