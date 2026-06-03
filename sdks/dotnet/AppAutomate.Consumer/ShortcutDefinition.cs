namespace AppAutomate.Consumer;

public sealed class ShortcutDefinition
{
    public string Keys { get; set; } = "";
    public string? KeysMacos { get; set; }
    public string? KeysLinux { get; set; }
    public string? KeysWindows { get; set; }
    public string Description { get; set; } = "";
    public string? Platform { get; set; }

    public string KeysForPlatform(string? platform = null)
    {
        var current = platform ?? Environment.OSVersion.Platform switch
        {
            PlatformID.MacOSX or PlatformID.Unix when System.Runtime.InteropServices.RuntimeInformation.IsOSPlatform(System.Runtime.InteropServices.OSPlatform.OSX) => "darwin",
            PlatformID.Unix => "linux",
            _ => "windows"
        };

        return current switch
        {
            "darwin" when KeysMacos != null => KeysMacos,
            "linux" when KeysLinux != null => KeysLinux,
            "windows" when KeysWindows != null => KeysWindows,
            _ => Keys
        };
    }
}
