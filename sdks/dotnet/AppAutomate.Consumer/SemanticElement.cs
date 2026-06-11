namespace AppAutomate.Consumer;

public sealed class SemanticElement
{
    public string Label { get; set; } = "";
    public List<string> Aliases { get; set; } = new();
    public string? Role { get; set; }
    public string? AutomationId { get; set; }
    public string? Selector { get; set; }
    public string Action { get; set; } = "click";
    public string? Hotkey { get; set; }
    public ShortcutDefinition? Shortcut { get; set; }
    public string? Text { get; set; }
    public int? ScrollClicks { get; set; }
    public double? DragDx { get; set; }
    public double? DragDy { get; set; }
    public int? WaitMs { get; set; }
}
