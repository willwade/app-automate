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

0 out of 7 applications use `aria-keyshortcuts`. Only Wikipedia uses `accesskey`, an HTML attribute from 1999 that is limited to single keys and doesn't support modifier combos.

## What Exists Today

### `accesskey` (HTML 4, 1999)

```html
<a href="/" accesskey="h">Home</a>
```

Limitations:
- Single key only — no modifier combinations
- Browser determines the modifier (Alt on Windows, Ctrl+Alt on Firefox, etc.)
- No way to document the shortcut's purpose
- Inconsistent behavior across browsers
- Limited to one shortcut per element

### `aria-keyshortcuts` (WAI-ARIA 1.1, 2017)

```html
<button aria-keyshortcuts="Ctrl+Shift+P">Show All Commands</button>
```

This is exactly the right attribute. It:
- Supports modifier combinations (`Ctrl+Shift+P`)
- Is part of the ARIA accessibility tree
- Gets exposed through platform accessibility APIs (AT-SPI, UIA, AX)
- Can be queried programmatically via CDP

**Nobody uses it.**

## Why This Matters

### For assistive technology users

Screen readers and alternative input devices can't discover keyboard shortcuts unless the application provides a separate help dialog. A user navigating by aria landmarks and roles has no way to know that `Ctrl+Shift+P` opens a command palette, or that `Ctrl+B` toggles bold text.

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

This is a single attribute addition. It requires no JavaScript changes.

### 2. Use `aria-keyshortcuts` on menu items

For command palettes, menus, and toolbars:

```html
<div role="menuitem" aria-keyshortcuts="Control+Shift+P" aria-label="Show All Commands">
  Show All Commands
</div>
```

### 3. Expose through the accessibility tree

Browsers already expose `aria-keyshortcuts` through their accessibility APIs. Adding the attribute means:
- Screen readers can announce shortcuts ("Show All Commands, Control Shift P")
- Automation tools can query the tree for available shortcuts
- Platform accessibility APIs expose it consistently

### 4. Consider a `keyboardShortcuts` manifest

For applications with many shortcuts (like code editors), a JSON manifest that can be discovered at a well-known URL:

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

1. **DOM scraping**: Query known CSS patterns (`.monaco-keybinding`, etc.)
2. **Documentation scraping**: Extract from help pages with table/dl/text extraction
3. **CDP queries**: Check `aria-keyshortcuts` and `accesskey` attributes
4. **Accessibility tree walk**: Use CDP's `Accessibility.getFullAXTree` to find nodes with `keyshortcuts` properties

We'd rather not need any of these workarounds. If web apps used `aria-keyshortcuts`, a single CDP query would give us every shortcut in the application.

## References

- [WAI-ARIA `aria-keyshortcuts` specification](https://www.w3.org/TR/wai-aria-1.2/#aria-keyshortcuts)
- [HTML `accesskey` attribute](https://html.spec.whatwg.org/multipage/interaction.html#the-accesskey-attribute)
- [MDN: aria-keyshortcuts](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Attributes/aria-keyshortcuts)
