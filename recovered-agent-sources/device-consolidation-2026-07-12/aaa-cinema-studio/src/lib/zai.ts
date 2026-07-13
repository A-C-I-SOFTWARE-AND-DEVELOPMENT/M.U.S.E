import ZAI from 'z-ai-web-dev-sdk'

// Singleton ZAI client for server-side AI calls.
let _zai: ZAI | null = null
let _pending: Promise<ZAI> | null = null

export async function getZAI(): Promise<ZAI> {
  if (_zai) return _zai
  if (_pending) return _pending
  _pending = ZAI.create().then((client) => {
    _zai = client
    _pending = null
    return client
  })
  return _pending
}

// ---- Typed wrappers -------------------------------------------------------

export interface LLMOptions {
  system?: string
  temperature?: number
  maxTokens?: number
  thinking?: 'enabled' | 'disabled'
}

export async function llm(prompt: string, opts: LLMOptions = {}): Promise<string> {
  const zai = await getZAI()
  const messages: { role: 'system' | 'user' | 'assistant'; content: string }[] = []
  if (opts.system) messages.push({ role: 'system', content: opts.system })
  messages.push({ role: 'user', content: prompt })
  const res = await zai.chat.completions.create({
    messages,
    temperature: opts.temperature,
    max_tokens: opts.maxTokens,
    thinking: opts.thinking ? { type: opts.thinking } : undefined,
  } as any)
  return res?.choices?.[0]?.message?.content ?? ''
}

export async function vision(prompt: string, imageUrl: string): Promise<string> {
  const zai = await getZAI()
  const res = await zai.chat.completions.createVision({
    model: 'glm-4.5v',
    messages: [
      {
        role: 'user',
        content: [
          { type: 'text', text: prompt },
          { type: 'image_url', image_url: { url: imageUrl } },
        ],
      },
    ],
  } as any)
  return res?.choices?.[0]?.message?.content ?? ''
}

export type ImageSize =
  | '1024x1024'
  | '768x1344'
  | '864x1152'
  | '1344x768'
  | '1152x864'
  | '1440x720'
  | '720x1440'

export async function image(prompt: string, size: ImageSize = '1344x768'): Promise<string> {
  const zai = await getZAI()
  const res = await zai.images.generations.create({ prompt, size })
  return res?.data?.[0]?.base64 ?? ''
}

export async function tts(
  text: string,
  voice = 'tongtong',
  speed = 1,
): Promise<string> {
  const zai = await getZAI()
  // The TTS endpoint returns a fetch Response whose body is the raw audio bytes
  // (valid response_format values are 'wav' and 'pcm'; 'mp3' is rejected).
  // The only documented voice is 'tongtong' — we route all directed profiles
  // through it and let the caller's speed convey tonal variation.
  const response: any = await zai.audio.tts.create({
    input: text,
    voice: 'tongtong',
    speed,
    response_format: 'wav',
    stream: false,
  })
  const arrayBuffer: ArrayBuffer = await response.arrayBuffer()
  const buf = Buffer.from(new Uint8Array(arrayBuffer))
  return buf.toString('base64')
}
