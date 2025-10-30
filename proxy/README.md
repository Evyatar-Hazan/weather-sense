# WeatherSense Cloudflare Worker Proxy

> **Tech Stack:** Cloudflare Workers · JavaScript (ES2022) · Wrangler CLI

This proxy serves as a critical component of the WeatherSense architecture, providing seamless `/healthz` endpoint compatibility for the assignment specification while working around Google Cloud Run's path restrictions. It ensures full compliance with the original requirements through a lightweight, zero-cost reverse proxy layer that transparently handles all API requests.

## Background / Problem

Google Cloud Run reserves URL paths ending with 'z' (including `/healthz`), which conflicts with the assignment specification requiring a `/healthz` health check endpoint.

## Solution

A zero-cost Cloudflare Worker reverse proxy implemented in JavaScript that:
- Maps `/healthz` requests to the Cloud Run `/health` endpoint
- Forwards all other requests transparently to Cloud Run
- Maintains CORS headers and error handling consistency
- Provides a lightweight, stateless proxy layer with minimal overhead

## Files

- **`index.js`**: Main Worker script with proxy logic
- **`wrangler.toml`**: Cloudflare deployment configuration
- **`README.md`**: This documentation file

## Quick Start

For local development and testing:

```bash
npm install -g wrangler
cd proxy
wrangler dev
```

Verify the proxy works by checking that `/healthz` returns `{"ok": true}` at `http://127.0.0.1:8787/healthz`.

## Deployment

1. Install Cloudflare CLI:
   ```bash
   npm install -g wrangler
   ```

2. Login to Cloudflare:
   ```bash
   wrangler login
   ```

3. Test the proxy locally (optional but recommended):
   ```bash
   cd proxy
   wrangler dev
   ```
   Verify that `/healthz` works locally before deploying to production.

4. Deploy the Worker:
   ```bash
   cd proxy
   wrangler deploy
   ```

5. Update the Cloud Run URL in `index.js` if needed:
   ```javascript
   const CLOUD_RUN_BASE_URL = "https://your-service.run.app";
   ```

## Usage

After deployment, the Worker provides:
- `https://your-worker.workers.dev/healthz` → Returns `{"ok": true}`
- `https://your-worker.workers.dev/weather` → Forwards to Cloud Run `/weather`
- All other endpoints work identically through the proxy

## Testing

Install pytest if not already available:
```bash
pip install pytest
```

Run the test suite to verify `/healthz` correctly maps to Cloud Run's `/health` endpoint:
```bash
pytest tests/test_proxy_healthz.py -v
```

## Cost

This solution uses only free-tier services:
- Cloudflare Workers: 100,000 requests/day (free)
- Google Cloud Run: 2 million requests/month (free)

## CI/CD Integration

For automated deployments in production environments:
```bash
wrangler deploy --env production
```

## Architecture

```
Client Request → Cloudflare Worker → Google Cloud Run
     ↓              ↓                    ↓
   /healthz  →   /health    →        {"ok": true}
```

The proxy is stateless, production-ready, and maintains full assignment compliance while working around the Google Cloud Run restriction.

## Notes

For detailed implementation rationale, Cloud Run restrictions, and technology choice explanations, see the comprehensive documentation in `../NOTES.md`. This includes the reasoning behind Cloud Run path restrictions and the proxy design decisions.

## GitHub Actions

For automated CI/CD deployment in GitHub Actions:

```yaml
- name: Deploy Cloudflare Worker
  run: wrangler deploy --env production
```
