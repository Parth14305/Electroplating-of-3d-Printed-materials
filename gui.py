"""
gui.py

Vibrant, user-friendly touchscreen GUI application for controlling an
electroplating system, optimized for a Raspberry Pi 5 with a compact
3.5-inch display (480x320 pixels).

Uses Kivy for touch-friendly interface.
"""

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.slider import Slider
from kivy.uix.modalview import ModalView
from kivy.uix.progressbar import ProgressBar
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp  # Density-independent pixels for scaling

# Import the utility modules (now provided)
from formulas import PlatingCalculator, format_time

# --- UPDATED: Importing the real PyVISA interface ---
from scpi import PowerSupplyInterface

# --- Configuration for 3.5-inch 480x320 Display ---
WINDOW_WIDTH = 480
WINDOW_HEIGHT = 320
# Ensure window size is fixed for the target device
Window.size = (WINDOW_WIDTH, WINDOW_HEIGHT)
Window.allow_resize = False


# --- Kivy App Class ---
class ElectroplatingControllerApp(App):
    def build(self):
        # 1. Initialize State and Services
        self.target_thickness_um = 10.0
        self.target_area_cm2 = 50.0
        self.complexity = 1
        self.current_readout_V = 0.0
        self.current_readout_A = 0.0
        self.status_message = "NOT CONNECTED"
        self.progress_percent = 0
        self.time_elapsed_sec = 0
        self.is_plating_active = False

        self.target_current_A = 0.0
        self.target_voltage_V = 0.0
        self.estimated_time_sec = 0

        # --- UPDATED: Initialize the real interface class ---
        self.psu_interface = PowerSupplyInterface()
        self.live_update_event = None

        # 2. Main Layout (Vertical, 480x320)
        main_layout = BoxLayout(
            orientation="vertical",
            padding=[dp(8)],
            spacing=dp(4),
            # Background color is handled by canvas, but good to set here too
            # background_color=(0.1, 0.1, 0.2, 1),
        )

        # Set a dark, industrial theme background for the root widget
        Window.clearcolor = (0.1, 0.1, 0.2, 1)

        # --- 2.1. Input Section (Top: ~100px height) ---
        input_section = GridLayout(
            cols=3, size_hint_y=None, height=dp(100), spacing=dp(5), padding=dp(5)
        )
        # Add background color to input section for visual grouping
        with input_section.canvas.before:
            Color(0.15, 0.15, 0.3, 1)
            self.input_rect = RoundedRectangle(
                size=input_section.size, pos=input_section.pos, radius=[dp(8)]
            )
        input_section.bind(
            size=lambda *x: setattr(self.input_rect, "size", x[0].size),
            pos=lambda *x: setattr(self.input_rect, "pos", x[0].pos),
        )

        # Thickness Input
        input_section.add_widget(
            self._create_input_widget(
                "Thickness ($\mu$m)",
                str(self.target_thickness_um),
                self.on_thickness_input,
                "thickness_input",
            )
        )
        # Area Input
        input_section.add_widget(
            self._create_input_widget(
                "Area ($\text{cm}^2$)",
                str(self.target_area_cm2),
                self.on_area_input,
                "area_input",
            )
        )
        # Complexity Slider
        input_section.add_widget(self._create_complexity_slider())

        main_layout.add_widget(input_section)

        # --- 2.2. Display Section (Center: ~140px height) ---
        display_section = BoxLayout(
            orientation="vertical", spacing=dp(5), size_hint_y=None, height=dp(140)
        )

        # Calculated Metrics (Row 1) - Size Hint 0.5 (was 0.4)
        calc_metrics = GridLayout(cols=3, size_hint_y=0.45, spacing=dp(5))
        self.target_current_label = self._create_display_label(
            "Target Current", "0.000 A", (0.2, 0.7, 0.9, 1)
        )
        self.target_voltage_label = self._create_display_label(
            "Target Voltage", "0.00 V", (0.9, 0.7, 0.2, 1)
        )
        self.estimated_time_label = self._create_display_label(
            "Est. Time", format_time(0), (0.7, 0.9, 0.2, 1)
        )
        calc_metrics.add_widget(self.target_current_label)
        calc_metrics.add_widget(self.target_voltage_label)
        calc_metrics.add_widget(self.estimated_time_label)
        display_section.add_widget(calc_metrics)

        # Live Monitoring (Row 2) - Size Hint 0.5 (was 0.4)
        live_monitoring = GridLayout(cols=3, size_hint_y=0.45, spacing=dp(5))
        self.actual_current_label = self._create_display_label(
            "Actual Current", "0.000 A", (0.2, 0.5, 0.8, 1)
        )
        self.actual_voltage_label = self._create_display_label(
            "Actual Voltage", "0.00 V", (0.8, 0.5, 0.2, 1)
        )
        self.time_elapsed_label = self._create_display_label(
            "Elapsed Time", format_time(0), (0.5, 0.8, 0.2, 1)
        )
        live_monitoring.add_widget(self.actual_current_label)
        live_monitoring.add_widget(self.actual_voltage_label)
        live_monitoring.add_widget(self.time_elapsed_label)
        display_section.add_widget(live_monitoring)

        # Status/Progress Bar (Row 3) - Size Hint 0.1 (was 0.2)
        status_box = BoxLayout(orientation="horizontal", size_hint_y=0.1, spacing=dp(5))

        self.status_label = Label(
            text=self.status_message,
            font_size="10dp",
            color=(1, 1, 1, 1),
            size_hint_x=0.35,  # Reserve space for status text
        )

        # New: Progress Bar
        self.progress_bar = ProgressBar(
            max=100,
            value=0,
            size_hint_x=0.65,  # Reserve majority of space for progress
        )
        self.progress_label = Label(
            text="0%",
            font_size="9dp",
            color=(0.9, 0.9, 0.9, 1),
            halign="center",
            valign="middle",
            text_size=(self.progress_bar.width, self.progress_bar.height),
        )
        # Overlay the progress percentage label onto the bar
        progress_stack = BoxLayout(size_hint_x=0.65)
        progress_stack.add_widget(self.progress_bar)

        status_box.add_widget(self.status_label)
        status_box.add_widget(progress_stack)
        display_section.add_widget(status_box)

        main_layout.add_widget(display_section)

        # --- 2.3. Control Section (Bottom: ~80px height) ---
        control_section = GridLayout(
            cols=4, size_hint_y=None, height=dp(70), spacing=dp(5), padding=dp(5)
        )

        # Connection Button
        self.connect_btn = self._create_control_button(
            "CONNECT", self.on_connect_toggle, (0.2, 0.6, 0.2, 1)
        )
        control_section.add_widget(self.connect_btn)

        # START Button
        self.start_btn = self._create_control_button(
            "START PLATING", self.on_start_plating, (0.3, 0.8, 0.3, 1)
        )
        self.start_btn.disabled = True
        control_section.add_widget(self.start_btn)

        # PAUSE Button
        self.pause_btn = self._create_control_button(
            "PAUSE", self.on_pause_plating, (0.9, 0.6, 0.2, 1)
        )
        self.pause_btn.disabled = True
        control_section.add_widget(self.pause_btn)

        # ABORT Button
        self.abort_btn = self._create_control_button(
            "ABORT", self.on_abort_plating, (0.8, 0.3, 0.3, 1)
        )
        self.abort_btn.disabled = True
        control_section.add_widget(self.abort_btn)

        main_layout.add_widget(control_section)

        # 3. Initial Calculations and Setup
        self.update_calculations()

        return main_layout

    # --- Widget Factory Methods (Omitted for brevity, no changes needed) ---
    def _create_input_widget(
        self, label_text, default_value, on_text_validate_callback, name
    ):
        """Creates a label/textinput pair for numeric input."""
        box = BoxLayout(orientation="vertical", size_hint_x=1)
        box.add_widget(
            Label(
                text=label_text,
                size_hint_y=0.4,
                font_size="10dp",  # Slightly smaller font for tight fit
                color=(0.9, 0.9, 0.9, 1),
            )
        )

        text_input = TextInput(
            text=default_value,
            multiline=False,
            input_type="number",
            size_hint_y=0.6,
            padding=[dp(5), dp(8), dp(5), dp(8)],  # Adjusted padding for better touch
            background_color=(0.2, 0.2, 0.4, 1),
            foreground_color=(1, 1, 1, 1),
            font_size="14dp",  # Slightly smaller font
            hint_text="Enter number",
            name=name,  # Used for retrieving widget later
        )
        text_input.bind(
            on_text_validate=on_text_validate_callback, focus=self.on_input_focus
        )
        box.add_widget(text_input)
        return box

    def _create_complexity_slider(self):
        """Creates the complexity slider widget."""
        box = BoxLayout(orientation="vertical", size_hint_x=1)
        self.complexity_label = Label(
            text=f"Complexity: {self.complexity} (Basic)",
            size_hint_y=0.4,
            font_size="10dp",  # Slightly smaller font
            color=(0.9, 0.9, 0.9, 1),
        )
        box.add_widget(self.complexity_label)

        slider = Slider(
            min=1,
            max=5,
            value=self.complexity,
            step=1,
            size_hint_y=0.6,
            orientation="horizontal",
            # Increased touch area for slider knob/track
            padding=dp(5),
            height=dp(30),
        )
        slider.bind(value=self.on_complexity_change)
        box.add_widget(slider)
        return box

    def _create_display_label(self, title, value, color):
        """Creates a stylish display box for metric readouts."""
        box = BoxLayout(
            orientation="vertical", size_hint_x=1, padding=dp(3), spacing=dp(1)
        )

        # Store the rectangle reference for canvas updates
        with box.canvas.before:
            Color(0.2, 0.2, 0.3, 1)
            rect = RoundedRectangle(size=box.size, pos=box.pos, radius=[dp(4)])
        box.bind(
            size=lambda instance, value: setattr(rect, "size", value),
            pos=lambda instance, value: setattr(rect, "pos", value),
        )

        box.add_widget(
            Label(
                text=title, size_hint_y=0.3, font_size="9dp", color=(0.7, 0.7, 0.8, 1)
            )
        )
        value_label = Label(
            text=value, size_hint_y=0.7, font_size="16dp", bold=True, color=color
        )
        box.add_widget(value_label)
        return value_label  # Return the value label so we can update its text

    def _create_control_button(self, text, on_press_callback, color):
        """Creates a styled, touch-friendly control button."""
        button = Button(
            text=text,
            font_size="12dp",  # Adjusted size for 4 buttons in a row
            color=(1, 1, 1, 1),
            background_color=color,
            background_normal="",
            background_down="",
            border=[dp(12), dp(12), dp(12), dp(12)],  # Ensure good touch border
            on_press=on_press_callback,
        )

        # Add a subtle visual feedback effect when disabled
        def update_color(instance, value):
            instance.background_color = (
                color if not instance.disabled else (0.4, 0.4, 0.5, 1)
            )

        button.bind(disabled=update_color)
        update_color(button, button.disabled)  # Initial call

        return button

    def show_modal(self, title, message, is_error=False, callback=None):
        """Displays a custom modal message instead of alert()."""
        modal = ModalView(
            size_hint=(0.85, 0.45),  # Slightly larger modal
            auto_dismiss=False,
            background_color=(0.1, 0.1, 0.2, 0.9),
        )
        layout = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))

        color = (0.8, 0.2, 0.2, 1) if is_error else (0.2, 0.8, 0.2, 1)

        layout.add_widget(
            Label(text=title, font_size="18dp", color=color, size_hint_y=0.2)
        )
        layout.add_widget(
            Label(text=message, font_size="11dp", color=(1, 1, 1, 1), size_hint_y=0.6)
        )

        close_btn = self._create_control_button("OK", modal.dismiss, color)
        if callback:
            close_btn.bind(on_press=callback)

        layout.add_widget(close_btn)
        modal.add_widget(layout)
        modal.open()

    # --- Input Handlers (No Changes) ---

    def on_input_focus(self, instance, value):
        """Deselects the text input on unfocus to hide the software keyboard."""
        if not value:
            # Re-validate the text when focus is lost
            if instance.name == "thickness_input":
                self.on_thickness_input(instance)
            elif instance.name == "area_input":
                self.on_area_input(instance)

    def on_thickness_input(self, instance):
        """Handles and validates thickness input."""
        try:
            val = float(instance.text)
            if val <= 0:
                raise ValueError
            self.target_thickness_um = val
            self.update_calculations()
        except ValueError:
            self.show_modal(
                "Input Error",
                "Please enter a valid, positive number for **thickness** ($\mu$m).",
                is_error=True,
            )
            instance.text = str(self.target_thickness_um)  # Revert to last valid value

    def on_area_input(self, instance):
        """Handles and validates area input."""
        try:
            val = float(instance.text)
            if val <= 0:
                raise ValueError
            self.target_area_cm2 = val
            self.update_calculations()
        except ValueError:
            self.show_modal(
                "Input Error",
                "Please enter a valid, positive number for **area** ($\text{cm}^2$).",
                is_error=True,
            )
            instance.text = str(self.target_area_cm2)  # Revert to last valid value

    def on_complexity_change(self, instance, value):
        """Handles complexity slider change."""
        self.complexity = int(value)
        complexity_map = {
            1: "Basic",
            2: "Simple",
            3: "Moderate",
            4: "Complex",
            5: "Highly Detailed",
        }
        self.complexity_label.text = f"Complexity: {self.complexity} ({complexity_map.get(self.complexity, 'Basic')})"
        self.update_calculations()

    def update_calculations(self, *args):
        """Performs all plating metric calculations and updates display labels."""
        metrics = PlatingCalculator.calculate_metrics(
            self.target_thickness_um, self.target_area_cm2, self.complexity
        )

        self.target_current_A = metrics["target_current_A"]
        self.target_voltage_V = metrics["target_voltage_V"]
        self.estimated_time_sec = metrics["estimated_time_sec"]

        self.target_current_label.text = f"{self.target_current_A:.3f} A"
        self.target_voltage_label.text = f"{self.target_voltage_V:.2f} V"
        self.estimated_time_label.text = format_time(self.estimated_time_sec)

        # Enable start button if connected and calculated values are valid
        self.start_btn.disabled = (
            not self.psu_interface.is_connected
            or self.estimated_time_sec <= 0
            or self.is_plating_active
        )

    # --- Control Handlers ---

    def on_connect_toggle(self, instance):
        """Toggles connection to the power supply."""
        if not self.psu_interface.is_connected:
            if self.psu_interface.connect():
                self.status_message = "CONNECTED (Ready to Apply)"
                self.connect_btn.text = "DISCONNECT"
                self.connect_btn.background_color = (
                    0.8,
                    0.3,
                    0.3,
                    1,
                )  # Red for disconnect
                self.start_btn.disabled = (
                    self.estimated_time_sec <= 0
                )  # Enable start if calculations are valid
            else:
                self.status_message = "CONNECTION FAILED"
                self.show_modal(
                    "Connection Failed",
                    "Could not establish connection to Power Supply. **Check PyVISA/serial setup** in `scpi.py` and device permissions.",
                    is_error=True,
                )
        else:
            self.psu_interface.disconnect()
            self.status_message = "DISCONNECTED"
            self.connect_btn.text = "CONNECT"
            self.connect_btn.background_color = (0.2, 0.6, 0.2, 1)  # Green for connect
            self.start_btn.disabled = True

        self.status_label.text = self.status_message
        self.pause_btn.disabled = True
        self.abort_btn.disabled = True

        # If disconnecting while plating, ensure we stop
        if not self.psu_interface.is_connected and self.is_plating_active:
            self._execute_abort()

    def start_process(self, *args):
        """Starts the plating process after confirmation."""
        if not self.psu_interface.is_connected or self.estimated_time_sec <= 0:
            self.show_modal(
                "Error", "Check connection and input parameters.", is_error=True
            )
            return

        # 1. Apply Settings
        apply_command = f"APPLY {self.target_voltage_V} {self.target_current_A}"
        if not self.psu_interface.send_command(apply_command):
            self.status_message = "ERROR: Failed to set parameters."
            self.status_label.text = self.status_message
            return

        # 2. Turn Output ON
        if self.psu_interface.send_command("OUTP ON"):
            self.is_plating_active = True
            self.time_elapsed_sec = 0
            self.progress_percent = 0

            # Start the live monitoring loop
            if self.live_update_event:
                self.live_update_event.cancel()
            self.live_update_event = Clock.schedule_interval(
                self.live_monitor, 1.0
            )  # Update every 1 second

            self.status_message = "PLATING ACTIVE"
            self.start_btn.text = "START PLATING"  # Reset text if it was 'RESUME'
            self.start_btn.disabled = True
            self.pause_btn.disabled = False
            self.abort_btn.disabled = False
            self.connect_btn.disabled = True

        else:
            self.status_message = "ERROR: Failed to turn output ON."

        self.status_label.text = self.status_message

    def on_start_plating(self, instance):
        """Shows a confirmation dialog before starting."""
        modal = ModalView(
            size_hint=(0.85, 0.5),
            auto_dismiss=False,
            background_color=(0.1, 0.1, 0.2, 0.9),
        )
        layout = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))

        message = (
            f"Confirm Plating Start/Resume?\n\n"
            f"V: **{self.target_voltage_V:.2f} V**, A: **{self.target_current_A:.3f} A**\n"
            f"Est. Time Remaining: **{format_time(self.estimated_time_sec - self.time_elapsed_sec)}**"
        )

        layout.add_widget(
            Label(
                text="START CONFIRMATION",
                font_size="16dp",
                color=(0.7, 0.9, 0.7, 1),
                size_hint_y=0.2,
            )
        )
        layout.add_widget(
            Label(text=message, font_size="11dp", color=(1, 1, 1, 1), size_hint_y=0.5)
        )

        btn_layout = BoxLayout(spacing=dp(10), size_hint_y=0.3)
        cancel_btn = self._create_control_button(
            "CANCEL", modal.dismiss, (0.8, 0.3, 0.3, 1)
        )

        start_btn = self._create_control_button(
            "START", modal.dismiss, (0.3, 0.8, 0.3, 1)
        )
        start_btn.bind(on_press=lambda *x: self.start_process())

        btn_layout.add_widget(cancel_btn)
        btn_layout.add_widget(start_btn)

        layout.add_widget(btn_layout)
        modal.add_widget(layout)
        modal.open()

    def on_pause_plating(self, instance):
        """Pauses the plating process."""
        if self.is_plating_active:
            self.psu_interface.send_command("OUTP OFF")
            self.is_plating_active = False

            if self.live_update_event:
                self.live_update_event.cancel()
                self.live_update_event = None

            self.status_message = (
                f"PAUSED (Elapsed: {format_time(self.time_elapsed_sec)})"
            )
            self.status_label.text = self.status_message
            self.start_btn.text = "RESUME"
            self.start_btn.disabled = False
            self.pause_btn.disabled = True
            self.abort_btn.disabled = False
            self.connect_btn.disabled = True

    def on_abort_plating(self, instance):
        """Shows confirmation dialog before aborting."""
        self.show_modal(
            "ABORT CONFIRMATION",
            "Are you sure you want to **ABORT** the plating process? This will stop the power supply immediately and reset progress.",
            is_error=True,
            callback=lambda *x: self._execute_abort(),
        )

    def _execute_abort(self):
        """Internal method to execute the abort action."""
        if self.live_update_event:
            self.live_update_event.cancel()
            self.live_update_event = None

        self.psu_interface.send_command("OUTP OFF")
        self.is_plating_active = False
        self.time_elapsed_sec = 0
        self.progress_percent = 0
        self.start_btn.text = "START PLATING"

        self.status_message = "ABORTED. Resetting."
        self.status_label.text = self.status_message

        # Reset buttons
        self.start_btn.disabled = False
        self.pause_btn.disabled = True
        self.abort_btn.disabled = True
        self.connect_btn.disabled = False

        # Clear live readouts and progress
        self.current_readout_V = 0.0
        self.current_readout_A = 0.0
        self.actual_voltage_label.text = f"{self.current_readout_V:.2f} V"
        self.actual_current_label.text = f"{self.current_readout_A:.3f} A"
        self.time_elapsed_label.text = format_time(self.time_elapsed_sec)
        self.progress_bar.value = 0
        self.status_label.text = "ABORTED. Resetting."  # Reset status text

    # --- Live Monitoring ---

    def live_monitor(self, dt):
        """Scheduled function to update live data and check progress."""
        if not self.is_plating_active:
            return

        # 1. Read Actual Data
        V, A, status = self.psu_interface.read_data()
        self.current_readout_V = V
        self.current_readout_A = A

        # 2. Update UI Readouts
        self.actual_voltage_label.text = f"{V:.2f} V"
        self.actual_current_label.text = f"{A:.3f} A"

        # 3. Update Time and Progress
        self.time_elapsed_sec += 1
        self.time_elapsed_label.text = format_time(self.time_elapsed_sec)

        if self.estimated_time_sec > 0:
            self.progress_percent = min(
                100, int((self.time_elapsed_sec / self.estimated_time_sec) * 100)
            )
        else:
            self.progress_percent = 0

        self.progress_bar.value = self.progress_percent
        self.status_label.text = f"{status} ({self.progress_percent}%)"

        # 4. Check for Alerts/Completion
        if "ALERT" in status:
            # We don't stop plating on alert, but warn the user
            self.show_modal(
                "Instrument Alert",
                f"**Status: {status}**\n\nCommunication or internal power supply error detected. Monitor closely or consider pausing/aborting.",
                is_error=True,
            )

        if self.time_elapsed_sec >= self.estimated_time_sec:
            if self.live_update_event:
                self.live_update_event.cancel()
                self.live_update_event = None

            self.psu_interface.send_command("OUTP OFF")
            self.is_plating_active = False
            self.status_message = "PLATING COMPLETE"

            # Final progress update
            self.progress_bar.value = 100
            self.status_label.text = self.status_message
            self.time_elapsed_label.text = format_time(self.estimated_time_sec)

            self.start_btn.disabled = True
            self.pause_btn.disabled = True
            self.abort_btn.disabled = True
            self.connect_btn.disabled = False
            self.show_modal(
                "Process Complete",
                "Desired plating thickness achieved. Output turned OFF. Check part.",
                is_error=False,
            )


if __name__ == "__main__":
    try:
        # Set default Kivy configurations for embedded use
        from kivy.config import Config

        Config.set("graphics", "width", str(WINDOW_WIDTH))
        Config.set("graphics", "height", str(WINDOW_HEIGHT))
        Config.set(
            "input", "mouse", "mouse,multitouch_on_demand"
        )  # Useful for touchscreen
        Config.write()

        ElectroplatingControllerApp().run()

    except Exception as e:
        print(f"An error occurred during application execution: {e}")
        # Optionally, log or display a critical error message
