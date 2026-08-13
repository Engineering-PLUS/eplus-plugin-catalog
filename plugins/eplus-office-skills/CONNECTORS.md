# Connectors

## Local MCP Server

The `view-pdf` skill needs a **local MCP server** — everything else in
this plugin (docx, pdf, pptx, xlsx, branding) is a pure skill with no
server dependency. The PDF viewer server runs on your machine via `npx`.

| Category | Server | How it runs |
|----------|--------|-------------|
| PDF viewer & annotator | `@modelcontextprotocol/server-pdf` | Local stdio via `npx` (auto-installed) |

### Requirements
- Node.js >= 18
- Internet access for remote PDFs (arXiv, bioRxiv, etc.)
- No API keys or authentication needed
