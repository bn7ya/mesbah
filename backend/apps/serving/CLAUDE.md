# apps/serving

The engines that run models, and Mesbah's own OpenAI- and Ollama-compatible APIs. The built-in
engine (`mesbah.runtime`, ADR-005) is created by a migration and is the default; vLLM, Ollama,
llama.cpp and any OpenAI-compatible server can be connected beside it. The backend half of the
Engines page.

## Its counterpart

`frontend/src/app/features/serving/` — the Engines page: engines, API keys, how to connect.

## Endpoints

| Method | Path | Who | Returns |
|---|---|---|---|
| `GET` | `/api/serving/engines/` | viewer | a page of engines, each asked what it holds (`state`) |
| `POST` | `/api/serving/engines/` | admin | `201` a connected engine (`vllm`, `ollama`, `llamacpp`, `openai`) |
| `GET` | `/api/serving/engines/<id>/` | viewer | one engine |
| `PATCH` | `/api/serving/engines/<id>/` | admin | name, address, model name, API key (empty removes it), on/off, default |
| `DELETE` | `/api/serving/engines/<id>/` | admin | `204`; `409 builtin_engine_kept` |
| `POST` | `/api/serving/engines/<id>/unload/` | trainer | the engine, with nothing loaded |
| `GET` | `/api/serving/keys/` | trainer | a page of API keys — an administrator's all, anyone else's own |
| `POST` | `/api/serving/keys/` | trainer | `201` a key, shown in this answer only |
| `DELETE` | `/api/serving/keys/<id>/` | trainer | `204`; the key stops working |
| `GET` | `/v1/models` | API key | OpenAI's model list |
| `POST` | `/v1/chat/completions` | API key | OpenAI's chat completion, streamed or whole |
| `POST` | `/ollama/api/chat`, `/ollama/api/generate` | API key | Ollama's newline-delimited JSON, streamed by default |
| `GET` | `/ollama/api/tags`; `POST` `/ollama/api/show` | API key | Ollama's model list and one model |
| `GET` | `/ollama/api/version` | public | the version Ollama clients ask for |

`state` always has the same keys: `running`, `loaded`, `busy`, `device`, `quantized`,
`base_model` (`id`, `repo_id`) and `versions` (each with its project).

A model name on the compatible APIs is a project's slug (its active version, also `:latest`)
or `slug:vN`. Their errors take each API's own shape — OpenAI's `{"error": {"message", "type",
"code"}}`, Ollama's `{"error": "…"}` — and they are not paginated: clients expect the lists whole.

A request with no key answers `401` `invalid_api_key`, "Send a Mesbah API key as a Bearer
token."; a Bearer key that is wrong, revoked or its owner's deactivated answers `401`
`invalid_api_key` too, with "This API key isn't valid. Create a new one on the Engines page."
Ollama's routes read the body as JSON whatever its `Content-Type` says (`curl -d '{…}'` sends
`application/x-www-form-urlencoded`); OpenAI's keep requiring `application/json`.

## Layers

```
views/engines.py → services/engine_service.py ─┐
views/keys.py → services/api_key_service.py    │
views/openai.py, views/ollama.py → services/gateway_service.py
gateway, engines, apps.chat, apps.training → services/deployment_service.py → services/engine_client.py → HTTP
                  └→ repositories/{engine,deployment,api_key}_repository.py → Engine, Deployment, ApiKey
authentication.py → services/api_key_service.py   (Bearer keys, for /v1 and /ollama only)
```

## Classes and methods

**`Engine`** — a server that runs models: its name, kind (`builtin`, `vllm`, `llamacpp`,
`ollama`, `openai`), address, the model it serves when it serves one, a sealed API key, whether
it is on and the default, and when it was last seen. **`Deployment`** — a version loaded, or
being loaded, on an engine, under the name the engine knows it by. **`ApiKey`** — a named key
for the compatible APIs: its shown prefix, the sha256 of the key, its owner and last use.

**`EngineRepository`** — engines with the default first, the default, the built-in one, and
clearing the default. **`DeploymentRepository`** — what is loaded on an engine, one version's
deployment, marking an engine's deployments unloaded. **`ApiKeyRepository`** — keys, one
owner's keys, a key by digest.

**`EngineClient`** (`services/engine_client.py`) — one engine over HTTP: `health()`, `status()`,
`load()`, `unload()` (the built-in engine's `/admin/*`), `models()` (`/v1/models`), `get()`,
`post()`, `has()` (HEAD) and `upload()` for the rest, and `stream_chat()`, which reads OpenAI's
streamed chunks into `Piece`s — thinking (`reasoning_content`, `reasoning`, or a `<think>` block
in the content, split with `mesbah.think`), content, the finish reason and the token counts.
Failures become `EngineError` with a code: `engine_unreachable`, `engine_timeout`,
`engine_rejected_token`, or the engine's own. Tests swap `transport` / `async_transport`.

**`DeploymentService`**, for the acting user:
- `target()` — the engine (the conversation's, else the default) and model name to send a
  version's chat to, after putting the version there: the built-in engine loads the base (4-bit
  only when half precision would not fit, on the GPUs chosen on the System page) and the
  version's adapter, but not while a training run is using the memory
  (`training_in_progress`); vLLM checks it serves the same base and loads the adapter by path
  (`engine_base_mismatch` otherwise); Ollama imports the version's GGUF export as
  `mesbah-<slug>-v<n>` (`needs_gguf` without one); llama.cpp and OpenAI-compatible servers answer
  with the one model they serve.
- `release()` — unloads the built-in engine, for training.
**`served_name()`**, **`external_name()`** — what each kind of engine calls a version; on the
built-in engine a root version (`base` or `scratch_root`) is the base model itself, `base`.
**`endpoint_of()`** — an engine's address and key; the built-in one's come from
`MESBAH_RUNTIME_URL` and `MESBAH_RUNTIME_TOKEN` (**`builtin_endpoint()`**, which
`apps.system` also uses to ask the engine which parts it has).

**`EngineService`** — `listing()`, `find()`, `describe()` (with its live `state`), `create()`,
`change()` (the built-in engine takes a name, on/off and default only), `remove()`, `unload()`.

**`ApiKeyService`** — `listing()`, `describe()`, `create()` (`msb_` and 32 random bytes; the
answer carries the key once), `revoke()`, `authenticate()` (a live key of an active owner; the
last use is written at most once a minute). **`ApiKeyAuthentication`** — DRF authentication from
`Authorization: Bearer`; a key that does not authenticate raises `AuthenticationFailed` with the
"isn't valid" message, no key at all is left to `NotAuthenticated`. **`ApiKeyScheme`** describes
it to the schema. **`AnyMediaTypeJSONParser`** (`parsers.py`) — a JSON parser that matches every
media type, for Ollama's routes.

**`GatewayService`** — `served()` (every project by slug and every version as `slug:vN`),
`resolve()` a name (`UnknownModel` when nothing matches), `target()`, `thinking_default()`, and
`stream()` / `collect()` over the engine's pieces. **`CompatView`** (`views/compat.py`) — API
key authentication and errors in OpenAI's shape (`unauthorized()` is the 401, with the message
for a missing or an invalid key); **`OllamaView`** — the same in Ollama's, any `Content-Type`
read as JSON, NDJSON lines and their merge into one answer. **`ModelListView`**, **`ChatCompletionView`**,
**`OllamaChatView`**, **`OllamaGenerateView`**, **`OllamaTagsView`**, **`OllamaShowView`**,
**`OllamaVersionView`** — the routes above (`compat_urls.py`, mounted at `/v1/` and `/ollama/`).

**`NoEngine`**, **`ModelNotOnDisk`**, **`EngineFailed`**, **`BuiltinEngineKept`**
(`services/errors.py`) — the refusals; `EngineFailed` carries the engine's code, and answers 503
when the engine is not there at all.

## Decisions worth not re-litigating

**Every engine is an OpenAI-compatible server.** One client streams from all of them; what
differs is how a version gets onto one, which `DeploymentService` owns.

**The built-in engine's address is settings, not a row.** In pip mode the launcher picks the
port and the token; in Docker the compose file does. The row holds what a person can change.

**API keys are stored as digests.** A key is shown once; losing it means making another. Keys
act as their owner, so a key never does more than its owner's role allows.

**The compatible APIs mirror their originals, not Mesbah's conventions.** Paths without a
trailing slash, unpaginated lists and each API's own error shape are what existing clients
parse; they are the exception rule 17 and the error convention allow for.
