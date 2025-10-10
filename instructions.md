**You are a senior Python engineer. Build the following module exactly as specified.**

---

### 0) Goal & non‑goals

**Goal:** Implement a pip‑installable Python package `vnc-use` that exposes a **LangGraph** agent which runs a tight *observe → propose → act* loop with **Google’s Gemini 2.5 *Computer Use* model** (“the model”), executing the returned **UI action function calls** against a **VNC** desktop (mouse/keyboard). The agent returns when the model stops proposing actions or a step/time budget is reached.

**Non‑goals (hard requirements):**

* ❌ **No OCR or template matching.** The model must ground actions directly from screenshots, per Computer Use design.
* ❌ No app‑specific heuristics; keep it **generic** (like `browser-use`, but the “hands” are VNC).
* ✅ **Safety‑aware:** if the model marks an action `require_confirmation`, the graph **pauses** (HITL) until user approval/denial.

---

### 1) Project layout

Create this structure:

```
vnc-use/
  __init__.py
  agent.py              # LangGraph graph + public Agent.run()
  backends/
    __init__.py
    vnc.py              # VNC controller (screenshots, mouse, keys, scroll, drag).
  planners/
    __init__.py
    gemini.py           # Gemini 2.5 Computer Use client wrapper.
  types.py              # Typed dicts / pydantic models for state & actions.
  safety.py             # HITL gating & safety decisions handling.
  logging_utils.py      # Structured logging + on-disk run artifacts.
  cli.py                # "cua-vnc run 'task...'" entrypoint with argparse.
pyproject.toml
README.md
```

Target **Python 3.10+**, type‑hint everything, include docstrings.

---

### 2) Dependencies

Add to `pyproject.toml`:

* `langgraph>=0.2`
* `langgraph-checkpoint-sqlite` (or use `langgraph.checkpoint.sqlite.SqliteSaver`)
* `google-genai>=0.3` (latest) for Gemini API (Developer API)
* `vncdotool>=0.9`
* `pillow`
* `typing-extensions`
* `pydantic>=2`
* `click` or stdlib `argparse` (use `argparse`)

The **only** network secret is `GOOGLE_API_KEY` read by `google.genai.Client()`.

---

### 3) Public API

Expose:

```python
# High-level entry point
from vnc-use.agent import VncUseAgent

agent = VncUseAgent(
    vnc_server="localhost::5901",
    vnc_password=None,
    screen_size=(1440, 900),         # default; can auto-detect from screenshot
    excluded_actions=None,           # list[str], passed to Computer Use tool
    step_limit=40,                   # guardrail
    seconds_timeout=300,             # guardrail
    hitl_mode=True                   # enable human approval for risky actions
)

# Synchronous run; returns final transcript & run artifacts folder
result = agent.run(task="Open a browser, search 'LangGraph', open the docs, summarize first screen.")
```

Also install a CLI:

```
python -m vnc-use.cli run \
  --vnc localhost::5901 \
  --task "Find today's weather for Paris and copy the temperature to clipboard"
```

---

### 4) Core behavioral spec (Computer Use‑correct)

Implement the **4‑step loop** the docs prescribe:

1. **Send request** to the model:

   * Use **model id** `gemini-2.5-computer-use-preview-10-2025`.
   * Include the **Computer Use tool** with `environment=ENVIRONMENT_BROWSER`.
   * Allow callers to pass `excluded_predefined_functions` and optional **custom user functions** (not required in this milestone).
   * Turn on `thinking_config.include_thoughts=False` by default (configurable).
   * First turn: include the user’s **task** and (optionally) an **initial screenshot**.

2. **Receive response**:

   * Parse **one or more** `function_call`s (parallel calls are allowed by the API; we will serially execute them for now).
   * If present, read **`safety_decision`**; when it says **`require_confirmation`**, **pause** via LangGraph interrupt (HITL) before executing.

3. **Execute actions** on VNC:

   * The model returns **normalized coordinates on a 0–999 grid** (a 1000×1000 reference). Convert to pixels using the **current screenshot width/height** (don’t assume the default).
   * Implement these built‑ins now:

     * `open_web_browser` (no‑op placeholder; rely on user’s VM having a browser pinned; optional custom function later)
     * `click_at(x, y)`
     * `hover_at(x, y)`
     * `type_text_at(x, y, text, press_enter?, clear_before_typing?)`
     * `key_combination(keys)`
     * `scroll_document(direction, magnitude=800)`
     * `scroll_at(x, y, direction, magnitude=800)`
     * `drag_and_drop(x, y, destination_x, destination_y)`
   * Map each action to **vncdotool** primitives.

4. **Capture new state**:

   * Immediately capture a **PNG screenshot** and return it to the model inside a **`FunctionResponse`** on the next **user** turn.
   * If multiple function calls were executed this turn, send **one `FunctionResponse` per function call** (iterate).
   * Include a `"url"` field when you have one (browser). In VNC desktop cases, set `"url": ""`.

Continue until the model returns **no function calls** (task done), a safety block occurs, or the step/time budget triggers an early stop.

---

### 5) VNC backend

Create `backends/vnc.py` with a `VNCController` class:

* `.connect(server: str, password: str|None)` returning self.
* `.screenshot_png() -> bytes` (write to tempfile, read bytes).
* Pointer methods: `.move(x, y)`, `.click(x, y, button=1)`, `.double_click(x, y)`, `.drag_and_drop(x0, y0, x1, y1)`.
* Keyboard: `.type_text(text, press_enter: bool, clear_first: bool)`, `.key_combo("control+a")`.
* Scrolling: `.scroll(direction: Literal["up","down","left","right"], magnitude: int=800)` implemented via PageUp/PageDown/Arrow keys (repeat by `magnitude/400` heuristic).
* Prefer `mouseMove` before `mousePress` to avoid injection glitches.

Use `vncdotool.api.connect`, `captureScreen`, `mouseMove`, `mousePress`, `mouseDown`, `mouseUp`, `mouseDrag`, `keyPress`, `keyDown`, `keyUp`.

---

### 6) Gemini *Computer Use* wrapper

Create `planners/gemini.py`:

* `GeminiComputerUse` with:

  * `__init__(excluded_actions: list[str]|None)`.
  * `start_contents(task: str, maybe_initial_png: bytes|None) -> list[Content]` (first “user” message).
  * `generate(contents, config) -> RawResponse` using `genai.Client().models.generate_content(...)`.
  * `extract_function_calls(response) -> list[dict{name, args}]`.
  * `build_function_response(name: str, screenshot_png: bytes, extra: dict|None) -> FunctionResponse`.

* `config = GenerateContentConfig(tools=[Tool(computer_use=ComputerUse(environment=ENVIRONMENT_BROWSER, excluded_predefined_functions=excluded))], thinking_config=ThinkingConfig(include_thoughts=False))`.

* **Denormalization helpers**: `denorm_x(x, w)`, `denorm_y(y, h)` converting **0–999** to pixels with rounding.

---

### 7) LangGraph agent

Create `agent.py`:

* **State** (`types.py`):

  ```python
  class CUAState(TypedDict):
      task: str
      contents: list[Any]                # Gemini content history (messages + function responses)
      pending_calls: list[dict]          # buffered function calls from last response
      last_screenshot_png: bytes | None
      step: int
      done: bool
      safety: dict | None                # last safety_decision (if any)
  ```

* **Nodes**:

  * `observe(state)`: take a VNC screenshot (PNG) on the **very first** turn only when `include_initial_screenshot=True` is set; otherwise skip.
  * `propose(state)`: call Gemini with `contents`; parse **function calls** and optional **safety_decision**. If no calls, mark `done=True`.
  * `act(state)`: pop **one** call from `pending_calls`, execute via VNC, capture a new **PNG**, append a **FunctionResponse** to `contents`.
  * `hitl_gate(state)`: if the last proposal included `require_confirmation`, interrupt here until the user resumes with `accept` or `deny`.

* **Edges**:

  ```
  START -> propose
  propose -> hitl_gate (if require_confirmation) else -> act
  hitl_gate -> act (if accepted) or END (if denied)
  act -> propose
  propose -> END (if done)
  ```

* **Checkpointing**: compile with **SQLite checkpointer**; set a `thread_id` so runs are resumable.

* **Guards**: `step_limit`, `seconds_timeout` (wall‑clock).

* **Logging**: after each step, write:

  * raw request/response JSON (redact API key),
  * the function call executed,
  * a PNG of the latest screenshot in a `runs/<run_id>/` folder.

---

### 8) Safety & HITL

Implement `safety.py`:

* If a response contains a `safety_decision` **`require_confirmation`**, the graph **interrupts** (HITL).
* Provide a convenience method `approve()` / `deny()` that resumes the graph via a LangGraph `Command` (document how to call this from a shell REPL or API).
* If denied, stop and return the current transcript.

---

### 9) Tests & acceptance

Add lightweight tests (can be pure unit tests without a live VNC):

* `test_denorm()` converts sample **0, 500, 999** to expected pixels at **(1440, 900)**.
* `test_function_response_shape()` asserts the built `FunctionResponse` embeds a **PNG** and a `name` matching the executed action.
* `test_sequential_function_calls()` ensures multiple calls in one candidate are queued and executed one by one.
* `test_hitl_block()` simulates a `require_confirmation` and verifies the graph interrupts.

**Manual acceptance (with a live VNC):**

* Start a VM with a **1440×900** desktop (or any size—agent must auto‑detect from screenshot).
* Run the CLI with a simple browser task (e.g., open a homepage, type text, press Enter).
* Confirm logs show **normalized → pixel** conversion, and that each step sent a **FunctionResponse with PNG**.

---

### 10) Implementation details (must‑do)

* **Screen size source of truth**: Detect from the **screenshot bytes** (Pillow) on each step; do **not** assume a fixed viewport even if default is 1440×900.
* **Parallel calls**: The model may return multiple `function_call`s in one turn; execute **sequentially** for now, but keep the type flexible for future parallelism.
* **Error handling**: Wrap each action and include `"error"` in the per‑call result that goes back with the screenshot.
* **Extensibility**: Leave hooks to add **custom user functions** later (e.g., `open_app`, `go_home`) and to **exclude** built‑ins via `excluded_actions`.
* **No secrets in logs**.
* **Docstrings** on public classes/functions; mypy‑clean.

---

### 11) Example snippets to generate

(You will implement, not just sketch.)

* **Gemini call config** (Python, with `google-genai`) to the **Computer Use model** including the **tool** and **excluded_predefined_functions**.
* A **`denorm(x,y,w,h)`** helper using the current screenshot size.
* Minimal **vncdotool** mappings for each action (click/hover/type/scroll/drag/key combo).
* Building a **`FunctionResponse`** carrying: `name`, `response={"url": "" | current_url}`, and an inline **PNG** blob.

---

### 12) README

Include a concise README with:

* What it is, diagram of the loop, and **why no OCR**.
* How to **install** and **run** (env var `GOOGLE_API_KEY`, VNC server address, optional password).
* Supported actions and how to add/remove (`excluded_actions`).
* Safety/HITL behavior and how to approve/deny from code or CLI.
* Known limitations (browser‑optimized model; non‑browser flows may need custom functions).

---

**Deliverables:** Working package with `VncUseAgent.run()`, CLI runner, unit tests, and a short README. No placeholders.


* **Use the specialized model + tool:** The docs require the **Computer Use model ID** `gemini-2.5-computer-use-preview-10-2025` and enabling the **Computer Use tool** (with optional `excluded_predefined_functions` and user‑defined functions). Trying to use the tool with another model errors. ([Google AI for Developers][1])

* **Return one FunctionResponse per executed function call**, embedding a **PNG screenshot** (and URL when applicable). ([Google AI for Developers][1])

* **Normalized coordinates grid:** 0–999 (1000×1000) for `click_at`, `scroll_at`, and `drag_and_drop`; convert to pixels each step using the current screenshot dimensions. ([Google AI for Developers][1])

* **`google-genai` Python SDK**: official client and docs for `Client`, `GenerateContentConfig`, `Tool`, `ComputerUse`, and the `types.*` used above. ([Google APIs][2])

* **LangGraph** features we rely on**:** StateGraph with **conditional edges**, **SQLite checkpointing** (persisted `thread_id`), and **HITL interrupts** to pause on risky actions. ([LangChain Docs][3])

* **VNC execution “hands”:** `vncdotool` methods we map to (`captureScreen`, `mouseMove`, `mousePress`, `mouseDown/Up`, `mouseDrag`, `keyPress`, `keyDown/Up`). ([VNCDoTool][4])



[1]: https://ai.google.dev/gemini-api/docs/computer-use "Computer Use  |  Gemini API  |  Google AI for Developers"
[2]: https://googleapis.github.io/python-genai/?utm_source=chatgpt.com "Google Gen AI SDK documentation"
[3]: https://docs.langchain.com/oss/python/langgraph/quickstart?utm_source=chatgpt.com "Quickstart - Docs by LangChain"
[4]: https://vncdotool.readthedocs.io/en/stable/modules.html "Code Documentation — VNCDoTool 0.9.0.dev0 documentation"

