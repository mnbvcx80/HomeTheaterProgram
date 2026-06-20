#!/usr/bin/env python3
import os
import time
import json
import subprocess
import argparse
import sys
import xml.etree.ElementTree as ET
import gi
gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib

CONFIG_DIR = os.path.expanduser("~/.config/hometheater")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
STATE_FILE = os.path.join(CONFIG_DIR, "state")
LOG_FILE = os.path.join(CONFIG_DIR, "daemon.log")

def log_msg(msg):
    print(msg)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except:
        pass

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_state(mode):
    try:
        with open(STATE_FILE, "w") as f:
            f.write(mode)
    except:
        pass

def get_saved_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return f.read().strip()
    return None

def apply_xml_layout(xml_path):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        # Find the first valid configuration
        config = root.find('configuration')
        
        logical_monitors = []
        for lm in config.findall('logicalmonitor'):
            x = int(lm.find('x').text)
            y = int(lm.find('y').text)
            scale = float(lm.find('scale').text)
            
            primary_elem = lm.find('primary')
            primary = (primary_elem is not None and primary_elem.text == 'yes')
            
            transform = 0
            if lm.find('transform') is not None:
                transform = int(lm.find('transform').text) # Often 0
                
            monitors = []
            for mon in lm.findall('monitor'):
                connector = mon.find('monitorspec/connector').text
                width = mon.find('mode/width').text
                height = mon.find('mode/height').text
                rate = float(mon.find('mode/rate').text)
                
                # Format to GNOME standard: 3840x2160@143.988
                mode_id = f"{width}x{height}@{rate:.3f}"
                
                props = {}
                if mon.find('colormode') is not None and mon.find('colormode').text == 'bt2100':
                    props['color-mode'] = GLib.Variant('u', 1)
                
                monitors.append((connector, mode_id, props))
                
            logical_monitors.append((x, y, scale, transform, primary, monitors))

        # Execute DBus injection
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        proxy = Gio.DBusProxy.new_sync(bus, Gio.DBusProxyFlags.NONE, None,
                                      'org.gnome.Mutter.DisplayConfig',
                                      '/org/gnome/Mutter/DisplayConfig',
                                      'org.gnome.Mutter.DisplayConfig', None)
        
        res = proxy.call_sync('GetCurrentState', None, Gio.DBusCallFlags.NONE, -1, None)
        serial = res.get_child_value(0).get_uint32()
        
        arg_serial = GLib.Variant('u', serial)
        arg_method = GLib.Variant('u', 1) 
        arg_logical_monitors = GLib.Variant('a(iiduba(ssa{sv}))', logical_monitors)
        arg_properties = GLib.Variant('a{sv}', {'layout-mode': GLib.Variant('u', 1)})

        params = GLib.Variant.new_tuple(arg_serial, arg_method, arg_logical_monitors, arg_properties)
        proxy.call_sync('ApplyMonitorsConfig', params, Gio.DBusCallFlags.NONE, -1, None)
        return True
    except Exception as e:
        log_msg(f"Failed to apply DBus config: {e}")
        return False

def set_audio_device(keyword):
    if not keyword: return
    for attempt in range(10):
        try:
            output = subprocess.check_output(["wpctl", "status"], text=True)
            in_sinks = False
            target_id = None
            for line in output.split('\n'):
                if "Sinks:" in line:
                    in_sinks = True
                    continue
                if in_sinks and not line.strip(): break
                if in_sinks and line.strip().startswith(("├", "└", "*", "│")):
                    parts = line.strip().replace("│", "").replace("├", "").replace("└", "").replace("*", "").strip().split()
                    if not parts: continue
                    try:
                        sink_id = parts[0].replace(".", "")
                        name = " ".join(parts[1:])
                        if keyword.lower() in name.lower():
                            target_id = sink_id
                            break
                    except: pass
            
            if target_id:
                log_msg(f"Switching audio to: {target_id} ({keyword})")
                subprocess.run(["wpctl", "set-default", target_id])
                return
        except Exception as e:
            log_msg(f"Error querying wpctl: {e}")
            
        time.sleep(1)
    log_msg(f"Audio device '{keyword}' not found.")

def toggle_audio():
    config = load_config()
    desk_audio = config.get("audio_desktop", "")
    tv_audio = config.get("audio_tv", "")
    try:
        output = subprocess.check_output(["wpctl", "status"], text=True)
        current_is_tv = False
        in_sinks = False
        for line in output.split('\n'):
            if "Sinks:" in line:
                in_sinks = True
            elif in_sinks and not line.strip():
                break
            elif in_sinks and line.strip().startswith("*"):
                if tv_audio and tv_audio.lower() in line.lower():
                    current_is_tv = True
                break
        
        if current_is_tv:
            set_audio_device(desk_audio)
        else:
            set_audio_device(tv_audio)
    except Exception as e:
        log_msg(f"Error toggling audio: {e}")

def set_mode(mode):
    config = load_config()
    xml_file = os.path.join(CONFIG_DIR, f"{mode}.xml")
    
    if os.path.exists(xml_file):
        log_msg(f"Applying display mode: {mode}")
        if apply_xml_layout(xml_file):
            save_state(mode)
            # Apply audio
            audio_key = config.get(f"audio_{mode}")
            set_audio_device(audio_key)
            
            # Note: Removed the experimental PowerSaveMode DBus "kick" because it
            # can cause the GNOME Mutter compositor to crash and log out the user.
    else:
        log_msg(f"Layout file for {mode} not found. Configure it in the GUI.")

def is_steam_bpm():
    try:
        output = subprocess.check_output("lsof -c steam | grep -i -E 'tenfoot|gamepadui'", shell=True, text=True)
        return bool(output.strip())
    except:
        pass
        
    try:
        root_props = subprocess.check_output(['xprop', '-root', '_NET_CLIENT_LIST'], text=True, stderr=subprocess.DEVNULL)
        if "_NET_CLIENT_LIST(WINDOW)" in root_props:
            window_ids = [w.strip() for w in root_props.split("window id # ")[1].strip().split(",")]
            for wid in window_ids:
                try:
                    win_info = subprocess.check_output(['xprop', '-id', wid, 'WM_NAME'], text=True, stderr=subprocess.DEVNULL)
                    if '"Steam Big Picture Mode"' in win_info: return True
                except: continue
    except:
        pass
    return False

def daemon_loop():
    config = load_config()
    if not config.get('enable_sniffer', True):
        log_msg("Sniffer disabled in config. Exiting.")
        return
        
    log_msg("Daemon started.")
    current_mode = get_saved_state() or "desktop"
    last_tick = time.time()
    
    while True:
        try:
            now = time.time()
            if now - last_tick > 10:
                log_msg("Woke up from sleep. Re-applying layout...")
                time.sleep(3)
                set_mode(current_mode)
            last_tick = now
            
            bpm_active = is_steam_bpm()
            if bpm_active and current_mode != "hometheater":
                set_mode("hometheater")
                current_mode = "hometheater"
            elif not bpm_active and current_mode == "hometheater":
                set_mode("desktop")
                current_mode = "desktop"
                
            time.sleep(config.get('interval', 3))
        except Exception as e:
            log_msg(f"Daemon error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--desktop", action="store_true")
    parser.add_argument("--hometheater", action="store_true")
    parser.add_argument("--toggle", action="store_true")
    parser.add_argument("--toggle-audio", action="store_true")
    args = parser.parse_args()
    
    if args.daemon: daemon_loop()
    elif args.desktop: set_mode("desktop")
    elif args.hometheater: set_mode("hometheater")
    elif args.toggle_audio: toggle_audio()
    elif args.toggle:
        m = get_saved_state()
        set_mode("desktop" if m == "hometheater" else "hometheater")
