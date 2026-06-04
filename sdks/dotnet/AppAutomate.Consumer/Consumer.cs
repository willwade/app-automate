using System.Text.Json;

namespace AppAutomate.Consumer;

public interface IInputAdapter
{
    // Keyboard
    void SendShortcut(string keys);
    void TypeText(string text);
    void SendKey(string key);
    // Mouse
    void Click(double x, double y);
    void DoubleClick(double x, double y);
    void RightClick(double x, double y);
    void MoveMouse(double x, double y);
    void Drag(double x, double y, double dx, double dy);
    void Scroll(double x, double y, int clicks);
}

public sealed class Consumer
{
    private readonly Profile _profile;
    private readonly IInputAdapter? _adapter;

    public Consumer(Profile profile, IInputAdapter? adapter = null)
    {
        _profile = profile;
        _adapter = adapter;
    }

    public static Consumer FromFile(string path, IInputAdapter? adapter = null)
    {
        var resolved = path;
        if (Directory.Exists(path))
            resolved = Path.Combine(path, "profile.json");

        var json = File.ReadAllText(resolved);
        var profile = JsonSerializer.Deserialize<Profile>(json, new JsonSerializerOptions
        {
            PropertyNamePolicy = JsonNamingPolicy.SnakeCaseLower,
        }) ?? throw new ProfileLoadException("Failed to deserialize profile");

        return new Consumer(profile, adapter);
    }

    public static Consumer FromJson(string json, IInputAdapter? adapter = null)
    {
        var profile = JsonSerializer.Deserialize<Profile>(json, new JsonSerializerOptions
        {
            PropertyNamePolicy = JsonNamingPolicy.SnakeCaseLower,
        }) ?? throw new ProfileLoadException("Failed to deserialize profile");

        return new Consumer(profile, adapter);
    }

    public Profile Profile => _profile;
    public string AppName => _profile.AppName;
    public string ProfileId => _profile.ProfileId;

    public SemanticElement Resolve(string command)
    {
        var id = ResolveId(command);
        return _profile.SemanticElements[id];
    }

    public string ResolveId(string command)
    {
        var normalized = command.Trim().ToLowerInvariant();
        foreach (var (elementId, element) in _profile.SemanticElements)
        {
            var candidates = new List<string> { element.Label };
            candidates.AddRange(element.Aliases);
            candidates.Add(elementId);
            if (candidates.Any(c => c.ToLowerInvariant() == normalized))
                return elementId;
        }

        throw new ElementNotFoundException(command, ListCommands().Distinct().OrderBy(c => c).ToArray());
    }

    public string[] ListCommands()
    {
        var commands = new List<string>();
        foreach (var (id, element) in _profile.SemanticElements)
        {
            commands.Add(element.Label);
            commands.AddRange(element.Aliases);
            commands.Add(id);
        }
        return commands.ToArray();
    }

    public Dictionary<string, string> ListShortcuts()
    {
        return _profile.Shortcuts.ToDictionary(kvp => kvp.Key, kvp => kvp.Value.Keys);
    }

    public ExecuteResult Execute(string command, string? text = null, bool dryRun = false)
    {
        var elementId = ResolveId(command);
        var element = _profile.SemanticElements[elementId];

        if (dryRun)
            return new ExecuteResult { ElementId = elementId, Label = element.Label, Action = element.Action };

        if (element.Action == "shortcut" && element.Shortcut != null)
        {
            GetAdapter().SendShortcut(element.Shortcut.KeysForPlatform());
            return new ExecuteResult { ElementId = elementId, Label = element.Label, Action = "shortcut" };
        }

        if (element.Action == "hotkey" && element.Hotkey != null)
        {
            GetAdapter().SendShortcut(element.Hotkey);
            return new ExecuteResult { ElementId = elementId, Label = element.Label, Action = "hotkey" };
        }

        if (element.Action == "type")
        {
            var typeText = text ?? element.Text;
            if (typeText == null)
                throw new InvalidOperationException($"type action requires text for element '{element.Label}'");
            GetAdapter().TypeText(typeText);
            return new ExecuteResult { ElementId = elementId, Label = element.Label, Action = "type" };
        }

        if (element.Action == "wait")
        {
            Thread.Sleep(element.WaitMs ?? 500);
            return new ExecuteResult { ElementId = elementId, Label = element.Label, Action = "wait" };
        }

        var adapter = GetAdapter();
        switch (element.Action)
        {
            case "click":
                adapter.Click(0, 0);
                return new ExecuteResult { ElementId = elementId, Label = element.Label, Action = "click" };
            case "double_click":
                adapter.DoubleClick(0, 0);
                return new ExecuteResult { ElementId = elementId, Label = element.Label, Action = "double_click" };
            case "right_click":
                adapter.RightClick(0, 0);
                return new ExecuteResult { ElementId = elementId, Label = element.Label, Action = "right_click" };
            case "drag":
                adapter.Drag(0, 0, element.DragDx ?? 0, element.DragDy ?? 0);
                return new ExecuteResult { ElementId = elementId, Label = element.Label, Action = "drag" };
            case "scroll":
                adapter.Scroll(0, 0, element.ScrollClicks ?? 3);
                return new ExecuteResult { ElementId = elementId, Label = element.Label, Action = "scroll" };
        }

        throw new NotImplementedException(
            $"action '{element.Action}' is not supported by the consumer. " +
            "Supported: shortcut, hotkey, type, wait, click, double_click, " +
            "right_click, drag, scroll.");
    }

    private IInputAdapter GetAdapter()
    {
        if (_adapter != null)
            return _adapter;
        throw new InvalidOperationException(
            "No input adapter configured. Pass an IInputAdapter to the Consumer constructor.");
    }
}
