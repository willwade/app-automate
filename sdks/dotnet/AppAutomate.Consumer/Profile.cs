namespace AppAutomate.Consumer;

public sealed class Profile
{
    public string ProfileId { get; set; } = "";
    public string AppName { get; set; } = "";
    public string Type { get; set; } = "semantic";
    public string? Backend { get; set; }
    public string? PlatformHint { get; set; }
    public string Notes { get; set; } = "";
    public Dictionary<string, SemanticElement> SemanticElements { get; set; } = new();
    public Dictionary<string, ShortcutDefinition> Shortcuts { get; set; } = new();
}
