namespace AppAutomate.Consumer;

public sealed class ShortcutDefinition
{
    public string Keys { get; set; } = "";
    public string Description { get; set; } = "";
    public string? Platform { get; set; }
}
