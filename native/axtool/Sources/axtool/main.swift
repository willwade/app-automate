import AppKit
import ApplicationServices
import Foundation

// MARK: - Main

func main() {
    let args = CommandLine.arguments.dropFirst()
    guard let subcommand = args.first else {
        printUsage()
        exit(1)
    }
    let rest = Array(args.dropFirst())

    switch subcommand {
    case "list": cmdList(rest)
    case "find": cmdFind(rest)
    case "shortcuts": cmdShortcuts(rest)
    case "window-bounds": cmdWindowBounds(rest)
    case "activate": cmdActivate(rest)
    case "click": cmdClick(rest)
    case "type": cmdType(rest)
    case "hotkey": cmdHotkey(rest)
    case "scroll": cmdScroll(rest)
    case "export-profile": cmdExportProfile(rest)
    case "check-permissions": cmdCheckPermissions(rest)
    case "--help", "-h": printUsage()
    default:
        fputs("Unknown command: \(subcommand)\n", stderr)
        exit(1)
    }
}

// MARK: - Usage

func printUsage() {
    print(
        """
        axtool - macOS accessibility CLI

        Commands:
          list              List UI elements
          find              Find elements matching text
          shortcuts         Extract keyboard shortcuts from menus
          window-bounds     Get front window bounds
          activate          Activate an application
          click             Click at coordinates
          type              Type text at coordinates
          hotkey            Send a keyboard shortcut
          scroll            Scroll at coordinates
          export-profile    Export a shortcut profile as JSON
          check-permissions Check Accessibility permissions

        Common flags:
          --app NAME        Application name
          --max-depth N     Maximum tree depth (default: 3)
          --actionable      Only show actionable controls
          --contains TEXT   Substring filter
          --json            JSON output
          --x N --y N       Coordinates for click/type/scroll
          --text TEXT       Text for type command
          --keys KEYS       Key combo for hotkey (e.g. "cmd+t")
          --clicks N        Scroll clicks (signed)
          --help            Show help
        """
    )
}

// MARK: - Argument parsing

struct Opts {
    var appName: String?
    var maxDepth: Int = 3
    var actionableOnly = false
    var contains: String?
    var asJson = false
    var x: CGFloat?
    var y: CGFloat?
    var text: String?
    var keys: String?
    var clicks: Int = 0

    init(_ args: [String]) {
        var i = 0
        while i < args.count {
            switch args[i] {
            case "--app":
                i += 1; if i < args.count { appName = args[i] }
            case "--max-depth":
                i += 1; if i < args.count { maxDepth = Int(args[i]) ?? 3 }
            case "--actionable":
                actionableOnly = true
            case "--contains":
                i += 1; if i < args.count { contains = args[i] }
            case "--json":
                asJson = true
            case "--x":
                i += 1; if i < args.count { x = CGFloat(Float(args[i]) ?? 0) }
            case "--y":
                i += 1; if i < args.count { y = CGFloat(Float(args[i]) ?? 0) }
            case "--text":
                i += 1; if i < args.count { text = args[i] }
            case "--keys":
                i += 1; if i < args.count { keys = args[i] }
            case "--clicks":
                i += 1; if i < args.count { clicks = Int(args[i]) ?? 0 }
            case "--help", "-h":
                printUsage(); exit(0)
            default:
                break
            }
            i += 1
        }
    }

    func requireApp() -> String {
        guard let name = appName else {
            fputs("--app is required\n", stderr)
            exit(1)
        }
        return name
    }
}

// MARK: - AX helpers

let ACTIONABLE_ROLES: Set<String> = [
    "AXButton", "AXCheckBox", "AXRadioButton", "AXPopUpButton",
    "AXTextField", "AXTextArea", "AXComboBox", "AXMenuButton",
    "AXSlider",
]

struct AXNode {
    let path: String
    let role: String
    let subrole: String?
    let title: String?
    let desc: String?
    let position: CGPoint?
    let size: CGSize?
    let enabled: Bool?
    let depth: Int
    let childCount: Int
    let roleDescription: String?

    var isActionable: Bool { ACTIONABLE_ROLES.contains(role) }

    var label: String {
        if let t = title, !t.isEmpty { return t }
        if let d = desc, !d.isEmpty { return d }
        if let rd = roleDescription, !rd.isEmpty { return rd }
        return role
    }

    func toJson() -> String {
        var parts: [String] = []
        parts.append("\"path\":\(enc(path))")
        parts.append("\"class_name\":\(enc(roleLabel(role)))")
        parts.append("\"role\":\(enc(role))")
        parts.append("\"subrole\":\(encO(subrole))")
        parts.append("\"description\":\(encO(desc))")
        parts.append("\"title\":\(encO(title))")
        parts.append("\"name\":\(encO(title))")
        if let p = position {
            parts.append("\"x\":\(Int(p.x))")
            parts.append("\"y\":\(Int(p.y))")
        } else {
            parts.append("\"x\":null")
            parts.append("\"y\":null")
        }
        if let s = size {
            parts.append("\"width\":\(Int(s.width))")
            parts.append("\"height\":\(Int(s.height))")
        } else {
            parts.append("\"width\":null")
            parts.append("\"height\":null")
        }
        if let e = enabled {
            parts.append("\"enabled\":\(e)")
        } else {
            parts.append("\"enabled\":null")
        }
        parts.append("\"depth\":\(depth)")
        parts.append("\"child_count\":\(childCount)")
        return "{\(parts.joined(separator: ","))}"
    }

    func toText() -> String {
        let indent = String(repeating: "  ", count: depth)
        let bounds: String
        if let p = position, let s = size {
            bounds = "\(Int(p.x)),\(Int(p.y)) \(Int(s.width))x\(Int(s.height))"
        } else {
            bounds = "unknown"
        }
        let status = enabled == true ? "enabled" : (enabled == false ? "disabled" : "unknown")
        return "\(indent)\(roleLabel(role)): \(label) [\(bounds)] (\(status), children=\(childCount))"
    }
}

func roleLabel(_ role: String) -> String {
    switch role {
    case "AXButton": return "button"
    case "AXCheckBox": return "checkbox"
    case "AXRadioButton": return "radio button"
    case "AXTextField": return "text field"
    case "AXTextArea": return "text area"
    case "AXPopUpButton": return "pop up button"
    case "AXMenuButton": return "menu button"
    case "AXComboBox": return "combo box"
    case "AXWindow": return "window"
    case "AXStaticText": return "static text"
    case "AXImage": return "image"
    case "AXScrollArea": return "scroll area"
    case "AXGroup": return "group"
    case "AXToolBar": return "toolbar"
    case "AXTabGroup": return "tab group"
    case "AXSplitGroup": return "splitter group"
    case "AXMenuBar": return "menu bar"
    default: return role
    }
}

func enc(_ s: String) -> String {
    let escaped = s
        .replacingOccurrences(of: "\\", with: "\\\\")
        .replacingOccurrences(of: "\"", with: "\\\"")
        .replacingOccurrences(of: "\n", with: "\\n")
        .replacingOccurrences(of: "\r", with: "\\r")
        .replacingOccurrences(of: "\t", with: "\\t")
    return "\"\(escaped)\""
}

func encO(_ s: String?) -> String {
    guard let s = s else { return "null" }
    return enc(s)
}

func getPID(for name: String) -> pid_t? {
    let ws = NSWorkspace.shared
    guard let app = ws.runningApplications.first(where: {
        $0.localizedName == name || $0.bundleIdentifier == name
    }) else {
        return nil
    }
    return app.processIdentifier
}

func getString(_ el: AXUIElement, _ attr: String) -> String? {
    var val: AnyObject?
    let err = AXUIElementCopyAttributeValue(el, attr as CFString, &val)
    guard err == .success else { return nil }
    return val as? String
}

func getBool(_ el: AXUIElement, _ attr: String) -> Bool? {
    var val: AnyObject?
    let err = AXUIElementCopyAttributeValue(el, attr as CFString, &val)
    guard err == .success else { return nil }
    return val as? Bool
}

func getPoint(_ el: AXUIElement, _ attr: String) -> CGPoint? {
    var val: AnyObject?
    let err = AXUIElementCopyAttributeValue(el, attr as CFString, &val)
    guard err == .success else { return nil }
    let axVal = val as! AXValue
    var point = CGPoint()
    guard AXValueGetValue(axVal, .cgPoint, &point) else { return nil }
    return point
}

func getSize(_ el: AXUIElement, _ attr: String) -> CGSize? {
    var val: AnyObject?
    let err = AXUIElementCopyAttributeValue(el, attr as CFString, &val)
    guard err == .success else { return nil }
    let axVal = val as! AXValue
    var size = CGSize()
    guard AXValueGetValue(axVal, .cgSize, &size) else { return nil }
    return size
}

func getCount(_ el: AXUIElement, _ attr: String) -> Int {
    var val: AnyObject?
    let err = AXUIElementCopyAttributeValue(el, attr as CFString, &val)
    guard err == .success else { return 0 }
    return CFArrayGetCount(val as! CFArray)
}

func getChildren(_ el: AXUIElement) -> [AXUIElement] {
    var val: AnyObject?
    let err = AXUIElementCopyAttributeValue(el, kAXChildrenAttribute as CFString, &val)
    guard err == .success, let arr = val as? [AXUIElement] else { return [] }
    return arr
}

func readNode(_ el: AXUIElement, path: String, depth: Int) -> AXNode {
    let role = getString(el, kAXRoleAttribute as String) ?? ""
    let subrole = getString(el, kAXSubroleAttribute as String)
    let title = getString(el, kAXTitleAttribute as String)
    let desc = getString(el, kAXDescriptionAttribute as String)
    let roleDesc = getString(el, kAXRoleDescriptionAttribute as String)
    let position = getPoint(el, kAXPositionAttribute as String)
    let size = getSize(el, kAXSizeAttribute as String)
    let enabled = getBool(el, kAXEnabledAttribute as String)
    let childCount = getCount(el, kAXChildrenAttribute as String)

    return AXNode(
        path: path,
        role: role,
        subrole: subrole,
        title: title,
        desc: desc,
        position: position,
        size: size,
        enabled: enabled,
        depth: depth,
        childCount: childCount,
        roleDescription: roleDesc
    )
}

func walkElements(
    _ el: AXUIElement,
    path: String,
    depth: Int,
    maxDepth: Int,
    into results: inout [AXNode]
) {
    let node = readNode(el, path: path, depth: depth)
    results.append(node)
    if depth >= maxDepth { return }
    let children = getChildren(el)
    for (i, child) in children.enumerated() {
        let childPath = "\(path) > UI element \(i + 1)"
        walkElements(child, path: childPath, depth: depth + 1, maxDepth: maxDepth, into: &results)
    }
}

func activateApp(_ pid: pid_t) {
    NSRunningApplication(processIdentifier: pid)?.activate()
    usleep(300_000)
}

func getFocusedWindow(_ app: AXUIElement) -> AXUIElement? {
    var val: AnyObject?
    let err = AXUIElementCopyAttributeValue(app, kAXFocusedWindowAttribute as CFString, &val)
    guard err == .success else { return nil }
    return (val as! AXUIElement)
}

// MARK: - Commands

func cmdList(_ args: [String]) {
    let opts = Opts(args)
    let appName = opts.requireApp()

    guard let pid = getPID(for: appName) else {
        fputs("App not found: \(appName)\n", stderr)
        exit(1)
    }
    activateApp(pid)
    let app = AXUIElementCreateApplication(pid)

    guard let win = getFocusedWindow(app) else {
        fputs("No focused window for \(appName)\n", stderr)
        exit(1)
    }

    var results: [AXNode] = []
    walkElements(win, path: "front window", depth: 0, maxDepth: opts.maxDepth, into: &results)

    var filtered = results
    if opts.actionableOnly {
        filtered = filtered.filter { $0.isActionable }
    }
    if let needle = opts.contains {
        let lower = needle.lowercased()
        filtered = filtered.filter { el in
            el.label.lowercased().contains(lower)
                || el.role.lowercased().contains(lower)
                || (el.subrole?.lowercased().contains(lower) ?? false)
        }
    }

    if opts.asJson {
        let items = filtered.map { $0.toJson() }.joined(separator: ",")
        print("[\(items)]")
    } else {
        for node in filtered {
            print(node.toText())
        }
    }
}

func cmdFind(_ args: [String]) {
    let opts = Opts(args)
    let appName = opts.requireApp()
    guard let needle = opts.contains else {
        fputs("--contains is required for find\n", stderr)
        exit(1)
    }

    guard let pid = getPID(for: appName) else {
        fputs("App not found: \(appName)\n", stderr)
        exit(1)
    }
    activateApp(pid)
    let app = AXUIElementCreateApplication(pid)

    guard let win = getFocusedWindow(app) else {
        fputs("No focused window for \(appName)\n", stderr)
        exit(1)
    }

    var results: [AXNode] = []
    walkElements(win, path: "front window", depth: 0, maxDepth: opts.maxDepth, into: &results)

    let lower = needle.lowercased()
    let matches = results.filter { el in
        el.isActionable
            && (el.enabled != false)
            && (
                el.label.lowercased().contains(lower)
                    || el.role.lowercased().contains(lower)
                    || (el.subrole?.lowercased().contains(lower) ?? false)
            )
    }

    if opts.asJson {
        let items = matches.map { $0.toJson() }.joined(separator: ",")
        print("[\(items)]")
    } else {
        for node in matches {
            print(node.toText())
        }
    }
}

// MARK: - Shortcuts

struct MenuShortcut: Codable {
    let action: String
    let cmdChar: String
    let cmdModifiers: Int
    let description: String
    let keys: String
}

func cmdShortcuts(_ args: [String]) {
    let opts = Opts(args)
    let appName = opts.requireApp()

    guard let pid = getPID(for: appName) else {
        fputs("App not found: \(appName)\n", stderr)
        exit(1)
    }
    let app = AXUIElementCreateApplication(pid)

    var menuBarVal: AnyObject?
    let err = AXUIElementCopyAttributeValue(app, kAXMenuBarAttribute as CFString, &menuBarVal)
    guard err == .success else {
        fputs("No menu bar for \(appName)\n", stderr)
        exit(1)
    }

    let menuBar = menuBarVal as! AXUIElement
    let menuBarItems = getChildren(menuBar)
    var shortcuts: [MenuShortcut] = []

    for barItem in menuBarItems {
        let barTitle = getString(barItem, kAXTitleAttribute as String) ?? ""
        let menuChildren = getChildren(barItem)
        guard let menu = menuChildren.first else { continue }
        walkMenuItems(menu, path: barTitle, into: &shortcuts)
    }

    let encoder = JSONEncoder()
    encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
    if let data = try? encoder.encode(shortcuts) {
        print(String(data: data, encoding: .utf8) ?? "[]")
    } else {
        print("[]")
    }
}

func walkMenuItems(_ menu: AXUIElement, path: String, into shortcuts: inout [MenuShortcut]) {
    let items = getChildren(menu)
    for item in items {
        let title = getString(item, kAXTitleAttribute as String) ?? ""
        guard !title.isEmpty else { continue }

        let cmdChar = getString(item, "AXMenuItemCmdChar") ?? ""
        let cmdMods = getAXMenuItemModifiers(item)

        if !cmdChar.isEmpty {
            let keys = formatShortcut(cmdChar: cmdChar, modifiers: cmdMods)
            shortcuts.append(
                MenuShortcut(
                    action: "\(path) > \(title)",
                    cmdChar: cmdChar,
                    cmdModifiers: cmdMods,
                    description: title,
                    keys: keys
                )
            )
        }

        let subChildren = getChildren(item)
        for child in subChildren {
            let childRole = getString(child, kAXRoleAttribute as String) ?? ""
            if childRole == "AXMenu" {
                walkMenuItems(child, path: "\(path) > \(title)", into: &shortcuts)
            }
        }
    }
}

func getAXMenuItemModifiers(_ item: AXUIElement) -> Int {
    var val: AnyObject?
    let err = AXUIElementCopyAttributeValue(item, "AXMenuItemCmdModifiers" as CFString, &val)
    guard err == .success else { return 0 }
    if let i = val as? Int { return i }
    return 0
}

func formatShortcut(cmdChar: String, modifiers: Int) -> String {
    var parts: [String] = []
    if modifiers & 0x0100 != 0 { parts.append("cmd") }
    if modifiers & 0x0200 != 0 { parts.append("alt") }
    if modifiers & 0x0400 != 0 { parts.append("ctrl") }
    if modifiers & 0x0800 != 0 { parts.append("shift") }
    // cmd-only (modifier 0) means cmd+key
    if parts.isEmpty && !cmdChar.isEmpty {
        parts.append("cmd")
    }
    parts.append(cmdChar.lowercased())
    return parts.joined(separator: "+")
}

// MARK: - Window bounds

func cmdWindowBounds(_ args: [String]) {
    let opts = Opts(args)
    let appName = opts.requireApp()

    guard let pid = getPID(for: appName) else {
        fputs("App not found: \(appName)\n", stderr)
        exit(1)
    }
    let app = AXUIElementCreateApplication(pid)

    guard let win = getFocusedWindow(app) else {
        fputs("No focused window for \(appName)\n", stderr)
        exit(1)
    }

    let pos = getPoint(win, kAXPositionAttribute as String)
    let size = getSize(win, kAXSizeAttribute as String)

    if opts.asJson {
        print(
            """
            {"x":\(pos.map { Int($0.x) } ?? 0),"y":\(pos.map { Int($0.y) } ?? 0),\
            "width":\(size.map { Int($0.width) } ?? 0),"height":\(size.map { Int($0.height) } ?? 0)}
            """
        )
    } else {
        let x = pos.map { Int($0.x) } ?? 0
        let y = pos.map { Int($0.y) } ?? 0
        let w = size.map { Int($0.width) } ?? 0
        let h = size.map { Int($0.height) } ?? 0
        print("\(x),\(y),\(w),\(h)")
    }
}

// MARK: - Activate

func cmdActivate(_ args: [String]) {
    let opts = Opts(args)
    let appName = opts.requireApp()

    guard let pid = getPID(for: appName) else {
        fputs("App not found: \(appName)\n", stderr)
        exit(1)
    }
    NSRunningApplication(processIdentifier: pid)?.activate()
}

// MARK: - CGEvent input helpers

func postClick(x: CGFloat, y: CGFloat) {
    let down = CGEvent(
        mouseEventSource: CGEventSource(stateID: .hidSystemState),
        mouseType: .leftMouseDown,
        mouseCursorPosition: CGPoint(x: x, y: y),
        mouseButton: .left
    )
    let up = CGEvent(
        mouseEventSource: CGEventSource(stateID: .hidSystemState),
        mouseType: .leftMouseUp,
        mouseCursorPosition: CGPoint(x: x, y: y),
        mouseButton: .left
    )
    down?.post(tap: CGEventTapLocation.cghidEventTap)
    up?.post(tap: CGEventTapLocation.cghidEventTap)
}

func postRightClick(x: CGFloat, y: CGFloat) {
    let down = CGEvent(
        mouseEventSource: CGEventSource(stateID: .hidSystemState),
        mouseType: .rightMouseDown,
        mouseCursorPosition: CGPoint(x: x, y: y),
        mouseButton: .right
    )
    let up = CGEvent(
        mouseEventSource: CGEventSource(stateID: .hidSystemState),
        mouseType: .rightMouseUp,
        mouseCursorPosition: CGPoint(x: x, y: y),
        mouseButton: .right
    )
    down?.post(tap: CGEventTapLocation.cghidEventTap)
    up?.post(tap: CGEventTapLocation.cghidEventTap)
}

func postDoubleClick(x: CGFloat, y: CGFloat) {
    postClick(x: x, y: y)
    usleep(50_000)
    postClick(x: x, y: y)
}

func postScroll(x: CGFloat, y: CGFloat, clicks: Int) {
    let scroll = CGEvent(
        scrollWheelEvent2Source: CGEventSource(stateID: .hidSystemState),
        units: .pixel,
        wheelCount: 1,
        wheel1: Int32(clicks * 10),
        wheel2: 0,
        wheel3: 0
    )
    scroll?.post(tap: CGEventTapLocation.cghidEventTap)
}

func postTypeText(_ text: String) {
    for char in text {
        let unichar = char.utf16.first!
        var chars = [unichar]
        let event = CGEvent(
            keyboardEventSource: CGEventSource(stateID: .hidSystemState),
            virtualKey: 0,
            keyDown: true
        )
        event?.keyboardSetUnicodeString(
            stringLength: 1,
            unicodeString: &chars
        )
        event?.post(tap: CGEventTapLocation.cghidEventTap)
        let up = CGEvent(
            keyboardEventSource: CGEventSource(stateID: .hidSystemState),
            virtualKey: 0,
            keyDown: false
        )
        up?.keyboardSetUnicodeString(
            stringLength: 1,
            unicodeString: &chars
        )
        up?.post(tap: CGEventTapLocation.cghidEventTap)
    }
}

let KEY_MAP: [String: CGKeyCode] = [
    "a": 0, "b": 11, "c": 8, "d": 2, "e": 14, "f": 3,
    "g": 5, "h": 4, "i": 34, "j": 38, "k": 40, "l": 37,
    "m": 46, "n": 45, "o": 31, "p": 35, "q": 12, "r": 15,
    "s": 1, "t": 17, "u": 32, "v": 9, "w": 13, "x": 7,
    "y": 16, "z": 6,
    "0": 29, "1": 18, "2": 19, "3": 20, "4": 21,
    "5": 23, "6": 22, "7": 26, "8": 28, "9": 25,
    "return": 36, "enter": 36, "tab": 48, "space": 49,
    "delete": 51, "backspace": 51, "escape": 53, "esc": 53,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96,
    "f6": 97, "f7": 98, "f8": 100, "f9": 101, "f10": 109,
    "f11": 103, "f12": 111,
    "home": 115, "end": 119, "pageup": 116, "pagedown": 121,
    "left": 123, "right": 124, "down": 125, "up": 126,
    "plus": 24, "minus": 27, "equal": 24, "slash": 42,
    "backslash": 42, "comma": 43, "period": 47, "bracketleft": 33,
    "bracketright": 30,
]

func parseHotkey(_ raw: String) -> (flags: CGEventFlags, keycode: CGKeyCode)? {
    let parts = raw.lowercased().split(separator: "+").map(String.init)
    var flags: CGEventFlags = []
    var keyCode: CGKeyCode?

    for part in parts {
        switch part {
        case "cmd", "command":
            flags.insert(.maskCommand)
        case "alt", "option":
            flags.insert(.maskAlternate)
        case "ctrl", "control":
            flags.insert(.maskControl)
        case "shift":
            flags.insert(.maskShift)
        default:
            if let code = KEY_MAP[part] {
                keyCode = code
            } else if part.count == 1, let scalar = part.unicodeScalars.first {
                keyCode = CGKeyCode(truncatingIfNeeded: scalar.value)
            }
        }
    }

    guard let kc = keyCode else { return nil }
    return (flags, kc)
}

func postHotkey(_ raw: String) {
    guard let (flags, keycode) = parseHotkey(raw) else {
        fputs("Cannot parse hotkey: \(raw)\n", stderr)
        exit(1)
    }
    let down = CGEvent(
        keyboardEventSource: CGEventSource(stateID: .hidSystemState),
        virtualKey: keycode,
        keyDown: true
    )
    down?.flags = flags
    down?.post(tap: CGEventTapLocation.cghidEventTap)

    let up = CGEvent(
        keyboardEventSource: CGEventSource(stateID: .hidSystemState),
        virtualKey: keycode,
        keyDown: false
    )
    up?.flags = flags
    up?.post(tap: CGEventTapLocation.cghidEventTap)
}

// MARK: - Click command

func cmdClick(_ args: [String]) {
    let opts = Opts(args)
    guard let px = opts.x, let py = opts.y else {
        fputs("--x and --y are required\n", stderr)
        exit(1)
    }
    postClick(x: px, y: py)
}

// MARK: - Type command

func cmdType(_ args: [String]) {
    let opts = Opts(args)
    guard let text = opts.text else {
        fputs("--text is required\n", stderr)
        exit(1)
    }
    if let px = opts.x, let py = opts.y {
        postClick(x: px, y: py)
        usleep(100_000)
    }
    postTypeText(text)
}

// MARK: - Hotkey command

func cmdHotkey(_ args: [String]) {
    let opts = Opts(args)
    guard let keys = opts.keys else {
        fputs("--keys is required\n", stderr)
        exit(1)
    }
    postHotkey(keys)
}

// MARK: - Scroll command

func cmdScroll(_ args: [String]) {
    let opts = Opts(args)
    guard let px = opts.x, let py = opts.y else {
        fputs("--x and --y are required\n", stderr)
        exit(1)
    }
    let clicks = opts.clicks
    guard clicks != 0 else {
        fputs("--clicks must be non-zero\n", stderr)
        exit(1)
    }
    postScroll(x: px, y: py, clicks: clicks)
}

// MARK: - Export profile

func cmdExportProfile(_ args: [String]) {
    let opts = Opts(args)
    let appName = opts.requireApp()

    guard let pid = getPID(for: appName) else {
        fputs("App not found: \(appName)\n", stderr)
        exit(1)
    }
    let app = AXUIElementCreateApplication(pid)

    var menuBarVal: AnyObject?
    let err = AXUIElementCopyAttributeValue(app, kAXMenuBarAttribute as CFString, &menuBarVal)
    guard err == .success else {
        fputs("No menu bar for \(appName)\n", stderr)
        exit(1)
    }

    let menuBar = menuBarVal as! AXUIElement
    let menuBarItems = getChildren(menuBar)
    var allShortcuts: [MenuShortcut] = []
    for barItem in menuBarItems {
        let barTitle = getString(barItem, kAXTitleAttribute as String) ?? ""
        let menuChildren = getChildren(barItem)
        guard let menu = menuChildren.first else { continue }
        walkMenuItems(menu, path: barTitle, into: &allShortcuts)
    }

    var profile: [String: Any] = [:]
    let slug = appName.lowercased().replacingOccurrences(of: " ", with: "-")
    profile["profile_id"] = slug
    profile["app_name"] = appName
    profile["type"] = "semantic"
    profile["backend"] = "ax"
    profile["platform_hint"] = "macos"

    var shortcuts: [String: Any] = [:]
    var semanticElements: [String: Any] = [:]

    for sc in allShortcuts {
        guard !sc.keys.isEmpty else { continue }
        let id = slugify(sc.description)
        guard !id.isEmpty else { continue }

        if shortcuts[id] != nil { continue }

        let shortcutDef: [String: String] = [
            "keys": sc.keys,
            "description": sc.description,
            "platform": "macos",
        ]
        shortcuts[id] = shortcutDef

        let elemId = "\(id)_shortcut"
        semanticElements[elemId] = [
            "label": id,
            "aliases": generateAliases(sc.description, path: sc.action),
            "action": "shortcut",
            "shortcut": shortcutDef,
        ] as [String: Any]
    }

    profile["shortcuts"] = shortcuts
    profile["semantic_elements"] = semanticElements

    if let data = try? JSONSerialization.data(
        withJSONObject: profile,
        options: [.prettyPrinted, .sortedKeys]
    ) {
        print(String(data: data, encoding: .utf8) ?? "{}")
    } else {
        print("{}")
    }
}

func slugify(_ s: String) -> String {
    return s
        .lowercased()
        .replacingOccurrences(of: "…", with: "")
        .replacingOccurrences(of: "(", with: "")
        .replacingOccurrences(of: ")", with: "")
        .replacingOccurrences(of: "/", with: " ")
        .replacingOccurrences(of: " - ", with: " ")
        .components(separatedBy: .whitespacesAndNewlines)
        .filter { !$0.isEmpty }
        .joined(separator: "_")
}

func generateAliases(_ desc: String, path: String) -> [String] {
    var aliases: [String] = []
    let lower = desc.lowercased()
    aliases.append(lower)

    let pathParts = path.components(separatedBy: " > ")
    if pathParts.count >= 2 {
        let menuName = pathParts[pathParts.count - 2].lowercased()
        if menuName != "apple" && menuName != lower {
            aliases.append("\(menuName) \(lower)")
        }
    }

    return aliases
}

// MARK: - Check permissions

func cmdCheckPermissions(_ args: [String]) {
    let pid = ProcessInfo.processInfo.processIdentifier
    let selfRef = AXUIElementCreateApplication(pid)

    var result: [String: Any] = [:]
    var testVal: AnyObject?
    let err = AXUIElementCopyAttributeValue(
        selfRef,
        kAXFocusedUIElementAttribute as CFString,
        &testVal
    )

    let hasAccessibility = err == .success || err == .noValue
    result["accessibility"] = hasAccessibility
    result["pid"] = pid
    result["process_name"] = ProcessInfo.processInfo.processName

    if !hasAccessibility {
        result["error"] = "Accessibility permission not granted"
        result["fix"] =
            "Open System Settings > Privacy & Security > Accessibility and add this binary"
    }

    if let data = try? JSONSerialization.data(
        withJSONObject: result,
        options: [.prettyPrinted, .sortedKeys]
    ) {
        print(String(data: data, encoding: .utf8) ?? "{}")
    }
}

// MARK: - Entry

main()
