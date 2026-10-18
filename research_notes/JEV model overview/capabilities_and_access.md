# JEV Model Overview: Capabilities, Benchmarks, Access, and Licensing

Research date: 2026-10-12. Every source below is from 2025–2026 unless labeled otherwise. Vendor claims are marked as vendor claims.

## Q0. What does "JEV" most likely refer to?

### Takeaway
"JEV" almost certainly means **Jev**, a proprietary, API-only "System One" decision model from **TypeSafe AI** (San Francisco), put into early access in September 2026. It does not generate text. You send it text or structured "state" plus typed questions, and it returns choices, scores, or yes/no probabilities with confidence values. The closest near-miss is Meta's open-weights **V-JEPA 2 / V-JEPA 2.1** video world models. That is a completely different kind of model, so it is the backup candidate only if the user misspoke.

### Cited Findings
- Jev is TypeSafe AI's first public "System One model". It makes structured decisions instead of writing text and returns a choice, a score, or a yes/no answer with a probability. It was released on 15 September 2026 after two years in stealth. The CEO is Diogo Almeida, a former OpenAI researcher. The name refers to William Stanley Jevons (Jevons paradox). — [DataNorth](https://datanorth.ai/blog/jev-what-it-is-and-why-this-new-model-matters); [MindStudio tag page](https://www.mindstudio.ai/blog/tag/jev-ai-model)
- Official launch post: TypeSafe calls Jev "a frontier-intelligence function call". It says Jev uses a new architecture, a parallel sampler, and a training method called "Reinforcement Learning for Calibrated Decisions (RLCD)", and that it is "not just a smaller LLM". No parameter count or model size is given. — [TypeSafe launch blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
- **Date conflict:** when fetched, the launch post appeared to carry a date of October 12, 2026 (today). Secondary sources consistently say 15 September 2026, and OpenRouter listed a Jev-based router on 25 September. The October date may be an artifact of a dynamically rendered page. Treat **mid-September 2026** as the most likely launch date. — [TypeSafe launch blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev); [DataNorth](https://datanorth.ai/blog/jev-what-it-is-and-why-this-new-model-matters); [RuntimeWire](https://runtimewire.com/article/typesafe-jev-router-openrouter-launch)
- Several independent ecosystem integrations exist, which confirms Jev is a real, widely discussed release: LiteLLM pass-through docs, a Pydantic AI provider page, a Real Python reference entry, an AI/ML API listing, an LLM Reference entry, and arXiv preprints ("Jev in the Wild", "JevOut: Natural Context Can Flip Decision Models"). — [LiteLLM](https://docs.litellm.ai/docs/pass_through/typesafe.md); [Pydantic AI docs](https://pydantic.dev/docs/ai/models/typesafe.md); [Real Python](https://realpython.com/ref/ai-coding-tools/jev/); [AIML API](https://aimlapi.com/models/typesafe-jev-latest); [LLM Reference](https://www.llmreference.com/provider/typesafe-ai/jev); [arXiv 2609.30216](https://arxiv.org/pdf/2609.30216); [arXiv 2609.30243](https://arxiv.org/pdf/2609.30243)
- Other things named "Jev" (lower confidence, mostly derivative):
  - "Simple Jev" from Featherless AI, which reportedly turns open Hugging Face models into typed classifiers by reading next-token logits. This comes from an aggregator summary only. — [hermes-ai.net](https://hermes-ai.net/news/featherless-ai-s-simple-jev-turns-open-hugging-face-models-into-classifier-apis/)
  - A small GitHub repo, Code-Forge-AU/jev-llm, with 2 contributors. — [Trendshift](https://trendshift.io/repositories/242168)
  - A third-party "Jev" MCP server. — [mcpmarket](https://mcpmarket.com/server/jev-8)
  - No official Jev model card exists on Hugging Face. — search results summarized above
- Near-miss: Meta's **V-JEPA 2** (arXiv 2506.09985, 2025-06-25) and **V-JEPA 2.1** (arXiv 2603.14482, 2026-03-16) are self-supervised video encoders and world models. The official README mentions no newer JEPA release. — [facebookresearch/vjepa2 README](https://cdn.jsdelivr.net/gh/facebookresearch/vjepa2@main/README.md)
- Late-2025 context: Meta's announced 2026 models ("Mango" for image/video, "Avocado" for text) are not JEPA models, and Yann LeCun, who led JEPA research, announced he was leaving Meta to found a startup. — [TechCrunch, 2025-12-19](https://techcrunch.com/2025/12/19/meta-is-developing-a-new-image-and-video-model-for-a-2026-release-report-says)

### Inferences
- If the user says "the new model jev" in October 2026, they almost certainly mean TypeSafe's Jev: it is new, has the exact name, and has a lot of developer coverage. V-JEPA is worth asking about only if they want video understanding or robotics.
- Jev is not a general LLM. Before committing, the user should confirm their project needs classification, routing, scoring, or gating decisions rather than generated text.

### Gaps
- I did not confirm the exact launch timestamp on the primary page; see the date conflict above.
- I found no parameter count, architecture paper, or training-data disclosure from TypeSafe. The launch FAQ lists questions on training data and the algorithm, but the answers were not in the fetched content.

---

## Q1. What tasks and modalities does Jev handle? What are its strengths and limitations?

### Takeaway
Jev takes text or JSON input and returns only typed, calibrated decisions, using three primitives: **Choice**, **Score**, and **Noul**. It is designed for fast routing, classification, guardrails, and gating inside software and agents. It cannot generate prose or code, and it is weak at math, counting, dates, and multi-hop reasoning.

### Cited Findings
- **Input:** text only, as a string, a JSON object, or an array of text values. Images, audio, and video are not accepted and must be converted to text first. — [TypeSafe Models docs](https://docs.typesafe.ai/models)
- **Primitives:**
  - **Choice** picks one option (up to 255 options) and returns per-option probabilities plus a confidence.
  - **Score** rates the state on an ordered rubric of 2–10 levels.
  - **Noul** answers yes/no with a probability between 0 and 1.
  - Several questions can be sent in one request.
  - Sources: [DataNorth](https://datanorth.ai/blog/jev-what-it-is-and-why-this-new-model-matters); [Docs index](https://docs.typesafe.ai/llms.txt)
- **Large option sets:** above 255 options, Jev uses a two-stage process (score each option independently, then choose), which "can cause occasional slowdowns". — [TypeSafe launch blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
- **Confidence vs. probability:** confidence is derived from the probability distribution. For three options, DataNorth gives the formula (3 × max probability − 1) ÷ 2. — [DataNorth](https://datanorth.ai/blog/jev-what-it-is-and-why-this-new-model-matters)
- **Context window:** 64k tokens per request (state plus all questions), and 32k for state plus the single longest question. — [TypeSafe Models docs](https://docs.typesafe.ai/models)
- **Language:** English works best. Other languages, including CJK, are handled less well. — [TypeSafe Models docs](https://docs.typesafe.ai/models)
- **Stated strengths:** jev-1.13 is "fast, calibrated, and good at common-sense judgment" and performs best on System One tasks. — [Jev 1.13 jaggedness page](https://docs.typesafe.ai/model-jaggedness/jev-1.13)
- **Stated limitations** (official jaggedness page):
  - It reads questions literally rather than inferring intent.
  - It is "not a calculator", so arithmetic should be done in code.
  - It counts unreliably.
  - It handles hex, RGB, and binary values poorly.
  - Score levels are only weakly calibrated as numeric magnitudes.
  - It reads dates as text and is unreliable at ordering dates, durations, and time windows.
  - Double negatives and multi-hop reasoning reduce accuracy.
  - Irrelevant content in a large state reduces accuracy ("context rot").
  - Adversarial text can shift its answers.
  - Contradictory criteria confuse it.
  - It leans toward the first option in a Choice.
  - It is not trained to generate text.
  - Source: [Jev 1.13 jaggedness](https://docs.typesafe.ai/model-jaggedness/jev-1.13)
- **"Zero hallucinations" claim:** this only means schema conformance is guaranteed by construction (0% type errors). The FAQ says Jev "guarantees the shape of its answers, not that every decision is correct." It is also not deterministic. — [TypeSafe launch blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev); [DataNorth](https://datanorth.ai/blog/jev-what-it-is-and-why-this-new-model-matters)
- **Recommended patterns:**
  - Speculative fan-out (many questions in one call)
  - Confidence-gated routing
  - Composite scoring with weights set in code
  - Intent routing to deterministic logic, a specialist LLM, or a human
  - Source: [Docs index](https://docs.typesafe.ai/llms.txt)
- **Independent research:** the "JevOut" preprint studies how natural added context can flip a decision model's answers. — [arXiv 2609.30243](https://arxiv.org/pdf/2609.30243)

### Inferences
- The best fit is architectures where an LLM or code handles generation and Jev handles high-volume cheap decisions: guardrails, RAG passage filtering, intent routing, moderation, triage, and agent tool or skill selection.
- Because of the first-option bias and adversarial sensitivity, production use should shuffle or validate option order and test against adversarial inputs.

### Gaps
- Official docs give no accuracy numbers per task type.
- I did not read the JevOut paper's quantitative results.

---

## Q2. What benchmarks were reported, and how does Jev compare to alternatives?

### Takeaway
TypeSafe **deliberately published no public-benchmark results**. All comparisons are vendor-run evaluations: speed and cost figures plus four in-house "workflow evals" whose reference labels come from frontier LLMs, not humans. The speed and cost advantages are large; accuracy parity is claimed but not independently verified.

### Cited Findings
- On public benchmarks, TypeSafe says: "We deliberately chose not to publish performance against public benchmarks." — [DataNorth](https://datanorth.ai/blog/jev-what-it-is-and-why-this-new-model-matters)
- **Speed claims:**
  - 40–200× faster than frontier LLMs on System One-shaped queries, at "similar levels of intelligence".
  - End-to-end latency of 70–500 ms, versus 3–329 s for frontier LLMs (citing llm-benchmarks.diegoromero.es).
  - Latency was measured from laptops on the US West Coast.
  - Source: [TypeSafe launch blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
- **Workflow evals:**
  - Four published workflows with fixed compute graphs, written by TypeSafe's own team.
  - Headline result: 193.6× faster and 444.6× cheaper, which TypeSafe calls "on the higher end of real world gains".
  - Reference probabilities are the average of "GPT-6 Astra" and "Fable 5.1"; TypeSafe admits this biases results toward OpenAI and Anthropic models.
  - TypeSafe claims Jev owns the Pareto frontier across almost 2 orders of magnitude.
  - Details are on evals.typesafe.ai.
  - Sources: [TypeSafe launch blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev); [DataNorth](https://datanorth.ai/blog/jev-what-it-is-and-why-this-new-model-matters)
- **Homepage side-by-side demo:**
  - Jev: 0.114 s and $0.000081. LLM: 8.566 s and $0.013880. That is about 75× faster and 171× cheaper.
  - The comparison model was GPT-5.6 Terra at default reasoning.
  - The only disagreement was on a "Churn likelihood level" question, which TypeSafe calls genuinely ambiguous.
  - TypeSafe concedes the short, dense state favors Jev.
  - Sources: [DataNorth](https://datanorth.ai/blog/jev-what-it-is-and-why-this-new-model-matters); [TypeSafe launch blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
- **Hallucination and type-error comparison:** the LLM figures come from OpenRouter (possible routing bias), and Jev's 0% holds by construction, not by measurement. — [TypeSafe launch blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
- **Demos:**
  - A Doom bot using structured state made about 10 queries per second at roughly $7/hour; TypeSafe admits a non-AI bot could play better.
  - In Wikiracing, Jev was compared against non-reasoning LLM modes, so the speedups there are smaller.
  - Source: [TypeSafe launch blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
- **Reviewer caveat:** TypeSafe's capabilities team wrote the workflows, and the "correct" answers are LLM averages rather than human-labeled ground truth. — [search summary of secondary reviews, e.g. Lindy](https://www.lindy.ai/blog/jev-ai); [DataNorth](https://datanorth.ai/blog/jev-what-it-is-and-why-this-new-model-matters)

### Inferences
- The realistic alternatives are:
  - Small or fast LLMs with structured outputs or logprobs
  - Fine-tuned classifiers or embedding-plus-classifier pipelines
  - TypeSafe's own open-source System One adapter, which wraps LLMs
- The user should build a small human-labeled eval set for their own task and compare Jev against a cheap LLM baseline before committing. Vendor accuracy claims are not independently validated.

### Gaps
- I found no third-party leaderboard results for Jev.
- I did not fetch evals.typesafe.ai or the "Jev in the Wild" preprint, so per-workflow accuracy numbers are missing.

---

## Q3. How can Jev be accessed (weights, API, pricing, SDKs, hardware)?

### Takeaway
Jev is **hosted-API only**: there are **no open weights** and no self-hosting, so local hardware or VRAM requirements do not apply. Access is through the TypeSafe API (early access, API key from the console). The official SDKs are Python (`typesafe-sdk`) and JavaScript/TypeScript (`@typesafe-ai/sdk`), and there are third-party integrations (Pydantic AI, LiteLLM, Vercel AI Gateway, OpenRouter's "Jev Router", AI/ML API). Official pricing is **$0.042 per million input tokens, with output free**.

### Cited Findings
- **Models and endpoint:**
  - Current model: Jev 1.13, versioned ID `jev-1.13.0`.
  - Aliases `jev-latest` and `jev-preview` both currently resolve to it.
  - Endpoint: `POST /v1/systemone`. `GET /v1/models` lists the accepted names.
  - Pin a version if you tune thresholds, because aliases move to new releases.
  - Source: [TypeSafe Models docs](https://docs.typesafe.ai/models)
- **Pricing:** $42 per billion tokens ($0.042 per million), input only; output tokens are free. — [TypeSafe Models docs](https://docs.typesafe.ai/models); [TypeSafe launch blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
  - Aggregators list different numbers: about $0.04 per million and about $0.058 per million (this may include a reseller markup). — [AIML API](https://aimlapi.com/models/typesafe-jev-latest) (as summarized in search)
  - TypeSafe says it cannot prove its pricing isn't subsidized and expects prices to fall. — [TypeSafe launch blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
- **Rate limits (official):**
  - 100K tokens per second and 80 requests per second; exceeding either returns HTTP 429.
  - The SDKs retry with backoff and honor `retry-after`.
  - Limits are dynamic, and higher limits are available on custom or enterprise plans via sales@typesafe.ai.
  - Source: [TypeSafe Models docs](https://docs.typesafe.ai/models)
  - **Conflict:** DataNorth reports 250,000 tokens per second and 1,200 requests per minute. Prefer the official docs. — [DataNorth](https://datanorth.ai/blog/jev-what-it-is-and-why-this-new-model-matters)
- **Access status:**
  - The launch post says Jev is in early access, with waitlist users being onboarded.
  - Links: console.typesafe.ai, a playground at console.typesafe.ai/playground (for early-access users with a shared link), and docs.typesafe.ai.
  - The quickstart simply says to get a key at console.typesafe.ai/keys and set `TYPESAFE_API_KEY`.
  - Sources: [TypeSafe launch blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev); [Quickstart](https://docs.typesafe.ai/introduction/quickstart.md)
- **Install:**
  - Python 3.10+: `pip install typesafe-sdk`, or `uv add typesafe-sdk`.
  - Node 20+: `npm install @typesafe-ai/sdk` (ESM). Running `.ts` files directly needs Node 22.18+.
  - Bash: curl 7.76+.
  - Agent skill: `npx skills add typesafe-ai/skills --skill typesafe-ai`, or `claude plugin install typesafe@typesafe-ai`.
  - Source: [Quickstart](https://docs.typesafe.ai/introduction/quickstart.md)
- **REST request:**
  - `POST https://api.typesafe.ai/v1/systemone` with `Authorization: Bearer <key>`.
  - The body contains `state`, `model`, and `questions`; each question has a `type` of `choice`, `score`, or `noul`.
  - The response includes `model`, `answers` keyed by question ID, and `usage` (`input_tokens`, `output_tokens`).
  - In Python the SDK exposes `response.choices`, `.scores`, and `.nouls`.
  - Source: [Quickstart](https://docs.typesafe.ai/introduction/quickstart.md)
  - Minimal Python pattern:
    ```python
    from typesafe_sdk import Noul, TypeSafeClient
    with TypeSafeClient(model="jev-latest") as client:
        r = client.system_one(state="...", questions={"urgent": Noul(instructions="Does the message convey urgency?")})
        print(r.nouls["urgent"].noul)
    ```
- **SDK stability:** sync and async Python clients exist. Only early SDK releases exist, and minor versions have already introduced breaking changes to question types. — [Docs index](https://docs.typesafe.ai/llms.txt); search summary citing [Real Python](https://realpython.com/ref/ai-coding-tools/jev/) and [towardsai](https://pub.towardsai.net/what-is-jev-how-jev-works-inside-an-ai-agent-c5a3b236f779)
- **Streaming:** not offered by the TypeSafe API. LiteLLM provides a pass-through (replace `https://api.typesafe.ai` with `LITELLM_PROXY_BASE_URL/typesafe`) rather than `/chat/completions` support. — [LiteLLM](https://docs.litellm.ai/docs/pass_through/typesafe.md)
- **Pydantic AI:** has a built-in TypeSafe provider. Install `pydantic-ai-slim` with the `typesafe` extra and use the model string `typesafe:jev-latest`. — [Pydantic AI docs](https://pydantic.dev/docs/ai/models/typesafe.md)
- **Vercel and OpenRouter:**
  - Jev 1.13 is reportedly available via Vercel AI Gateway and OpenRouter. — [search summary](https://www.mindstudio.ai/blog/tag/jev-ai-model)
  - OpenRouter definitely lists **`typesafe/jev-router`**, a Jev-based *router* that picks a model and reasoning effort per request through the standard chat-completions API. It was reportedly listed on 25 September, priced at $0.
  - I could not confirm whether plain `jev-1.13` is available as an OpenRouter model ID.
  - Sources: [OpenRouter](https://openrouter.ai/typesafe/jev-router); [RuntimeWire](https://runtimewire.com/article/typesafe-jev-router-openrouter-launch)
  - An aggregator claims the router has a 1M-token context and multimodal input. Those specs describe the routed LLMs, not Jev itself (Jev is text-only with 64k context). — [lmmarketcap](https://lmmarketcap.com/zh/model/typesafe-jev-router)
- **AI/ML API:** offers OpenAI-compatible access as `typesafe/jev` at api.aimlapi.com/v1. — [AIML API](https://aimlapi.com/models/typesafe-jev-latest)
- **Data handling:** TypeSafe does not train on customer requests or responses. Zero data retention is available for enterprise customers. — [TypeSafe Models docs](https://docs.typesafe.ai/models); [Legal](https://docs.typesafe.ai/legal.md)
- **Open weights:** none. The only open-source model-side component mentioned is the **System One LLM adapter** for Python, which constrains LLMs to output structured decisions. — [TypeSafe launch blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev); [GitHub](https://github.com/typesafe-ai/system-one-adapter-python)

### Inferences
- Local GPU hardware is irrelevant for Jev. Cost is driven by input tokens only; for example, 1B input tokens costs about $42 at list price, and multiple questions can be batched per call.
- Early-access status, changing SDKs, and dynamic rate limits mean the user should pin `jev-1.13.0` and the SDK version, and design for 429 errors and breaking changes.

### Gaps
- I could not determine whether early access still requires waitlist approval or whether keys are self-serve; the quickstart and launch post differ in tone.
- I found no free-tier or credit details.
- I did not confirm the regions or the deprecation policy.

---

## Q4. What license governs Jev? Is commercial use allowed?

### Takeaway
Jev is not open-licensed. Use is governed by TypeSafe's **Master Customer Agreement (MCA)**, Data Processing Agreement, Privacy Policy, and Acceptable Use Policy. **Commercial use is allowed** for embedding the API in your own apps, and you own the outputs. The main restrictions are no reselling the API as a standalone offering, no distillation or training competing models, no reverse engineering, and no security testing. The service comes with no SLA, is provided "AS IS", and TypeSafe may make breaking API changes.

### Cited Findings
- **Commercial use (MCA §2.2):** you may embed the API in your own applications for your end users, as long as they follow the Documentation and the Agreement. — [TypeSafe MCA](https://typesafe.ai/legal/mca)
- **Restrictions (MCA §2.3):**
  - No reselling the Services as a standalone offering.
  - No using the Services or Output for distillation, or to train a model that imitates the Services or builds a "similar or competing product or service".
  - No reverse engineering.
  - No derivative works of the Services.
  - No vulnerability or security testing.
  - No exceeding usage limits or sharing credentials.
  - The Acceptable Use Policy also applies.
  - Source: [TypeSafe MCA](https://typesafe.ai/legal/mca)
- **Ownership:** you keep your Input (§11). TypeSafe assigns you its rights in Output, "if any" (§4.2). — [TypeSafe MCA](https://typesafe.ai/legal/mca)
- **Data use:** TypeSafe may not train on Customer Data without your consent (§4.1). It may use Telemetry "without restriction" (§4.3). It has no obligation to retain Customer Data and may delete it at any time (§10.3). — [TypeSafe MCA](https://typesafe.ai/legal/mca)
- **Warranty and stability:**
  - No uptime SLA. TypeSafe warrants only that the Services perform materially as documented (§9.1).
  - Provided "AS IS" and "AS AVAILABLE", and "MAY PRODUCE INACCURATE OR ERRONEOUS OUTPUT" (§9.3).
  - TypeSafe may make API changes that break integrations, with commercially reasonable notice (§2.5).
  - Source: [TypeSafe MCA](https://typesafe.ai/legal/mca)
- **Liability:** capped at the greater of 12 months' fees or $50 (§12.2). TypeSafe indemnifies you against US IP claims about the Services, excluding Output. — [TypeSafe MCA](https://typesafe.ai/legal/mca)
- **Billing:** prepaid Credits are non-refundable, and purchased Credits expire after 12 months (§8.2). — [TypeSafe MCA](https://typesafe.ai/legal/mca)
- **Disputes and changes:** California law, JAMS arbitration in San Francisco, and a class-action waiver (§15–16). Term changes take effect at least 60 days after notice. — [TypeSafe MCA](https://typesafe.ai/legal/mca)
- **Other legal documents:** the DPA, Privacy Policy (which commits to "not to train models on user data"), and enterprise ZDR. — [Legal](https://docs.typesafe.ai/legal.md)

### Inferences
- Building a commercial product on top of Jev is permitted. Building a competing decision-model product, or using Jev outputs to train a substitute classifier, appears to be prohibited by the anti-distillation clause. The user should check this if they plan to bootstrap their own model from Jev labels.
- The lack of an SLA and the breaking-change clause make Jev risky as a single point of failure. The user should plan a fallback, such as the open-source System One adapter over an LLM.

### Gaps
- I did not read the contents of the Acceptable Use Policy (for example, high-risk or regulated uses).
- I could not find the licenses of the SDKs or of `system-one-adapter-python`.
- The MCA does not address publishing benchmark results.

---

## Q5. What official code, quickstarts, notebooks, or fine-tuning recipes exist?

### Takeaway
The official docs include a 5-minute quickstart, concept guides, architecture patterns, about 20 cookbooks, a smart-home demo, full Python and JavaScript SDK references, and an agent skill for Claude Code and Codex. **No fine-tuning is offered or documented.** Users customize behavior through question instructions, structured criteria, and confidence thresholds.

### Cited Findings
- **Getting started:** Quick start, "Jev with coding agents", and an AI primer. **Concepts:** System One, State, and How to build with TypeSafe. **Primitives:** Choice, Score, Noul, Advanced structure, and Confidence. — [Docs index](https://docs.typesafe.ai/llms.txt)
- **Cookbooks:**
  - Function calling
  - Skill suggestion (choosing from a catalog of 182 skills)
  - Guardrails for LLMs
  - Citation checking
  - Classifying RAG passages
  - Simple memory
  - Hierarchical classification (beam search)
  - Classification using confidence (SEC reports)
  - Twitch chat filter
  - SDE cascade
  - Date extraction
  - Pre-parsed value extraction
  - Structure recovery
  - Re-ranking (BM25 legal passages)
  - Line-by-line semantic search
  - Knowledge-graph entity alignment
  - Self-consistency for choices and for nouls
  - Parallel questions (13 regulatory questions in one call)
  - Autoresearch feature discovery
  - Source: [Docs index](https://docs.typesafe.ai/llms.txt)
- **Demos:** a smart-home assistant. **SDK docs:** Python usage, changelog, sync and async clients, retries, and exceptions; JavaScript classes (e.g. `TypeSafeClient`, `RateLimitError`) and helper functions `choice()`, `noul()`, and `score()`. — [Docs index](https://docs.typesafe.ai/llms.txt)
- **Other official resources:** a Discord community and a machine-readable docs index at docs.typesafe.ai/llms.txt. — [Jev 1.13 jaggedness](https://docs.typesafe.ai/model-jaggedness/jev-1.13)
- **Open-source repos:** github.com/typesafe-ai/system-one-adapter-python and the typesafe-ai/skills agent skill marketplace. — [TypeSafe launch blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev); [Quickstart](https://docs.typesafe.ai/introduction/quickstart.md)
- **Third-party tutorials:**
  - "A Hands-On Guide to Jev" (Level Up Coding)
  - "What is Jev: How Jev works inside an AI agent" (Towards AI)
  - A guide to using Jev via typesafe_sdk, pydantic_ai, and OpenRouter
  - A Luma hands-on event, "JEV explained"
  - Sources: [Level Up](https://levelup.gitconnected.com/a-hands-on-guide-to-jev-69771edd027a); [Towards AI](https://pub.towardsai.net/what-is-jev-how-jev-works-inside-an-ai-agent-c5a3b236f779); [rogue-marketing guide](https://the-rogue-marketing.github.io/how-to-use-jev-typesafe-sdk-pydantic-ai-openrouter/); [Luma](https://luma.com/9v2t909b)

### Inferences
- The guardrails, RAG-passage classification, intent-routing, and confidence-gated routing cookbooks are the fastest starting points for a typical agent or app project.

### Gaps
- I found no fine-tuning, custom-training, or adapter-training documentation. It appears not to be offered, but the docs do not explicitly say so.

---

## Backup candidate: Meta V-JEPA 2 / 2.1 (if the user actually meant "JEPA")

### Takeaway
V-JEPA 2 (June 2025, older info) and V-JEPA 2.1 (March 2026) are **open-weights, MIT-licensed** self-supervised video encoders for video understanding, action anticipation, and, in the V-JEPA 2-AC variant, robot planning. They run locally on a GPU and fit the description "world model". They do not fit "the new model" in October 2026 as well as TypeSafe's Jev does.

### Cited Findings
- **Sizes:**
  - V-JEPA 2: ViT-L/16 300M, ViT-H/16 600M, ViT-g/16 1B (at 256 and 384 resolution).
  - V-JEPA 2.1 (384 resolution): ViT-B 80M, ViT-L 300M, ViT-g 1B, ViT-G 2B.
  - V-JEPA 2-AC: an action-conditioned model on a ViT-g backbone.
  - Source: [vjepa2 README](https://cdn.jsdelivr.net/gh/facebookresearch/vjepa2@main/README.md)
- **License:** "The majority of V-JEPA 2 is licensed under MIT", and three files are Apache 2.0. — [vjepa2 README](https://cdn.jsdelivr.net/gh/facebookresearch/vjepa2@main/README.md)
- **Benchmarks (V-JEPA 2):**

  | Benchmark | V-JEPA 2 | Previous best |
  |---|---|---|
  | SSv2 (probe) | 77.3% | 69.7% (InternVideo2-1B) |
  | Diving48 | 90.2% | 86.4% |
  | EK100 (action anticipation) | 39.7% | 27.6% |
  | MVP (video QA) | 44.5% | — |
  | TempCompass (video QA) | 76.9% | — |

  Source: [vjepa2 README](https://cdn.jsdelivr.net/gh/facebookresearch/vjepa2@main/README.md)
- **Robot tasks (V-JEPA 2-AC vs. Octo vs. Cosmos):** 100/60/20/80/50% vs. 100/10/0/10/10% vs. 80/0/20/0/0% across Reach, Grasp Cup, Grasp Box, Pick-Place Cup, and Pick-Place Box. — [vjepa2 README](https://cdn.jsdelivr.net/gh/facebookresearch/vjepa2@main/README.md)
- **Access:**
  - Hugging Face: `facebook/vjepa2-vitl-fpc64-256`, `facebook/vjepa2-vith-fpc64-256`, `facebook/vjepa2-vitg-fpc64-256`, `facebook/vjepa2-vitg-fpc64-384` (loaded with transformers `AutoModel` and `AutoVideoProcessor`).
  - V-JEPA 2.1 loads via PyTorch Hub.
  - Notebooks: `vjepa2_demo.ipynb` (also on Colab) and `energy_landscape_example.ipynb`.
  - A CUDA GPU is recommended. On macOS, `decord` must be replaced (e.g. with `eva-decord`).
  - Source: [vjepa2 README](https://cdn.jsdelivr.net/gh/facebookresearch/vjepa2@main/README.md)
- **Speed claim:** Meta claimed V-JEPA 2 is 30× faster than Nvidia's Cosmos, possibly on different benchmarks. — [cnyes](https://anuenews.cnyes.com/news/id/6019124)

### Gaps
- I did not find exact VRAM requirements per size, and V-JEPA 2.1 benchmark numbers were not extracted.
