# Competitor Architecture Teardown

| Feature / Metric | **WeaveCrawl** | **Browser-Use** | **Stagehand** | **TypeSafe Jev** | **LangChain Agent** |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Site Navigation Memory** | **Persistent SQLite Graph** | Stateless (Memoryless) | Cached selectors only | Stateless | In-context message history |
| **Tool Calling Architecture** | **Hybrid 2-Tier Pruner + Pointer** | Naive prompt dump | Fixed action schema | 1-step Speculative Head | Full catalog dump |
| **Token Bloat Tax (33 tools)** | **137 tokens (-87.4%)** | ~1,100 tokens (100%) | ~850 tokens | Dynamic per-turn table | ~1,200 tokens |
| **Token Bloat Tax (140 tools)**| **136 tokens (-97.1%)** | ~4,650 tokens (Degraded)| N/A (Fixed schema) | N/A | ~4,800 tokens (Fails) |
| **Replay Cost & Latency** | **0.223 ms / 0 tokens** | 5–15 s / ~2,000 tokens | 2–5 s / ~800 tokens | N/A (Full re-eval) | 6–20 s / Full tokens |
| **Shadow DOM Support** | **Full (Microsecond probe)** | Flaky (CDP traverse) | Partial | None | None |
| **Wire Observation Size** | **2,658 tokens (-82.2%)** | Full tree (~15k tokens) | Hybrid snapshot | Indexed element table | Raw DOM dump |
| **Self-Hosting Cost** | **Zero GPU (CPU Silicon)** | Requires frontier API | Requires frontier API | Cloud API subscription | Requires frontier API |

---

## Technical Differentiators

### 1. The Tool Bloat Tax
Existing agent frameworks pass full JSON schemas for every registered capability into the LLM system prompt on every turn. As agent platforms expand to 70–140+ tools, prompt token consumption exceeds 4,500 tokens per turn before the model even reads the webpage. WeaveCrawl eliminates this overhead locally in ~1.05s on CPU silicon, delivering a lean ~136-token prompt.

### 2. Structural Memory vs. Cold Re-Discovery
When Browser-Use or LangChain visits a multi-step workflow for the 100th time, it still navigates blind — taking screenshots, issuing LLM calls, and spending tokens. WeaveCrawl compiles successful paths into a local SQLite graph. Subsequent executions resolve the exact navigation sequence deterministically in 0.223 ms at zero token cost.
