# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Artax Network, please report it responsibly. **Do not open a public GitHub issue for security vulnerabilities.**

Email: **security@artax-network.dev**

Include the following in your report:

- **Description** of the vulnerability.
- **Steps to reproduce** the issue.
- **Potential impact.**
- **Suggested fix** (if you have one).

## Response Timeline

| Step | Timeline |
|---|---|
| Acknowledgment of report | Within 48 hours |
| Initial assessment | Within 5 business days |
| Fix development | Depends on severity; critical issues prioritized |
| Public disclosure | After fix is released |

We will coordinate with you on disclosure timing. We ask that you do not disclose the vulnerability publicly until a fix is available.

## Scope

The following are in scope:

- The `artax` Python package.
- The runtime core (`artax/runtime/`, `artax/core/`).
- The Chromium driver.
- The dashboard and its WebSocket API.
- Docker configurations.

The following are out of scope:

- Third-party dependencies (report these to their maintainers).
- Social engineering attacks.
- Issues in development environments (not deployed).

## Supported Versions

| Version | Supported |
|---|---|
| 0.1.x | Yes |
| < 0.1 | No |

## Safe Harbor

We consider security research conducted in accordance with this policy to be:

- Authorized under applicable anti-hacking laws.
- Exempt from DMCA restrictions on circumventing technological measures.
- Conducted in good faith.

We will not pursue legal action against researchers who follow this policy.

## Dependencies

Artax Network depends on third-party packages. Vulnerabilities in dependencies should be reported to both us and the upstream maintainer. We will update dependencies promptly when vulnerabilities are disclosed.

## Configuration Security

In production, ensure:

- `ARTAX_SECRET_KEY` is set to a strong, unique value (not the default).
- The runtime is not exposed to untrusted networks without authentication.
- `ARTAX_CHROMIUM_HEADLESS` is set to `true` in production.
- Event logs do not contain sensitive data.
