export function base64ToDataUrl(base64: string, mime = 'image/png'): string {
  if (!base64) return ''
  if (base64.startsWith('data:')) return base64
  return `data:${mime};base64,${base64}`
}

export function audioBase64ToDataUrl(base64: string): string {
  if (!base64) return ''
  if (base64.startsWith('data:')) return base64
  return `data:audio/wav;base64,${base64}`
}

export function json<T = unknown>(data: T, status = 200) {
  return Response.json(data, { status })
}

export function err(message: string, status = 500) {
  return Response.json({ ok: false, error: message }, { status })
}
