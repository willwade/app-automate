using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Windows.Automation;

namespace UiaTool;

class Program
{
    static void Main(string[] args)
    {
        if (args.Length == 0 || args[0] == "--help" || args[0] == "-h")
        {
            PrintUsage();
            return;
        }

        var command = args[0];
        var rest = args.Skip(1).ToArray();

        try
        {
            switch (command)
            {
                case "list": CmdList(rest); break;
                case "find": CmdFind(rest); break;
                case "click": CmdClick(rest); break;
                case "type": CmdType(rest); break;
                case "shortcuts": CmdShortcuts(rest); break;
                case "window-bounds": CmdWindowBounds(rest); break;
                case "activate": CmdActivate(rest); break;
                default: Fail($"Unknown command: {command}"); break;
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"Error: {ex.Message}");
            Environment.ExitCode = 1;
        }
    }

    static void PrintUsage()
    {
        Console.WriteLine(@"uia - Windows UI Automation CLI

Commands:
  list <app>              List UI elements for an app
  find <app> <text>       Find elements matching text
  click <app> <text>      Click element matching text
  type <app> <text> <msg> Type text into element
  shortcuts <app>         Extract accelerator keys
  window-bounds <app>     Get front window bounds
  activate <app>          Bring app to foreground

Options:
  --max-depth N           Max tree depth (default 15)
  --actionable            Only actionable elements
  --json                  JSON output");
    }

    static void Fail(string msg) { Console.Error.WriteLine(msg); Environment.ExitCode = 1; }

    static string ArgVal(string[] a, string n, string d = "")
    { for (int i = 0; i < a.Length - 1; i++) if (a[i] == $"--{n}") return a[i + 1]; return d; }
    static bool ArgFlag(string[] a, string n) => a.Contains($"--{n}");
    static string[] PosArgs(string[] a) => a.Where(x => !x.StartsWith("--")).ToArray();

    // --- Window finding ---

    static AutomationElement FindWindow(string appName)
    {
        var needle = appName.ToLowerInvariant();
        foreach (AutomationElement win in AutomationElement.RootElement.FindAll(
            TreeScope.Children, Condition.TrueCondition))
        {
            try
            {
                var pid = win.Current.ProcessId;
                var procName = "";
                try { procName = System.Diagnostics.Process.GetProcessById(pid).ProcessName; } catch { }
                string[] vals = [win.Current.Name ?? "", win.Current.ClassName ?? "",
                    win.Current.AutomationId ?? "", procName];
                if (vals.Any(v => !string.IsNullOrEmpty(v) && v.ToLowerInvariant().Contains(needle)))
                    return win;
            }
            catch { }
        }
        throw new Exception($"No window found for \"{appName}\"");
    }

    // --- Element model ---

    class El
    {
        public string path { get; set; } = "";
        public string class_name { get; set; } = "";
        public string? role { get; set; }
        public string? subrole { get; set; }
        public string label { get; set; } = "";
        public string? name { get; set; }
        public string? automation_id { get; set; }
        public string? accelerator_key { get; set; }
        public int? x { get; set; }
        public int? y { get; set; }
        public int? width { get; set; }
        public int? height { get; set; }
        public bool? enabled { get; set; }
        public int depth { get; set; }
        public int child_count { get; set; }
        public bool actionable { get; set; }
    }

    static readonly HashSet<string> Actionable = new(StringComparer.OrdinalIgnoreCase)
    { "button", "checkbox", "combobox", "edit", "hyperlink", "list item",
      "menu item", "radio button", "split button", "tab item", "tree item" };

    static El ToEl(AutomationElement e, string p, int d)
    {
        string n = "", cn = "", lt = "", ai = "", ht = "", ak = "";
        bool en = false; System.Windows.Rect r = default;
        try { n = e.Current.Name ?? ""; } catch { }
        try { cn = e.Current.ClassName ?? ""; } catch { }
        try { lt = e.Current.LocalizedControlType ?? ""; } catch { }
        try { ai = e.Current.AutomationId ?? ""; } catch { }
        try { ht = e.Current.HelpText ?? ""; } catch { }
        try { ak = e.Current.AcceleratorKey ?? ""; } catch { }
        try { en = e.Current.IsEnabled; } catch { }
        try { r = e.Current.BoundingRectangle; } catch { }

        var ctName = e.Current.ControlType.ToString();

        int? rx = null, ry = null, rw = null, rh = null;
        if (r.Width > 0 && r.Height > 0) { rx = (int)r.X; ry = (int)r.Y; rw = (int)r.Width; rh = (int)r.Height; }

        return new El
        {
            path = p, class_name = ctName, role = string.IsNullOrEmpty(lt) ? null : lt,
            subrole = string.IsNullOrEmpty(cn) ? null : cn,
            label = !string.IsNullOrEmpty(n) ? n : (!string.IsNullOrEmpty(ht) ? ht : ctName),
            name = string.IsNullOrEmpty(n) ? null : n,
            automation_id = string.IsNullOrEmpty(ai) ? null : ai,
            accelerator_key = string.IsNullOrEmpty(ak) ? null : ak,
            x = rx, y = ry, width = rw, height = rh, enabled = en, depth = d,
            child_count = 0, actionable = Actionable.Contains(lt)
        };
    }

    // --- Tree walk ---

    static List<El> Walk(AutomationElement root, string path, int depth, int maxDepth)
    {
        var result = new List<El>();
        if (depth > maxDepth) return result;
        var walker = TreeWalker.ControlViewWalker;
        AutomationElement child;
        try { child = walker.GetFirstChild(root); } catch { return result; }
        int idx = 1;
        while (child != null)
        {
            var cp = $"{path} > child[{idx}]";
            result.Add(ToEl(child, cp, depth));
            result.AddRange(Walk(child, cp, depth + 1, maxDepth));
            try { child = walker.GetNextSibling(child); } catch { break; }
            idx++;
        }
        return result;
    }

    static List<El> Collect(string app, int maxDepth, bool actOnly)
    {
        var win = FindWindow(app);
        var els = new List<El> { ToEl(win, "window[1]", 0) };
        els.AddRange(Walk(win, "window[1]", 1, maxDepth));
        if (actOnly) els = els.Where(e => e.actionable && e.x != null).ToList();
        foreach (var e in els) e.child_count = els.Count(o => o.path.StartsWith(e.path + " > "));
        return els;
    }

    static readonly JsonSerializerOptions JOpts = new()
    { WriteIndented = true, DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull };

    // --- Commands ---

    static void CmdList(string[] args)
    {
        var p = PosArgs(args);
        if (p.Length < 1) { Fail("Usage: uia list <app>"); return; }
        var maxD = int.TryParse(ArgVal(args, "max-depth", "15"), out var d) ? d : 15;
        var els = Collect(p[0], maxD, ArgFlag(args, "actionable"));
        if (ArgFlag(args, "json")) { Console.WriteLine(JsonSerializer.Serialize(els, JOpts)); return; }
        Console.WriteLine($"{els.Count} elements:");
        foreach (var e in els)
        {
            var lbl = (e.label ?? "").PadRight(30)[..Math.Min(30, (e.label??"").Length)];
            Console.WriteLine($"  {lbl,-30} {(e.role ?? ""),-18} {(e.x ?? 0),5} {(e.y ?? 0),5}");
        }
    }

    static void CmdFind(string[] args)
    {
        var p = PosArgs(args);
        if (p.Length < 2) { Fail("Usage: uia find <app> <text>"); return; }
        var els = Collect(p[0], 15, false);
        var needle = p[1].ToLowerInvariant();
        var matches = els.Where(e =>
            (e.label?.ToLowerInvariant().Contains(needle) == true) ||
            (e.name?.ToLowerInvariant().Contains(needle) == true) ||
            (e.automation_id?.ToLowerInvariant().Contains(needle) == true)).ToList();
        Console.WriteLine(JsonSerializer.Serialize(matches, JOpts));
    }

    static void CmdClick(string[] args)
    {
        var p = PosArgs(args);
        if (p.Length < 2) { Fail("Usage: uia click <app> <text>"); return; }
        var win = FindWindow(p[0]);
        var needle = p[1];

        var candidates = new List<(AutomationElement el, string name, bool exact)>();
        foreach (AutomationElement el in win.FindAll(TreeScope.Descendants, Condition.TrueCondition))
        {
            string name = "", autoId = "";
            try { name = el.Current.Name ?? ""; } catch { }
            try { autoId = el.Current.AutomationId ?? ""; } catch { }
            bool exactName = name.Equals(needle, StringComparison.OrdinalIgnoreCase);
            bool exactId = autoId.Equals(needle, StringComparison.OrdinalIgnoreCase);
            bool contains = name.Contains(needle, StringComparison.OrdinalIgnoreCase) ||
                autoId.Contains(needle, StringComparison.OrdinalIgnoreCase);
            if (exactName || exactId || contains)
                candidates.Add((el, name, exactName || exactId));
        }

        // Prefer exact matches, then take first
        var match = candidates.FirstOrDefault(c => c.exact);
        if (match.el == null) match = candidates.FirstOrDefault();
        if (match.el == null) { Fail($"No element found matching \"{needle}\""); return; }

        try
        {
            ((InvokePattern)match.el.GetCurrentPattern(InvokePattern.Pattern)).Invoke();
            Console.WriteLine($"Invoked: {match.name}"); return;
        }
        catch { }

        try
        {
            var r = match.el.Current.BoundingRectangle;
            if (r.Width > 0) { ClickAt((int)(r.X + r.Width / 2), (int)(r.Y + r.Height / 2)); Console.WriteLine($"Clicked: {match.name}"); return; }
        }
        catch { }
        Fail($"Could not click \"{needle}\"");
    }

    static void CmdType(string[] args)
    {
        var p = PosArgs(args);
        if (p.Length < 3) { Fail("Usage: uia type <app> <text> <message>"); return; }
        var win = FindWindow(p[0]);
        var needle = p[1];
        var msg = p[2];

        foreach (AutomationElement el in win.FindAll(TreeScope.Descendants, Condition.TrueCondition))
        {
            string name = "";
            try { name = el.Current.Name ?? ""; } catch { }
            if (!name.Contains(needle, StringComparison.OrdinalIgnoreCase)) continue;
            el.SetFocus();
            try { ((ValuePattern)el.GetCurrentPattern(ValuePattern.Pattern)).SetValue(msg); Console.WriteLine($"Set: {name}"); return; }
            catch { }
            SendText(msg);
            Console.WriteLine($"Typed into: {name}"); return;
        }
        Fail($"No element found matching \"{needle}\"");
    }

    static void CmdShortcuts(string[] args)
    {
        var p = PosArgs(args);
        if (p.Length < 1) { Fail("Usage: uia shortcuts <app>"); return; }
        var els = Collect(p[0], 15, false);
        var accels = els.Where(e => !string.IsNullOrEmpty(e.accelerator_key))
            .Select(e => new { e.label, e.accelerator_key, e.role, e.class_name }).ToList();
        Console.WriteLine(JsonSerializer.Serialize(accels, JOpts));
    }

    static void CmdWindowBounds(string[] args)
    {
        var p = PosArgs(args);
        if (p.Length < 1) { Fail("Usage: uia window-bounds <app>"); return; }
        var win = FindWindow(p[0]);
        var r = win.Current.BoundingRectangle;
        Console.WriteLine(JsonSerializer.Serialize(new { x = (int)r.X, y = (int)r.Y,
            width = (int)r.Width, height = (int)r.Height, title = win.Current.Name }, JOpts));
    }

    static void CmdActivate(string[] args)
    {
        var p = PosArgs(args);
        if (p.Length < 1) { Fail("Usage: uia activate <app>"); return; }
        var win = FindWindow(p[0]);
        win.SetFocus();
        Console.WriteLine($"Activated: {win.Current.Name}");
    }

    // --- Native input ---

    [DllImport("user32.dll")] static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] static extern void mouse_event(uint f, int dx, int dy, uint d, IntPtr ex);
    [DllImport("user32.dll")] static extern uint SendInput(uint n, INPUT[] i, int s);

    const uint MOUSEDOWN = 0x0002, MOUSEUP = 0x0004, KEY_UNICODE = 0x0004, KEY_UP = 0x0002;

    static void ClickAt(int x, int y)
    {
        SetCursorPos(x, y);
        mouse_event(MOUSEDOWN, 0, 0, 0, IntPtr.Zero);
        System.Threading.Thread.Sleep(10);
        mouse_event(MOUSEUP, 0, 0, 0, IntPtr.Zero);
    }

    static void SendText(string text)
    {
        foreach (char c in text)
        {
            var inp = new INPUT[2];
            inp[0].type = 1; inp[0].u.ki.wScan = (ushort)c; inp[0].u.ki.dwFlags = KEY_UNICODE;
            inp[1].type = 1; inp[1].u.ki.wScan = (ushort)c; inp[1].u.ki.dwFlags = KEY_UNICODE | KEY_UP;
            SendInput(2, inp, Marshal.SizeOf<INPUT>());
            System.Threading.Thread.Sleep(5);
        }
    }

    [StructLayout(LayoutKind.Sequential)] struct INPUT { public uint type; public U u; }
    [StructLayout(LayoutKind.Explicit)] struct U { [FieldOffset(0)] public KI ki; }
    [StructLayout(LayoutKind.Sequential)] struct KI { public ushort wVk; public ushort wScan; public uint dwFlags; public uint time; public IntPtr ex; }
}
