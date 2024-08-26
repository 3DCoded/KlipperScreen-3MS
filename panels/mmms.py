import logging
import re
import gi # type: ignore # noqa: E402, F401
import copy # noqa: E402, F401

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango # type: ignore # noqa: E402, F401
from ks_includes.KlippyGcodes import KlippyGcodes # noqa: E402, F401
from ks_includes.screen_panel import ScreenPanel # noqa: E402, F401
from ks_includes.widgets.autogrid import AutoGrid # noqa: E402, F401
from ks_includes.KlippyGtk import find_widget # noqa: E402, F401


class Panel(ScreenPanel):

    def __init__(self, screen, title):
        title = '3MS Control'
        super().__init__(screen, title)
        self.current_extruder = self._printer.get_stat("toolhead", "extruder")
        macros = self._printer.get_config_section_list("gcode_macro ")

        conf = self._printer.get_config_section("gcode_macro MMMS_SETTINGS")
        self.config_tools = int(conf.get('variable_num_tools', 2))

        self.load_filament = any("LOAD_FILAMENT" in macro.upper() for macro in macros)
        self.unload_filament = any("UNLOAD_FILAMENT" in macro.upper() for macro in macros)

        self.tools = list(map(str, range(self.config_tools)))
        self.speeds = ['5', '10', '50', '100', '150']
        self.distances = ['5', '10', '50', '100', '200']
        if self.ks_printer_cfg is not None:
            dis = self.ks_printer_cfg.get("extrude_distances", '')
            if re.match(r'^[0-9,\s]+$', dis):
                dis = [str(i.strip()) for i in dis.split(',')]
                if 1 < len(dis) < 5:
                    self.distances = dis
            vel = self.ks_printer_cfg.get("extrude_speeds", '')
            if re.match(r'^[0-9,\s]+$', vel):
                vel = [str(i.strip()) for i in vel.split(',')]
                if 1 < len(vel) < 5:
                    self.tools = vel
        self.speed = int(self.speeds[1])
        self.distance = int(self.distances[1])
        self.selected_tool = int(self.tools[1])
        self.buttons = {
            'extrude': self._gtk.Button("extrude", _("Extrude"), "color4"),
            'load': self._gtk.Button("arrow-down", _("Load"), "color3"),
            'unload': self._gtk.Button("arrow-up", _("Unload"), "color2"),
            'retract': self._gtk.Button("retract", _("Retract"), "color1"),
            'temperature': self._gtk.Button("heat-up", _("Temperature"), "color4"),
            'settings': self._gtk.Button('settings', 'Settings', "color1"),
            'clear_tool': self._gtk.Button('delete', 'Clear Tool', "color3"),
            '3ms_load': self._gtk.Button('arrow-down', "3MS Load", "color1"),
            '3ms_unload': self._gtk.Button('arrow-up', "3MS Unload", "color4")
        }
        self.buttons['extrude'].connect("clicked", self.check_min_temp, "extrude", "+")
        self.buttons['load'].connect("clicked", self.check_min_temp, "load_unload", "+")
        self.buttons['unload'].connect("clicked", self.check_min_temp, "load_unload", "-")
        self.buttons['3ms_load'].connect("clicked", self.check_min_temp, "load_unload", "3+")
        self.buttons['3ms_unload'].connect("clicked", self.check_min_temp, "load_unload", "3-")
        self.buttons['retract'].connect("clicked", self.check_min_temp, "extrude", "-")
        self.buttons['temperature'].connect("clicked", self.menu_item_clicked, {
            "panel": "temperature"
        })
        self.buttons['settings'].connect("clicked", self.menu_item_clicked, {
            "panel": "mmms_settings"
        })
        self.buttons['clear_tool'].connect("clicked", self.clear_tool)

        xbox = Gtk.Box(homogeneous=True)
        limit = 4
        i = 0
        self.labels = {}

        xbox.add(self.buttons['settings'])
        if not self._screen.vertical_mode:
            xbox.add(self.buttons['clear_tool'])
        xbox.add(self.buttons['temperature'])

        speedgrid = Gtk.Grid()
        for j, i in enumerate(self.speeds):
            self.labels[f"speed{i}"] = self._gtk.Button(label=i)
            self.labels[f"speed{i}"].connect("clicked", self.change_speed, int(i))
            ctx = self.labels[f"speed{i}"].get_style_context()
            ctx.add_class("horizontal_togglebuttons")
            if self._screen.vertical_mode:
                ctx.add_class("horizontal_togglebuttons_smaller")
            if int(i) == self.distance:
                ctx.add_class("horizontal_togglebuttons_active")
            speedgrid.attach(self.labels[f"speed{i}"], j, 0, 1, 1)

        distgrid = Gtk.Grid()
        for j, i in enumerate(self.distances):
            self.labels[f"dist{i}"] = self._gtk.Button(label=i)
            self.labels[f"dist{i}"].connect("clicked", self.change_distance, int(i))
            ctx = self.labels[f"dist{i}"].get_style_context()
            ctx.add_class("horizontal_togglebuttons")
            if self._screen.vertical_mode:
                ctx.add_class("horizontal_togglebuttons_smaller")
            if int(i) == self.distance:
                ctx.add_class("horizontal_togglebuttons_active")
            distgrid.attach(self.labels[f"dist{i}"], j, 0, 1, 1)

        selectgrid = Gtk.Grid()
        for j, i in enumerate(self.tools):
            self.labels[f"tool{i}"] = self._gtk.Button(label=i)
            self.labels[f"tool{i}"].connect("clicked", self.change_selected_tool, int(i))
            ctx = self.labels[f"tool{i}"].get_style_context()
            ctx.add_class("horizontal_togglebuttons")
            if self._screen.vertical_mode:
                ctx.add_class("horizontal_togglebuttons_smaller")
            if int(i) == self.selected_tool:
                ctx.add_class("horizontal_togglebuttons_active")
            selectgrid.attach(self.labels[f"tool{i}"], j, 0, 1, 1)

        speedbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.labels['extrude_speed'] = Gtk.Label('Speed (mm/s)')
        speedbox.pack_start(self.labels['extrude_speed'], True, True, 0)
        speedbox.add(speedgrid)
        distbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.labels['extrude_dist'] = Gtk.Label(_("Distance (mm)"))
        distbox.pack_start(self.labels['extrude_dist'], True, True, 0)
        distbox.add(distgrid)
        selectbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.labels['tool_selection'] = Gtk.Label(_("Select Tool"))
        selectbox.pack_start(self.labels['tool_selection'], True, True, 0)
        selectbox.add(selectgrid)

        filament_sensors = self._printer.get_filament_sensors()
        sensors = Gtk.Grid(valign=Gtk.Align.CENTER, row_spacing=5, column_spacing=5)

        self.labels['status'] = Gtk.Label("Loading Status...")
        sensors.attach(self.labels['status'], 0, 0, 1, 1)

        with_switches = (
            len(filament_sensors) < 4
            and not (self._screen.vertical_mode and self._screen.height < 600)
        )
        for s, x in enumerate(filament_sensors):
            if s > 8:
                break
            name = x.split(" ", 1)[1].strip()
            self.labels[x] = {
                'label': Gtk.Label(
                    label=self.prettify(name), hexpand=True, halign=Gtk.Align.CENTER,
                    ellipsize=Pango.EllipsizeMode.START),
                'box': Gtk.Box()
            }
            self.labels[x]['box'].pack_start(self.labels[x]['label'], True, True, 10)
            if with_switches:
                self.labels[x]['switch'] = Gtk.Switch()
                self.labels[x]['switch'].connect("notify::active", self.enable_disable_fs, name, x)
                self.labels[x]['box'].pack_start(self.labels[x]['switch'], False, False, 0)

            self.labels[x]['box'].get_style_context().add_class("filament_sensor")
            if s // 2:
                self.labels[x]['box'].get_style_context().add_class("filament_sensor_detected")
            else:
                self.labels[x]['box'].get_style_context().add_class("filament_sensor_empty")
            sensors.attach(self.labels[x]['box'], s, 1, 1, 1)

        grid = Gtk.Grid(column_homogeneous=True)
        grid.attach(xbox, 0, 0, 4, 1)

        if self._screen.vertical_mode:
            grid.attach(self.buttons['extrude'], 0, 1, 2, 1)
            grid.attach(self.buttons['retract'], 2, 1, 2, 1)
            grid.attach(self.buttons['load'], 0, 2, 2, 1)
            grid.attach(self.buttons['unload'], 2, 2, 2, 1)
            settings_box = Gtk.Box(homogeneous=True)
            grid.attach(settings_box, 0, 3, 4, 1)
            grid.attach(distbox, 0, 4, 4, 1)
            grid.attach(selectbox, 0, 5, 4, 1)
            grid.attach(sensors, 0, 6, 4, 1)
        else:
            grid.attach(self.buttons['extrude'], 0, 2, 1, 1)
            grid.attach(self.buttons['load'], 1, 2, 1, 1)
            grid.attach(self.buttons['unload'], 2, 2, 1, 1)
            grid.attach(self.buttons['retract'], 3, 2, 1, 1)
            grid.attach(self.buttons['3ms_load'], 0, 3, 2, 1)
            grid.attach(self.buttons['3ms_unload'], 2, 3, 2, 1)
            grid.attach(distbox, 0, 4, 2, 1)
            grid.attach(selectbox, 2, 4, 2, 1)
            grid.attach(speedbox, 0, 5, 2, 1)
            grid.attach(sensors, 2, 5, 2, 1)
        
        self.grid = grid

        self.menu = ['extrude_menu']
        self.labels['extrude_menu'] = grid

        scroll = self._gtk.ScrolledWindow()
        scroll.add(self.labels['extrude_menu'])

        self.content.add(scroll)
        self.content.show_all()

    def enable_buttons(self, enable):
        for button in self.buttons:
            if button in ("pressure", "retraction", "spoolman", "temperature", "settings", "clear_tool", "desync_all", "sync", "status"):
                continue
            self.buttons[button].set_sensitive(enable)

    def activate(self):
        self.enable_buttons(self._printer.state in ("ready", "paused"))
    
    def set_status(self, new_synced, new_tool):
        status = f'Current Tool: T{new_tool}' if new_tool > -1 else 'No Tool Loaded'
        self.labels['status'].set_label(status)

        self.change_selected_tool(None, new_synced)
    
    def clear_tool(self, widget):
        self._screen.show_popup_message('Clearing Tool', 1)
        self._screen._send_action(widget, "printer.gcode.script",
                                        {"script": "CLEAR_TOOL"})

    def process_update(self, action, data):
        if action == "notify_status_update" and "save_variables" in data:
            save_variables = data['save_variables']['variables']
            if 'synced' in save_variables and 'p' in save_variables:
                self.set_status(save_variables['synced'], save_variables['p'])
            else:
                logging.info(f'3MS: Save variables: {save_variables}')
            
        if action == "notify_gcode_response":
            if "action:cancel" in data or "action:paused" in data:
                self.enable_buttons(True)
            elif "action:resumed" in data:
                self.enable_buttons(False)
            return
        if action != "notify_status_update":
            return
        if "current_extruder" in self.labels:
            self.labels["current_extruder"].set_label(self.labels[self.current_extruder].get_label())

        if ("toolhead" in data and "extruder" in data["toolhead"] and
                data["toolhead"]["extruder"] != self.current_extruder):
            for extruder in self._printer.get_tools():
                self.labels[extruder].get_style_context().remove_class("button_active")
            self.current_extruder = data["toolhead"]["extruder"]
            self.labels[self.current_extruder].get_style_context().add_class("button_active")
            if "current_extruder" in self.labels:
                n = self._printer.get_tool_number(self.current_extruder)
                self.labels["current_extruder"].set_image(self._gtk.Image(f"extruder-{n}"))

        for x in self._printer.get_filament_sensors():
            if x in data and x in self.labels:
                if 'enabled' in data[x] and 'switch' in self.labels[x]:
                    self.labels[x]['switch'].set_active(data[x]['enabled'])
                if 'filament_detected' in data[x] and self._printer.get_stat(x, "enabled"):
                    if data[x]['filament_detected']:
                        self.labels[x]['box'].get_style_context().remove_class("filament_sensor_empty")
                        self.labels[x]['box'].get_style_context().add_class("filament_sensor_detected")
                    else:
                        self.labels[x]['box'].get_style_context().remove_class("filament_sensor_detected")
                        self.labels[x]['box'].get_style_context().add_class("filament_sensor_empty")

    def change_distance(self, widget, distance):
        logging.info(f"### Distance {distance}")
        self.labels[f"dist{self.distance}"].get_style_context().remove_class("horizontal_togglebuttons_active")
        self.labels[f"dist{distance}"].get_style_context().add_class("horizontal_togglebuttons_active")
        self.distance = distance
    
    def change_speed(self, widget, speed):
        logging.info(f"### Speed {speed}")
        self.labels[f"speed{self.speed}"].get_style_context().remove_class("horizontal_togglebuttons_active")
        self.labels[f"speed{speed}"].get_style_context().add_class("horizontal_togglebuttons_active")
        self.speed = speed

    def change_extruder(self, widget, extruder):
        logging.info(f"Changing extruder to {extruder}")
        for tool in self._printer.get_tools():
            self.labels[tool].get_style_context().remove_class("button_active")
        self.labels[extruder].get_style_context().add_class("button_active")
        self._screen._send_action(widget, "printer.gcode.script",
                                  {"script": f"T{self._printer.get_tool_number(extruder)}"})

    def change_selected_tool(self, widget, selected):
        logging.info(f"### Selected Tool {selected}")

        if selected == self.selected_tool and widget is None:
            return
        
        self.labels[f"tool{self.selected_tool}"].get_style_context().remove_class("horizontal_togglebuttons_active")
        if selected == -1:
            return
        self.labels[f"tool{selected}"].get_style_context().add_class("horizontal_togglebuttons_active")

        if widget is not None:
            if selected == self.selected_tool:
                self._screen._send_action(widget, "printer.gcode.script", {"script": f"DESYNC_TOOL TOOL={selected}"})
            else:
                self._screen._send_action(widget, "printer.gcode.script", {"script": f"SYNC_TOOL TOOL={selected}"})

        self.selected_tool = selected

    def check_min_temp(self, widget, method, direction):
        temp = float(self._printer.get_stat(self.current_extruder, 'temperature'))
        target = float(self._printer.get_stat(self.current_extruder, 'target'))
        min_extrude_temp = float(self._printer.config[self.current_extruder].get('min_extrude_temp', 170))
        if temp < min_extrude_temp:
            if target > min_extrude_temp:
                self._screen._send_action(
                    widget, "printer.gcode.script",
                    {"script": f"M109 S{target}"}
                )
        if method == "extrude":
            self.extrude(widget, direction)
        elif method == "load_unload":
            self.load_unload(widget, direction)

    def extrude(self, widget, direction):
        self._screen._ws.klippy.gcode_script(KlippyGcodes.EXTRUDE_REL)
        self._screen._send_action(widget, "printer.gcode.script",
                                  {"script": f"G1 E{direction}{self.distance} F{self.speed * 60}"})

    def load_unload(self, widget, direction):
        if direction == "-":
            self._screen._send_action(widget, "printer.gcode.script",
                                        {"script": "UNLOAD_FILAMENT"})
        if direction == "+":
            self._screen._send_action(widget, "printer.gcode.script",
                                        {"script": "LOAD_FILAMENT"})
        if direction == "3+":
            self._screen._send_action(widget, "printer.gcode.script",
                                        {"script": "MMMS_LOAD"})
        if direction == "3-":
            self._screen._send_action(widget, "printer.gcode.script",
                                        {"script": "MMMS_UNLOAD"})

    def enable_disable_fs(self, switch, gparams, name, x):
        if switch.get_active():
            self._screen._ws.klippy.gcode_script(f"SET_FILAMENT_SENSOR SENSOR={name} ENABLE=1")
            if self._printer.get_stat(x, "filament_detected"):
                self.labels[x]['box'].get_style_context().add_class("filament_sensor_detected")
            else:
                self.labels[x]['box'].get_style_context().add_class("filament_sensor_empty")
        else:
            self._screen._ws.klippy.gcode_script(f"SET_FILAMENT_SENSOR SENSOR={name} ENABLE=0")
            self.labels[x]['box'].get_style_context().remove_class("filament_sensor_empty")
            self.labels[x]['box'].get_style_context().remove_class("filament_sensor_detected")