// @vitest-environment node
import { mkdtemp, readdir, readFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { build } from 'vite'
import { afterEach, describe, expect, it, vi } from 'vitest'

const SENTINEL = 'sentinel-write-token-7f3a91'

async function filesUnder(dir: string): Promise<string[]> {
  const entries = await readdir(dir, { withFileTypes: true })
  const nested = await Promise.all(entries.map((e) => (e.isDirectory() ? filesUnder(path.join(dir, e.name)) : [path.join(dir, e.name)])))
  return nested.flat()
}

describe('production bundle', () => {
  it('carries neither the write token nor the variable that used to hold it', async () => {
    const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
    const outDir = await mkdtemp(path.join(tmpdir(), 'console-bundle-'))
    process.env.VITE_CORE_WRITE_TOKEN = SENTINEL
    try {
      await build({ root, logLevel: 'silent', build: { outDir, emptyOutDir: true } })
      const files = await filesUnder(outDir)
      expect(files.length).toBeGreaterThan(0)
      for (const file of files) {
        const text = await readFile(file, 'utf8')
        expect(text, file).not.toContain(SENTINEL)
        expect(text, file).not.toContain('VITE_CORE_WRITE_TOKEN')
      }
    } finally {
      delete process.env.VITE_CORE_WRITE_TOKEN
      await rm(outDir, { recursive: true, force: true })
    }
  }, 120_000)
})

describe('signIn', () => {
  const store = new Map<string, string>()

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.resetModules()
    store.clear()
  })

  async function session(status: number | Error) {
    vi.stubGlobal('sessionStorage', {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => void store.set(key, value),
      removeItem: (key: string) => void store.delete(key),
    })
    const fetchStub = vi.fn(() => (status instanceof Error ? Promise.reject(status) : Promise.resolve(new Response('{}', { status }))))
    vi.stubGlobal('fetch', fetchStub)
    return { fetchStub, ...(await import('./session')) }
  }

  it('stores the code and the officer when core accepts it', async () => {
    const { fetchStub, signIn, accessCode, officer } = await session(200)
    expect(await signIn('good-code')).toBeNull()
    expect(fetchStub).toHaveBeenCalledWith('/api/v1/admin/health', { headers: { Authorization: 'Bearer good-code' } })
    expect(accessCode()).toBe('good-code')
    expect(officer.value?.role).toBe('officer')
    expect(store.get('access_code')).toBe('good-code')
  })

  it('says the code was not accepted on 401 and stores nothing', async () => {
    const { signIn, accessCode, officer } = await session(401)
    expect(await signIn('bad-code')).toBe('Access code not accepted')
    expect(accessCode()).toBe('')
    expect(officer.value).toBeNull()
    expect(store.size).toBe(0)
  })

  it('asks the officer to wait on 429', async () => {
    const { signIn } = await session(429)
    expect(await signIn('any-code')).toBe('Too many attempts. Try again in a few minutes.')
  })

  it('refuses an empty code without a request', async () => {
    const { fetchStub, signIn } = await session(200)
    expect(await signIn('  ')).toBe('Enter the access code')
    expect(fetchStub).not.toHaveBeenCalled()
  })

  it('reports a network error on its own', async () => {
    const { signIn } = await session(new TypeError('offline'))
    expect(await signIn('any-code')).toBe('Could not reach the server. Check the connection and try again.')
  })
})
