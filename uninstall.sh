#!/bin/bash
set -euo pipefail

if (( EUID == 0 )); then
  echo "Run this uninstaller as your normal desktop user, without sudo." >&2
  exit 1
fi

data_home=${XDG_DATA_HOME:-"$HOME/.local/share"}
state_dir=${XDG_STATE_HOME:-"$HOME/.local/state"}/alienware-lights
install_dir="$data_home/alienware-lights"
marker="$install_dir/.managed-by-alienware-lights"
bundled_rule="$install_dir/70-alienware-lights.rules"

if [[ -d "$install_dir" && ! -f "$marker" ]]; then
  echo "$install_dir was not created by this installer; refusing to remove it." >&2
  exit 1
fi

rm -f "$HOME/.config/omarchy/hooks/theme-set.d/90-alienware-lights"
rm -f "$HOME/.config/omarchy/hooks/post-boot.d/90-alienware-lights"
rule=/etc/udev/rules.d/70-alienware-lights.rules
if [[ -e "$rule" ]]; then
  if [[ -f "$bundled_rule" ]] && cmp -s "$rule" "$bundled_rule"; then
    echo "Administrator access is needed to remove the controller-access rule."
    sudo rm -f -- "$rule"
    sudo udevadm control --reload-rules
  else
    echo "Leaving $rule in place because it no longer matches this installation." >&2
  fi
fi

rm -f "$HOME/.local/bin/alienlights"
rm -f "$HOME/.local/bin/alienware-lights-gui"
rm -f "$HOME/.local/bin/alienlights-theme-sync"
rm -f "$HOME/.local/bin/alienlights-uninstall"
rm -f "$data_home/applications/alienware-lights.desktop"
if [[ -f "$marker" ]]; then
  rm -rf -- "$install_dir"
fi
rm -f "$state_dir/state.json"
rmdir "$state_dir" 2>/dev/null || true

if command -v update-desktop-database >/dev/null; then
  update-desktop-database "$data_home/applications" >/dev/null 2>&1 || true
fi
echo "Alienware Lights removed. Current LED colors remain until changed or reset."
