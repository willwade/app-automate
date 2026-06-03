using System.Text.Json;

namespace AppAutomate.Consumer;

public sealed class ProfileLoadException : Exception
{
    public ProfileLoadException(string message) : base(message) { }
    public ProfileLoadException(string message, Exception inner) : base(message, inner) { }
}

public sealed class ElementNotFoundException : Exception
{
    public string Command { get; }
    public string[] AvailableCommands { get; }

    public ElementNotFoundException(string command, string[] available)
        : base($"No element matches command: '{command}'. Available: {string.Join(", ", available)}")
    {
        Command = command;
        AvailableCommands = available;
    }
}
