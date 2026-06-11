from __future__ import annotations

_SYNONYM_GROUPS: list[list[str]] = [
    ["delete", "remove", "erase", "clear", "destroy", "discard", "trash"],
    ["close", "dismiss", "cancel", "exit", "quit"],
    ["open", "launch", "start", "run", "execute"],
    ["save", "store", "commit", "apply", "confirm", "ok", "done"],
    ["search", "find", "lookup", "query", "filter", "spotlight"],
    ["edit", "modify", "change", "update", "alter", "adjust"],
    ["create", "new", "add", "insert", "compose"],
    ["send", "submit", "post", "publish", "share", "deliver"],
    ["copy", "duplicate", "clone", "replicate"],
    ["cut", "remove", "snip"],
    ["paste", "insert", "place"],
    ["undo", "revert", "restore"],
    ["redo", "repeat", "reapply"],
    ["refresh", "reload", "update", "sync", "synchronize"],
    ["download", "fetch", "pull", "get"],
    ["upload", "push", "send", "attach"],
    ["print", "export", "pdf"],
    ["settings", "preferences", "options", "config", "configure"],
    ["help", "support", "info", "information", "about"],
    ["next", "forward", "continue", "proceed", "advance"],
    ["previous", "back", "prior", "return"],
    ["play", "start", "resume"],
    ["pause", "stop", "halt"],
    ["zoom", "magnify", "enlarge", "scale"],
    ["select", "choose", "pick", "highlight"],
    ["deselect", "unselect", "clear selection"],
    ["expand", "show", "reveal", "open", "unfold"],
    ["collapse", "hide", "minimize", "fold"],
    ["enable", "activate", "turn on", "check"],
    ["disable", "deactivate", "turn off", "uncheck"],
    ["lock", "secure", "protect"],
    ["unlock", "release", "unprotect"],
    ["login", "sign in", "authenticate"],
    ["logout", "sign out", "log off"],
    ["register", "sign up", "enroll", "join"],
    ["accept", "agree", "confirm", "approve"],
    ["reject", "decline", "deny", "refuse"],
    ["approve", "authorize", "confirm", "accept"],
    ["block", "ban", "restrict", "prevent"],
    ["connect", "link", "join", "pair"],
    ["disconnect", "unlink", "unpair"],
    ["move", "relocate", "transfer"],
    ["rename", "retitle", "relabel"],
    ["sort", "arrange", "order", "organize"],
    ["group", "bundle", "cluster"],
    ["share", "distribute", "collaborate"],
    ["reply", "respond", "answer"],
    ["forward", "redirect", "pass on"],
    ["archive", "store", "file away"],
    ["flag", "mark", "pin", "bookmark", "star", "favorite"],
    ["mute", "silence", "quiet"],
    ["unmute", "unsilence"],
    ["attach", "add", "include", "enclose"],
    ["detach", "remove", "exclude"],
    ["bold", "strong"],
    ["italic", "emphasis", "em"],
    ["underline", "underscore"],
    ["button", "btn"],
    ["link", "hyperlink", "url", "anchor"],
    ["menu", "dropdown", "popup menu"],
    ["tab", "section", "panel"],
    ["checkbox", "check box", "tick box"],
    ["radio", "radio button", "option button"],
    [
        "textfield",
        "text field",
        "input",
        "input field",
        "edit field",
        "text box",
        "textbox",
    ],
    ["textarea", "text area", "text editor", "editor"],
    ["slider", "range", "range control"],
    ["toggle", "switch", "on/off"],
    ["spinner", "stepper", "number input"],
    ["progress", "progress bar", "loading bar"],
    ["scrollbar", "scroll bar", "scroller"],
    ["tooltip", "hint", "popup tip"],
    ["dialog", "modal", "popup", "alert", "sheet"],
    ["notification", "toast", "banner", "alert"],
    ["toolbar", "tool bar", "action bar"],
    ["sidebar", "side panel", "navigation panel", "nav panel"],
    ["statusbar", "status bar", "info bar"],
    ["tabbar", "tab bar", "tab strip"],
    ["navbar", "nav bar", "navigation bar"],
    ["breadcrumb", "trail", "path"],
    ["image", "picture", "photo", "icon", "thumbnail"],
    ["video", "movie", "clip", "player"],
    ["audio", "sound", "music", "player"],
]

_SYNONYM_MAP: dict[str, list[str]] = {}
for _group in _SYNONYM_GROUPS:
    for _word in _group:
        _key = _word.lower()
        if _key not in _SYNONYM_MAP:
            _SYNONYM_MAP[_key] = []
        for _w in _group:
            if _w.lower() != _key and _w.lower() not in _SYNONYM_MAP[_key]:
                _SYNONYM_MAP[_key].append(_w.lower())


def expand_synonyms(query: str) -> list[str]:
    words = query.lower().split()
    if not words:
        return []
    expanded: set[str] = {query.lower()}
    for word in words:
        synonyms = _SYNONYM_MAP.get(word, [])
        expanded.update(synonyms)
        for syn in synonyms:
            expanded.add(f"{syn} {' '.join(w for w in words if w != word)}".strip())
    return sorted(expanded)


def get_synonyms(word: str) -> list[str]:
    return _SYNONYM_MAP.get(word.lower(), [])


ROLE_ALIASES: dict[str, list[str]] = {
    "button": ["axbutton", "buttoncontrol", "push button", "btn"],
    "link": ["axlink", "hyperlink", "anchor"],
    "textfield": [
        "axtextfield",
        "axcombobox",
        "text field",
        "input",
        "edit field",
        "editcontrol",
        "entry",
    ],
    "textarea": ["axtextarea", "text area", "text editor"],
    "checkbox": ["axcheckbox", "check box", "tick box"],
    "radio": ["axradio", "axradiobutton", "radio button", "option button"],
    "menuitem": ["axmenuitem", "menu item"],
    "menubar": ["axmenubar", "menu bar"],
    "menu": ["axmenu", "popup menu", "dropdown"],
    "tab": ["axtab", "tabitem", "tab item"],
    "slider": ["axslider", "range"],
    "toggle": ["axtoggle", "switch"],
    "statictext": ["axstatictext", "text", "label", "textblock"],
    "image": ["aximage", "picture", "imagecontrol"],
    "table": ["axtable", "grid", "data grid"],
    "row": ["axrow", "tablerow", "treeitem", "tree item"],
    "column": ["axcolumn", "tablecolumn"],
    "heading": ["axheading", "header", "heading"],
    "dialog": ["axdialog", "window", "modal", "sheet"],
    "toolbar": ["axtoolbar", "tool bar"],
    "scrollbar": ["axscrollbar", "scroll bar"],
    "progressbar": ["axprogressbar", "progress bar"],
    "pop up button": ["axpopupbutton", "pop up", "dropdown", "combobox"],
    "combo box": ["axcombobox", "combo", "select", "dropdown"],
    "search field": ["axsearchfield", "search box", "search"],
    "secure text field": ["axsecuretextfield", "password", "password field"],
    "window": ["axwindow", "window", "panel", "dialog"],
    "application": ["axapplication", "app"],
}


def normalise_role_alias(alias: str) -> str | None:
    lower = alias.lower().strip()
    for canonical, aliases in ROLE_ALIASES.items():
        if lower == canonical or lower in aliases:
            return canonical
    return None


def role_matches(element_role: str | None, target_alias: str) -> bool:
    if not element_role:
        return False
    canonical = normalise_role_alias(target_alias)
    if canonical is None:
        return target_alias.lower() in (element_role or "").lower()
    aliases = ROLE_ALIASES.get(canonical, [canonical])
    role_lower = element_role.lower()
    return any(a.lower() in role_lower for a in aliases) or canonical in role_lower
