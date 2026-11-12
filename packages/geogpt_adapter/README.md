# geogpt_adapter

Wraps the GeoGPT API. Handles prompt construction, structured JSON output, retries, token
usage tracking, model metadata, and versioned prompt responses.

Current scope:

- `GeoGPTAdapter` defines the adapter boundary for prompt completion.
- `FakeGeoGPTAdapter` records prompts and returns deterministic JSON for tests.
- `GeoGPTHTTPAdapter` creates a session and consumes the streaming
  `sendMsg` endpoint before returning the complete response.
- Set `GEOGPT_TRUST_ENV=false` to ignore system proxy environment variables.
