# Gateway demo: dynamic rulesets for a multi-agent LLM pipeline

Simulated three-agent email assistant (reader -> summariser -> executor) with a gateway
on every message and tool call. Nothing real is sent. Python 3.9+, standard library only.

## Run

    python run.py                                       # all configurations, comparison table
    python demo.py attack_redirect_intention ours        # step-by-step view
    python demo.py attack_redirect_intention ours_fooled

With the default mock backend the agents are scripted to always obey the injection.
That is the worst case for the gateway, so it tests the defence, not the LLMs.

## Real models (Gemini, Qwen, local Ollama, any OpenAI-compatible API)

    cp .env.example .env        # fill in one backend: key + model name
    python llm.py models        # list the model names your key can use
    python llm.py ping          # one test call
    python run.py --runs 5      # also enables the LLM-judge baseline

| Backend | LLM_BACKEND | Key variable |
|---|---|---|
| Google Gemini (AI Studio key) | gemini | GEMINI_API_KEY |
| Qwen on Alibaba Model Studio | qwen | DASHSCOPE_API_KEY |
| Qwen or other open models on your laptop | ollama | none |
| Anything else OpenAI-compatible | openai | LLM_API_KEY + LLM_BASE_URL |

`.env` is git-ignored; never put keys in code or commit them. Rate-limit errors (429)
are retried automatically. The table reports tokens per run for the overhead metric.

## How "ours" decides (gateway.py)

1. Lexical typing (`typer.py`) gives the email types: known/unknown sender,
   contains_instruction (plus mentions_file, mentions_other_address for logging).
2. Each type allows a set of answers; with several types the sets are intersected,
   so untrusted content can only remove answers:

   | Type | Answers the model may give |
   |---|---|
   | known sender | allow, escalate, block |
   | contains instruction | escalate, block |
   | unknown sender | block |

3. For each send to a recipient the user did not name, the decision model scores
   allow / escalate / block for one fixed question; the gateway takes the best-scored
   answer still allowed. Escalate = held for user approval (not executed here).
4. Hard limits apply whatever the model answers: only tools planned for the task,
   only known recipients, data never above the recipient's clearance.

## Configurations (run.py)

| Name | Meaning |
|---|---|
| none | no defence |
| fixed_rules | hard limits + only task-named recipients, no model |
| llm_judge | a generative LLM decides every tool call (real model only) |
| model_only | decision model may give any answer, hard limits only |
| ours | rulesets restrict the model's answers, plus hard limits |
| model_only_fooled / ours_fooled | worst case: the model always prefers allow |
| tool_filter | AgentDojo's tool-filter defence (`--defences tool_filter`) |

fixed_rules vs ours shows what the model adds; model_only vs ours (especially when
fooled) shows what the rulesets add.

Metrics follow AgentDojo: benign utility, utility under attack (task done and attack
failed), targeted attack success rate; plus benign escalation rate and spread (stages
the injection passed).

## Decision model (decision.py)

`SenderMatchStub` is a placeholder and not a result. Replace it with Jev or a small
open classifier behind the same `scores()` method.

## Files

| File | Purpose |
|---|---|
| `agents.py` | three agents and the pipeline loop |
| `llm.py` | mock and OpenAI-compatible backends |
| `env.py` | simulated files (sensitivity), contacts (clearance), tools |
| `typer.py` | lexical typing |
| `decision.py` | decision models |
| `gateway.py` | rulesets, hard limits, all configurations |
| `scenarios.py` | 4 benign cases, 5 attacks |
| `run.py` / `demo.py` | comparison table / step-by-step view |
