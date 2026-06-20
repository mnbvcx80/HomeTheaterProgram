#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
import json
import os
import subprocess
import shutil

CONFIG_DIR = os.path.expanduser("~/.config/hometheater")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

def get_audio_sinks():
    try:
        output = subprocess.check_output(["wpctl", "status"], text=True)
        sinks = []
        in_sinks = False
        for line in output.split('\n'):
            if "Sinks:" in line: in_sinks = True; continue
            if in_sinks and not line.strip(): break
            if in_sinks and line.strip().startswith(("├", "└", "*", "│")):
                parts = line.strip().replace("│", "").replace("├", "").replace("└", "").replace("*", "").strip().split()
                if not parts: continue
                try:
                    sinks.append(" ".join(parts[1:]))
                except: pass
        return sinks
    except: return []

class AppWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Home Theater Switcher")
        self.set_border_width(10)
        self.set_default_size(450, 450)
        
        self.config = {"audio_desktop": "", "audio_tv": "", "enable_sniffer": True, "interval": 3}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                self.config.update(json.load(f))
                
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(vbox)
        
        # Audio Section
        audio_frame = Gtk.Frame(label="Audio Devices")
        vbox.pack_start(audio_frame, False, False, 0)
        
        grid = Gtk.Grid(column_spacing=10, row_spacing=10, margin=10)
        audio_frame.add(grid)
        
        sinks = get_audio_sinks()
        
        grid.attach(Gtk.Label(label="Desktop Audio:"), 0, 0, 1, 1)
        self.combo_desk = Gtk.ComboBoxText.new_with_entry()
        for s in sinks: self.combo_desk.append_text(s)
        self.combo_desk.get_child().set_text(self.config['audio_desktop'])
        grid.attach(self.combo_desk, 1, 0, 1, 1)
        
        grid.attach(Gtk.Label(label="TV Audio:"), 0, 1, 1, 1)
        self.combo_tv = Gtk.ComboBoxText.new_with_entry()
        for s in sinks: self.combo_tv.append_text(s)
        self.combo_tv.get_child().set_text(self.config['audio_tv'])
        grid.attach(self.combo_tv, 1, 1, 1, 1)
        
        # Displays Section
        disp_frame = Gtk.Frame(label="Display Layouts")
        vbox.pack_start(disp_frame, False, False, 0)
        
        d_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=10)
        disp_frame.add(d_box)
        
        btn_desk = Gtk.Button(label="Save Current Displays as DESKTOP")
        btn_desk.connect("clicked", self.on_save_desktop)
        d_box.pack_start(btn_desk, False, False, 0)
        
        btn_tv = Gtk.Button(label="Save Current Displays as HOME THEATER")
        btn_tv.connect("clicked", self.on_save_tv)
        d_box.pack_start(btn_tv, False, False, 0)
        
        # Hotkeys Section
        hotkey_frame = Gtk.Frame(label="GNOME Shortcuts")
        vbox.pack_start(hotkey_frame, False, False, 0)
        
        hk_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=10)
        hotkey_frame.add(hk_box)
        
        lbl_hk = Gtk.Label(label="Set custom GNOME keybinds for manual toggling.\nMake sure to enter a valid GNOME shortcut (e.g. <Super>P)")
        lbl_hk.set_justify(Gtk.Justification.CENTER)
        hk_box.pack_start(lbl_hk, False, False, 0)
        
        hk_grid = Gtk.Grid(column_spacing=10, row_spacing=10)
        hk_box.pack_start(hk_grid, False, False, 0)
        
        hk_grid.attach(Gtk.Label(label="Toggle Mode:"), 0, 0, 1, 1)
        self.entry_hk_mode = Gtk.Entry()
        self.entry_hk_mode.set_text(self.config.get("hk_mode", "<Super>F11"))
        hk_grid.attach(self.entry_hk_mode, 1, 0, 1, 1)
        
        hk_grid.attach(Gtk.Label(label="Toggle Audio:"), 0, 1, 1, 1)
        self.entry_hk_audio = Gtk.Entry()
        self.entry_hk_audio.set_text(self.config.get("hk_audio", "<Super>F12"))
        hk_grid.attach(self.entry_hk_audio, 1, 1, 1, 1)
        
        btn_apply_hk = Gtk.Button(label="Apply Shortcuts to GNOME")
        btn_apply_hk.connect("clicked", self.on_apply_hotkeys)
        hk_box.pack_start(btn_apply_hk, False, False, 0)
        daemon_frame = Gtk.Frame(label="Sniffer Service (Background)")
        vbox.pack_start(daemon_frame, False, False, 0)
        
        daemon_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=10)
        daemon_frame.add(daemon_box)
        
        self.lbl_status = Gtk.Label(label="Status: Checking...")
        daemon_box.pack_start(self.lbl_status, False, False, 0)
        
        db_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        daemon_box.pack_start(db_box, False, False, 0)
        
        btn_start = Gtk.Button(label="Start Sniffer")
        btn_start.connect("clicked", self.on_start_daemon)
        db_box.pack_start(btn_start, True, True, 0)
        
        btn_stop = Gtk.Button(label="Kill Sniffer")
        btn_stop.connect("clicked", self.on_stop_daemon)
        db_box.pack_start(btn_stop, True, True, 0)
        
        # Save Button
        save_btn = Gtk.Button(label="Save Configuration")
        save_btn.connect("clicked", self.on_save_all)
        vbox.pack_end(save_btn, False, False, 0)

        # Timer to update daemon status
        GLib.timeout_add_seconds(2, self.update_daemon_status)
        self.update_daemon_status()

    def update_daemon_status(self):
        try:
            # We must use 'is-active' but also catch the non-zero exit code if it's inactive
            result = subprocess.run(
                ["systemctl", "--user", "is-active", "hometheater-daemon.service"], 
                capture_output=True, 
                text=True,
                check=False
            )
            status = result.stdout.strip()
            
            if status == "active":
                self.lbl_status.set_markup("Status: <span foreground='green'><b>Running in Background</b></span>")
            else:
                self.lbl_status.set_markup("Status: <span foreground='red'><b>Stopped</b></span>")
        except Exception as e:
            self.lbl_status.set_markup("Status: <b>Error checking service</b>")
        return True # Keep repeating

    def on_start_daemon(self, button):
        subprocess.run(["systemctl", "--user", "enable", "--now", "hometheater-daemon.service"])
        self.update_daemon_status()

    def on_stop_daemon(self, button):
        subprocess.run(["systemctl", "--user", "stop", "hometheater-daemon.service"])
        # Failsafe: kill any orphaned manual sniffer processes just in case
        subprocess.run(["pkill", "-f", "backend.py --daemon"])
        subprocess.run(["pkill", "-f", "hometheater.py --sniff"])
        self.update_daemon_status()

    def on_apply_hotkeys(self, button):
        # GNOME is case-sensitive for modifiers. Convert <CTRL> to <Ctrl>
        mode_hk = self.entry_hk_mode.get_text().replace("<CTRL>", "<Ctrl>").replace("<ALT>", "<Alt>").replace("<SHIFT>", "<Shift>")
        audio_hk = self.entry_hk_audio.get_text().replace("<CTRL>", "<Ctrl>").replace("<ALT>", "<Alt>").replace("<SHIFT>", "<Shift>")
        
        self.config['hk_mode'] = mode_hk
        self.config['hk_audio'] = audio_hk
        
        # GNOME uses a dconf array for custom keybindings. 
        # We define our two paths
        path_mode = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom_ht_mode/"
        path_audio = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom_ht_audio/"
        
        # Build the new bindings list
        new_bindings = f"['{path_mode}', '{path_audio}']"
        
        # Use absolute path to the backend script so it works universally in GNOME shortcuts
        backend_path = os.path.expanduser("~/.local/share/hometheater/backend.py")
        
        commands = [
            # Add to the global custom-keybindings list
            f"gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings \"{new_bindings}\"",
            
            # Configure Mode Toggle
            f"gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:{path_mode} name 'HT Toggle Mode'",
            f"gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:{path_mode} command '{backend_path} --toggle'",
            f"gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:{path_mode} binding '{mode_hk}'",
            
            # Configure Audio Toggle
            f"gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:{path_audio} name 'HT Toggle Audio'",
            f"gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:{path_audio} command '{backend_path} --toggle-audio'",
            f"gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:{path_audio} binding '{audio_hk}'"
        ]
        
        try:
            for cmd in commands:
                os.system(cmd)
            self.show_dialog("GNOME Shortcuts applied successfully!")
        except Exception as e:
            self.show_dialog(f"Failed to apply shortcuts: {e}")

    def on_save_desktop(self, button):
        src = os.path.expanduser("~/.config/monitors.xml")
        dest = os.path.join(CONFIG_DIR, "desktop.xml")
        if os.path.exists(src):
            shutil.copy(src, dest)
            self.show_dialog("Desktop layout saved!")
        else:
            self.show_dialog("Error: ~/.config/monitors.xml not found")

    def on_save_tv(self, button):
        src = os.path.expanduser("~/.config/monitors.xml")
        dest = os.path.join(CONFIG_DIR, "hometheater.xml")
        if os.path.exists(src):
            shutil.copy(src, dest)
            self.show_dialog("Home Theater layout saved!")
        else:
            self.show_dialog("Error: ~/.config/monitors.xml not found")

    def on_save_all(self, button):
        self.config['audio_desktop'] = self.combo_desk.get_child().get_text()
        self.config['audio_tv'] = self.combo_tv.get_child().get_text()
        # We don't strictly need 'enable_sniffer' in config anymore since systemd manages it, but we keep it for legacy
        
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=4)
        self.show_dialog("Configuration saved successfully!")

    def show_dialog(self, message):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=message,
        )
        dialog.run()
        dialog.destroy()

if __name__ == "__main__":
    os.makedirs(CONFIG_DIR, exist_ok=True)
    win = AppWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
