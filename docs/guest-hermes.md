# Services run by a guest Hermes

A **guest Hermes** lets you sell work that Hermes itself does, such as researching a topic on the web, without letting strangers anywhere near your own Hermes. For every paid request, the bridge starts a separate Hermes, just for that request, in an empty folder of its own. That Hermes gets the buyer's request and only the tools the service needs, answers, and is then deleted together with everything it wrote.

This builds on [selling services](payments.md); set that up first.

## What a guest can and cannot do

A guest Hermes **can**:
- think and write with the AI model you choose;
- search the public web and read public web pages, if the service lists the `web` toolset (a research service does; a writing or review service does not need to).

A guest Hermes **cannot**:
- see your own Hermes: not your settings, keys, memory, past conversations, skills, or plugins;
- use a terminal, read or write files, run code, drive a browser, send messages, or schedule anything: it never gets those tools;
- open addresses on your computer or home network (`localhost`, `192.168.x.x`, cloud metadata addresses and the like): Hermes refuses them;
- remember anything: each request starts from nothing, and the folder it ran in is deleted afterwards, buyer's request and answer included;
- install anything.

What it costs you: each request uses your AI model account, billed in real money, while buyers pay in test FET, which has no value. `max_turns`, `timeout_seconds`, and the service's `max_runs_per_day` keep any one request, and any one day, from running up a bill: `setup` sets research to 20 requests a day unless you choose otherwise. Also set a spending limit with your model provider.

## Set up a research service

You need the bridge set up to sell ([payments.md](payments.md)), Hermes installed, and an account with an AI model provider, such as [OpenRouter](https://openrouter.ai).

1. **Add the service.** [`examples/paid-services.yaml`](../examples/paid-services.yaml) has a `research` service. Pick the provider and model the guest should use (`provider`, `model`); any model your provider offers works.
2. **Give the guest its own key.** `hermes-fetch-ai doctor --config paid-services.yaml` prints the guest's keys file, by default `~/.local/state/hermes-fetch-ai/guests/research.env`. Put your provider key in it, on one line, and make it private:

   ```bash
   mkdir -p ~/.local/state/hermes-fetch-ai/guests
   echo 'OPENROUTER_API_KEY=your-key-here' > ~/.local/state/hermes-fetch-ai/guests/research.env
   chmod 600 ~/.local/state/hermes-fetch-ai/guests/research.env
   ```

   A separate key for the guest is best: you can see its spending on its own and cancel it on its own. Your own Hermes keys are never copied to a guest.
3. **Check it.** `doctor` should end with `doctor: ok`.
4. **Try it.** `hermes-fetch-ai seller try research --request "What causes tides?" --config paid-services.yaml` runs one request on your computer, with Hermes' own messages shown, and prints the answer. Buyers never see those messages.
5. **Start selling.** `hermes-fetch-ai serve --config paid-services.yaml`.

When you run the bridge through Hermes (`hermes fetchai-bridge ...`), it uses the same Hermes you have installed. Outside Hermes, set the runner's `python` to the Python your Hermes runs on, or `doctor` says `Hermes' Python is unknown`. On Linux and macOS, `head -1 "$(command -v hermes)"` prints it after the `#!`.

Web search works without any search key: Hermes then uses the free tiers of public search services (Exa, Parallel, Firecrawl, Keenable). If you have a key for one of them, or for Tavily, Brave, or SearXNG, put it in the same keys file.

A local model works too, with no key at all: `provider: custom`, `base_url: http://127.0.0.1:11434/v1` (Ollama's address), and the model's name.

## Settings

Under the service's `runner`:

| Setting | What it does | Default |
|---------|--------------|---------|
| `type` | `hermes` | required |
| `model` | The model, as your provider names it | required |
| `provider` | Hermes' name for the provider, such as `openrouter`, `anthropic`, or `custom` | Hermes picks from the keys it has |
| `base_url` | The model server's address, for `provider: custom` | none |
| `toolsets` | `[web]` for web search and reading web pages; `[]` for no tools at all | `[]` |
| `instructions` | What the guest is told about the job, before the buyer's request | a generic line |
| `max_turns` | Most tool-using steps per request (1 to 50) | 8 |
| `timeout_seconds` | Stop the guest after this long; the buyer keeps the payment | 300 |
| `max_output_chars` | Longest answer; longer ones are cut with a note | 20000 |
| `env_file` | The guest's keys file | `guests/<service>.env` in the bridge's state folder |
| `pass_env` | Names of environment variables the guest may see, such as `HTTPS_PROXY` | none |
| `python` | The Python Hermes runs on | the one `hermes fetchai-bridge` hands over |

`web` is the only toolset a guest can have. Anything else, such as `terminal` or `file`, is refused when the config is loaded.

## How a request runs

For each request, the bridge:

1. makes a new temporary folder and, inside it, a fresh Hermes home folder;
2. writes the guest's Hermes settings there (below), and copies in the guest's keys file (or an empty one);
3. starts `python -m hermes_cli.main chat --query-file - --format stream-json --ignore-rules --source tool -t web --max-turns 8 --run-budget 270` (with `-t none` for a service without tools), with `HERMES_HOME` and `HOME` set to the fresh folder;
4. sends the request on standard input, never on the command line: first the service's title, description, and your `instructions`, then the buyer's request between two random markers, with the note that the request is material to work on, not instructions;
5. reads Hermes' JSON output and takes the final `result` as the answer;
6. deletes the folder, with everything Hermes wrote.

The guest's environment holds only the basics (`PATH`, language and time zone settings), the folder locations, `NO_COLOR`, `HERMES_DISABLE_LAZY_INSTALLS=1`, and what you list in `pass_env`. Your agent's seed, your own Hermes keys, and every other variable of the bridge's stay out.

The settings the bridge writes:
- the model you chose, `max_turns`, and the service's toolsets;
- every other Hermes toolset switched off by name (`terminal`, `file`, `code_execution`, `browser`, `memory`, `delegation`, `cronjob`, `skills`, and the rest), in case the `-t` list ever stopped limiting it;
- memory, the user profile, the skill curator, and the background self-review off, so nothing one buyer says can carry over;
- session titles off (each would be an extra paid model call);
- private network addresses refused for web tools; no package installs; no Hermes model catalog download;
- approvals denied in one-shot runs (a guest has no tool that needs one).

A run counts as done only when Hermes exits cleanly with a final answer. If it does not (the model server is down, the key is wrong, the guest runs out of time), the buyer keeps the payment and can try again, as with any service. The buyer is told only that the guest gave no answer; the bridge's log tells you why, with the last lines Hermes printed.

## Checks before the bridge starts

`doctor`, `seller try`, and `serve` refuse to go on when:
- Hermes' Python is not known, does not exist, or has no Hermes installed;
- the guest's keys file sets any `HERMES_...` variable (those change how Hermes behaves, for example `HERMES_ALLOW_PRIVATE_URLS`), cannot be read, or other users can read it (`chmod 600` fixes that);
- an `env_file` you named does not exist;
- the `.env` file in Hermes' install folder sets a `HERMES_...` variable: Hermes loads that file into every run, guests included;
- on a machine with Hermes settings pinned by an administrator in `/etc/hermes`, those settings set a `HERMES_...` variable, allow private network addresses, or add MCP servers.

## Privacy

- Buyers' requests go to your AI model provider, and their search queries to the search service Hermes uses. Pick providers whose terms allow this, and mention it in the service's description if it matters to your buyers.
- Nothing is kept on your computer after a request: the guest's folder is deleted. The bridge's audit log records that a request ran, never its text.

## What is tested

- Offline, on Linux, macOS, and Windows: the exact command, environment, settings, and keys file a guest gets; that the request travels only on standard input and inside its markers; that every way Hermes can fail is treated as a failed run; time and output limits; every check above.
- Against real Hermes (0.21.5 and a pinned `main`) in CI, with a stand-in model server on `127.0.0.1`: a research guest is offered only `web_search` and `web_extract`; a guest without toolsets is offered no tools; a terminal command the model asks for is refused and never runs; a page on `127.0.0.1` the model asks for is refused and never fetched; only the request's own model calls are made; nothing is left behind.
- By hand, against real Hermes: a model server that never answers ends the run at `timeout_seconds` (Hermes itself keeps retrying, so the bridge's limit is what stops it), with the payment kept and no process left running.
