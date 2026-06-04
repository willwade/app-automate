# Keyboard Shortcuts and Web Accessibility: The Missing Metadata

## The Problem in One Number

We audited **105 web applications** across 7 domains for keyboard shortcut metadata. The result:

**98.1% expose zero keyboard shortcut metadata through the accessibility layer.**

Only **Excalidraw** (1 app out of 103 that loaded) correctly implements `aria-keyshortcuts`. Zero apps use `accesskey`. Meanwhile, **21 apps document 1,422 shortcuts** in external help pages—shortcuts that are completely invisible to assistive technology.

This is the first large-scale audit of `aria-keyshortcuts` adoption. The full research is in our [keyboard-shortcut-gap repository](https://github.com/willwade/keyboard-shortcut-gap); this article covers the background, results, and what we're doing about it.

## Who This Affects

The impact is not evenly distributed.

### Keyboard-only users with motor impairments

Users who cannot operate a mouse rely entirely on keyboard input. For them, shortcuts are not a productivity boost—they are the **primary interaction mechanism**. Not knowing that `Ctrl+B` toggles bold means navigating through menus via Tab and Enter, which can take 10–20× longer.

### Switch access and eye gaze users

Users of switch access, eye gaze, and AAC software (Grid 3, Snap + Core First, Communicator 5) face an even more acute problem. Their AT must be **manually programmed** with the target application's shortcuts. A clinician or caregiver looks up shortcuts in documentation and enters them one by one.

If `aria-keyshortcuts` were widely adopted, AT software could **automatically query the accessibility tree** and generate shortcut grid cells. This would eliminate the manual configuration step, reduce clinician burden, and keep AT in sync when apps update.

### Screen reader users

Screen reader users benefit from knowing application shortcuts, but face a different challenge: screen readers already define hundreds of keystrokes, and adding application shortcuts on top creates conflicts and cognitive overload. For these users, `aria-keyshortcuts` enables announcement ("Rectangle button, shortcut R") and conflict detection—but it's secondary to the motor-impairment use case where shortcuts may be the **only viable input method**.

## The Numbers

We used three extraction channels:

### Channel A: DOM and Accessibility Tree (103 apps loaded)

| Metric | Count | Rate |
|---|---|---|
| `aria-keyshortcuts` | 1 | 1.0% |
| `accesskey` | 0 | 0.0% |
| AX tree keyshortcuts | 1 | 1.0% |
| Heuristic DOM matches | 2 | 1.9% |
| **Any DOM metadata** | **2** | **1.9%** |

The one app: **Excalidraw**, an open-source virtual whiteboard, declares 12 shortcuts via `aria-keyshortcuts` on its toolbar buttons.

### Channel B: Documentation Scraping (94 apps loaded)

| Metric | Value |
|---|---|
| Apps with documented shortcuts | 21 (22.3%) |
| Total documented shortcuts | 1,422 |

Top extractors: Google Docs (512), Google Sheets (365), Slack (205), Observable (115), Gmail (72), Asana (71).

### Channel A3: JS Runtime Proxying (103 apps)

We injected proxy scripts intercepting three keyboard frameworks (Mousetrap, hotkeys-js, tinykeys) to capture shortcut registrations at runtime.

Result: **0 shortcuts captured**. Only 1 app (Datawrapper) loaded a detectable framework (hotkeys-js). Modern web apps build custom shortcut engines for good reason—complex modifier combinations, suppressing browser defaults, context-dependent bindings, user customization—but this means framework-level tooling cannot bridge the gap.

### The Gap

Of 94 apps analyzed in both channels:

| Category | Apps | Rate |
|---|---|---|
| Docs but NO DOM metadata (the gap) | 20 | 21.3% |
| Both docs AND DOM | 1 | 1.1% |
| Neither | 72 | 76.6% |

20 apps document shortcuts externally but expose **nothing** through the accessibility layer.

### By Domain

| Domain | DOM metadata | Doc shortcuts | Total doc shortcuts |
|---|---|---|---|
| IDE | 1/15 | 8/15 | 176 |
| Documents | 0/15 | 2/13 | 513 |
| Data/Spreadsheets | 0/15 | 3/13 | 437 |
| Communication | 0/15 | 3/14 | 279 |
| Design | 1/14 | 2/13 | 7 |
| Collaboration | 0/14 | 2/13 | 6 |
| Scientific | 0/15 | 1/13 | 4 |

IDEs have the highest documentation rate (53.3%), yet only VS Code (via heuristic) exposes any DOM metadata.

## A Brief History: Why Web Shortcut Accessibility Failed

### 1999: `accesskey` arrives

HTML 4 introduced the `accesskey` attribute:

```html
<a href="/" accesskey="h">Home</a>
```

Problems from the start:
- **Single key only** — no modifier combinations
- **Browser chooses the modifier** — Alt on Chrome/Windows, Alt+Shift on Firefox, Ctrl+Opt on Mac
- **No documentation mechanism** — doesn't tell the user what to press

### 2002: Accesskeys break accessibility

The WATS study found that `accesskey` combinations conflicted with screen reader and browser shortcuts. Their recommendation: **avoid using accesskeys altogether**.

The accessibility community spent the next 15 years learning that "keyboard shortcut attributes don't work."

### 2005–2010: XHTML 2 — the failed ancestor that birthed ARIA

The W3C's XHTML 2 working group deprecated `accesskey` in favour of a new `<access>` element. XHTML 2 was abandoned, but its role attribute framework migrated into what became **WAI-ARIA**—the specification that would later introduce `aria-keyshortcuts`.

### 2017: `aria-keyshortcuts` — the right answer nobody uses

WAI-ARIA 1.1 introduced `aria-keyshortcuts`:

```html
<button
  aria-keyshortcuts="Control+Shift+B"
  aria-label="Toggle bold (Control plus Shift plus B)"
>
  B
</button>
```

This solves every problem that killed `accesskey`:
- **Modifier combinations** — `Control+Shift+P`, not just a single key
- **No collision with browser shortcuts** — it's declarative, not an active binding
- **Exposed in the accessibility tree** — AT can query it
- **Works alongside existing bindings** — the app handles the keyboard event in JS, `aria-keyshortcuts` just documents it

Critically, `aria-keyshortcuts` does **not** create key listeners. It is purely a **declarative label** that tells the accessibility API what the application's existing JavaScript handlers already do. Developers need not choose between implementing shortcuts in code and declaring them in ARIA—it's additive.

But by 2017, nobody was listening. Our audit confirms the result: 1 out of 103 apps.

## Excalidraw: The One App Doing It Right

Excalidraw is the sole application in our corpus that correctly implements `aria-keyshortcuts`. The HTML is straightforward:

```html
<button
  aria-label="Rectangle"
  aria-keyshortcuts="R"
  data-testid="toolbar-rectangle">
  <!-- SVG icon -->
</button>
```

This surfaces correctly in the accessibility tree:

```json
{
  "role": {"value": "button"},
  "name": {"value": "Rectangle"},
  "properties": [
    {"name": "keyshortcuts", "value": {"type": "string", "value": "R"}}
  ]
}
```

Excalidraw is open-source, collaborative, real-time, and handles dynamic state. It proves that `aria-keyshortcuts` is feasible in production web applications.

## Why Adoption Is So Low

### Developer awareness

Most web developers are unaware of `aria-keyshortcuts`. Unlike ARIA roles (`role="button"`) caught by automated testing tools, `aria-keyshortcuts` absence is not flagged by axe-core, Lighthouse, or WAVE.

### Spec ambiguity

The specification describes the attribute but provides minimal implementation guidance. Screen readers do not consistently announce it, reducing the perceived benefit.

### Custom shortcut engines

Modern apps build custom engines for complex modifiers, context-dependent bindings, and user customization. This is necessary—but `aria-keyshortcuts` is independent of the engine. It's a declaration layer, not a replacement.

## What app-automate Is Doing

[app-automate](https://github.com/Smartbox-Assistive-Technology/app-automate) is building open-source tooling to extract shortcuts from web apps:

1. **CDP shortcut extraction**: Query `aria-keyshortcuts`, `accesskey`, and AX tree via `app-automate cdp-shortcuts`
2. **DOM scraping**: Known CSS patterns (`.monaco-keybinding`, `kbd`, `.shortcut`)
3. **Documentation scraping**: Extract from help pages with table/dl/text extraction using Playwright
4. **JS runtime proxying**: Inject via `addInitScript` to intercept keyboard frameworks

We'd rather not need any of these. If web apps used `aria-keyshortcuts`, a single accessibility tree query would give AT software every shortcut in the application—automatically generating grid cells for eye gaze users, announcing shortcuts to screen reader users, and enabling keyboard-only navigation for motor-impaired users.

## Recommendations

### For web developers

- Add `aria-keyshortcuts` to elements with keyboard bindings—it's additive, not a replacement for your JS handlers
- Include the shortcut in the `aria-label` as well, since screen reader support is still inconsistent
- Consider Excalidraw as a reference implementation

### For AT vendors

- Screen readers: announce `aria-keyshortcuts`, detect conflicts with your own keystrokes
- AAC/switch/eye-gaze software: query the accessibility tree to **auto-generate** shortcut grid cells

### For standards bodies

- Add `aria-keyshortcuts` examples to the ARIA Authoring Practices Guide
- Consider a machine-readable shortcut manifest (e.g. `/.well-known/keyboard-shortcuts.json`)

### For browser vendors

- Expose `aria-keyshortcuts` in developer tools
- Provide a "shortcut discovery" UI showing all declared shortcuts

## Implementation Gotchas

### String formatting is strict

The ARIA spec requires specific token modifiers: **`Alt`**, **`Control`**, **`Meta`**, **`Shift`** — separated by `+` with no spaces. `Ctrl` is invalid. `ctrl` is invalid. The correct string is `Control+Shift+P`.

### Dynamic modifiers per platform

If an app uses `Ctrl+B` on Windows/Linux and `Cmd+B` on macOS, the `aria-keyshortcuts` string must dynamically update. Use `navigator.userAgentData?.platform` to detect the OS.

### Include the shortcut in the accessible name

Screen reader support for `aria-keyshortcuts` is inconsistent. Always include the shortcut in `aria-label` or `aria-describedby` as well.

## References

### Standards and specifications

- [WAI-ARIA `aria-keyshortcuts` specification](https://www.w3.org/TR/wai-aria-1.2/#aria-keyshortcuts)
- [HTML `accesskey` attribute](https://html.spec.whatwg.org/multipage/interaction.html#the-accesskey-attribute)
- [MDN: aria-keyshortcuts](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Attributes/aria-keyshortcuts)
- [WATS: Using Accesskeys (2002)](https://web.archive.org/web/20120204224705/http://www.wats.ca/show.php?contentid=32)

### Academic literature

- Chiou, Alotaibi & Halfond (2021). "Detecting and localizing keyboard accessibility failures in web applications." *ASE 2021.*
- Martins & Duarte (2024). "A large-scale web accessibility analysis considering technology adoption." *Universal Access in the Information Society.*
- Krishna Vajjala et al. (2024). "MotorEase: Automated detection of motor impairment accessibility issues in mobile app UIs." *ICSE 2024.*
- Larradet, Barresi & Mattos (2019). "Design and Evaluation of an Open-source Gaze-controlled GUI for Web-browsing." *CEEC 2019.*
- Momotaz, Ehtesham-Ul-Haque & Billah (2023). "Understanding the usages, lifecycle, and opportunities of screen readers' plugins." *ACM TACCESS.*
- Lee & Ashok (2020). "Towards personalized annotation of webpages for efficient screen-reader interaction." *HT 2020.*
- Ara, Sik-Lanyi & Kelemen (2024). "Accessibility engineering in web evaluation process: a systematic literature review." *Universal Access in the Information Society.*
- Georgakas (2023). "How Do I Know I'm Doing It Right?" *A11Y Unraveled.* Apress.

### Data and code

- [Full research repository](https://github.com/willwade/keyboard-shortcut-gap) — corpus, extraction scripts, results, and paper
- [app-automate](https://github.com/Smartbox-Assistive-Technology/app-automate) — the tooling used for extraction
