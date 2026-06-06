# Settings First-Run API Contract

> Status: accepted
> Last Updated: 2026-06-06
> Plan: [Settings first-run frontend completion](../plans/feature/settings-first-run-frontend-completion.md)
> Baseline: [Settings and first-run readiness](../plans/feature/settings-first-run-readiness.md)

This contract finalizes the Product 1.0 backend slice needed for the Settings
first-run frontend completion path. It is intentionally smaller than the full
centralized runtime configuration plan.

## Scope

The sidecar supports local read/write setup for:

- LLM provider: `litellm`, `deepseek`, `openrouter`;
- LLM model;
- write-only API key replacement;
- logging profile selection.

Out of scope:

- centralized runtime configuration;
- provider network validation;
- automatic retry policy;
- exposing stored secret values.

## Endpoints

All responses use the existing sidecar JSON envelope.

```text
GET /api/v1/settings/config
PATCH /api/v1/settings/config
POST /api/v1/settings/readiness/recheck
```

`GET /api/v1/settings/config` returns only safe summaries:

```json
{
  "ok": true,
  "data": {
    "schemaVersion": "plato.settings_config.v1",
    "llm": {
      "provider": "litellm",
      "providerSource": "default",
      "model": "anthropic/claude-sonnet-4-5-20250929",
      "modelSource": "default",
      "apiKeyConfigured": false,
      "apiKeySource": "none",
      "apiKeyEnvVar": "LLM_API_KEY"
    },
    "logging": {
      "selectedProfile": null,
      "selectedProfileSource": "default",
      "selectedProfileKnown": true,
      "defaultProfile": "normal",
      "profiles": []
    },
    "diagnostics": {
      "bundleExportAvailable": true,
      "httpExportRouteAvailable": true
    }
  },
  "error": null
}
```

`PATCH /api/v1/settings/config` accepts:

```json
{
  "llm": {
    "provider": "litellm",
    "model": "anthropic/test-model",
    "apiKey": "write-only replacement"
  },
  "logging": {
    "selectedProfile": "normal"
  }
}
```

The API key is write-only. It is never returned, logged, or included in
diagnostic descriptors. If `apiKey` is omitted, existing local or environment
configuration is kept. If `apiKey` is an empty string and an effective key
already exists, the secret is unchanged. If the requested setup would still
have no effective API key, the request returns `bad_request` with Product error
metadata and safe field errors.

Successful `PATCH` returns:

```json
{
  "ok": true,
  "data": {
    "schemaVersion": "plato.settings_config_update.v1",
    "config": {},
    "readiness": {}
  },
  "error": null
}
```

`config` is the same safe summary returned by `GET /api/v1/settings/config`.
`readiness` is a freshly recomputed `plato.settings_readiness.v1` payload.

`POST /api/v1/settings/readiness/recheck` returns the same refreshed readiness
payload as `GET /api/v1/settings/readiness`.

## Storage Policy

Product 1.0 stores this local setup under `.taskweavn/settings/`:

- `config.json`: provider, model, and logging profile;
- `secrets.json`: the active provider's API key.

The secret file is treated as local, write-only sidecar state. Reads only expose
booleans, source labels, and env var names. Diagnostic bundle export does not
include the settings files directly, and all diagnostic payload writes still run
through the Product 1.0 redaction profile.

## Errors

Validation failures keep the top-level `ApiError` shape:

```json
{
  "code": "bad_request",
  "message": "settings config update is invalid",
  "retryable": false,
  "details": {
    "productCategory": "input_validation",
    "recoveryActions": ["edit_input", "open_settings"],
    "severity": "action_required",
    "fieldErrors": [
      {
        "path": "llm.provider",
        "message": "unsupported provider",
        "allowedValues": ["litellm", "deepseek", "openrouter"]
      }
    ]
  }
}
```

Error details must not contain raw secrets, provider payloads, prompts, logs, or
SQLite payloads.
