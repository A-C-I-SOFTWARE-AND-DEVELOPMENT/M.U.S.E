// ============================================================================
// Fusion-graph executor — the Mixture-of-Agents runner (MoA, arXiv 2406.04692).
//
// For each layer: run its legs IN PARALLEL (Promise.all). If passPreviousOutputs,
// each leg sees the prior layer's outputs as labeled context. After all layers,
// an optional aggregator SYNTHESIZES (not just ranks) the proposals into one
// answer. route/ensemble/pipeline/graph are all just shapes of this.
//
// Transport-agnostic: leg execution is delegated to completeText(model, msgs)
// passed in from the gateway (official provider APIs, your keys).
// ============================================================================

const AGG_SYSTEM =
  'You are an expert aggregator. You have been given the user task and several ' +
  'candidate responses from different models. Synthesize a single, superior ' +
  'answer: combine the strongest, correct elements; resolve contradictions; ' +
  'fix errors; do not merely pick one. Respond only with the final answer.';

function labeledProposals(legResults) {
  return legResults
    .map((r, i) => `[Response ${i + 1}${r.error ? ' (failed)' : ''}]\n${r.error ? '(no output)' : r.content}`)
    .join('\n\n');
}

/** Pure shape check shared with the PWA's fusionTypes.shapeOf (kept in sync). */
export function shapeOf(def) {
  const layers = def.layers.length;
  const maxLegs = Math.max(0, ...def.layers.map((l) => l.legs.length));
  if (layers <= 1 && maxLegs <= 1 && !def.aggregator) return 'route';
  if (layers <= 1 && def.aggregator) return 'ensemble';
  if (layers > 1 && maxLegs <= 1) return 'pipeline';
  return 'graph';
}

// Synchronous FNV-1a content hash (mirrors the PWA attestationHash style).
export function attestationHash(obj) {
  const s = JSON.stringify(obj);
  let h1 = 0x811c9dc5, h2 = 0xcbf29ce4;
  for (let i = 0; i < s.length; i++) {
    const c = s.charCodeAt(i);
    h1 = Math.imul(h1 ^ c, 0x01000193) >>> 0;
    h2 = Math.imul(h2 ^ ((c << 1) | 1), 0x01000193) >>> 0;
  }
  return h1.toString(16).padStart(8, '0') + h2.toString(16).padStart(8, '0');
}

/**
 * Run the fusion graph. Writes an OpenAI-shaped response (streaming or not) to
 * `res`. In transparent mode, proposer outputs are emitted as tagged frames
 * before the aggregated answer; in unified mode only the final answer streams.
 */
export async function runFusion({ fusion, messages, stream, res, completeText, json, sseHeaders }) {
  const userMessages = messages;
  const allLegs = [];
  let priorOutputs = [];

  for (let li = 0; li < fusion.layers.length; li++) {
    const layer = fusion.layers[li];
    const ctxPrefix =
      layer.passPreviousOutputs && priorOutputs.length
        ? [{ role: 'user', content: `Prior candidate responses to build on / critique:\n\n${labeledProposals(priorOutputs)}` }]
        : [];

    const results = await Promise.all(
      layer.legs.map(async (leg) => {
        const started = Date.now();
        try {
          const content = await completeText(leg.model, [...userMessages, ...ctxPrefix], {
            temperature: leg.temperature,
            system: leg.systemHint,
          });
          return { model: leg.model, role: leg.role || 'proposer', layer: li, content, latencyMs: Date.now() - started };
        } catch (e) {
          return { model: leg.model, role: leg.role || 'proposer', layer: li, content: '', error: String(e?.message ?? e), latencyMs: Date.now() - started };
        }
      }),
    );
    allLegs.push(...results);
    priorOutputs = results;
  }

  // Aggregate (synthesize) unless this is a pure route / a pipeline whose last
  // layer already finalized.
  let finalText;
  if (fusion.aggregator) {
    const aggInput = [
      ...userMessages,
      { role: 'user', content: `Candidate responses:\n\n${labeledProposals(priorOutputs)}` },
    ];
    finalText = await completeText(fusion.aggregator.model, aggInput, {
      temperature: fusion.aggregator.temperature ?? 0.3,
      system: fusion.aggregator.systemHint || AGG_SYSTEM,
    });
    allLegs.push({ model: fusion.aggregator.model, role: 'aggregator', layer: fusion.layers.length, content: finalText });
  } else {
    // No aggregator: the final answer is the last layer's (single) output.
    finalText = priorOutputs.map((r) => r.content).filter(Boolean).join('\n\n');
  }

  const attestation = fusion.attest
    ? `fusion:${attestationHash({ name: fusion.name, mode: fusion.mode, models: allLegs.map((l) => l.model), out: finalText })}`
    : null;

  const id = `fusion-${Date.now()}`;
  const meta = { fusion_id: fusion.id, fusion_name: fusion.name, mode: shapeOf(fusion), attestation, legs: allLegs.map((l) => ({ model: l.model, role: l.role, layer: l.layer, error: l.error, content: fusion.displayMode === 'transparent' ? l.content : undefined })) };

  if (!stream) {
    return json(res, 200, {
      id, object: 'fusion.completion', model: fusion.name,
      choices: [{ index: 0, message: { role: 'assistant', content: finalText }, finish_reason: 'stop' }],
      fusion: meta,
    });
  }

  sseHeaders(res);
  // Transparent mode: emit each proposer's output as a tagged frame first.
  if (fusion.displayMode === 'transparent') {
    for (const l of allLegs) {
      if (l.role === 'aggregator') continue;
      res.write(`data: ${JSON.stringify({ id, object: 'fusion.leg', leg: { model: l.model, role: l.role, layer: l.layer, content: l.content, error: l.error } })}\n\n`);
    }
  }
  // Stream the final answer in word chunks (already computed; chunk for UX).
  const words = finalText.split(/(\s+)/);
  for (const w of words) {
    res.write(`data: ${JSON.stringify({ id, object: 'chat.completion.chunk', model: fusion.name, choices: [{ index: 0, delta: { content: w } }] })}\n\n`);
  }
  res.write(`data: ${JSON.stringify({ id, object: 'fusion.done', fusion: meta })}\n\n`);
  res.write('data: [DONE]\n\n');
  res.end();
}
