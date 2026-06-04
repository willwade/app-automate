# Keyboard Shortcuts and Web Accessibility: A Missing Standard

## The Problem

Web applications increasingly rely on keyboard shortcuts for power users. VS Code, Google Docs, Figma, Desmos, Notion, and GitHub all offer extensive keyboard shortcut systems. Yet **none of them expose these shortcuts through the browser's accessibility layer**.

We surveyed major web applications using the Chrome DevTools Protocol and found:

| Application | `aria-keyshortcuts` | `accesskey` | Shortcuts in DOM |
|---|---|---|---|
| VS Code (web) | No | No | Partial (`.monaco-keybinding` only in Command Palette) |
| Google Docs | No | No | No |
| GitHub | No | No | No (shown in a dialog) |
| Notion | No | No | No |
| Figma | No | No | No |
| Desmos | No | No | No |
| Wikipedia | No | Yes (19 links) | N/A |

0 out of 7 applications use `aria-keyshortcuts`. Only Wikipedia uses `accesskey`. Note on VS Code: the `.monaco-keybinding` spans are only rendered when the Command Palette or Keyboard Shortcuts editor is actively open — they are not bound to core interactive workspace nodes. This underscores why DOM scraping is fragile for shortcut extraction.

## The Evolutionary Leap

Before diving into the history, here is the core technical difference between what we had and what we have now:

| Feature | `accesskey` (Old) | `aria-keyshortcuts` (New) |
|---|---|---|
| **Behaviour** | Active — browser intercepts the key | Declarative — documents an existing JS binding |
| **Modifiers** | Forced by browser/OS (Alt, Alt+Shift, etc.) | Custom defined (`Control+Shift+P`) |
| **Collisions** | High — breaks screen reader shortcuts | Zero — screen reader respects or bypasses |
| **Discovery** | Not announced to user | Exposed in accessibility tree |
| **Scope** | One key per element | Full modifier combos |

## A Brief History: Why Web Shortcut Accessibility Failed

### 1999: `accesskey` arrives

HTML 4 introduced the `accesskey` attribute. A single attribute let you bind a key to an element:

```html
<a href="/" accesskey="h">Home</a>
```

It quickly achieved near-universal browser support. But it had problems from the start:

- **Single key only** — no modifier combinations possible
- **Browser chooses the modifier** — Alt on Chrome/Windows, Alt+Shift on Firefox, Ctrl+Opt on Mac, Shift+Esc on Opera
- **No documentation mechanism** — the attribute doesn't tell the user what key to press
- **One shortcut per element**

### 2002: Accesskeys break accessibility

A Canadian web accessibility consultancy (WATS) conducted research into whether accesskeys caused problems for users of assistive technology — screen readers, alternative input devices, and other tools that rely heavily on keyboard shortcuts. Their finding: most key combinations conflicted with existing browser or screen reader shortcuts. A blind user navigating with JAWS or Window-Eyes would find that a web page's `accesskey="h"` clashed with a screen reader command, breaking their workflow.

**Their recommendation: avoid using accesskeys altogether.** ([WATS, 2002](https://web.archive.org/web/20120204224705/http://www.wats.ca/show.php?contentid=32))

Browsers responded by changing the modifier keys required for accesskeys (shifting to Alt+Shift on Windows, Ctrl+Opt on Mac) to reduce collisions. But the damage was done — the accessibility community had learned to distrust the mechanism.

### 2004–2014: Standardisation attempts

In 2004, a numeric standard emerged (promoted by the UK government): `1` for homepage, `0` for search, `/` for contact, etc. This improved consistency but couldn't overcome the fundamental limitation of single keys.

In 2014, [SAK2014 (Standard Access Keys 2014)](https://web.archive.org/web/20230401101600/https://www.standardaccesskeys.com/) released a more comprehensive standard using both letters and numbers. It didn't gain traction either.

### 2005–2010: XHTML 2 — the failed ancestor that birthed ARIA

The W3C's XHTML 2 working group deprecated `accesskey` in favour of a new `<access>` element alongside a standardised role attribute framework in the XHTML Role Access Module. XHTML 2 was eventually abandoned in favour of HTML5, which kept `accesskey` and never adopted `<access>`.

But the work didn't vanish. The role attribute framework from XHTML 2 was directly migrated into what became **WAI-ARIA** — the same specification that would later introduce `aria-keyshortcuts`. XHTML 2 wasn't just a dead end; it was the failed evolutionary ancestor that accidentally created the foundation for modern web accessibility attributes.

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
- **No collision with browser shortcuts** — it's declarative, not an active binding; the browser doesn't intercept the keys
- **Exposed in the accessibility tree** — screen readers can announce it, automation tools can query it
- **Works alongside existing bindings** — the app handles the keyboard event in JS, `aria-keyshortcuts` just documents it

But by 2017, the web development community had spent 15 years learning that "keyboard shortcut attributes don't work." The collective memory of `accesskey`'s failures meant nobody adopted the replacement.

---

### 2024: We verified the gap

We queried 7 major web applications through the Chrome DevTools Protocol, checking:
1. DOM attributes (`aria-keyshortcuts`, `accesskey`)
2. The browser accessibility tree (CDP `Accessibility.getFullAXTree`, looking for `keyshortcuts` properties)

Result: **zero applications expose keyboard shortcuts through the accessibility layer.** Meanwhile, the same applications support dozens to hundreds of keyboard shortcuts, stored in JavaScript and inaccessible to assistive technology.

## Why This Matters

### For assistive technology users

Screen readers and alternative input devices can't discover keyboard shortcuts unless the application provides a separate help dialog. A user navigating by ARIA landmarks and roles has no way to know that `Control+Shift+P` opens a command palette, or that `Control+B` toggles bold text.

There is an important nuance here. When a screen reader is in **Browse Mode** (the default for reading web content), almost every letter key is a navigation shortcut — H for heading, B for button, L for list. A web app that uses single-key shortcuts (like J and K in Gmail) will conflict regardless of `aria-keyshortcuts`, because the screen reader intercepts the key first. The user must toggle into **Focus Mode** (also called Forms Mode) to pass keystrokes through to the web page. `aria-keyshortcuts` does not override this screen reader behaviour — it only tells the AT that a shortcut exists, so it can be announced when the user navigates to the element.

### For automation tooling

[app-automate](https://github.com/Smartbox-Assistive-Technology/app-automate) is an open-source cross-platform desktop automation tool that programmatically controls applications via keyboard shortcuts, accessibility APIs, and computer vision. It builds machine-readable profiles of application shortcuts and elements so that assistive technology and automation scripts can drive any app.

Tools like app-automate, Puppeteer, and browser automation frameworks could query the accessibility tree to discover available keyboard shortcuts. Instead, we resort to:
- Scraping documentation pages (fragile, often behind JS rendering)
- Manual profile creation (time-consuming)
- Reverse-engineering DOM structures (`.monaco-keybinding` in VS Code)

### For cross-platform consistency

Native applications expose shortcuts through accessibility APIs:
- **macOS**: `AXMenuItemCmdChar` / `AXMenuItemCmdModifiers` on menu items
- **Windows**: `AcceleratorKey` property on UIA elements
- **Linux**: AT-SPI action key bindings

Web applications are the only platform where this information is systematically hidden from the accessibility tree.

## What Web Apps Do Instead

Web apps store keyboard shortcuts in JavaScript:

```javascript
// VS Code (simplified)
keybindings.register({
    key: 'ctrl+shift+p',
    command: 'workbench.action.showCommands',
    when: undefined
});
```

```javascript
// Google Docs (simplified)
{
    'ctrl+b': 'bold',
    'ctrl+i': 'italic',
    'ctrl+u': 'underline',
}
```

This data is:
- Not in the DOM
- Not in the accessibility tree
- Only discoverable by reading JavaScript source or triggering each shortcut

## Proposal

### 1. Adopt `aria-keyshortcuts` on interactive elements

When a web element has a keyboard shortcut, add `aria-keyshortcuts`:

```html
<button
  aria-keyshortcuts="Control+Shift+B"
  aria-label="Toggle bold (Control plus Shift plus B)"
>
  B
</button>
```

This is a single attribute addition. The app continues to handle the keyboard event in JavaScript — `aria-keyshortcuts` just documents the existing binding for the accessibility tree. No behaviour change required.

Note: the ARIA spec requires that the shortcut must also be included in the accessible name (`aria-label`) or description, because current screen reader support for `aria-keyshortcuts` is inconsistent. Including it in the label ensures it is always announced.

### 2. Use `aria-keyshortcuts` on menu items and toolbar buttons

For command palettes, menus, and toolbars:

```html
<div
  role="menuitem"
  aria-keyshortcuts="Control+Shift+P"
  aria-label="Show All Commands (Control plus Shift plus P)"
>
  Show All Commands
</div>
```

### 3. The accessibility tree already works — mostly

Browsers already expose `aria-keyshortcuts` through their accessibility APIs. We verified this with Chromium's CDP: setting `aria-keyshortcuts="Control+Shift+P"` on a button causes it to appear in the `keyshortcuts` property of the corresponding AX tree node. The pipeline works at the browser level.

However, **assistive technology is lagging behind the browser tree support**:
- **NVDA** and **JAWS** do a poor job of automatically announcing `aria-keyshortcuts` unless the user explicitly requests a shortcut list or is navigating a menu.
- **VoiceOver** on macOS struggles because macOS expects shortcuts to live in the native Application Menu bar (`AXMenuBar`), not inside the web viewport rendering layer.

Adding the attribute is still the right thing to do — it populates the tree correctly and future-proofs against AT improvements. But developers should not expect immediate, universal screen reader announcements. Including the shortcut in the `aria-label` (as shown above) is the practical workaround for today.

### 4. Consider a `keyboardShortcuts` manifest

For applications with many shortcuts (like code editors), a JSON manifest discoverable at a well-known URL:

```
/.well-known/keyboard-shortcuts.json
```

```json
{
  "schema": "1.0",
  "shortcuts": [
    {
      "keys": ["ctrl+shift+p", "cmd+shift+p"],
      "action": "show-commands",
      "description": "Show All Commands",
      "group": "general"
    }
  ]
}
```

This could be **auto-generated at build time** from the application's JavaScript shortcut registry — developers would not need to maintain a separate hand-written file. The build step that registers keybindings in JS can also emit the manifest, keeping both in sync automatically.

## Implementation Gotchas

Developers looking to adopt `aria-keyshortcuts` should be aware of:

### String formatting is strict

The ARIA spec requires specific token modifiers: **`Alt`**, **`Control`**, **`Meta`**, **`Shift`** — separated by `+` with no spaces. `Ctrl` is invalid. `ctrl` is invalid. The correct string is `Control+Shift+P`.

### Dynamic modifiers per platform

If an application uses `Ctrl+B` on Windows/Linux and `Cmd+B` on macOS, the `aria-keyshortcuts` string must dynamically update based on the user's platform. Use `navigator.userAgentData?.platform` or `navigator.platform` to detect the OS and inject the correct string at render time. A static string like `Ctrl+B` will confuse macOS VoiceOver users who expect `Cmd+B`.

### Include the shortcut in the accessible name

Because current screen reader support is inconsistent (see above), always include the shortcut in the `aria-label` or `aria-describedby` as well. Do not rely solely on `aria-keyshortcuts` for discovery today.

## What app-automate Is Doing

Regardless of adoption, we're building open-source tooling to extract shortcuts from web apps:

1. **CDP shortcut extraction**: Query `aria-keyshortcuts`, `accesskey`, and AX tree `keyshortcuts` properties via `app-automate cdp-shortcuts`
2. **DOM scraping**: Query known CSS patterns (`.monaco-keybinding`, etc.)
3. **Documentation scraping**: Extract from help pages with table/dl/text extraction, using both HTTP and headless browser (Playwright) fetchers
4. **Accessibility tree walk**: Use CDP's `Accessibility.getFullAXTree` to find nodes with `keyshortcuts` properties

We'd rather not need any of these workarounds. If web apps used `aria-keyshortcuts`, a single CDP query would give us every shortcut in the application.

## Related Work

This gap has not been studied directly, but several strands of research are relevant.

### Large-scale accessibility audits

Multiple studies have audited web accessibility compliance at scale. Campoverde-Molina et al. (2020) reviewed empirical web accessibility studies in educational websites. Ara, Sik-Lanyi & Kelemen (2024) conducted a systematic literature review of accessibility engineering in web evaluation, covering ARIA roles and automated evaluation tools. Chouchane et al. (2026) investigated the diffuseness of accessibility issues across public web applications. None of these studies specifically measured `aria-keyshortcuts` adoption or keyboard shortcut discoverability through the accessibility tree.

### Keyboard accessibility detection

Chiou, Alotaibi & Halfond (2021, ASE) developed automated techniques for detecting keyboard accessibility failures in web applications — specifically, whether UI elements are reachable and operable via keyboard. Their follow-up work, Bagel (CHI 2023), extended this to navigation-based barriers. Both focus on whether elements are *reachable*, not whether keyboard shortcuts are *discoverable* by assistive technology. Moore, Smith & Greenberg (2018) addressed keyboard and screen reader access in complex interactive science simulations (PhET), identifying design patterns for making interactive elements accessible.

### Screen reader interaction

Ashok et al. (ASSETS 2017) investigated web screen reading automation using semantic abstraction, relevant to understanding how assistive technology processes web content. Jain, Huq, He & Malek (ASE 2025) developed automated detection of navigation barriers specifically for screen reader users by simulating screen reader interaction. Antonelli, Sensiate, Watanabe et al. (2019) identified challenges in automatically evaluating RIA accessibility, including gaps in handling dynamic ARIA attributes.

### ARIA adoption

Bassi et al. (2025) proposed LLM-based accessibility auditing, and Genne (2022) addressed accessibility-first enterprise web platform design at scale. Both reference ARIA attributes and keyboard navigation but do not analyze `aria-keyshortcuts` specifically.

### The gap

**No published study has specifically audited `aria-keyshortcuts` adoption across web applications.** Existing research measures whether elements are keyboard-reachable (WCAG 2.1.1), whether ARIA roles are correct, and whether screen readers can read content. None measure whether web applications expose their keyboard shortcut bindings through the accessibility tree, or evaluate the gap between documented shortcuts and AT-accessible shortcuts.

We are conducting a larger-scale study to fill this gap, auditing 105 web applications across 7 domains. See [the research repository](https://github.com/willwade/keyboard-shortcut-gap) for the full research plan and corpus.

## References

### Standards and specifications

- [Wikipedia: Access key](https://en.wikipedia.org/wiki/Access_key) — history of accesskey, conflicts, and standardisation attempts
- [WATS: Using Accesskeys — is it worth it? (2002)](https://web.archive.org/web/20120204224705/http://www.wats.ca/show.php?contentid=32) — the accessibility consultancy report that recommended avoiding accesskeys
- [SAK2014: Standard Access Keys 2014](https://web.archive.org/web/20230401101600/https://www.standardaccesskeys.com/) — the last attempt to standardise accesskey mappings
- [WAI-ARIA `aria-keyshortcuts` specification](https://www.w3.org/TR/wai-aria-1.2/#aria-keyshortcuts)
- [HTML `accesskey` attribute](https://html.spec.whatwg.org/multipage/interaction.html#the-accesskey-attribute)
- [MDN: aria-keyshortcuts](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Attributes/aria-keyshortcuts)

### Academic literature

- Campoverde-Molina et al. (2020). "Empirical studies on web accessibility of educational websites: A systematic literature review." *IEEE Access.* [DOI](https://ieeexplore.ieee.org/abstract/document/9092982/)
- Ara, Sik-Lanyi & Kelemen (2024). "Accessibility engineering in web evaluation process: a systematic literature review." *Universal Access in the Information Society.* [DOI](https://link.springer.com/article/10.1007/s10209-023-00967-2)
- Chouchane et al. (2026). "An Empirical Investigation on the Diffuseness of Accessibility Issues in Public Web Applications." *International Journal of Human-Computer Interaction.* [DOI](https://www.tandfonline.com/doi/abs/10.1080/10447318.2026.2640458)
- Chiou, Alotaibi & Halfond (2021). "Detecting and localizing keyboard accessibility failures in web applications." *ASE 2021.* [DOI](https://dl.acm.org/doi/abs/10.1145/3468264.3468581)
- Chiou, Alotaibi & Halfond (2023). "Bagel: An Approach to Automatically Detect Navigation-Based Web Accessibility Barriers for Keyboard Users." *CHI 2023.* [DOI](https://dl.acm.org/doi/abs/10.1145/3544548.3580749)
- Moore, Smith & Greenberg (2018). "Keyboard and screen reader accessibility in complex interactive science simulations." *UAHCI 2018.* [DOI](https://link.springer.com/chapter/10.1007/978-3-319-92049-8_28)
- Ashok et al. (2017). "Web screen reading automation assistance using semantic abstraction." *ASSETS 2017.* [DOI](https://dl.acm.org/doi/abs/10.1145/3025171.3025229)
- Jain, Huq, He & Malek (2025). "Automated Detection of Web Application Navigation Barriers for Screen Reader Users." *ASE 2025.* [DOI](https://ieeexplore.ieee.org/abstract/document/11334511/)
- Antonelli et al. (2019). "Challenges of automatically evaluating rich internet applications accessibility." *SAC 2019.* [DOI](https://dl.acm.org/doi/abs/10.1145/3328020.3353950)
- Bassi et al. (2025). "Supporting accessibility auditing and HTML validation using large language models." *SAC 2025.* [DOI](https://dl.acm.org/doi/abs/10.1145/3672608.3707912)
