# Security

## Secrets

- `NEURONPEDIA_API_KEY` is read only by the server process.
- `PRISMORA_WORKER_TOKEN` is sent only from control plane to worker.
- The browser never receives either secret through an API response.
- Do not put keys inside experiment JSON, model registry records or raw prompts.

## Network exposure

The control plane has no user accounts in v0.2. Default binding is
`127.0.0.1`. A non-local binding prints a warning. Use an authenticated reverse
proxy, VPN or SSH tunnel for remote access.

The worker bearer token is a basic shared secret. Prefer private networking and
TLS. Rotate the token when a rented machine is destroyed or reassigned.

## Data sensitivity

Raw prompts, chats and model outputs are stored by design. Audit them before
publishing bundles. Do not run private conversations through a public backend
unless the relevant privacy policy permits it.

## Reporting

This is a research scaffold. Record security issues privately with the project
maintainer before public disclosure when possible.
