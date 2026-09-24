# Demo 6: build an agent in LibreChat

**What it shows:** EPLUS LibreChat (the EPLUS AI Platform) gives everyone
GPT, Gemini, Claude and Grok models side by side, and anyone can build their
own agent there. Claude walks the user through building one, live, in the
browser.

Address: `https://chat-engineering-plus.centralus.cloudapp.azure.com/`

## Sign-in: the user does it, always

The page opens on "Welcome back" with Email address and Password. **You never
type the email or the password, and you never offer to.** Say: "Please sign in
with your EPLUS LibreChat account in the browser tab. I don't type passwords.
Once you're in, it stays signed in for a while, so you won't have to do this
every time." Wait until they say they are in, then check the page shows
"New chat".

## What the Agent Builder looks like (LibreChat v0.8.8, checked 2026-09-24)

- Left icon bar: New chat, Chat History, **Agent Builder**, Skills, Prompts,
  Bookmarks, Attach Files, Parameters, MCP Settings, Account Settings.
- Agent Builder panel ("Create New Agent"): avatar, **Agent name**,
  **Agent description**, **Model** (required), **Category** (required,
  default General), **Instructions**, **Tools** (+ Add), **Skills**
  (Off / All / Selected), File Context (only after the agent is created),
  Support contact, **Advanced**, Admin Settings, **Create**.
- **Model** opens Model Parameters: **Provider** then **Model**.
  - GPT-6 Sol: Provider **OpenAI (Azure Foundry)**, model `gpt-6-sol`
    (reasoning effort slider available).
  - Gemini 3.8 Flash: Provider **Google**, model `gemini-3.8-flash`, with a
    **Grounding with Google Search** toggle.
  - Other providers: Anthropic, Model Router, Grok, Moonshot, Mistral.
- **Add tools** opens the Tool Library. Native: Run Code, **Web Search**,
  Artifacts, **File Search**, Ask User. Others: Google, Tavily Search,
  Wolfram, Calculator, Azure AI Search, OpenWeather, image tools and more.
- **Advanced**: Max Agent Steps, then Multi-agent orchestration:
  **Subagents** (beta toggle; then Allow self-spawn and **Add subagent**, up
  to 10), Handoffs, Chain. **Add subagent lists only agents that already
  exist**, so a helper agent is created first, then added to the main one.

## Steps

1. Ask which agent to build, with one `AskUserQuestion`:
   - **Deep research agent (recommended)**: GPT-6 Sol leads the research and
     writes the report; a fast Gemini 3.8 Flash helper runs the web searches.
   - **Spec and standards helper**: GPT-6 Sol with File Search, for questions
     against documents the user uploads.
   - **Quick answers agent**: Gemini 3.8 Flash with Web Search, for fast
     everyday questions.
2. Say what you will create and get a clear yes (tour rule 4). For the deep
   research agent that is two agents: the helper, then the lead.
3. Build it in the Agent Builder while they watch. For the deep research agent:
   - **Helper first.** Name "Research Scout", description "Fast web searches
     for the Deep Research agent", Provider Google, model `gemini-3.8-flash`,
     Grounding with Google Search on, tool Web Search, instructions: "You run
     web searches for a lead research agent. For each question, search, then
     return the five most relevant sources with a one-line summary and the
     link for each. No opinions, no final report." Click **Create**.
   - **Lead.** Name "Deep Research", description "Researches a question in
     depth and writes a sourced report", Provider OpenAI (Azure Foundry),
     model `gpt-6-sol`, tools Web Search and Artifacts, instructions: "You are
     a research lead for EPLUS engineers. Break the question into parts, send
     each part to Research Scout, then write a clear report with headings, a
     short summary first, and a source list with links. Say what you could not
     confirm." In **Advanced**, turn **Subagents** on, **Add subagent**:
     Research Scout. Click **Create**.
   The other two agents are one agent each, built the same way.
4. Try it once: start a chat with the new agent and ask one short question
   from their trade (from demo 2). Let them read the answer.
5. Tell them it is theirs: it appears in their agent list, they can edit it in
   Agent Builder, and they can build more by asking you.
6. Add the card to the cheat sheet: title "LibreChat agents", what "I can
   build agents for you in EPLUS LibreChat and set their models, tools and
   helpers.", try "Build me a LibreChat agent that ..."

## Close

- What you just saw: "I built an agent in LibreChat with its own model, tools
  and a helper agent, and you can use it any time."
- Try saying: "Build me a LibreChat agent that ..." / "Add a tool to my
  Deep Research agent."
