# AppAutomate.Consumer (.NET)

A thin .NET SDK for loading and executing [app-automate](https://github.com/Smartbox-Assistive-Technology/app-automate) profiles.

## Install

```bash
dotnet add package AppAutomate.Consumer
```

## Usage

```csharp
using AppAutomate.Consumer;

// Load a profile
var consumer = Consumer.FromFile("profiles/firefox/profile.json");

// List available commands
foreach (var cmd in consumer.ListCommands().Distinct())
    Console.WriteLine(cmd);

// Execute a keyboard shortcut (requires IInputAdapter)
var adapter = new YourPlatformAdapter();
var firefox = Consumer.FromFile("profiles/firefox", adapter);

firefox.Execute("new tab");      // sends Ctrl+T
firefox.Execute("url bar");      // sends Ctrl+L
adapter.TypeText("https://example.com");
adapter.SendKey("enter");
```

## IInputAdapter

Implement `IInputAdapter` for your platform:

```csharp
public interface IInputAdapter
{
    void SendShortcut(string keys);  // e.g. "ctrl+t", "alt+left", "f5"
    void TypeText(string text);
    void SendKey(string key);
}
```

### Windows example

```csharp
using WindowsInput;
using WindowsInput.Native;

public sealed class WindowsAdapter : IInputAdapter
{
    private readonly InputSimulator _sim = new();

    public void SendShortcut(string keys)
    {
        var parts = keys.Split('+');
        _sim.Keyboard.ModifiedKeyStroke(
            parts[..^1].Select(ParseKey),
            ParseKey(parts[^1])
        );
    }

    public void TypeText(string text) => _sim.Keyboard.TextEntry(text);
    public void SendKey(string key) => _sim.Keyboard.KeyPress(ParseKey(key));

    private static VirtualKeyCode ParseKey(string key) => key.ToLower() switch
    {
        "ctrl" => VirtualKeyCode.LCONTROL,
        "alt" => VirtualKeyCode.LMENU,
        "shift" => VirtualKeyCode.LSHIFT,
        "enter" => VirtualKeyCode.RETURN,
        "tab" => VirtualKeyCode.TAB,
        "escape" => VirtualKeyCode.ESCAPE,
        "f5" => VirtualKeyCode.F5,
        // ... etc
        _ => (VirtualKeyCode)char.ToUpper(key[0])
    };
}
```

## Running Tests

```bash
cd sdks/dotnet
dotnet test
```
