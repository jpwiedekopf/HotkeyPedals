#!/usr/bin/env python
# encoding: utf-8
import threading
import npyscreen
import serial
from serial.tools import list_ports
from apscheduler.schedulers.background import BackgroundScheduler
from pynput.keyboard import Key, KeyCode, Controller
from enum import Enum


class SerialReader:
    scheduler = None
    job = None

    def __init__(self, serial, callback, interval=0.1):
        self.active = True
        self.interval = interval
        self.serial = serial
        self.data = None
        self.callback = callback

    def start(self):
        self.scheduler = BackgroundScheduler()
        self.job = self.scheduler.add_job(self.test, 'interval', seconds=self.interval)
        self.scheduler.start()

    def pause(self):
        self.scheduler.pause()

    def resume(self):
        self.scheduler.resume()

    def test(self):
        n_in = self.serial.in_waiting
        if n_in > 0:
            self.data = self.serial.read()
            if self.data is not None and len(self.data) > 0:
                self.callback(self.data)

    def stop(self):
        self.scheduler.remove_all_jobs()
        self.scheduler.shutdown()


class PedalModel:
    comport = None
    serial = None

    left_trigger = None
    left_modifiers = []
    left_key = None

    right_trigger = None
    right_modifiers = []
    right_key = None

    read_thread = None
    history_callback = None
    keyboard = Controller()

    def __init__(self, history_callback=None, action_callback=None, key_error_callback=None):
        self.history_callback = history_callback
        self.action_callback = action_callback
        self.key_error_callback = key_error_callback

    def update_trigger(self, what, value):
        if len(value.strip()) > 1:
            self.key_error_callback(what, value)
        if what is SetupForm.action_widgets.LT:
            self.left_trigger = value.strip()
        else:
            self.right_trigger = value.strip()

    def update_modifiers(self, what, value):
        if len(value) == 0:
            assign_mod = []
        else:
            names = list([SetupForm.modifiers_names[i] for i in value])
            assign_mod = list([SetupForm.modifiers[n] for n in names])
        if what is SetupForm.action_widgets.LM:
            self.left_modifiers = assign_mod
        else:
            self.right_modifiers = assign_mod

    def update_key(self, what, value):
        if len(value.strip()) > 1:
            self.key_error_callback(what, value)
        else:
            key = KeyCode.from_char(value[0])
            if what is SetupForm.action_widgets.LK:
                self.left_key = key
            else:
                self.right_key = key

    def process_message(self, message):
        s = message.decode("ascii")[0]
        self.serial_reader.pause()
        self.fire_action(s)
        if self.history_callback is not None:
            self.history_callback(s)
        self.serial_reader.resume()

    def fire_action(self, message):
        if message == self.left_trigger:
            key = self.left_key
            modifiers = self.left_modifiers
            fired = "left"
        elif message == self.right_trigger:
            key = self.right_key
            modifiers = self.right_modifiers
            fired = "right"
        else:
            return
        sequence = self.press_key_sequence(key, modifiers)
        if self.action_callback is not None:
            self.action_callback(fired, sequence)

    def open(self):
        if self.comport is not None:
            self.serial = serial.Serial(self.comport)
            self.serial_reader = SerialReader(self.serial, self.process_message)
            self.serial_reader.start()

    def close(self):
        if self.serial is not None:
            self.serial_reader.stop()
            self.serial.close()
            self.serial = None

    def press_key_sequence(self, key, modifiers):
        for mod in modifiers:
            self.keyboard.press(mod)
        self.keyboard.press(key)
        self.keyboard.release(key)
        for mod in modifiers:
            self.keyboard.release(mod)
        if len(modifiers) > 0:
            return f"{'+'.join([m.name for m in modifiers])}-{key}"
        return key


class PedalApplication(npyscreen.NPSAppManaged):
    def onStart(self):
        self.addForm('MAIN', SetupForm, name='Pedal Setup')


class SetupForm(npyscreen.FormBaseNew):
    ports = {f"{p.description} ({p.device})": p for p in list_ports.comports()}
    ports_names = list(ports.keys())
    modifiers = {"CTRL": Key.ctrl, "ALT": Key.alt, "SHIFT": Key.shift, "SUPER": Key.cmd}
    modifiers_names = list(modifiers.keys())
    history = ""
    open_checkbox = False
    action_widgets = Enum('Widgets', ('LT', 'LM', 'LK', 'RT', 'RM', 'RK'))
    defaults = {action_widgets.LT: "l", action_widgets.RT: "r", action_widgets.LK: "L", action_widgets.RK: "R"}

    def set_defaults(self):
        for k, v in self.defaults.items():
            if k is self.action_widgets.LT or k is self.action_widgets.RT:
                self.model.update_trigger(k, v)
            else:
                self.model.update_key(k, v)

    def activate(self):
        self.edit()

    def open_toggled(self):
        if self.open_checkbox != self.open_widget.value:
            self.open_checkbox = self.open_widget.value
            if self.open_checkbox:
                self.history_widget.value = "<connecting>"
                self.history = ""
                self.model.open()
            else:
                self.model.close()
                self.history_widget.value = "<disconnected>"
            self.display()

    def add_to_history(self, c):
        if len(self.history) >= 10:
            self.history = f"{c}"
        else:
            self.history += c
        self.history_widget.value = self.history
        self.history_widget.update()
        self.display()

    def comport_changed(self):
        self.model.close()
        if len(self.comport_widget.value) > 0:
            port_name = self.ports_names[self.comport_widget.value[0]]
            self.model.comport = self.ports[port_name].device
            self.open_widget.editable = True
        else:
            self.open_widget.value = False
            self.open_widget.editable = False

    def key_error(self, what, value):
        message = "Can only press one key at a time!"
        if what is self.action_widgets.LT:
            self.left_trigger_widget.value = value[0]
            message = "Can only trigger from one character!"
        elif what is self.action_widgets.RT:
            self.right_trigger_widget.value = value[0]
            message = "Can only trigger from one character!"
        elif what is self.action_widgets.LK:
            self.left_key_widget.value = value[0]
        else:
            self.right_key_widget.value = value[0]
        npyscreen.notify_wait(message, title="Input too long!")

    def show_action(self, triggered, sequence):
        if triggered != "":
            npyscreen.notify_wait(f"Triggered the {triggered} action, " +
                                  f"sending the combination {sequence}",
                                  title="Triggered!")

    def create(self):
        # npyscreen.notify_wait(f"{self.lines} lines, {self.columns} cols")
        self.model = PedalModel(history_callback=self.add_to_history,
                                key_error_callback=self.key_error,
                                action_callback=self.show_action)
        self.set_defaults()
        rely = 2
        self.comport_widget = self.add(npyscreen.TitleSelectOne,
                                       name="COM port:",
                                       values=self.ports_names,
                                       max_height=len(self.ports),
                                       scroll_exit=True,
                                       rely=rely)
        self.comport_widget.when_value_edited = self.comport_changed
        rely += len(self.ports) + 1
        self.open_widget = self.add(npyscreen.CheckBox,
                                    max_height=2,
                                    name="Open Connection",
                                    scroll_exit=True,
                                    editable=False,
                                    rely=rely)
        self.open_widget.when_value_edited = self.open_toggled
        rely += 1

        self.history_widget = self.add(npyscreen.TitleText,
                                       name="History:",
                                       value="<not connected>",
                                       max_height=1,
                                       editable=False,
                                       rely=rely)
        rely += 2

        self.left_trigger_widget = self.add(npyscreen.TitleText,
                                            name="Left Pedal trigger character",
                                            value=self.defaults[self.action_widgets.LT],
                                            max_width=30,
                                            max_height=2,
                                            rely=rely)
        self.left_trigger_widget.when_value_edited = lambda: self.model.update_trigger(self.action_widgets.LT,
                                                                                       self.left_trigger_widget.value)
        self.right_trigger_widget = self.add(npyscreen.TitleText,
                                             name="Right Pedal trigger character",
                                             value=self.defaults[self.action_widgets.RT],
                                             max_width=30,
                                             max_height=2,
                                             relx=40,
                                             rely=rely)
        self.right_trigger_widget.when_value_edited = lambda: self.model.update_trigger(self.action_widgets.RT,
                                                                                        self.right_trigger_widget.value)
        rely += 2
        mod_length = len(self.modifiers) + 1
        self.left_modifier_widget = self.add(npyscreen.TitleMultiSelect,
                                             name="Left Command Modifiers:",
                                             max_height=mod_length,
                                             values=self.modifiers_names,
                                             max_width=30,
                                             rely=rely,
                                             scroll_exit=True)
        self.left_modifier_widget.when_value_edited = lambda: self.model.update_modifiers(self.action_widgets.LM,
                                                                                          self.left_modifier_widget.value)
        self.right_modifier_widget = self.add(npyscreen.TitleMultiSelect,
                                              name="Right Command Modifiers:",
                                              max_height=mod_length,
                                              values=self.modifiers_names,
                                              max_width=30,
                                              scroll_exit=True,
                                              relx=40,
                                              rely=rely)
        self.right_modifier_widget.when_value_edited = lambda: self.model.update_modifiers(self.action_widgets.RM,
                                                                                           self.right_modifier_widget.value)
        rely += mod_length

        self.left_key_widget = self.add(npyscreen.TitleText,
                                        name="Left Command Key:",
                                        value=self.defaults[self.action_widgets.LK],
                                        scroll_exit=True,
                                        max_width=30,
                                        max_height=2,
                                        rely=rely)
        self.left_key_widget.when_value_edited = lambda: self.model.update_key(self.action_widgets.LK,
                                                                               self.left_key_widget.value)
        self.right_key_widget = self.add(npyscreen.TitleText,
                                         name="Right Command Key:",
                                         value=self.defaults[self.action_widgets.RK],
                                         max_height=2,
                                         max_width=30,
                                         scroll_exit=True,
                                         relx=40,
                                         rely=rely)
        self.right_key_widget.when_value_edited = lambda: self.model.update_key(self.action_widgets.RK,
                                                                                self.right_key_widget.value)
        rely += 2
        # npyscreen.notify_wait(f"{rely} rely")


if __name__ == '__main__':
    app = PedalApplication().run()
