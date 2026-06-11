using System.Text.Json;
using AppAutomate.Consumer;
using Xunit;

public class ConsumerTests
{
    private const string FirefoxJson = """
    {
        "profile_id": "firefox",
        "app_name": "Firefox",
        "type": "semantic",
        "backend": "atspi",
        "platform_hint": "linux",
        "shortcuts": {
            "new_tab": {"keys": "ctrl+t", "description": "Open new tab"},
            "quit": {"keys": "ctrl+q", "description": "Quit Firefox"}
        },
        "semantic_elements": {
            "new_tab_shortcut": {
                "label": "new_tab",
                "aliases": ["open tab", "new tab"],
                "action": "shortcut",
                "shortcut": {"keys": "ctrl+t", "description": "Open new tab"}
            },
            "url_bar_shortcut": {
                "label": "url_bar",
                "aliases": ["address bar", "url", "navigate"],
                "action": "shortcut",
                "shortcut": {"keys": "ctrl+l", "description": "Focus URL bar"}
            }
        }
    }
    """;

    [Fact]
    public void FromJson_LoadsProfile()
    {
        var consumer = Consumer.FromJson(FirefoxJson);
        Assert.Equal("firefox", consumer.ProfileId);
        Assert.Equal("Firefox", consumer.AppName);
    }

    [Fact]
    public void Resolve_FindsByLabel()
    {
        var consumer = Consumer.FromJson(FirefoxJson);
        var el = consumer.Resolve("url_bar");
        Assert.Equal("shortcut", el.Action);
        Assert.NotNull(el.Shortcut);
        Assert.Equal("ctrl+l", el.Shortcut.Keys);
    }

    [Fact]
    public void Resolve_FindsByAlias()
    {
        var consumer = Consumer.FromJson(FirefoxJson);
        var el = consumer.Resolve("address bar");
        Assert.NotNull(el.Shortcut);
    }

    [Fact]
    public void Resolve_CaseInsensitive()
    {
        var consumer = Consumer.FromJson(FirefoxJson);
        var el = consumer.Resolve("URL_BAR");
        Assert.NotNull(el.Shortcut);
    }

    [Fact]
    public void Resolve_NotFound_Throws()
    {
        var consumer = Consumer.FromJson(FirefoxJson);
        var ex = Assert.Throws<ElementNotFoundException>(() => consumer.Resolve("nonexistent"));
        Assert.Equal("nonexistent", ex.Command);
    }

    [Fact]
    public void ListCommands_ReturnsAll()
    {
        var consumer = Consumer.FromJson(FirefoxJson);
        var cmds = consumer.ListCommands();
        Assert.Contains("new_tab", cmds);
        Assert.Contains("open tab", cmds);
        Assert.Contains("new tab", cmds);
    }

    [Fact]
    public void ListShortcuts_ReturnsAll()
    {
        var consumer = Consumer.FromJson(FirefoxJson);
        var shortcuts = consumer.ListShortcuts();
        Assert.Equal("ctrl+t", shortcuts["new_tab"]);
        Assert.Equal("ctrl+q", shortcuts["quit"]);
    }

    [Fact]
    public void Execute_DryRun_ReturnsResult()
    {
        var consumer = Consumer.FromJson(FirefoxJson);
        var result = consumer.Execute("new tab", dryRun: true);
        Assert.Equal("new_tab_shortcut", result.ElementId);
        Assert.Equal("shortcut", result.Action);
    }

    [Fact]
    public void Execute_Shortcut_CallsAdapter()
    {
        var mockAdapter = new MockInputAdapter();
        var consumer = Consumer.FromJson(FirefoxJson, mockAdapter);
        var result = consumer.Execute("new tab");
        Assert.Equal("ctrl+t", mockAdapter.LastShortcut);
        Assert.Equal("shortcut", result.Action);
    }

    [Fact]
    public void Execute_Type_RequiresText()
    {
        var json = """
        {
            "profile_id": "test",
            "app_name": "Test",
            "type": "semantic",
            "backend": "shortcut",
            "semantic_elements": {
                "field": {"label": "field", "action": "type"}
            }
        }
        """;
        var consumer = Consumer.FromJson(json, new MockInputAdapter());
        Assert.Throws<InvalidOperationException>(() => consumer.Execute("field"));
    }

    [Fact]
    public void Execute_Type_UsesProvidedText()
    {
        var json = """
        {
            "profile_id": "test",
            "app_name": "Test",
            "type": "semantic",
            "backend": "shortcut",
            "semantic_elements": {
                "field": {"label": "field", "action": "type"}
            }
        }
        """;
        var mock = new MockInputAdapter();
        var consumer = Consumer.FromJson(json, mock);
        consumer.Execute("field", text: "hello");
        Assert.Equal("hello", mock.LastTypedText);
    }
}

file sealed class MockInputAdapter : IInputAdapter
{
    public string? LastShortcut { get; private set; }
    public string? LastTypedText { get; private set; }

    public void SendShortcut(string keys) => LastShortcut = keys;
    public void TypeText(string text) => LastTypedText = text;
    public void SendKey(string key) => LastShortcut = key;
}
