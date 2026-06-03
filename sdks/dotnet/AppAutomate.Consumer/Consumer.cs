using System.Text.Json;

namespace AppAutomate.Consumer;

public interface IInputAdapter
{
    void SendShortcut(string keys);
    void TypeText(string text);
    void SendKey(string key);
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

        throw new NotImplementedException(
            $"action '{element.Action}' requires a platform-specific backend. " +
            "Use shortcut-based elements for cross-platform consumer usage.");
    }

    private IInputAdapter GetAdapter()
    {
        if (_adapter != null)
            return _adapter;
        throw new InvalidOperationException(
            "No input adapter configured. Pass an IInputAdapter to the Consumer constructor.");
    }
}
