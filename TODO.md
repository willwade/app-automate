# Development TODO

Things to do when you have access to a macOS or Linux desktop for hands-on testing.

## Linux

### High priority

- [ ] **Test AT-SPI on a real desktop session.** The AT-SPI backend is written but untested against a running app. Boot a GNOME/XFCE session, run `atspi-list --app "Calculator" --actionable-only`, and verify element output.
- [ ] **Fix virtualenv gi bindings.** `uv run` uses its own Python, but `gi.repository.Atspi` is in the system Python. Either:
  - Use `--system-site-packages` in the venv
  - Set `PYTHONPATH=/usr/lib/python3/dist-packages` before running
  - Or document the workaround clearly
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

- [ ] **Test `ax-list` on a real macOS session.** The AX backend is written but the CLI split changed import paths. Verify `ax-list --app "Safari"` still works.
- [ ] **Test `ax-click` and `ax-type` end-to-end.** Click a button in Safari or TextEdit.
- [ ] **Build a Safari profile.** Use keyboard shortcuts (same approach as Firefox) plus AX elements for the URL bar.
- [ ] **Train a semantic profile on macOS.** Run `train --backend uia --app "Safari"` — wait, macOS uses AX not UIA. Add `train --backend ax` support.
- [ ] **Verify window capture.** `front_window_bounds()` uses `osascript` for app window bounds. Test on Retina and non-Retina displays.

### Medium priority

- [ ] **Integrate `MacOSActionAdapter`.** Currently defined but unused in `create_action_adapter()`. macOS now falls through to `PyAutoGuiAdapter`. Decide: is the platform guard useful? If so, wire it up.
- [ ] **Extract keyboard shortcuts from AX menu items.** The `extract_from_ax_menu_items()` extractor is written but untested. It reads `AXMenuItemCmdChar` and `AXMenuItemCmdModifiers` from the accessibility tree.
- [ ] **Notes.app profile.** Simple, good accessibility, good for type testing.
- [ ] **TextEdit profile.** Standard text editor. Good for type/drag testing.
- [ ] **Demo script for Safari.** Navigate, search, close tab — all via shortcuts + AX.

### Low priority

- [ ] **Retina display coordinate verification.** `mss` reports logical coordinates on Retina. Verify anchor detection and click alignment at 2x scale.
- [ ] **Permission handling.** Document the Screen Recording and Accessibility permission setup process. Can we detect missing permissions and give a helpful error?
- [ ] **Test multi-state profiles on macOS.** Visual profiles with state detection — does it work on Retina?

## Cross-platform

### High priority

- [ ] **Shortcut file library.** Build a collection of shortcut JSON files for common apps: Firefox, Chrome, VS Code, LibreOffice, TextEdit/Notepad. Contributors can add more.
- [ ] **Combined profiles.** A profile should be able to mix shortcut elements (reliable) with accessibility elements (specific). Test a Firefox profile that uses shortcuts for nav and AT-SPI/UIA for specific buttons.
- [ ] **Test `probe` on all three platforms.** Verify recommendation logic: UIA on Windows, AT-SPI on Linux, AX on macOS, CV fallback everywhere.

### Medium priority

- [ ] **Hybrid profile schema.** Allow a single profile to specify `backend: "mixed"` with per-element backend hints.
- [ ] **CI testing.** Run the test suite on all three platforms via GitHub Actions. At minimum, run `ruff check` + `pytest` on Linux.
- [ ] **Profile validator command.** `app-automate validate <profile>` that checks the profile against the schema and warns about common mistakes.
- [ ] **Profile migration tool.** Help convert old visual profiles to semantic or shortcut-based profiles.
