# Security Policy

GOD is an open-source research and product prototype for running, observing, and steering agent societies. Because local experiments can involve model API keys, generated profiles, logs, replay databases, and user-authored scenario data, please report security concerns privately.

## Supported Versions

Security fixes are handled on the default branch, `main`. Older local clones, experiment snapshots, and unpublished branches are not separately supported.

## Reporting a Vulnerability

Please do not open a public issue for suspected vulnerabilities. Use GitHub's private vulnerability reporting flow instead:

https://github.com/XiaoLuoLYG/GOD/security/advisories/new

Include as much of the following as you can:

- The affected commit, branch, or release.
- A clear description of the vulnerability and the impacted component.
- Minimal reproduction steps or a proof of concept.
- Whether any secrets, private data, logs, replay databases, or model-provider credentials may be exposed.
- Any suggested mitigation, if you already have one.

## Handling Expectations

The maintainers will review incoming reports, ask for clarification when needed, and coordinate a fix or mitigation before public disclosure when the issue is confirmed. Please avoid destructive testing, accessing data that is not yours, or sharing exploit details publicly before the maintainers have had a chance to respond.

## Secrets and Local Data

If you accidentally commit or publish an API key, token, credential, private dataset, or local runtime artifact, revoke or rotate the credential first. Then open a private report if the exposure affects this repository or its users.

Runtime outputs such as `.god/`, `.live/`, generated experiment folders, replay databases, logs, and local `.env` files should stay out of normal pull requests unless they are intentionally sanitized sample assets.
