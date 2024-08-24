import logging
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):

    def __init__(self, screen, title):
        title = "3MS Settings"
        super().__init__(screen, title)
        self.options = None
        self.grid = Gtk.Grid()
        self.values = {}
        self.list = {}
        conf = self._printer.get_config_section("gcode_macro MMMS_SETTINGS")

        load_distance = float(conf['variable_load_distance']) if 'variable_load_distance' in conf else 110
        load_speed = int(float((conf['variable_load_speed']))) if 'variable_load_speed' in conf else 4500
        unload_distance = float(conf['variable_unload_distance']) if 'variable_unload_distance' in conf else 100
        unload_speed = int(float((conf['variable_unload_speed']))) if 'variable_unload_speed' in conf else 6000
        maxlength = load_distance * 1.2 if load_distance >= 6 else 6
        maxspeed = load_speed * 1.2 if load_speed >= 100 else 100

        self.options = [
            {"name": _("Load Distance"),
             "units": _("mm"),
             "option": "load_distance",
             "value": load_distance,
             "digits": 0,
             "maxval": maxlength},
            {"name": _("Load Speed"),
             "units": _("mm/s"),
             "option": "load_speed",
             "value": load_speed,
             "digits": 0,
             "maxval": maxspeed},
            {"name": _("Unload Distance"),
             "units": _("mm"),
             "option": "unload_distance",
             "value": unload_distance,
             "digits": 0,
             "maxval": maxlength},
            {"name": _("Unload Speed"),
             "units": _("mm/s"),
             "option": "unload_speed",
             "value": unload_speed,
             "digits": 0,
             "maxval": maxspeed}
        ]

        for opt in self.options:
            self.add_option(opt['option'], opt['name'], opt['units'], opt['value'], opt['digits'], opt["maxval"])

        self.reload_btn = self._gtk.Button("refresh", "Reload", "color1")
        self.reload_btn.connect("clicked", self.reload)
        self.grid.attach(self.reload_btn, 0, len(self.options)+1, 1, 1)

        scroll = self._gtk.ScrolledWindow()
        scroll.add(self.grid)

        self.content.add(scroll)
        self.content.show_all()

    def reload(self):
        self._screen.init_klipper()
        self._screen.show_popup_message('Reloading', 1)
        settings = self._printer.get_stat('gcode_macro MMMS_SETTINGS')
        self.update_option('load_distance', settings['load_distance'])
        self.update_option('load_speed', settings['load_speed'])
        self.update_option('unload_distance', settings['unload_distance'])
        self.update_option('unload_speed', settings['unload_speed'])
        self._screen.show_popup_message('Reloaded', 1)

    def process_update(self, action, data):
        if action == "notify_status_update" and "gcode_macro MMMS_SETTINGS" in data:
            for opt in self.list:
                if opt in data["gcode_macro MMMS_SETTINGS"]:
                    self.update_option(opt, data["gcode_macro MMMS_SETTINGS"][opt])

    def update_option(self, option, value):
        if option not in self.list:
            return

        if self.list[option]['scale'].has_grab():
            return

        self.values[option] = float(value)
        # Infinite scale
        for opt in self.options:
            if opt['option'] == option:
                if self.values[option] > opt["maxval"] * .75:
                    self.list[option]['adjustment'].set_upper(self.values[option] * 1.5)
                else:
                    self.list[option]['adjustment'].set_upper(opt["maxval"])
                break
        self.list[option]['scale'].set_value(self.values[option])
        self.list[option]['scale'].disconnect_by_func(self.set_opt_value)
        self.list[option]['scale'].connect("button-release-event", self.set_opt_value, option)

    def add_option(self, option, optname, units, value, digits, maxval):
        logging.info(f"Adding option: {option}")

        name = Gtk.Label(
            hexpand=True, vexpand=True, halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
        name.set_markup(f"<big><b>{optname}</b></big> ({units})")
        minimum = 1 if option in ["load_speed", "unload_speed"] else 0
        self.values[option] = value
        # adj (value, lower, upper, step_increment, page_increment, page_size)
        adj = Gtk.Adjustment(value, minimum, maxval, 1, 5, 0)
        scale = Gtk.Scale(adjustment=adj, digits=digits, hexpand=True,
                          has_origin=True)
        scale.get_style_context().add_class("option_slider")
        scale.connect("button-release-event", self.set_opt_value, option)

        reset = self._gtk.Button("refresh", style="color1")
        reset.connect("clicked", self.reset_value, option)
        reset.set_hexpand(False)

        item = Gtk.Grid()
        item.attach(name, 0, 0, 2, 1)
        item.attach(scale, 0, 1, 1, 1)
        item.attach(reset, 1, 1, 1, 1)

        self.list[option] = {
            "row": item,
            "scale": scale,
            "adjustment": adj,
        }

        pos = sorted(self.list).index(option)
        self.grid.attach(self.list[option]['row'], 0, pos, 1, 1)
        self.grid.show_all()

    def reset_value(self, widget, option):
        for x in self.options:
            if x["option"] == option:
                self.update_option(option, x["value"])
        self.set_opt_value(None, None, option)

    def set_opt_value(self, widget, event, opt):
        value = self.list[opt]['scale'].get_value()
        cmd = f'SET_MMMS_SETTINGS {opt}={value}'
        self._screen._ws.klippy.gcode_script(cmd)