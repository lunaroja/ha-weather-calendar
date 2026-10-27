<!-- second-brain-repository-bootstrap:v1 -->

# Repository agent guide

This repository extends Abraham's canonical agent contract at
`/Users/abraham/src/second-brain/AGENTS.md`. Repository-specific instructions
below add to that contract; they do not replace it.

## Required task-start synchronization

Before substantive work or a substantive response in a new task:

1. Run `.codex/bin/repository-preflight` from anywhere inside this repository.
2. If it reports a dirty, detached, untracked, or diverged checkout, preserve
   the existing work and report the exact synchronization blocker. Never reset,
   clean, force, or overwrite work to make the preflight pass.
3. After a successful pull, read the current Second Brain `AGENTS.md`, then this
   file, before acting. Start a new task if pulled instruction changes must be
   loaded by the runtime immediately.

The preflight verifies the global Second Brain link and performs only
fast-forward pulls for clean checkouts with tracking branches.

## Repository-specific instructions

This public repository owns the Weather Calendar custom integration, tests and user documentation. Household configuration belongs in the private homeassistant repository. Never copy home coordinates, email, feed URLs, credentials, config-entry IDs or runtime state here.

Validate using CONTRIBUTING.md. Release from main only after tests, hassfest and HACS validation pass. Preserve the weather_calendar domain, version-1 config-entry data/options, entity unique IDs, entry-based feed paths and date UIDs across upgrades. Use only bounded literal templates, never evaluated code or unrestricted HA templates. Keep unauthenticated feed access opt-in and documented.

This checkout has no permission to control a contributor's live home. Abraham's own live migration must follow the private Home Assistant repository queue, baseline, restoration and verification workflow.
