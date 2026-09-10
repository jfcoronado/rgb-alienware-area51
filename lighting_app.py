#!/usr/bin/env python3
"""Alienware Lights — one color across the laptop. GPL-3.0."""
import threading
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib
import lighting_service as service


class Lights(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='local.alienware.Lights')
        self.connect('activate', self.activate)
        self.window = None
        self.busy = False

    def activate(self, *_):
        if self.window:
            self.window.present()
            return
        css = Gtk.CssProvider()
        css.load_from_data(b'''
          window { background: #11131b; color: #f3f2fa; }
          .title { font-size: 30px; font-weight: 800; }
          .muted { color: #a5a8bd; }
          .preview { border-radius: 20px; min-height: 95px; }
          button { border-radius: 12px; padding: 12px 16px; }
          .apply { background: #8050df; color: white; font-weight: bold; }
          entry { padding: 12px; border-radius: 12px; }
        ''')
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, 600)
        self.window = Gtk.ApplicationWindow(application=self, title='Alienware Lights')
        self.window.connect('close-request', self.close_requested)
        self.window.set_default_size(480, 550)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        for side in ('top', 'bottom', 'start', 'end'):
            getattr(box, 'set_margin_' + side)(28)
        self.window.set_child(box)
        title = Gtk.Label(label='Alienware Lights', xalign=0)
        title.add_css_class('title')
        box.append(title)
        subtitle = Gtk.Label(label='One color. Your whole laptop.', xalign=0)
        subtitle.add_css_class('muted')
        box.append(subtitle)
        self.preview = Gtk.Box()
        self.preview.add_css_class('preview')
        self.preview_css = Gtk.CssProvider()
        self.preview.get_style_context().add_provider(self.preview_css, 800)
        box.append(self.preview)
        scope = Gtk.Label(label='Keyboard · Rear bar · Logo · Fans\nPower light · Trackpad', xalign=0)
        scope.add_css_class('muted')
        box.append(scope)
        row = Gtk.Box(spacing=10)
        self.entry = Gtk.Entry(placeholder_text='#8000FF', hexpand=True)
        self.entry.set_max_length(7)
        self.entry.set_tooltip_text('Six-digit hex color')
        self.entry.connect('changed', self.changed)
        self.entry.connect('activate', lambda *_: self.apply())
        row.append(self.entry)
        self.picker = Gtk.ColorButton(title='Choose a color for all lights')
        self.picker.set_use_alpha(False)
        self.picker.set_tooltip_text('Open color picker')
        self.picker.connect('color-set', self.picked)
        row.append(self.picker)
        box.append(row)
        presets = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=4,
                              min_children_per_line=4, row_spacing=6, column_spacing=6)
        for name, color in [('Purple','8000FF'),('Blue','0066FF'),('Cyan','00FFFF'),('Green','00FF40'),
                            ('Pink','FF0080'),('Red','FF0000'),('Amber','FF8000'),('White','FFFFFF')]:
            button = Gtk.Button(label=name)
            button.connect('clicked', lambda _, c=color: self.entry.set_text('#'+c))
            presets.append(button)
        box.append(presets)
        self.apply_button = Gtk.Button(label='Apply to all lights')
        self.apply_button.add_css_class('apply')
        self.apply_button.connect('clicked', lambda *_: self.apply())
        box.append(self.apply_button)
        self.off_button = Gtk.Button(label='Turn all lights off')
        self.off_button.connect('clicked', lambda *_: self.apply('000000'))
        box.append(self.off_button)
        self.status = Gtk.Label(xalign=0, wrap=True, selectable=True)
        box.append(self.status)
        self.access = Gtk.Button(label='Enable access')
        self.access.set_tooltip_text('Authorize temporary access to both lighting controllers')
        self.access.connect('clicked', lambda *_: self.job(service.enable_access, self.access_done))
        box.append(self.access)
        self.entry.set_text('#'+service.saved_color())
        self.check_access()
        self.window.present()

    def changed(self, *_):
        try:
            color = service.normalize_color(self.entry.get_text())
            self.preview_css.load_from_data(f'.preview {{ background: #{color}; }}'.encode())
            rgba = Gdk.RGBA()
            rgba.parse('#'+color)
            self.picker.set_rgba(rgba)
            self.apply_button.set_sensitive(not self.busy)
            self.status.set_text('Color selected. Click Apply to update the lights.')
        except ValueError:
            self.apply_button.set_sensitive(False)
            self.status.set_text('Enter a six-digit color, such as #8000FF.')

    def picked(self, *_):
        c = self.picker.get_rgba()
        self.entry.set_text('#' + ''.join(f'{round(x*255):02X}' for x in (c.red,c.green,c.blue)))

    def check_access(self):
        try:
            ready = all(d['accessible'] for d in service.devices())
            self.access.set_visible(not ready)
            self.status.set_text('Ready. Choose a color and click Apply.' if ready else
                                 'Enable access to control the lights. You may be asked for your password.')
        except Exception as exc:
            self.status.set_text(str(exc))
            self.access.set_visible(False)

    def job(self, work, done):
        if self.busy:
            return
        self.busy = True
        for widget in (self.apply_button,self.off_button,self.access):
            widget.set_sensitive(False)
        self.status.set_text('Working…')
        def worker():
            try:
                result, error = work(), None
            except Exception as exc:
                result, error = None, exc
            GLib.idle_add(finish, result, error)
        def finish(result, error):
            self.busy = False
            for widget in (self.off_button,self.access):
                widget.set_sensitive(True)
            self.changed()
            if error:
                self.status.set_text(str(error))
                if isinstance(error, PermissionError):
                    self.access.set_visible(True)
            else:
                done(result)
            return False
        threading.Thread(target=worker, daemon=True).start()

    def access_done(self, _):
        self.check_access()

    def close_requested(self, *_):
        if self.busy:
            self.status.set_text('Please wait for the current operation to finish before closing.')
        return self.busy

    def apply(self, override=None):
        if self.busy:
            return
        try:
            color = service.normalize_color(override or self.entry.get_text())
        except ValueError as exc:
            self.status.set_text(str(exc))
            return
        def done(_):
            message = 'Off command sent to all lights.' if color == '000000' else f'Applied #{color} to all lights.'
            if color != '000000':
                try:
                    service.save_color(color)
                except OSError:
                    message += ' Could not remember this color for next time.'
            self.status.set_text(message)
        self.job(lambda: service.apply_color(color), done)


if __name__ == '__main__':
    Lights().run()
