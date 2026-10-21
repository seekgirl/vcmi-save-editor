# Security Policy

## Status and scope

This directory contains the `v0.2.0-alpha.1` source preview for VCMI 1.7.5 / save format 902 on Apple Silicon macOS. It is a local, offline save editor. It does not provide an online account, server, telemetry, or account-level anti-cheat service. No stable-version security support commitment has been made.

The most sensitive inputs are users' save files, local paths, game data, and build logs. Treat them as private even when a failure appears unrelated to security.

## Reporting a vulnerability

There is no independent security email for this source preview. If the repository enables private vulnerability reporting, use **Security → Report a vulnerability**. If that channel is unavailable, make only a public request for a private maintainer contact; do not post vulnerability details, personal saves, credentials, private paths, or proof-of-concept material containing private data. Preserve a minimal reproduction locally.

For ordinary non-security bugs, use the repository issue template. Provide the VCMI version, save format, macOS/CPU, editor build, and redacted reproduction steps using a copy of the save.

## Safe disclosure

Do not test against another person's saves, accounts, game installation, or online service. Do not request or upload passwords, API keys, signing credentials, or copyrighted game data. A local build and a synthetic or lawfully redistributable fixture are sufficient for most reports.

