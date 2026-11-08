# cloro web search for Hermes Agent

A [Hermes Agent](https://github.com/NousResearch/hermes-agent) web search backend that gives the built-in `web_search` tool live Google Search results through the [cloro](https://cloro.dev?utm_source=hermes-agent&utm_medium=byok) API.

The plugin is search only. For `web_extract`, keep or choose another extract backend (for example Firecrawl, Tavily or Exa).

## Install

```bash
hermes plugins install cloro
```

Or install from this repository:

```bash
hermes plugins install https://github.com/cloro-dev/hermes-plugin-cloro
```

Hermes asks for `CLORO_API_KEY` during the install. Get a key from the [cloro dashboard](https://dashboard.cloro.dev/api-keys?utm_source=hermes-agent&utm_medium=byok).

## Use it as the search backend

```bash
hermes plugins enable cloro
hermes tools          # choose "cloro (Google Search)" for web search
```

Or set it in `~/.hermes/config.yaml`:

```yaml
web:
  search_backend: cloro
  extract_backend: firecrawl   # optional: any extract backend you use
```

## Settings

| Setting | Default | Description |
| -- | -- | -- |
| `CLORO_API_KEY` | (required) | Your cloro API key. Hermes stores it as a secret. |
| `country` | `US` | 2-letter ISO 3166-1 code for the location of the results, for example `DE`. |

## What it does

Each `web_search` call sends one request to `POST https://api.cloro.dev/v1/monitor/google` with the query and the country. cloro loads the live Google results page and returns the organic results. The plugin returns their title, URL and snippet, up to the limit the tool asks for. Results that have no resolved link are skipped.

## Disclosure

- **Network:** search queries go to `api.cloro.dev` with your `CLORO_API_KEY`. Each search uses cloro credits on your account.
- **Credentials:** the plugin reads `CLORO_API_KEY` only through Hermes (`agent.secret_scope.get_secret`).
- **Nothing else:** it registers no tools, hooks or middleware, writes no files, starts no processes, has no telemetry and does not update itself. It uses only the Python standard library.

## Development

```bash
pytest
```

The tests mock the network. They run with or without Hermes installed.

## License

MIT
