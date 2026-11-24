import { describe, expect, it } from 'vitest'
import {
  adaptAudit,
  adaptCampaign,
  adaptCampaigns,
  adaptCase,
  adaptConfirmResult,
  adaptEvent,
  adaptEvidence,
  adaptGraph,
  adaptHelplines,
  adaptHunterFeed,
  adaptPacks,
  adaptQueue,
  adaptRefused,
  adaptRequest,
  adaptResponse,
  adaptTakedownCreated,
  adaptTakedownList,
  adaptVerify,
} from './adapt'
import { backend as b } from './adapt.fixtures'
import { defang } from './defang'

describe('queue', () => {
  const { cases } = adaptQueue(b.queue, '2026-11-24T16:00:00Z')

  it('keeps the raw domain and never the defanged display', () => {
    expect(cases[0].domain).toBe('capolice.live')
    expect(JSON.stringify(cases)).not.toContain('[.]')
    expect(defang(cases[0].domain)).toBe(b.queue.cases[0].display)
  })

  it('maps state, score, brand and counts; age comes from last_seen', () => {
    expect(cases[0]).toMatchObject({ state: 'open', score: 100, brand: 'Abu Dhabi Police', reports: 0, hits: 0, sources: ['hunter'] })
    expect(cases[0].first_seen).toBe(b.queue.cases[0].last_seen)
    expect(cases[0].evidence_id).toBe('ev_dd8f608abc31419589a86732')
  })

  it('handles a row without evidence', () => {
    const bare = cases.find((c) => c.evidence_id === null)
    expect(bare).toBeDefined()
    expect(bare?.campaign_id).toBeNull()
  })

  it('routes by path', () => {
    expect(adaptResponse('/v1/admin/queue?state=open', b.queue)).toMatchObject({ cases: expect.any(Array) })
  })
})

describe('case detail', () => {
  const open = adaptCase(b.caseOpen)
  const rich = adaptCase(b.caseRich)

  it('renames infra, history and report notes and takes the score from the latest check', () => {
    expect(open.score).toBe(100)
    expect(open.verdict).toBe('block')
    expect(open.brand).toBe('Abu Dhabi Police')
    expect(open.url).toBe('https://capolice.live/')
    expect(open.infrastructure.registrar).toBe('Spaceship, Inc.')
    expect(open.infrastructure.name_servers).toEqual(b.caseOpen.infra.ns)
    expect(open.infrastructure.ip).toBe(b.caseOpen.infra.a[0])
    expect(open.checks).toHaveLength(1)
    expect(open.report_notes).toEqual([])
    expect(open.summary).toBeNull()
  })

  it('uses report_count and hit_count, not the per-channel hits map', () => {
    expect(rich.reports).toBe(1)
    expect(rich.hits).toBe(3)
    expect(rich.report_notes).toEqual([{ id: 'r_0123456789ab', note: 'came by SMS', created_at: '2026-11-24T10:00:00+00:00' }])
  })

  it('keeps the title, reasons and lead time', () => {
    expect(open.title).toBe('Index of /')
    expect(open.reasons[0]).toMatchObject({ code: 'LOOKALIKE', weight: 35, source: 'kartoshka' })
    expect(open.reasons[0].ar).toContain('adpolice.gov.ae')
    expect(open.lead_time).toEqual({ gsb: { state: 'not_polled', at_least_hours: null }, vt: { state: 'not_polled', at_least_hours: null } })
    expect(rich.lead_time?.gsb).toEqual({ state: 'ahead', at_least_hours: 30 })
    expect(rich.lead_time?.vt).toEqual({ state: 'hit', at_least_hours: 20 })
  })

  it('shows the applied weight of a capped credential reason', () => {
    expect(rich.reasons[0].weight).toBe(20)
    expect(rich.reasons[0]).not.toHaveProperty('weight_full')
  })

  it('reads network facts from the asn record, and hides them behind a proxy', () => {
    expect(rich.infrastructure).toMatchObject({ ip: '203.0.113.5', ip_owner: 'Hoster BV', ip_network: '203.0.113.0/24', registered_at: '2026-11-20T00:00:00Z' })
    const proxied = adaptCase({ ...b.caseRich, location: { ...b.caseRich.location, behind_proxy: true, hosted_in: null, network_owner: null } })
    expect(proxied.infrastructure.ip_owner).toBeNull()
    expect(proxied.location?.behind_proxy).toBe(true)
  })

  it('maps reviews (the backend has no review id) and the four states', () => {
    expect(rich.state).toBe('confirmed')
    expect(rich.reviews).toEqual([{ id: 0, decision: 'confirm', reason: null, reviewer: 'Demo Officer', reviewed_at: '2026-11-24T11:00:00+00:00' }])
    expect(adaptCase({ ...b.caseOpen, state: 'auto_confirmed' }).state).toBe('auto_confirmed')
    expect(adaptCase({ ...b.caseOpen, state: 'rejected' }).state).toBe('rejected')
  })

  it('does not carry the defanged display fields', () => {
    expect(JSON.stringify(open)).not.toContain('[.]')
    expect(JSON.stringify(open)).not.toContain('hxxp')
  })

  it('carries the screenshot flag and evidence id', () => {
    expect(open.has_screenshot).toBe(true)
    expect(open.evidence_id).toBe('ev_dd8f608abc31419589a86732')
  })

  it('keeps the evidence export fields only', () => {
    const exported = adaptEvidence(b.evidence)
    expect(Object.keys(exported).sort()).toEqual(['check_id', 'created_at', 'hash', 'id', 'prev_hash', 'seq'])
    expect(exported.seq).toBe(30)
  })
})

describe('verify and audit', () => {
  it('maps the chain check', () => {
    expect(adaptVerify({ ok: true, intact: true, rows: 76, count: 76, broken_at: null, first_broken: null, message: 'chain intact' })).toEqual({
      count: 76,
      intact: true,
      first_broken: null,
      message: 'chain intact',
    })
    const broken = adaptVerify({ intact: false, count: 5, first_broken: { id: 'ev_1', seq: 5, reason: 'prev_hash_mismatch' } })
    expect(broken.first_broken).toEqual({ id: 'ev_1', seq: 5, reason: 'prev_hash_mismatch' })
    expect(broken.message).toContain('prev_hash_mismatch')
  })

  it('renames feat/app audit actions to the ones the console labels and counts', () => {
    const { entries } = adaptAudit(b.audit)
    expect(entries.map((e) => e.action)).toEqual(['case.confirm', 'watchlist.add', 'case.auto_confirm'])
    expect(entries[0]).toMatchObject({ actor: 'Demo Officer', target: 'detail.example', reason: null })
    expect(entries[0]).not.toHaveProperty('target_kind')
  })
})

describe('helplines', () => {
  it('keeps the table columns', () => {
    expect(adaptHelplines(b.helplines).numbers[0]).toEqual({
      phone: '+971500000000',
      brand: 'TAMM',
      source: 'page',
      domain: 'scam.example',
      first_seen: '2026-11-24T10:00:00Z',
      confirmed: true,
    })
  })
})

describe('campaigns', () => {
  it('maps the list, with suspected and confirmed to main\'s status values', () => {
    const { campaigns } = adaptCampaigns(b.campaigns)
    expect(campaigns[0]).toMatchObject({ status: 'suspected', brand: null, domains: { total: 9, confirmed: 0 }, active: true })
    const confirmed = adaptCampaigns({ campaigns: [{ ...b.campaigns.campaigns[0], status: 'confirmed', confirmed_count: 2 }] }).campaigns[0]
    expect(confirmed.status).toBe('campaign')
    expect(confirmed.domains.confirmed).toBe(2)
  })

  it('maps the detail: domains keep the raw name and the tick advice, entities become shared', () => {
    const detail = adaptCampaign(b.campaign)
    expect(detail.domains[0]).toMatchObject({ domain: 'dg41e.top', score: 40, excluded: null, tick: false })
    expect(JSON.stringify(detail)).not.toContain('[.]')
    expect(detail.shared[0]).toEqual({ kind: 'ip', value: '154.215.0.19', strength: 'strong', domain_count: 9 })
    expect(detail.locations).toEqual([])
  })

  it('turns the flat graph into cytoscape data, handing the view raw domain labels', () => {
    const graph = adaptGraph(b.graph)
    const domain = graph.nodes.find((n) => n.data.kind === 'domain')
    expect(domain?.data.label).toBe(domain?.data.id.slice(2))
    expect(domain?.data.label).not.toContain('[.]')
    expect(graph.edges[0].data).toMatchObject({ source: b.graph.edges[0].source, target: b.graph.edges[0].target, strength: 'strong' })
    expect(graph.edges[0].data.id).toBeTruthy()
  })

  it('drops excluded edges', () => {
    const graph = adaptGraph({ nodes: [], edges: [{ source: 'd:a.top', target: 'ip:1.1.1.1', strength: 'strong', excluded: true }] })
    expect(graph.edges).toEqual([])
  })

  it('maps the bulk confirm answer', () => {
    expect(adaptConfirmResult(b.confirmResult)).toEqual({
      confirmed: ['dg41e.top'],
      skipped: [{ domain: 'x.example', reason: 'already confirmed' }],
    })
  })
})

describe('takedowns', () => {
  it('groups one request per domain and recipient into one pack per recipient', () => {
    const { packs } = adaptTakedownList(b.takedowns)
    expect(packs).toHaveLength(2)
    expect(packs[0]).toMatchObject({ id: 't_1', recipient_kind: 'registrar', domains: ['a.example', 'b.example'], sent_at: null })
    expect(packs[1]).toMatchObject({ id: 't_3', recipient: 'https://host.example/abuse', domains: ['a.example'] })
  })

  it('reports a pack as sent when its requests are', () => {
    const sent = adaptPacks(b.takedowns.requests.map((r: object) => ({ ...r, status: 'sent', sent_at: '2026-11-24T13:00:00+00:00', sent_by: 'Demo Officer' })))
    expect(sent[0]).toMatchObject({ sent_at: '2026-11-24T13:00:00+00:00', sent_by: 'Demo Officer' })
  })

  it('maps a created answer, with refusals listed', () => {
    const made = adaptTakedownCreated(b.takedownCreated)
    expect(made.packs).toHaveLength(1)
    expect(made.refused).toEqual([{ domain: 'c.example', reason: 'no evidence record' }])
  })

  it('reads the 409 body', () => {
    expect(adaptRefused(b.refused409)).toEqual([{ domain: 'c.example', reason: 'not confirmed by an officer' }])
    expect(adaptRefused(null)).toEqual([])
  })

  it('sends reviewer where main sent generated_by and sent_by', () => {
    expect(adaptRequest('/v1/admin/takedowns', { domains: ['a.example'], generated_by: 'Demo Officer' })).toEqual({ domains: ['a.example'], reviewer: 'Demo Officer' })
    expect(adaptRequest('/v1/admin/takedowns/t_1/sent', { sent_by: 'Demo Officer' })).toEqual({ reviewer: 'Demo Officer' })
    expect(adaptRequest('/v1/review/ev_1', { decision: 'confirm', reason: null, reviewer: 'Demo Officer' })).toEqual({ decision: 'confirm', reason: null, reviewer: 'Demo Officer' })
  })

  it('tells GET and POST on the same path apart', () => {
    expect(adaptResponse('/v1/admin/takedowns', b.takedowns)).toHaveProperty('packs')
    expect(adaptResponse('/v1/admin/takedowns', b.takedownCreated, 'POST')).toHaveProperty('without_recipient')
  })
})

describe('hunter feed and live events', () => {
  it('maps feed entries and shares keys with the live candidate event', () => {
    const { rows } = adaptHunterFeed(b.feed)
    const first = b.feed.entries[0]
    expect(rows[0]).toMatchObject({ type: 'hunter.candidate', domain: first.domain, brand: first.brand_id, verdict: first.verdict, score: first.score })
    expect(JSON.stringify(rows)).not.toContain('[.]')
    const live = adaptEvent({ type: 'hunter.candidate', at: 'x', data: { source: first.source, domain: first.domain, brand_id: first.brand_id, first_seen: first.first_seen } })
    expect(live?.key).toBe(rows[0].key)
    expect(adaptEvent(b.events.candidate)?.type).toBe('hunter.candidate')
  })

  it('maps check.verdict, case.reviewed, brand.spike, watchlist.woke and campaign.new_domain', () => {
    expect(adaptEvent(b.events.verdict)).toMatchObject({ key: 'check.verdict:c_1', type: 'check.verdict', domain: 'capolice.live', verdict: 'block', score: 100, brand: 'Abu Dhabi Police' })
    expect(adaptEvent(b.events.reviewed)).toMatchObject({ type: 'case.reviewed', domain: 'capolice.live', verdict: 'confirm' })
    expect(adaptEvent(b.events.spike)).toMatchObject({ type: 'brand.spike', domain: null, brand: 'adcb' })
    expect(adaptEvent(b.events.woke)).toMatchObject({ type: 'watchlist.woke', domain: 'parked.example' })
    expect(adaptEvent(b.events.newDomain)).toMatchObject({ type: 'campaign.new_domain', domain: 'new.example' })
  })

  it('ignores hello, main-only names and junk', () => {
    expect(adaptEvent(b.events.hello)).toBeNull()
    expect(adaptEvent({ type: 'check.completed', at: 'x', data: { check_id: 'c' } })).toBeNull()
    expect(adaptEvent({ type: 'takedown.offline', at: 'x', data: {} })).toBeNull()
  })
})

it('passes unknown routes through untouched', () => {
  const body = { anything: 1 }
  expect(adaptResponse('/v1/admin/cases/x.example/recheck', body, 'POST')).toBe(body)
})
