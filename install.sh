#!/usr/bin/env bash
set -e

echo "Installing Home Theater Switcher..."

# Define directories
INSTALL_DIR="$HOME/.local/share/hometheater"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
SYSTEMD_DIR="$HOME/.config/systemd/user"

# Create directories
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"
mkdir -p "$APP_DIR"
mkdir -p "$SYSTEMD_DIR"
mkdir -p "$HOME/.config/hometheater"

# Copy python source files
echo "Copying source files..."
cp src/backend.py "$INSTALL_DIR/"
cp src/gui.py "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/backend.py"
chmod +x "$INSTALL_DIR/gui.py"

# Create CLI symlinks
echo "Creating terminal commands..."
ln -sf "$INSTALL_DIR/backend.py" "$BIN_DIR/hometheater"
ln -sf "$INSTALL_DIR/gui.py" "$BIN_DIR/hometheater-gui"

# Create the Desktop entry for GUI
echo "Creating application launcher..."
cat <<DESKTOP > "$APP_DIR/hometheater.desktop"
[Desktop Entry]
Name=Home Theater Switcher
Comment=Configure displays and audio for Steam Big Picture
Exec=$INSTALL_DIR/gui.py
Icon=preferences-desktop-display
Terminal=false
Type=Application
Categories=Settings;HardwareSettings;
DESKTOP

# Create Systemd User Service for the background sniffer
echo "Creating background service..."
cat <<SERVICE > "$SYSTEMD_DIR/hometheater-daemon.service"
[Unit]
Description=Home Theater Steam Big Picture Sniffer
After=graphical-session.target

[Service]
ExecStart=$INSTALL_DIR/backend.py --daemon
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
SERVICE

# Reload systemd
systemctl --user daemon-reload

echo "--------------------------------------------------------"
echo "Installation Complete!"
echo ""
echo "1. You can now launch 'Home Theater Switcher' from your GNOME App Grid."
echo "2. Use the GUI to start/kill the background sniffer."
echo "3. CLI commands available: 'hometheater --toggle' or 'hometheater-gui'"
echo "--------------------------------------------------------"
