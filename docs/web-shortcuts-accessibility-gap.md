# Keyboard Shortcuts and Web Accessibility: A Missing Standard

## The Problem

Web applications increasingly rely on keyboard shortcuts for power users. VS Code, Google Docs, Figma, Desmos, Notion, and GitHub all offer extensive keyboard shortcut systems. Yet **none of them expose these shortcuts through the browser's accessibility layer**.

We surveyed major web applications and found:

| Application | `aria-keyshortcuts` | `accesskey` | Shortcuts in DOM |
|---|---|---|---|
| VS Code (web) | No | No | Yes (`.monaco-keybinding` spans) |
| Google Docs | No | No | No |
| GitHub | No | No | No (shown in a dialog) |
| Notion | No | No | No |
| Figma | No | No | No |
| Desmos | No | No | No |
| Wikipedia | No | Yes (19 links) | N/A |

0 out of 7 applications use `aria-keyshortcuts`. Only Wikipedia uses `accesskey`.

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

### 2005–2010: XHTML 2 tries to replace it

The W3C's XHTML 2 working group deprecated `accesskey` in favour of a new `<access>` element in the XHTML Role Access Module. But XHTML 2 was abandoned in favour of HTML5, which kept `accesskey` and never adopted `<access>`.

### 2017: `aria-keyshortcuts` — the right answer nobody uses

WAI-ARIA 1.1 introduced `aria-keyshortcuts`:

```html
<button aria-keyshortcuts="Control+Shift+P" aria-label="Show All Commands">
  Show All Commands
</button>
```

This solves every problem that killed `accesskey`:
- **Modifier combinations** — `Control+Shift+P`, not just a single key
- **No collision with browser shortcuts** — it's declarative, not an active binding; the browser doesn't intercept the keys
- **Exposed in the accessibility tree** — screen readers can announce it, automation tools can query it
- **Works alongside existing bindings** — the app handles the keyboard event in JS, `aria-keyshortcuts` just documents it

But by 2017, the web development community had spent 15 years learning that "keyboard shortcut attributes don't work." The collective memory of `accesskey`'s failures meant nobody adopted the replacement.

### 2024: We verified the gap

We queried 7 major web applications through the Chrome DevTools Protocol, checking:
1. DOM attributes (`aria-keyshortcuts`, `accesskey`)
2. The browser accessibility tree (CDP `Accessibility.getFullAXTree`, looking for `keyshortcuts` properties)

Result: **zero applications expose keyboard shortcuts through the accessibility layer.** Meanwhile, the same applications support dozens to hundreds of keyboard shortcuts, stored in JavaScript and inaccessible to assistive technology.

## Why This Matters

### For assistive technology users

Screen readers and alternative input devices can't discover keyboard shortcuts unless the application provides a separate help dialog. A user navigating by ARIA landmarks and roles has no way to know that `Ctrl+Shift+P` opens a command palette, or that `Ctrl+B` toggles bold text.

### For automation tooling

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
<button aria-keyshortcuts="Control+Shift+B" aria-label="Toggle bold">
  B
</button>
```

This is a single attribute addition. The app continues to handle the keyboard event in JavaScript — `aria-keyshortcuts` just documents the existing binding for the accessibility tree. No behaviour change required.

### 2. Use `aria-keyshortcuts` on menu items and toolbar buttons

For command palettes, menus, and toolbars:

```html
<div role="menuitem" aria-keyshortcuts="Control+Shift+P" aria-label="Show All Commands">
  Show All Commands
</div>
```

### 3. The accessibility tree already works

Browsers already expose `aria-keyshortcuts` through their accessibility APIs. We verified this with Chromium's CDP: setting `aria-keyshortcuts="Control+Shift+P"` on a button causes it to appear in the `keyshortcuts` property of the corresponding AX tree node. Screen readers can announce it. Automation tools can query it. The pipeline works — it just needs developers to set the attribute.

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

This would be the web equivalent of desktop app shortcut documentation, machine-readable from the start.

## What app-automate Is Doing

Regardless of adoption, we're building tooling to extract shortcuts from web apps:

1. **CDP shortcut extraction**: Query `aria-keyshortcuts`, `accesskey`, and AX tree `keyshortcuts` properties via `app-automate cdp-shortcuts`
2. **DOM scraping**: Query known CSS patterns (`.monaco-keybinding`, etc.)
3. **Documentation scraping**: Extract from help pages with table/dl/text extraction, using both HTTP and headless browser (Playwright) fetchers
4. **Accessibility tree walk**: Use CDP's `Accessibility.getFullAXTree` to find nodes with `keyshortcuts` properties

We'd rather not need any of these workarounds. If web apps used `aria-keyshortcuts`, a single CDP query would give us every shortcut in the application.

## References

- [Wikipedia: Access key](https://en.wikipedia.org/wiki/Access_key) — history of accesskey, conflicts, and standardisation attempts
- [WATS: Using Accesskeys — is it worth it? (2002)](https://web.archive.org/web/20120204224705/http://www.wats.ca/show.php?contentid=32) — the accessibility consultancy report that recommended avoiding accesskeys
- [SAK2014: Standard Access Keys 2014](https://web.archive.org/web/20230401101600/https://www.standardaccesskeys.com/) — the last attempt to standardise accesskey mappings
- [WAI-ARIA `aria-keyshortcuts` specification](https://www.w3.org/TR/wai-aria-1.2/#aria-keyshortcuts)
- [HTML `accesskey` attribute](https://html.spec.whatwg.org/multipage/interaction.html#the-accesskey-attribute)
- [MDN: aria-keyshortcuts](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Attributes/aria-keyshortcuts)
