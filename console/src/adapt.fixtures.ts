// Backend-shaped data. Queue, case, campaign, graph, feed and evidence are captured from the running core; audit, takedown,
// confirm, helplines, events and the enriched case follow the response builders in core/app and the backend tests.
/* eslint-disable */
export const backend: Record<string, any> = {
 "queue": {
  "total": 155,
  "cases": [
   {
    "domain": "capolice.live",
    "display": "capolice[.]live",
    "state": "open",
    "priority": 0.0,
    "rank_score": 99.22,
    "score": 100,
    "band": "block",
    "verdict": "block",
    "stage": "deep",
    "brand": "Abu Dhabi Police",
    "brand_id": "adpolice",
    "check_id": "c_cf1f42874549463ba2b73ee8d10aaeb3",
    "evidence_id": "ev_dd8f608abc31419589a86732",
    "campaign_id": null,
    "preview": "/v1/preview/ev_dd8f608abc31419589a86732.png",
    "reports": 0,
    "hits": 0,
    "checks": 2,
    "sources": [
     "hunter"
    ],
    "feeds": [
     "ct"
    ],
    "status": null,
    "last_seen": "2026-11-24T14:53:34.114736+00:00",
    "top_reasons": [
     {
      "code": "LOOKALIKE",
      "weight": 35,
      "en": "Domain looks like adpolice.gov.ae but differs by 2 character(s)"
     },
     {
      "code": "DOMAIN_AGE",
      "weight": 25,
      "en": "Registered less than an hour ago"
     },
     {
      "code": "GOV_LOOKALIKE",
      "weight": 20,
      "en": "Domain imitates a government or police address but is not under .gov.ae"
     }
    ]
   },
   {
    "domain": "3dewa.online",
    "display": "3dewa[.]online",
    "state": "open",
    "priority": 0.0,
    "rank_score": 99.06,
    "score": 100,
    "band": "block",
    "verdict": "block",
    "stage": "deep",
    "brand": "DEWA",
    "brand_id": "dewa",
    "check_id": "c_46fa819272c243b5b949320225c2c351",
    "evidence_id": "ev_0c5f5ab7efcc404790955069",
    "campaign_id": null,
    "preview": null,
    "reports": 0,
    "hits": 0,
    "checks": 1,
    "sources": [
     "hunter"
    ],
    "feeds": [
     "nrd"
    ],
    "status": null,
    "last_seen": "2026-11-24T14:50:07.387408+00:00",
    "top_reasons": [
     {
      "code": "BRAND_IN_DOMAIN",
      "weight": 40,
      "en": "Domain uses 'dewa' but is not an official DEWA domain"
     },
     {
      "code": "DOMAIN_AGE",
      "weight": 25,
      "en": "Registered less than an hour ago"
     },
     {
      "code": "BRAND_ACTION",
      "weight": 15,
      "en": "A DEWA name is combined with a payment or login word"
     }
    ]
   },
   {
    "domain": "icp-chatbot-fr.pages.dev",
    "display": "icp-chatbot-fr[.]pages[.]dev",
    "state": "open",
    "priority": 0.0,
    "rank_score": 90.98,
    "score": 70,
    "band": "warn",
    "verdict": "warn",
    "stage": "fast",
    "brand": "ICP",
    "brand_id": "icp",
    "check_id": "c_9d12511a888248f78b80b9ffa34b8eb9",
    "evidence_id": null,
    "campaign_id": null,
    "preview": null,
    "reports": 0,
    "hits": 0,
    "checks": 1,
    "sources": [
     "hunter"
    ],
    "feeds": [
     "ct"
    ],
    "status": null,
    "last_seen": "2026-11-24T15:09:18.832181+00:00",
    "top_reasons": [
     {
      "code": "BRAND_IN_DOMAIN",
      "weight": 40,
      "en": "Domain uses 'icp' but is not an official ICP domain"
     },
     {
      "code": "FREE_HOSTING",
      "weight": 20,
      "en": "Page is on a free hosting service (pages.dev)"
     },
     {
      "code": "FRESH_CERT",
      "weight": 10,
      "en": "First TLS certificate issued less than an hour ago"
     }
    ]
   }
  ],
  "next_cursor": "50"
 },
 "caseOpen": {
  "domain": "capolice.live",
  "display": "capolice[.]live",
  "state": "open",
  "status": null,
  "status_source": null,
  "confirmed_by": null,
  "url": "https://capolice.live/",
  "final_url": null,
  "title": "Index of /",
  "reasons": [
   {
    "code": "LOOKALIKE",
    "weight": 35,
    "source": "kartoshka",
    "en": "Domain looks like adpolice.gov.ae but differs by 2 character(s)",
    "ar": "النطاق يشبه adpolice.gov.ae لكنه يختلف بـ2 حرف"
   },
   {
    "code": "RISKY_TLD",
    "weight": 15,
    "source": "kartoshka",
    "en": "The .live ending is common on scam sites",
    "ar": "النهاية ‎.live‎ شائعة في مواقع الاحتيال"
   },
   {
    "code": "GOV_LOOKALIKE",
    "weight": 20,
    "source": "kartoshka",
    "en": "Domain imitates a government or police address but is not under .gov.ae",
    "ar": "النطاق يقلّد عنوانًا حكوميًا أو شرطيًا لكنه ليس تحت ‎.gov.ae‎"
   },
   {
    "code": "FRESH_CERT",
    "weight": 10,
    "source": "ct",
    "en": "First TLS certificate issued less than an hour ago",
    "ar": "صدرت أول شهادة أمان قبل أقل من ساعة"
   },
   {
    "code": "DOMAIN_AGE",
    "weight": 25,
    "source": "rdap",
    "en": "Registered less than an hour ago",
    "ar": "تم تسجيله قبل أقل من ساعة"
   }
  ],
  "evidence_id": "ev_dd8f608abc31419589a86732",
  "campaign_id": null,
  "sources": [
   "hunter"
  ],
  "report_count": 0,
  "hit_count": 0,
  "first_seen": "2026-11-24T14:53:33.254837+00:00",
  "last_seen": "2026-11-24T14:53:34.114736+00:00",
  "rank": 0.0,
  "has_screenshot": true,
  "location": {
   "hosted_in": null,
   "registered_through": "Spaceship, Inc.",
   "network_owner": null,
   "behind_proxy": false
  },
  "lead_time": {
   "gsb": {
    "state": "not_polled",
    "at_least_hours": null
   },
   "vt": {
    "state": "not_polled",
    "at_least_hours": null
   }
  },
  "latest": {
   "check_id": "c_cf1f42874549463ba2b73ee8d10aaeb3",
   "url": "https://capolice.live/",
   "display_url": "hxxps://capolice[.]live/",
   "final_url": null,
   "display_final_url": null,
   "verdict": "block",
   "score": 100,
   "stage": "deep",
   "brand": "Abu Dhabi Police",
   "brand_id": "adpolice",
   "reasons": [],
   "sources": [],
   "features": {},
   "safe_action": {
    "label_en": "Go to the official Abu Dhabi Police website",
    "label_ar": "الانتقال إلى الموقع الرسمي",
    "url": "https://adpolice.gov.ae"
   },
   "deep_status": "done",
   "evidence_id": "ev_dd8f608abc31419589a86732",
   "preview": {
    "screenshot": "/v1/preview/ev_dd8f608abc31419589a86732.png",
    "asks_for": []
   },
   "created_at": "2026-11-24T14:53:33.259773+00:00"
  },
  "page": null,
  "infra": {
   "a": [
    "66.29.148.113"
   ],
   "aaaa": [],
   "asn": {},
   "ct": null,
   "mx": [
    "mx1.spacemail.com",
    "mx2.spacemail.com"
   ],
   "ns": [
    "launch1.spaceship.net",
    "launch2.spaceship.net"
   ],
   "rdap": {
    "abuse_emails": [
     "abuse@spaceship.com"
    ],
    "found": true,
    "nameservers": [
     "launch1.spaceship.net",
     "launch2.spaceship.net"
    ],
    "registered": "2026-11-24T14:36:33.507Z",
    "registrar": "Spaceship, Inc.",
    "status": [
     "client transfer prohibited",
     "add period"
    ]
   }
  },
  "visual": null,
  "kit": null,
  "discovery": [
   {
    "source": "ct",
    "first_seen": "2026-11-24T14:53:33.254837+00:00",
    "url": "https://capolice.live/",
    "display_url": "hxxps://capolice[.]live/",
    "brand_id": "adpolice"
   }
  ],
  "reports": {
   "count": 0,
   "notes": []
  },
  "hits": {},
  "campaign": null,
  "watchlist": null,
  "reviews": [],
  "history": [
   {
    "check_id": "c_b4dba955a5c54a18b4c543c3498ae5ef",
    "source": "hunter",
    "verdict": "block",
    "score": 100,
    "stage": "deep",
    "at": "2026-11-24T14:53:34.114736+00:00"
   }
  ]
 },
 "caseRich": {
  "domain": "capolice.live",
  "display": "capolice[.]live",
  "state": "confirmed",
  "status": null,
  "status_source": null,
  "confirmed_by": null,
  "url": "https://capolice.live/",
  "final_url": null,
  "title": "Index of /",
  "reasons": [
   {
    "code": "CREDENTIAL_FORM",
    "weight": 20,
    "weight_full": 30,
    "capped": true,
    "source": "sandbox",
    "en": "Page asks for a password",
    "ar": "الصفحة تطلب كلمة مرور"
   }
  ],
  "evidence_id": "ev_dd8f608abc31419589a86732",
  "campaign_id": null,
  "sources": [
   "hunter"
  ],
  "report_count": 1,
  "hit_count": 3,
  "first_seen": "2026-11-24T14:53:33.254837+00:00",
  "last_seen": "2026-11-24T14:53:34.114736+00:00",
  "rank": 0.0,
  "has_screenshot": true,
  "location": {
   "hosted_in": "NL",
   "registered_through": "Example Registrar",
   "network_owner": "Hoster BV",
   "behind_proxy": false
  },
  "lead_time": {
   "gsb": {
    "state": "ahead",
    "at_least_hours": 30
   },
   "vt": {
    "state": "hit",
    "at_least_hours": 20
   }
  },
  "latest": {
   "check_id": "c_cf1f42874549463ba2b73ee8d10aaeb3",
   "url": "https://capolice.live/",
   "display_url": "hxxps://capolice[.]live/",
   "final_url": null,
   "display_final_url": null,
   "verdict": "block",
   "score": 100,
   "stage": "deep",
   "brand": "Abu Dhabi Police",
   "brand_id": "adpolice",
   "reasons": [],
   "sources": [],
   "features": {},
   "safe_action": {
    "label_en": "Go to the official Abu Dhabi Police website",
    "label_ar": "الانتقال إلى الموقع الرسمي",
    "url": "https://adpolice.gov.ae"
   },
   "deep_status": "done",
   "evidence_id": "ev_dd8f608abc31419589a86732",
   "preview": {
    "screenshot": "/v1/preview/ev_dd8f608abc31419589a86732.png",
    "asks_for": []
   },
   "created_at": "2026-11-24T14:53:33.259773+00:00"
  },
  "page": null,
  "infra": {
   "a": [
    "203.0.113.5"
   ],
   "asn": {
    "203.0.113.5": {
     "asn": "64500",
     "country": "NL",
     "name": "Hoster BV",
     "prefix": "203.0.113.0/24"
    }
   },
   "ns": [
    "ns1.example.net"
   ],
   "rdap": {
    "registrar": "Example Registrar",
    "registered": "2026-11-20T00:00:00Z"
   }
  },
  "visual": null,
  "kit": null,
  "discovery": [
   {
    "source": "ct",
    "first_seen": "2026-11-24T14:53:33.254837+00:00",
    "url": "https://capolice.live/",
    "display_url": "hxxps://capolice[.]live/",
    "brand_id": "adpolice"
   }
  ],
  "reports": {
   "count": 1,
   "notes": [
    {
     "id": "r_0123456789ab",
     "note": "came by SMS",
     "created_at": "2026-11-24T10:00:00+00:00"
    }
   ]
  },
  "hits": {},
  "campaign": null,
  "watchlist": null,
  "reviews": [
   {
    "decision": "confirm",
    "reason": null,
    "reviewer": "Demo Officer",
    "note": null,
    "at": "2026-11-24T11:00:00+00:00",
    "evidence_id": "ev_x"
   }
  ],
  "history": [
   {
    "check_id": "c_b4dba955a5c54a18b4c543c3498ae5ef",
    "source": "hunter",
    "verdict": "block",
    "score": 100,
    "stage": "deep",
    "at": "2026-11-24T14:53:34.114736+00:00"
   }
  ]
 },
 "campaigns": {
  "total": 3,
  "campaigns": [
   {
    "id": "cmp_651bb5e4",
    "name": "Unbranded · *.top · since 24 Nov 2026",
    "brand_id": null,
    "status": "suspected",
    "domain_count": 9,
    "confirmed_count": 0,
    "first_seen": "2026-11-24T14:58:20.415339+00:00",
    "last_activity_at": "2026-11-24T15:05:47.870597+00:00",
    "active": true
   },
   {
    "id": "cmp_348156d6",
    "name": "Unbranded · *.top · since 24 Nov 2026",
    "brand_id": null,
    "status": "suspected",
    "domain_count": 4,
    "confirmed_count": 0,
    "first_seen": "2026-11-24T14:59:26.394541+00:00",
    "last_activity_at": "2026-11-24T14:57:57.337439+00:00",
    "active": true
   }
  ],
  "next_cursor": null
 },
 "campaign": {
  "id": "cmp_651bb5e4",
  "name": "Unbranded · *.top · since 24 Nov 2026",
  "brand_id": null,
  "status": "suspected",
  "domain_count": 9,
  "confirmed_count": 0,
  "first_seen": "2026-11-24T14:58:20.415339+00:00",
  "last_activity_at": "2026-11-24T15:05:47.870597+00:00",
  "active": true,
  "domains": [
   {
    "domain": "dg41e.top",
    "display": "dg41e[.]top",
    "status": null,
    "score": 40,
    "verdict": "warn",
    "evidence_id": "ev_ec04c055abce45b68e5a2af3",
    "brand_id": null,
    "last_seen": "2026-11-24T14:53:55.815933+00:00",
    "links": [
     "cert",
     "ip"
    ],
    "tick": false
   },
   {
    "domain": "me85u.top",
    "display": "me85u[.]top",
    "status": null,
    "score": 40,
    "verdict": "warn",
    "evidence_id": "ev_6ae166819943407fbe97aea5",
    "brand_id": null,
    "last_seen": "2026-11-24T14:58:56.414239+00:00",
    "links": [
     "cert",
     "ip"
    ],
    "tick": false
   },
   {
    "domain": "mq73n.top",
    "display": "mq73n[.]top",
    "status": null,
    "score": 40,
    "verdict": "warn",
    "evidence_id": "ev_c16e1dbadbdc4eeb8c8323b7",
    "brand_id": null,
    "last_seen": "2026-11-24T14:50:03.737227+00:00",
    "links": [
     "cert",
     "ip"
    ],
    "tick": false
   }
  ],
  "entities": [
   {
    "kind": "ip",
    "value": "154.215.0.19",
    "label": "154.215.0.19",
    "strength": "strong",
    "domain_count": 9,
    "in_campaign": 9
   },
   {
    "kind": "ip",
    "value": "154.215.0.22",
    "label": "154.215.0.22",
    "strength": "strong",
    "domain_count": 9,
    "in_campaign": 9
   },
   {
    "kind": "ip",
    "value": "154.215.0.24",
    "label": "154.215.0.24",
    "strength": "strong",
    "domain_count": 9,
    "in_campaign": 9
   },
   {
    "kind": "ip",
    "value": "154.221.0.212",
    "label": "154.221.0.212",
    "strength": "strong",
    "domain_count": 9,
    "in_campaign": 9
   }
  ]
 },
 "graph": {
  "nodes": [
   {
    "id": "ip:154.215.0.19",
    "kind": "ip",
    "label": "154.215.0.19",
    "domain_count": 9,
    "hub": false
   },
   {
    "id": "ip:154.215.0.22",
    "kind": "ip",
    "label": "154.215.0.22",
    "domain_count": 9,
    "hub": false
   },
   {
    "id": "ip:154.215.0.24",
    "kind": "ip",
    "label": "154.215.0.24",
    "domain_count": 9,
    "hub": false
   },
   {
    "id": "d:dg41e.top",
    "kind": "domain",
    "label": "dg41e[.]top",
    "status": null,
    "score": 40
   },
   {
    "id": "d:me85u.top",
    "kind": "domain",
    "label": "me85u[.]top",
    "status": null,
    "score": 40
   }
  ],
  "edges": [
   {
    "source": "d:dg41e.top",
    "target": "ip:154.215.0.19",
    "strength": "strong",
    "excluded": false
   },
   {
    "source": "d:dg41e.top",
    "target": "ip:154.215.0.22",
    "strength": "strong",
    "excluded": false
   },
   {
    "source": "d:dg41e.top",
    "target": "ip:154.215.0.24",
    "strength": "strong",
    "excluded": false
   },
   {
    "source": "d:me85u.top",
    "target": "ip:154.215.0.19",
    "strength": "strong",
    "excluded": false
   }
  ],
  "collapsed": []
 },
 "feed": {
  "entries": [
   {
    "id": 184,
    "source": "ct",
    "domain": "gregnathansalik.com",
    "display": "gregnathansalik[.]com",
    "display_url": "hxxps://hub[.]gregnathansalik[.]com/",
    "brand_id": "salik",
    "detail": "name: salik",
    "first_seen": "2026-11-24T15:12:20.027966+00:00",
    "verdict": null,
    "score": null,
    "stage": null
   },
   {
    "id": 183,
    "source": "ct",
    "domain": "iubtelecom.com.br",
    "display": "iubtelecom[.]com[.]br",
    "display_url": "hxxps://www[.]links[.]iubtelecom[.]com[.]br/",
    "brand_id": "du",
    "detail": "typo: dutelecom~iubtelecom",
    "first_seen": "2026-11-24T15:12:08.493577+00:00",
    "verdict": "allow",
    "score": 0,
    "stage": "fast"
   }
  ],
  "next_cursor": 124
 },
 "evidence": {
  "id": "ev_dd8f608abc31419589a86732",
  "seq": 30,
  "check_id": "c_cf1f42874549463ba2b73ee8d10aaeb3",
  "prev_hash": "47241991f02ed9f9c64f351068b8332f963f44541098dbd13ee3de6df99db468",
  "hash": "190f75db7f1d08f5658a724948ce56ce80f9306498010b630d7605e5210bbd1d",
  "created_at": "2026-11-24T14:58:23.864682Z"
 },
 "audit": {
  "entries": [
   {
    "id": 3,
    "actor": "Demo Officer",
    "action": "review.confirm",
    "target_kind": "domain",
    "target": "detail.example",
    "before": {
     "status": null
    },
    "after": {
     "status": "confirmed"
    },
    "reason": null,
    "created_at": "2026-11-24T11:00:00+00:00"
   },
   {
    "id": 2,
    "actor": "Demo Officer",
    "action": "case.watch",
    "target_kind": "domain",
    "target": "detail.example",
    "before": {
     "watched": false
    },
    "after": {
     "watched": true
    },
    "reason": null,
    "created_at": "2026-11-24T10:00:00+00:00"
   },
   {
    "id": 1,
    "actor": "system",
    "action": "case.auto_confirm",
    "target_kind": "domain",
    "target": "auto.example",
    "before": null,
    "after": null,
    "reason": null,
    "created_at": "2026-11-24T09:00:00+00:00"
   }
  ]
 },
 "takedowns": {
  "total": 3,
  "requests": [
   {
    "id": "t_1",
    "domain": "a.example",
    "display": "a[.]example",
    "campaign_id": "cmp_1",
    "recipient_kind": "registrar",
    "recipient": "abuse@registrar.example",
    "form": false,
    "status": "pack_ready",
    "overdue": false,
    "pack_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "generated_at": "2026-11-24T12:00:00+00:00",
    "sent_at": null,
    "sent_by": null,
    "offline_at": null,
    "offline_reason": null,
    "checks_offline": 0
   },
   {
    "id": "t_2",
    "domain": "b.example",
    "display": "b[.]example",
    "campaign_id": "cmp_1",
    "recipient_kind": "registrar",
    "recipient": "abuse@registrar.example",
    "form": false,
    "status": "pack_ready",
    "overdue": false,
    "pack_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "generated_at": "2026-11-24T12:00:00+00:00",
    "sent_at": null,
    "sent_by": null,
    "offline_at": null,
    "offline_reason": null,
    "checks_offline": 0
   },
   {
    "id": "t_3",
    "domain": "a.example",
    "display": "a[.]example",
    "campaign_id": "cmp_1",
    "recipient_kind": "hosting",
    "recipient": "https://host.example/abuse",
    "form": false,
    "status": "pack_ready",
    "overdue": false,
    "pack_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "generated_at": "2026-11-24T12:00:00+00:00",
    "sent_at": null,
    "sent_by": null,
    "offline_at": null,
    "offline_reason": null,
    "checks_offline": 0
   }
  ],
  "next_cursor": null
 },
 "takedownCreated": {
  "requests": [
   {
    "id": "t_1",
    "domain": "a.example",
    "display": "a[.]example",
    "campaign_id": "cmp_1",
    "recipient_kind": "registrar",
    "recipient": "abuse@registrar.example",
    "form": false,
    "status": "pack_ready",
    "overdue": false,
    "pack_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "generated_at": "2026-11-24T12:00:00+00:00",
    "sent_at": null,
    "sent_by": null,
    "offline_at": null,
    "offline_reason": null,
    "checks_offline": 0
   },
   {
    "id": "t_2",
    "domain": "b.example",
    "display": "b[.]example",
    "campaign_id": "cmp_1",
    "recipient_kind": "registrar",
    "recipient": "abuse@registrar.example",
    "form": false,
    "status": "pack_ready",
    "overdue": false,
    "pack_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "generated_at": "2026-11-24T12:00:00+00:00",
    "sent_at": null,
    "sent_by": null,
    "offline_at": null,
    "offline_reason": null,
    "checks_offline": 0
   }
  ],
  "refused": [
   {
    "domain": "c.example",
    "display": "c[.]example",
    "why": "no evidence record"
   }
  ]
 },
 "confirmResult": {
  "confirmed": [
   {
    "domain": "dg41e.top",
    "display": "dg41e[.]top",
    "evidence_id": "ev_1"
   }
  ],
  "refused": [
   {
    "domain": "x.example",
    "display": "x[.]example",
    "why": "already confirmed"
   }
  ],
  "blocklist_version": 4
 },
 "helplines": {
  "numbers": [
   {
    "phone": "+971500000000",
    "brand": "TAMM",
    "source": "page",
    "domain": "scam.example",
    "evidence_id": "ev_1",
    "first_seen": "2026-11-24T10:00:00Z",
    "confirmed": true
   }
  ]
 },
 "events": {
  "candidate": {
   "type": "hunter.candidate",
   "at": "2026-11-24T15:09:39.800000+00:00",
   "data": {
    "source": "ct",
    "domain": "mckinsey.cloud",
    "brand_id": "adcb",
    "first_seen": "2026-11-24T15:12:20.027966+00:00"
   }
  },
  "verdict": {
   "type": "check.verdict",
   "at": "2026-11-24T15:10:00+00:00",
   "data": {
    "check_id": "c_1",
    "domain": "capolice.live",
    "host": "capolice.live",
    "verdict": "block",
    "score": 100,
    "stage": "deep",
    "source": "hunter",
    "brand": "Abu Dhabi Police"
   }
  },
  "reviewed": {
   "type": "case.reviewed",
   "at": "2026-11-24T15:11:00+00:00",
   "data": {
    "domain": "capolice.live",
    "decision": "confirm",
    "reviewer": "Demo Officer"
   }
  },
  "spike": {
   "type": "brand.spike",
   "at": "2026-11-24T15:12:00+00:00",
   "data": {
    "brand_id": "adcb",
    "count": 12
   }
  },
  "woke": {
   "type": "watchlist.woke",
   "at": "2026-11-24T15:13:00+00:00",
   "data": {
    "domain": "parked.example",
    "check_id": "c_2"
   }
  },
  "newDomain": {
   "type": "campaign.new_domain",
   "at": "2026-11-24T15:14:00+00:00",
   "data": {
    "campaign_id": "cmp_1",
    "domain": "new.example"
   }
  },
  "hello": {
   "type": "hello"
  }
 },
 "refused409": {
  "detail": {
   "refused": [
    {
     "domain": "c.example",
     "display": "c[.]example",
     "why": "not confirmed by an officer"
    }
   ]
  }
 },
 "stats": {
  "range": "7d",
  "since": "2026-11-17T18:00:23.885639+00:00",
  "now": "2026-11-24T18:00:23.885639+00:00",
  "totals": {
   "checks": 729, "warn": 523, "block": 50, "candidates": 721,
   "candidates_by_source": { "ct": 715, "nrd": 6 },
   "reports": 1, "confirmed": 1, "rejected": 1,
   "blocked_hits": { "share": 3 },
   "blocklist_size": 5, "taken_down": 0
  },
  "series": {
   "buckets": ["2026-11-23T00:00:00+00:00", "2026-11-24T00:00:00+00:00", "2026-11-25T00:00:00+00:00"],
   "checks": [0, 573],
   "candidates": [0, 721, 4],
   "confirmed": [0, 1, 0]
  },
  "lead_time": {
   "domains": [
    {
     "domain": "lead-one.example", "display": "lead-one[.]example", "brand_id": "adpolice",
     "seen": "2026-11-24T10:00:00+00:00", "confirmed": "2026-11-24T12:00:00+00:00", "hours_to_confirm": 2.0,
     "gsb_first_hit": null, "vt_first_hit": null,
     "lead_vs_gsb_h": 5.0, "lead_vs_gsb_open": true, "lead_vs_vt_h": null, "lead_vs_vt_open": false
    }
   ],
   "median_hours_to_confirm": 2.0, "median_lead_vs_gsb_h": 5.0, "median_lead_vs_vt_h": null,
   "flagged_by_gsb_later": 0, "not_flagged_by_gsb_yet": 1
  },
  "takedown_median_hours": null,
  "quality": {
   "days": 30, "reviews": 2,
   "by_band": {
    "warn": { "confirmed": 1, "cleared": 0, "other_reject": 0 },
    "block": { "confirmed": 0, "cleared": 0, "other_reject": 1 }
   },
   "block_precision": null, "warn_confirm_rate": 1.0, "false_blocks": 0,
   "url_model": null, "labels_for_retrain": 1
  }
 },
 "statsModel": {
  "range": "24h",
  "totals": {},
  "series": { "buckets": [], "checks": [], "candidates": [], "confirmed": [] },
  "lead_time": { "domains": [] },
  "quality": {
   "days": 30, "reviews": 40,
   "by_band": {
    "allow": { "confirmed": 1, "cleared": 3, "other_reject": 0 },
    "warn": { "confirmed": 9, "cleared": 6, "other_reject": 1 },
    "block": { "confirmed": 18, "cleared": 2, "other_reject": 0 }
   },
   "block_precision": 0.9, "warn_confirm_rate": 0.56, "false_blocks": 2,
   "url_model": {
    "updated_at": "2026-11-20T09:00:00+00:00", "score": 0.93,
    "metrics": {
     "train_rows": 12000, "holdout_rows": 3000, "precision@0.5": 0.94, "recall@0.5": 0.88, "recall@0.9": 0.61,
     "top_features": ["url_length", "digit_ratio"], "officer_phish": 18, "officer_benign": 5
    }
   },
   "labels_for_retrain": 23
  }
 },
 "watchlist": {
  "total": 335,
  "entries": [
   {
    "domain": "watch-one.example", "display": "watch-one[.]example", "display_url": "hxxps://watch-one[.]example/",
    "reason": "PARKED", "brand_id": null, "last_status": "parked",
    "last_checked_at": "2026-11-24T14:51:15.078256+00:00", "offline_since": null, "checks_done": 0,
    "next_check_at": "2026-11-24T20:51:15.078256+00:00", "expires_at": "2026-12-08T14:51:15.078256+00:00"
   },
   {
    "domain": "watch-two.example", "display": "watch-two[.]example", "display_url": "hxxps://www[.]watch-two[.]example/",
    "reason": "UNREACHABLE", "brand_id": "adpolice", "last_status": "unreachable",
    "last_checked_at": "2026-11-24T14:51:22.069081+00:00", "offline_since": "2026-11-24T14:51:22.069081+00:00", "checks_done": 1,
    "next_check_at": "2026-11-24T20:51:22.069081+00:00", "expires_at": "2026-12-08T14:51:22.069081+00:00"
   }
  ],
  "next_cursor": 2
 },
 "health": {
  "checked_at": "2026-11-24T18:00:23.965187+00:00",
  "deep_queue": { "waiting": 30, "failed": 0, "workers": 1 },
  "redis": "ok",
  "hunter": {
   "ct": { "last": "2026-11-24T18:00:19.463191+00:00", "last_24h": 715 },
   "nrd": { "last": null, "last_24h": 0 }
  },
  "checks": { "last": "2026-11-24T18:00:19.465967+00:00", "last_hour": 195, "deep_running": 31, "deep_stale": 40 },
  "models": { "url_model": null, "visual_refs": { "updated_at": "2026-11-20T09:00:00+00:00", "score": 0.8 } },
  "evidence": { "records": 491 },
  "blocklist_version": 46,
  "ai": "configured"
 },
 "takedownStats": {
  "by_status": { "pack_ready": 1, "sent": 0, "offline_pending": 0, "closed": 0, "reopened": 0 },
  "overdue": 0,
  "median_hours_to_offline": null,
  "recipients": { "gsb": { "requests": 1, "closed": 0, "median_hours": null }, "registrar": { "requests": 2, "closed": 1, "median_hours": 6.5 } },
  "sla_hours": 48
 },
 "takedownDetail": {
  "id": "td_1", "domain": "a.example", "display": "a[.]example", "campaign_id": null,
  "recipient_kind": "gsb", "recipient": "https://safebrowsing.google.com/safebrowsing/report_phish/", "form": true,
  "status": "offline_pending", "overdue": false, "pack_sha256": "a16fa6a960a89453cf67701b74fab70ba7820e00228ec95ae5898857318c87a4",
  "generated_at": "2026-11-24T15:22:20.928128+00:00", "sent_at": "2026-11-24T16:00:00+00:00", "sent_by": "Demo Officer",
  "offline_at": "2026-11-24T17:00:00+00:00", "offline_reason": "nxdomain", "checks_offline": 1,
  "pack": [
   {
    "id": "td_1", "domain": "a.example", "display": "a[.]example", "campaign_id": null,
    "recipient_kind": "gsb", "recipient": "https://safebrowsing.google.com/safebrowsing/report_phish/", "form": true,
    "status": "offline_pending", "overdue": false, "pack_sha256": "a16fa6a960a89453cf67701b74fab70ba7820e00228ec95ae5898857318c87a4",
    "generated_at": "2026-11-24T15:22:20.928128+00:00", "sent_at": "2026-11-24T16:00:00+00:00", "sent_by": "Demo Officer",
    "offline_at": "2026-11-24T17:00:00+00:00", "offline_reason": "nxdomain", "checks_offline": 1
   }
  ]
 },
 "recheck": { "queued": true, "domain": "a.example", "display": "a[.]example" },
 "excludeResult": { "domain": "b.example", "display": "b[.]example", "campaign": "cmp_1", "domain_count": 3 },
 "mergeResult": { "id": "cmp_1", "name": "Merged campaign", "status": "suspected", "merged": ["cmp_2"] },
 "pivot": {
  "leads": [
   {
    "domain": "lead-a.example", "display": "lead-a[.]example",
    "via": [{ "kind": "ns", "label": "ns1[.]shared[.]example", "strong": true }, { "kind": "ip", "label": "203.0.113.7", "strong": false }],
    "status": "open", "score": 82, "campaign": null
   },
   { "domain": "lead-b.example", "display": "lead-b[.]example", "via": [], "status": null, "score": null, "campaign": "cmp_9" }
  ],
  "total": 2
 },
 "entity": {
  "kind": "ns", "value": "ns1.shared.example", "label": "ns1[.]shared[.]example", "first_seen": "2026-11-20T10:00:00+00:00",
  "domain_count": 2, "hub": false,
  "domains": [
   { "domain": "c.example", "display": "c[.]example", "status": "confirmed", "strength": "strong", "excluded": false, "campaign": "cmp_1", "evidence_id": "ev_1", "score": 91 },
   { "domain": "d.example", "display": "d[.]example", "status": null, "strength": "weak", "excluded": true, "campaign": null, "evidence_id": null, "score": null }
  ]
 }
}
