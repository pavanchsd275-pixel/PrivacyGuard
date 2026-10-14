// Splits `text` into plain pieces and entity pieces so the UI can highlight
// detected PII in place. Entities must be sorted by position; any entity that
// starts inside the previous one is skipped (fusion should prevent overlaps,
// this is just a safety net so the highlighter can never duplicate text).
export function buildSegments(text, entities) {
  const sorted = [...entities].sort((a, b) => a.start - b.start || b.end - a.end)
  const out = []
  let cursor = 0
  for (const e of sorted) {
    if (e.start < cursor) continue
    if (e.start > cursor) out.push({ text: text.slice(cursor, e.start) })
    out.push({ text: text.slice(e.start, e.end), entity: e })
    cursor = e.end
  }
  if (cursor < text.length) out.push({ text: text.slice(cursor) })
  return out
}
