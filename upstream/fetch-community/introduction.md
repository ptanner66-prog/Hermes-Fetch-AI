# Introducing the project to Fetch.ai's developers

A short post for Fetch.ai's developer community, from the repository owner's account. Fetch.ai's
docs point developers to its Discord, <https://discord.gg/fetchai>; post it in the developer
channel there. The Innovation Lab is also on X as [@fetch_ai_IL](https://x.com/fetch_ai_IL). It
also asks four things about ASI:One's payment card that Fetch.ai's docs leave open. None of them
blocks setup, and one test purchase in ASI:One shows the real answers
([`docs/validation.md`](../../docs/validation.md#open-for-the-real-world-trial)). Whatever they
are, the bridge never delivers without a verified payment. Only one could need a code change: if
the card rounds amounts, the order codes must get coarser, or chat sales are refused. Asking puts
the answers on record and starts a conversation.
Post it once the fet-example pull request is open, and link that too.

---

**Hermes Agent on Fetch.ai: selling to ASI:One users and buying from other agents (testnet)**

Hi all. I've built [Hermes Fetch AI](https://github.com/ptanner66-prog/Hermes-Fetch-AI), an open-source (MIT) bridge and plugin that puts [Hermes Agent](https://hermes-agent.nousresearch.com/), Nous Research's open-source agent, on Fetch.ai's network. It's a community project, not affiliated with Nous Research or Fetch.ai. On Dorado it can:

- sell services the owner defines (web research, a code review by a local model, or their own program) to other agents and to ASI:One users, through the Agent Chat Protocol and the Agent Payment Protocol, with each payment checked on the ledger before delivery;
- let Hermes find agents on Agentverse, message them, and pay them, with the owner approving every payment in Hermes' own prompt;
- run the research itself on ASI:One's model, through its OpenAI-compatible API, if the owner chooses.

While building it I found a few gaps in `fet-example`'s payment check: the buyer's stated amount is trusted, a payment can be reused, and float rounding turns away exact payments. I've opened a fix: <link to the PR>.

Four questions about ASI:One's payments that the docs don't answer:

1. When ASI:One pays a `RequestPayment`, does it put the request's `reference` in the transaction memo, in `CommitPayment.reference`, or neither?
2. Does the payment card pay the requested amount exactly, down to a billionth of a FET? My agent tells orders apart by their amounts' digits at that scale (for example 0.100012345 FET).
3. Which `RequestPayment` fields does the card show: `description`, `metadata.content`, `deadline_seconds`?
4. When Dorado gives way to Eridanus, will the card support it, and with which `fet_network` value?

Thanks for building in the open. Feedback is very welcome.
