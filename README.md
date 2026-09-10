# Alienware Lights for Omarchy

Alienware Lights sets one color across the Alienware 16 Area-51 AA16250 and
automatically follows the selected Omarchy theme. It controls the rear light
bar, lid logo, fan lights, power button, RGB trackpad, and whole keyboard.

This project was tested on one AA16250 with these USB controllers:

- Alienware AW-ELC `187c:0551`
- Dell/Alienware keyboard `0d62:1bbc`

The app checks the laptop model and controller descriptors before writing.

## Install or update

Clone the project and run its installer as your normal desktop user:

```sh
git clone git@github.com:jfcoronado/rgb-alienware-area51.git
cd rgb-alienware-area51
./install.sh
```

If you prefer HTTPS, clone
`https://github.com/jfcoronado/rgb-alienware-area51.git` instead.

Run the same command again to update an existing installation. The installer:

1. Copies the application to `~/.local/share/alienware-lights`.
2. Adds the `alienlights` command and graphical launcher.
3. Installs Omarchy `theme-set` and `post-boot` user hooks.
4. Requests administrator access once to install a device rule for the two RGB
   controllers.
5. Applies the current Omarchy theme color.

Run the installer as your normal desktop user. Do not prefix it with `sudo`.
It uses `sudo` only for the device rule and asks for your password there. Use
`./install.sh --no-udev` when the rule is managed separately, or `--no-sync`
to install without changing the current lights.

Requirements are checked before installation: Python 3, GTK 4/PyGObject,
hidapi-hidraw, Omarchy, `install`, and `sudo` unless `--no-udev` is used. The
required components are already present on the laptop used to build this.

## Use

The graphical app appears as **Alienware Lights** in the application launcher.
It offers presets, a custom picker, one Apply button, and an off button.

The CLI accepts named colors or six-digit RGB values:

```sh
alienlights set purple
alienlights set '#FF0080'
alienlights off
alienlights on
alienlights status
alienlights colors
```

`on` restores the last nonblack color selected in either interface. `off`
preserves that saved color. Use `--dry-run` with `set`, `on`, or `off` to preview
the operation. `alienlights status --json` produces machine-readable status.
The controller does not provide a reliable current-color readback, so status
shows the saved color and labels it accordingly.
The remembered color is stored in `~/.local/state/alienware-lights/state.json`.

If `alienlights` is not found immediately after installation, open a new
terminal or run `~/.local/bin/alienlights`.

## Omarchy theme synchronization

When Omarchy changes themes, Alienware Lights reads `keyboard.rgb` from the
staged theme. If that file is missing or invalid, it uses `accent` from
`colors.toml`. Every confirmed light receives that color. The same sync runs
after the desktop starts.

```sh
alienlights theme --dry-run
alienlights theme
journalctl -t alienware-lights -n 20 --no-pager
```

The integration uses Omarchy's supported user hooks:

- `~/.config/omarchy/hooks/theme-set.d/90-alienware-lights`
- `~/.config/omarchy/hooks/post-boot.d/90-alienware-lights`

It does not modify `/usr/share/omarchy`, run a continuous background service,
or save a startup effect into the laptop firmware. Theme and manual operations
share a lock so their hardware reports cannot interleave.

To pause automatic synchronization, create
`~/.config/omarchy/alienware-lights.json` containing:

```json
{"enabled": false}
```

Change it to `true` to resume. An explicit `alienlights theme` still applies the
theme color while automatic synchronization is paused. A manual color remains
until the next theme change or login when automatic sync is enabled.

## Controller access

The installer adds `/etc/udev/rules.d/70-alienware-lights.rules`. It grants the
active local desktop user access only to the two tested controllers through
`uaccess`; it does not make them world-writable.

If the persistent rule was skipped and access is lost after a reboot, run:

```sh
alienlights access
```

This opens the system administrator prompt and grants temporary access to the
currently verified device nodes.

## Remove

```sh
alienlights-uninstall
```

The uninstaller removes the app, launchers, and the two managed Omarchy hooks.
It asks for administrator access to remove the device rule only when that file
still matches this installation. It leaves changed or unrelated rule files
alone. Current LED colors remain until another command or hardware reset changes
them. The uninstaller also removes the locally remembered color.

## Troubleshooting

`alienlights status` should list both controllers as accessible. If a theme
change does not reach the lights, inspect the hook log shown above and run
`alienlights theme` manually. A mid-operation disconnect can leave some devices
on the previous color; retrying the command safely sends the requested color to
all devices again.

Colors may look slightly different between the keyboard and diffused chassis
lighting even when they receive identical RGB values. Restart persistence should
be verified after the first installation because the original prototype used
temporary ACLs before the device rule was added.

## Development and provenance

Run the test suite from the source directory:

```sh
python -m unittest -q
```

[lighting-map.json](lighting-map.json) records the visually verified hardware
mapping. [SOURCES.md](SOURCES.md) documents the AlienFX protocol sources and
adaptations. The project is licensed under GPL-3.0; see [LICENSE](LICENSE).
