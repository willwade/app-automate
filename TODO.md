# Development TODO

Things to do when you have access to a macOS or Linux desktop for hands-on testing.

## Linux

### High priority

- [ ] **Test AT-SPI on a real desktop session.** The AT-SPI backend is written but untested against a running app. Boot a GNOME/XFCE session, run `atspi-list --app "Calculator" --actionable-only`, and verify element output.
- [x] **Fix virtualenv gi bindings.** `uv run` uses its own Python, but `gi.repository.Atspi` is in the system Python. Fixed with `_ensure_gi_atspi()` helper that adds `/usr/lib/python3/dist-packages` to `sys.path` as fallback.
- [ ] **Train and test a real AT-SPI profile.** Run `train --backend atspi --app "Calculator"` on a desktop, then execute `click "5" --profile examples/profiles/calc/profile.json`.
- [ ] **Test Wayland compatibility.** Try `xdotool` and `pyautogui` on a Wayland session. If they fail, add `ydotool` support to `adapters/linux.py`.
- [ ] **GNOME Calculator profile.** Replace the Galculator profile with GNOME Calculator (the default on Ubuntu). Build it with `train --backend atspi`.

### Medium priority

- [ ] **LibreOffice Writer profile.** Full office suite with excellent AT-SPI support. Good semantic profile demo.
- [ ] **Nautilus/Files profile.** Standard file manager. Good for drag-and-drop testing.
- [ ] **GIMP visual profile.** Poor accessibility = good CV test candidate. Requires LLM key.
- [ ] **AT-SPI menu accelerator extraction.** Test `extract-shortcuts --source atspi-menu` with a running GTK app that has menu bar items with accelerators.
- [ ] **Demo script for Firefox.** `demos/firefox_shortcuts.py` that opens Firefox, navigates to a URL, searches, goes back — all via shortcuts.
- [ ] **Demo script for Calculator.** `demos/calculator.py` that performs `2+3=` via the galculator profile.

### Low priority

- [ ] **KDE Plasma testing.** AT-SPI works on KDE too but the tree structure may differ. Test and adjust if needed.
- [ ] **AppImage / Flatpak app testing.** Sandboxed apps may not expose AT-SPI. Document which ones work.
- [ ] **X11 vs Wayland coordinate verification.** Run the CV path on both and confirm `mss` capture + `pyautogui` click alignment.
- [ ] **Headless AT-SPI testing.** Explore `at-spi-bus-launcher --address` for CI testing without a full desktop session.

## macOS

### High priority

- [x] **Test `ax-list` on a real macOS session.** Verified working with Safari and TextEdit. Built native `axtool` Swift CLI for fast AX operations.
- [x] **Test `ax-click` and `ax-type` end-to-end.** Both work. `ax-click` tested on TextEdit Bold checkbox. `ax-type` added and tested typing "Hello ax-type" into TextEdit.
- [x] **Build a Safari profile.** 94 keyboard shortcuts extracted via `axtool export-profile`. Saved at `examples/profiles/safari/profile.json`.
- [x] **Train a semantic profile on macOS.** Shortcut extraction now works via `axtool shortcuts`. Full `train --backend ax` still needs wiring.
- [x] **Verify window capture.** `front_window_bounds()` now uses `axtool window-bounds` (49ms vs osascript's ~1s). Works on Retina.

### Medium priority

- [x] **Integrate `MacOSActionAdapter`.** Wired up as the macOS fallback in `create_action_adapter()` in `_shared.py`. Platform guard raises RuntimeError if not on macOS.
- [x] **Extract keyboard shortcuts from AX menu items.** `extract_from_ax_menu_items()` now uses `axtool shortcuts` (native Swift, 99 shortcuts in 0.5s vs 90s via osascript).
- [x] **Notes.app profile.** 91 shortcuts extracted via `axtool export-profile`. Saved at `examples/profiles/notes/profile.json`.
- [x] **TextEdit profile.** 71 shortcuts extracted via `axtool export-profile`. Saved at `examples/profiles/textedit/profile.json`.
- [x] **Demo script for Safari.** `demos/safari_shortcuts.py` drives Safari via native axtool input (click, type, hotkey).

### Low priority

- [ ] **Retina display coordinate verification.** `mss` reports logical coordinates on Retina. Verify anchor detection and click alignment at 2x scale.
- [ ] **Permission handling.** Document the Screen Recording and Accessibility permission setup process. Can we detect missing permissions and give a helpful error?
- [ ] **Test multi-state profiles on macOS.** Visual profiles with state detection — does it work on Retina?

## Shortcut Harvesting

Strategies for extracting keyboard shortcuts from live apps on each platform.

### Linux

- [ ] **AT-SPI menu accelerator extraction.** `extract-shortcuts --source atspi-menu` reads accelerator labels from GTK/Qt menu items via AT-SPI. Needs running app + desktop session.
- [ ] **`.desktop` file parsing.** `extract-shortcuts --source desktop` reads `~/.local/share/applications/*.desktop` for `Exec=` lines with keyboard hints. Already written, needs testing.
- [ ] **GNOME WM keybindings.** `extract-shortcuts --source gnome-wm` reads `gsettings` for window manager shortcuts. Already written, needs testing.
- [ ] **GTK Inspector.** For apps without AT-SPI menu bars (header bar apps), explore using GTK Inspector to extract action accelerators programmatically.
- [ ] **Qt accessibility.** Qt apps expose shortcuts via `QAccessibleActionInterface`. Investigate if AT-SPI exposes these.

### macOS

- [x] **AX menu item extraction.** `extract_from_ax_menu_items()` now uses native Swift `axtool shortcuts` for fast extraction. 99 Safari shortcuts in 0.5s.
- [x] **`defaults` plist parsing.** `extract_from_plist()` reads `NSUserKeyEquivalents` from app plists via `defaults export` + `plistlib`. Supports custom shortcuts like `@s` → `cmd+s`.
- [x] **System Preferences keyboard shortcuts.** `extract_system_shortcuts()` reads `com.apple.symbolichotkeys` via `defaults export` + `plistlib`. Named 40+ system actions (Spotlight, Mission Control, etc.).
- [ ] **Safari WebExtension shortcuts.** Safari extensions have `commands` in their manifest. Investigate extraction.
- [ ] **iWork shortcuts (Pages, Numbers, Keynote).** Apple's apps have rich shortcut sets but don't expose them via AX menus consistently. May need manual curation.

### Windows

- [x] **UIA accelerator key extraction.** `extract-shortcuts --source uia-menu` reads `AcceleratorKey` from all UIA controls (not just menus). Added `accelerator_key` field to `UIAElement`. Tested on Paint (ctrl+S, ctrl+Z, ctrl+Y).
- [x] **Registry shortcut harvesting.** `extract-shortcuts --source registry` walks HKCU/HKLM Software keys matching app name, recursing into shortcut/hotkey subkeys.
- [x] **`.lnk` file parsing.** `extract-shortcuts --source lnk` scans Start Menu .lnk files for IShellLink hotkey assignments with raw binary fallback parser.
- [ ] **MS Office ribbon shortcuts.** Office apps have "Key Tips" (Alt sequences). Investigate if UIA exposes these or if they need manual documentation.
- [ ] **PowerShell `Get-Command` + help.** For Windows-native CLI tools, harvest `-Key` parameter docs.

### Cross-platform

- [x] **ShortcutMapper bulk import.** Converter script `scripts/convert_shortcutmapper.py` imports from `waldobronchart/ShortcutMapper`. 20 apps done.
- [x] **JSON/TXT file import.** `extract-shortcuts --source file` reads user-provided JSON or `key = value` text files.
- [ ] **Web scraping pipeline.** For apps that only document shortcuts on web pages (e.g. Google Docs, Figma, Notion), write targeted scrapers. Consider per-app scrapers rather than generic.
- [ ] **User contribution workflow.** Define how users submit new shortcut files or corrections. GitHub PR to `examples/profiles/` or `examples/profiles-imported/`?
- [ ] **Version pinning.** ShortcutMapper data is old (PS CC 2014, Blender 2.78). Add version fields to profiles and a way to flag when an app update may have changed shortcuts.
- [ ] **Shortcut validation at profile load time.** Warn if a shortcut references keys that don't exist on the current platform (e.g. `super` on Windows).

## Native Adapter Libraries

Standalone native libraries for each platform that handle profile loading + platform input without Python.

### Why native?

- **macOS**: Accessibility permission is per-binary. Python venv paths change on rebuild, breaking the permission. Signed Swift binary = stable identity, permission sticks.
- **Windows**: `SendInput` with `uiAccess=true` in manifest allows interacting with UAC-elevated apps. Requires code signing. Python can't get UIAccess.
- **Linux**: No security benefit, but C/XTest avoids the `pyautogui` → `xdg` → `DISPLAY` dependency chain.

### Roadmap

- [ ] **NuGet package `AppAutomate.Consumer`** (highest priority — Smartbox .NET apps)
  - [x] `uia` native .NET CLI — list, find, click, type, shortcuts, window-bounds, activate. Built with managed `System.Windows.Automation` via WPF. Single-file publish.
  - [ ] Add `WindowsNativeAdapter` with `SendInput` P/Invoke (example in `docs/native-adapters.md`)
  - [ ] Add NuGet metadata (icon, description, tags)
  - [ ] Set up CI publish to nuget.org on tag
  - [ ] Test with a real .NET app loading Firefox profile
- [ ] **Swift Package `AppAutomateConsumer`** (macOS AT products)
  - [x] `axtool` native Swift CLI — list, find, shortcuts, window-bounds, click, type, hotkey, scroll, export-profile, check-permissions
  - [x] CGEvent input — native click, type, hotkey, scroll via CGEvent API
  - [x] AX menu shortcut extraction — recursive walk with AXMenuItemCmdChar/AXMenuItemCmdModifiers
  - [x] Auto-profile export — `axtool export-profile --app NAME` generates full semantic profile JSON
  - [x] Permission check — `axtool check-permissions` reports Accessibility permission status
  - [ ] Create `Package.swift` with profile model structs
  - [ ] Test Accessibility permission flow with signed binary
- [ ] **CI/CD for native tools**
  - [ ] GitHub Actions workflow to build axtool (macOS runner, Swift) and uia.exe (Windows runner, .NET) on tag push
  - [ ] Attach built binaries to GitHub Release
- [ ] **C header-only library** (Linux/embedded)
  - [ ] `adapter.h` with XTest key sending (example in `docs/native-adapters.md`)
  - [ ] Profile parsing via any JSON-C library (json-c, cJSON)
- [ ] **Cross-platform docs**
  - [x] `docs/native-adapters.md` — full examples for all three platforms
  - [x] `docs/consumer-spec.md` — interface spec
  - [x] `sdks/dotnet/` — .NET SDK skeleton with `IInputAdapter`

## Cross-platform

### High priority

- [x] **Shortcut file library.** 25 apps with shortcut profiles: 5 hand-crafted in `examples/profiles/`, 20 auto-imported in `examples/profiles-imported/`.
- [x] **Combined profiles.** Profiles already support mixing shortcut elements with accessibility elements in a single `semantic_elements` dict.
- [ ] **Test `probe` on all three platforms.** Verify recommendation logic: UIA on Windows, AT-SPI on Linux, AX on macOS, CV fallback everywhere. AX probe now implemented — `probe` checks AX on macOS and recommends it when 10+ interactive elements found. UIA probe tested on Windows — 37 Calculator elements found in 0.35s.

### Live Element Search (Shortcat-style, all platforms)

Cross-platform live search over the accessibility tree — query, filter, and act on elements without a pre-built profile. Inspired by [Shortcat](https://shortcat.app/) but scriptable and cross-platform.

- [x] **Synonym expansion map.** Built in `accessibility/synonyms.py` — 75+ synonym groups covering common UI concepts (delete/remove/erase, button/btn, close/dismiss, search/find, etc.). `expand_synonyms("erase")` → `[clear, delete, destroy, discard, erase, remove, trash]`. Works across all backends.
- [x] **`app-automate search` CLI command.** `search "delete" --app Safari` queries the live accessibility tree (AX on macOS, UIA on Windows, AT-SPI on Linux), scores by label/role/synonym match, returns ranked results. Tested on Safari with 187 elements.
- [x] **Element type filtering.** `search "search" --role textfield` filters by normalised role aliases (AXButton→button, AXTextField→textfield, etc.). 30+ role aliases mapped across platforms in `ROLE_ALIASES`.
- [x] **Search + act in one step.** `search "share" --click --execute` finds and clicks. `search "email" --type "hello@example.com"` finds a text field and types. `--dry-run` (default) shows what would be done.
- [x] **Fuzzy matching.** Scoring engine in `accessibility/search.py` — exact match (100), substring (80+), token (60+), role (55), synonym (30+). Actionable elements get +5 bonus. Ranked by score then depth/position.
- [x] **Backend abstraction for search.** `search_elements()` takes any `list[UIElement]` — works with AX, UIA, and AT-SPI backends. No profile needed.

### Medium priority

- [x] **Hybrid profile schema.** `backend: "mixed"` with per-element action types.
- [x] **CI testing.** GitHub Actions workflow runs `ruff check` + `pytest` on push/PR.
- [x] **Profile validator command.** `app-automate validate <profile>` checks profiles for common issues (exit 0/1/2).
- [ ] **Profile migration tool.** Help convert old visual profiles to semantic or shortcut-based profiles.
- [ ] **Human review step for builder output.** Before a trained profile is considered final, show the user what was detected and let them confirm/edit.
- [ ] **Anchor scoring and ranking.** Rank candidate anchors before accepting the LLM's proposal. Prefer stable, high-contrast, positionally useful anchors.
- [ ] **Prompt improvements for repeated-grid interfaces.** Apps with grid layouts (calculators, spreadsheets) produce repetitive elements. Improve the builder prompt to handle these better.

### Hard problems

- [ ] **Controls that animate or move** independently from the window frame (tooltips, floating panels, auto-hide toolbars).
- [ ] **Layouts that don't scale linearly.** Some apps use non-linear scaling or fixed-size elements at certain breakpoints.
- [ ] **Robust anchor re-training.** When an anchor breaks (app update, theme change), make it easy to re-train just that anchor without rebuilding the whole profile.
- [ ] **Profile versioning and migration.** When the schema changes, provide a migration path for existing profiles.
