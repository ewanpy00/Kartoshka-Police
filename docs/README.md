# Documentation

Start with the [README](../README.md): what Kartoshka-Police is, how to run it, and how it scores. This page lists every other document and says which ones describe the system as it is and which ones record how it was planned.

## Product

| Document | What it covers |
|---|---|
| [IDEA.md](../IDEA.md) | The problem, the three product ideas, and how they were weighed against the hackathon judging criteria |
| [FUTURE.md](../FUTURE.md) | What comes after the hackathon: a link check inside TAMM |
| [apple-development-plan.md](apple-development-plan.md) | How the app could run on iPhone as a real web browser (plan, not built) |
| [pdf/](pdf/) | Product brief, versions 4 and 5 |

## How the system works

| Document | What it covers |
|---|---|
| [ARCHITECTURE.md](../ARCHITECTURE.md) | The design of every layer: core, Hunter, Gatekeeper, DNS Shield, the officer console and the AI layer. Each section says what is built and what is still planned. |
| [gatekeeper/README.md](../gatekeeper/README.md) | The Android app: what it does, how to build it, how it reaches core |
| [dns/README.md](../dns/README.md) | DNS Shield: AdGuard Home and its sync service |

## Data

| Document | What it covers |
|---|---|
| [data_set/DATASET_SOURCES.md](data_set/DATASET_SOURCES.md) | A labelled test set of 2,221 URLs (UAE and worldwide, phishing and benign), where each row came from, and the script that builds it |

## Build records

These documents are the plans each part was built from, with the decisions taken and a progress log. Everything in them is built and merged into `main`, except where a document says otherwise. They explain why the code is the way it is; for how to run it, use the README.

| Document | Part | Status |
|---|---|---|
| [devops-plan.md](devops-plan.md) | Docker Compose stack, make targets, network isolation | Built |
| [app-plan.md](app-plan.md) | Core, sandbox, Hunter, AI layer, resident screens, DNS Shield, Gatekeeper source, evaluation | Built |
| [admin-panel.md](admin-panel.md) | Proposal for the officer console's admin pages (queue, campaigns, takedowns) | Proposal; built through the two plans below |
| [admin-dashboard.md](admin-dashboard.md) | Build contract for the admin pages: routes, migration, campaign and takedown rules | Built |
| [admin-plan.md](admin-plan.md) | Officer console build log: first build, restyle, and stage 2 (Impact, Model quality, Health, watchlist, campaign actions, takedown tracking) | Built |
