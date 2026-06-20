#!/usr/bin/env bash
set -e

echo "Uninstalling Home Theater Switcher..."

# 1. Stop and disable the background service
if systemctl --user list-unit-files | grep -q "hometheater-daemon.service"; then
    echo "Stopping and disabling background service..."
    systemctl --user stop hometheater-daemon.service || true
    systemctl --user disable hometheater-daemon.service || true
fi

# 2. Remove systemd service
echo "Removing systemd service file..."
rm -f "$HOME/.config/systemd/user/hometheater-daemon.service"
systemctl --user daemon-reload

# 3. Remove CLI commands (symlinks)
echo "Removing executable commands..."
rm -f "$HOME/.local/bin/hometheater"
rm -f "$HOME/.local/bin/hometheater-gui"

# 4. Remove GNOME App Launcher
echo "Removing application launcher..."
rm -f "$HOME/.local/share/applications/hometheater.desktop"

# 5. Remove Application Source Files
echo "Removing installation directory..."
rm -rf "$HOME/.local/share/hometheater"

# 6. Remove Configurations and saved layouts
echo "Removing configuration directory..."
rm -rf "$HOME/.config/hometheater"

# 7. Remove GNOME Custom Shortcuts from dconf registry
echo "Removing GNOME custom shortcuts..."
dconf reset -f /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom_ht_mode/ 2>/dev/null || true
dconf reset -f /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom_ht_audio/ 2>/dev/null || true

# Note: We leave the references in the 'custom-keybindings' array as removing them safely in bash is tricky and leaving dead paths is completely harmless to GNOME.

echo "--------------------------------------------------------"
echo "Uninstallation Complete!"
echo "All files, services, app icons, and configurations have been successfully removed."
echo "--------------------------------------------------------"
