#!/bin/bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./install.sh [--no-udev] [--no-sync]

Install or update Alienware Lights for the current user.
  --no-udev  Skip the persistent controller-access rule.
  --no-sync  Do not immediately apply the current Omarchy theme.
EOF
}

install_udev=1
sync_now=1
while (( $# )); do
  case "$1" in
    --no-udev) install_udev=0 ;;
    --no-sync) sync_now=0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

if (( EUID == 0 )); then
  echo "Run this installer as your normal desktop user, without sudo." >&2
  exit 1
fi

source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
data_home=${XDG_DATA_HOME:-"$HOME/.local/share"}
install_dir="$data_home/alienware-lights"
bin_dir="$HOME/.local/bin"
applications_dir="$data_home/applications"
state_dir=${XDG_STATE_HOME:-"$HOME/.local/state"}/alienware-lights
marker="$install_dir/.managed-by-alienware-lights"

for command in python omarchy install; do
  command -v "$command" >/dev/null || { echo "Missing required command: $command" >&2; exit 1; }
done
for command in dbus-monitor systemctl; do
  command -v "$command" >/dev/null || { echo "Missing required command: $command" >&2; exit 1; }
done
if (( install_udev )) && ! command -v sudo >/dev/null; then
  echo "Missing sudo; rerun with --no-udev or install the device rule manually." >&2
  exit 1
fi

python - <<'PY'
import ctypes.util
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
if not ctypes.util.find_library('hidapi-hidraw'):
    raise SystemExit('Missing hidapi-hidraw library')
PY

if [[ -e "$install_dir" && ! -f "$marker" ]]; then
  echo "$install_dir exists but was not created by this installer; refusing to overwrite it." >&2
  exit 1
fi

for hook in "$HOME/.config/omarchy/hooks/theme-set.d/90-alienware-lights" \
            "$HOME/.config/omarchy/hooks/post-boot.d/90-alienware-lights"; do
  if [[ -f "$hook" ]] && ! grep -q 'alienware-lights' "$hook"; then
    echo "$hook exists and belongs to another customization; refusing to overwrite it." >&2
    exit 1
  fi
done
resume_unit="$HOME/.config/systemd/user/alienware-lights-resume.service"
if [[ -f "$resume_unit" ]] && ! grep -q 'Restore Alienware lighting after resume' "$resume_unit"; then
  echo "$resume_unit belongs to another customization; refusing to overwrite it." >&2
  exit 1
fi

install -d -m 0755 "$install_dir" "$bin_dir" "$applications_dir" "$state_dir"
if [[ ! -f "$state_dir/state.json" && -f "$source_dir/.last-color.json" ]]; then
  install -m 0644 "$source_dir/.last-color.json" "$state_dir/state.json"
fi
install -m 0644 "$source_dir/LICENSE" "$source_dir/README.md" \
  "$source_dir/SOURCES.md" "$source_dir/lighting-map.json" \
  "$source_dir/VERSION" "$source_dir/omarchy/70-alienware-lights.rules" "$install_dir/"
install -m 0644 "$source_dir/alienrgb.py" "$source_dir/keyboard_test.py" \
  "$source_dir/lighting_service.py" "$source_dir/lighting_cli.py" \
  "$source_dir/lighting_app.py" "$source_dir/theme_sync.py" "$install_dir/"
install -m 0755 "$source_dir/uninstall.sh" "$install_dir/uninstall.sh"
install -m 0755 "$source_dir/omarchy/alienware-lights-resume" \
  "$install_dir/alienware-lights-resume"
printf '%s\n' 'Installed by Alienware Lights. Safe to update with install.sh.' >"$marker"

cat >"$bin_dir/alienlights" <<'EOF'
#!/bin/bash
# Managed by Alienware Lights installer.
exec /usr/bin/python "${XDG_DATA_HOME:-$HOME/.local/share}/alienware-lights/lighting_cli.py" "$@"
EOF
cat >"$bin_dir/alienware-lights-gui" <<'EOF'
#!/bin/bash
# Managed by Alienware Lights installer.
exec /usr/bin/python "${XDG_DATA_HOME:-$HOME/.local/share}/alienware-lights/lighting_app.py" "$@"
EOF
cat >"$bin_dir/alienlights-theme-sync" <<'EOF'
#!/bin/bash
# Managed by Alienware Lights installer.
exec /usr/bin/python "${XDG_DATA_HOME:-$HOME/.local/share}/alienware-lights/theme_sync.py" "$@"
EOF
cat >"$bin_dir/alienlights-uninstall" <<'EOF'
#!/bin/bash
# Managed by Alienware Lights installer.
exec "${XDG_DATA_HOME:-$HOME/.local/share}/alienware-lights/uninstall.sh" "$@"
EOF
cat >"$bin_dir/alienlights-resume-monitor" <<'EOF'
#!/bin/bash
# Managed by Alienware Lights installer.
exec "${XDG_DATA_HOME:-$HOME/.local/share}/alienware-lights/alienware-lights-resume" "$@"
EOF
chmod 0755 "$bin_dir/alienlights" "$bin_dir/alienware-lights-gui" \
  "$bin_dir/alienlights-theme-sync" "$bin_dir/alienlights-uninstall" \
  "$bin_dir/alienlights-resume-monitor"

install -m 0644 "$source_dir/Alienware Lights.desktop" \
  "$applications_dir/alienware-lights.desktop"

omarchy hook install theme-set "$source_dir/omarchy/90-alienware-lights"
omarchy hook install post-boot "$source_dir/omarchy/90-alienware-lights"
install -d -m 0755 "$HOME/.config/systemd/user"
install -m 0644 "$source_dir/omarchy/alienware-lights-resume.service" "$resume_unit"
systemctl --user daemon-reload
systemctl --user enable --now alienware-lights-resume.service

if (( install_udev )); then
  echo "Administrator access is needed once to install the controller-access rule."
  sudo /usr/bin/bash "$source_dir/omarchy/install-device-access" \
    "$source_dir/omarchy/70-alienware-lights.rules"
fi

if command -v update-desktop-database >/dev/null; then
  update-desktop-database "$applications_dir" >/dev/null 2>&1 || true
fi

if (( sync_now )); then
  if "$bin_dir/alienlights" theme; then
    echo "Current Omarchy theme applied."
  else
    echo "Installed successfully, but the current theme could not be applied yet." >&2
    echo "Run: alienlights status" >&2
  fi
fi

echo "Alienware Lights installed. Commands: alienlights --help"
