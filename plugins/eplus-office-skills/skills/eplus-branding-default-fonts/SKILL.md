---
name: eplus-branding-default-fonts
description: Applies the EPLUS corporate brand guidelines, color palette, and logos to UI components using only default, universally-available system fonts (Arial and standard sans-serif fallbacks) instead of the custom Montserrat/Sui Generis company fonts. Use this whenever the output must stay editable or render correctly across applications and machines that do not support installed custom fonts — for example a PowerPoint exported to PDF and reopened in Bluebeam, AutoCAD, or on a reviewer's computer. Optimized for web, Microsoft Teams, Windows apps (WPF), PowerPoint/Office, PDF deliverables, and pyRevit (XAML/Python) extensions. Prefer this over the eplus-branding skill any time portability, PDF round-tripping, or cross-app text editing matters.
---

# EPLUS Branding Skill Workflow (Default-Fonts Edition)

You are an expert UI/UX developer. Your goal is to style applications strictly adhering to the EPLUS Brand Guidelines, using **default, universally-available system fonts** so that all code and assets are fully portable and all text remains editable for distribution to other users and other applications.

**Why this edition exists:** The custom company fonts (`Montserrat`, `Sui Generis`) are not supported by many applications even when the font files are installed. A common failure: a PowerPoint styled in Montserrat is exported to PDF and reopened in Bluebeam, where the text can no longer be edited because Bluebeam does not support that font. This edition avoids that entirely by mapping the brand hierarchy onto `Arial` and standard fallbacks. If the deliverable genuinely requires the embedded company fonts, use the `eplus-branding` skill instead.

## Step 1: Context Gathering
- Read the `brand-summary.md` file located in this skill's directory to load the exact color palette (Blue: #666f89, accent Green: #3c7d7f, etc.), the color role/proportion rules, and the default-font typography hierarchy.
- Identify the user's current framework: Are they building a web app (HTML/CSS), a Teams app, a Windows app (WPF), an Office/PowerPoint deliverable, a PDF, or a pyRevit extension (XAML/Python)?
- **No font opt-in is required.** This edition always uses default system fonts, so proceed directly without asking whether to install company fonts. (If the user explicitly asks for the embedded Montserrat/Sui Generis fonts, point them to the `eplus-branding` skill.)

## Step 2: Asset Portability & Copying
**NEVER hardcode absolute paths** to this skill's directory (e.g., never use `C:\Users\...\.copilot\skills\`). All assets must live locally within the project for distribution.
1. **Logos:** Always write the terminal command (PowerShell or Bash) to copy the necessary `.jpg`/`.png` logo files from this skill's `assets/logos/` directory directly into the active project workspace.
2. **Fonts:** No font files are copied or embedded. Brand typography is achieved with system fonts only, so there is nothing to bundle and nothing that can break on another machine.
3. **Use Relative Paths:** All generated code must reference these newly copied logo files using relative paths.

## Step 3: Tech-Specific Implementations

### For pyRevit (XAML / Python)
- Generate XAML that references the local image/logo using a relative path, or instruct the user on how to bind the image path dynamically using Python's `__file__` directory context.
- Colors in XAML must use the exact EPLUS Hex codes (e.g., `<SolidColorBrush Color="#666f89"/>`).
- Set the `FontFamily` property to `Arial` (e.g., `FontFamily="Arial"`). Use `FontWeight="Bold"` for headlines, headings, and sub-headings — differentiate headlines by size, never with `Arial Black`.

### For Web / Teams Apps (HTML / CSS)
- Ensure all `<img src="...">` tags point to the local project folder (e.g., `./assets/logos/SQ-EPlus-Logo-URL-3.5x2.25.jpg`).
- Apply the brand font with a portable stack and **no** `@font-face` declarations: `font-family: Arial, Helvetica, "Liberation Sans", sans-serif;`. Differentiate the hierarchy with `font-weight` and `text-transform`, not custom faces.

### For Office / PowerPoint / PDF Deliverables
- Set fonts to `Arial` throughout so the document round-trips to PDF and reopens as editable text in Bluebeam and other reviewers.
- Use `Arial Bold` for headlines (larger size), sub-headings, and section headings, and `Arial Regular` for body copy. Never `Arial Black` — renderers without it substitute unpredictably (LibreOffice falls back to a serif face).
- Do not embed or substitute custom fonts; rely on the system Arial that is present on essentially all target machines.

## Step 4: UI Generation Rules
- **Colors:** Strictly use the HEX colors provided in `brand-summary.md`. Never hallucinate brand colors. Follow the **Color Roles & Proportions** table: the design is blue-and-grey led. Green `#3c7d7f` is an accent used **sparingly** — only to make a special section/callout stand out and for header/footer graphics. Never use green for body text, headings, links, buttons, or table headers; when in doubt, use Blue `#666f89`.
- **Logos:** Ensure logos are implemented without distortion (maintain aspect ratio). Use the white logo on dark backgrounds, and the standard blue logo on light backgrounds.
- **Typography:** Apply the brand hierarchy using default fonts only — `Arial Bold` for headlines (differentiated by size), sub-headlines, and section headings (Title Case or ALL CAPS, not exceeding headline size), and `Arial Regular` for body copy (sentence case). Never use `Arial Black`, and never declare, embed, or reference `Montserrat` or `Sui Generis` in this edition.
