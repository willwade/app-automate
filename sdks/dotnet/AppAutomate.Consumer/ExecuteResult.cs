namespace AppAutomate.Consumer;

public sealed class ExecuteResult
{
    public string ElementId { get; init; } = "";
    public string Label { get; init; } = "";
    public string Action { get; init; } = "";
    public double? X { get; init; }
    public double? Y { get; init; }
}
