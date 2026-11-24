// Client-side defang for names that arrive raw over the live socket (core defangs everything it serves itself).
export function defang(value: string): string {
  return value.replace(/^https:\/\//, 'hxxps://').replace(/^http:\/\//, 'hxxp://').replace(/\./g, '[.]')
}

const SCRIPTS: [RegExp, string][] = [
  [/\p{Script=Cyrillic}/u, 'Cyrillic'],
  [/\p{Script=Greek}/u, 'Greek'],
  [/\p{Script=Arabic}/u, 'Arabic'],
  [/\p{Script=Armenian}/u, 'Armenian'],
  [/\p{Script=Cherokee}/u, 'Cherokee'],
  [/\p{Script=Latin}/u, 'Latin (accented)'],
]

export interface Glyph {
  text: string
  odd: boolean
  title?: string
}

/** Splits a domain into runs, marking every non-ASCII character with its code point and script. */
export function glyphs(value: string): Glyph[] {
  const out: Glyph[] = []
  for (const char of value) {
    const code = char.codePointAt(0) ?? 0
    if (code < 0x80) {
      const last = out[out.length - 1]
      if (last && !last.odd) last.text += char
      else out.push({ text: char, odd: false })
      continue
    }
    const script = SCRIPTS.find(([pattern]) => pattern.test(char))?.[1] ?? 'non-ASCII'
    out.push({ text: char, odd: true, title: `U+${code.toString(16).toUpperCase().padStart(4, '0')} · ${script}` })
  }
  return out
}

export function hasLookalikes(value: string | null | undefined): boolean {
  return !!value && /[^\x00-\x7f]/.test(value)
}
