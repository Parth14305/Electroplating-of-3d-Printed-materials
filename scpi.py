"""
scpi.py: Interface for real-world power supply unit (PSU) using PyVISA/SCPI commands.
The configuration is based on the user's provided PyVISA script, assuming a serial
connection over a USB-to-Serial adapter.
"""

import pyvisa
import time

# --- CONFIGURATION (Based on user's PyVISA script) ---
# IMPORTANT: This must match your device's VISA resource string.
PSU_ADDRESS = "ASRL/dev/ttyUSB0::INSTR"
BAUD_RATE = 115200
TIMEOUT_MS = 5000  # 5 seconds


class PowerSupplyInterface:
    def __init__(self):
        self.is_connected = False
        self.output_on = False
        self.psu = None
        self.rm = None

    def connect(self):
        """Attempts to establish a PyVISA connection to the instrument."""
        if self.is_connected:
            return True

        try:
            # Specify the pyvisa-py backend for maximum compatibility
            self.rm = pyvisa.ResourceManager("@py")
            self.psu = self.rm.open_resource(PSU_ADDRESS)

            # Configure serial connection parameters based on user's script
            self.psu.baud_rate = BAUD_RATE
            self.psu.read_termination = "\n"
            self.psu.write_termination = "\n"
            self.psu.timeout = TIMEOUT_MS

            # Test connection with a common SCPI command
            idn = self.psu.query("*IDN?").strip()
            print(f"SCPI: Connected to: {idn}")

            self.is_connected = True
            return True

        except pyvisa.errors.VisaIOError as e:
            print(f"SCPI Error: Connection failed. Details: {e}")
            self.is_connected = False
            self.psu = None
            self.rm = None
            return False
        except Exception as e:
            print(f"SCPI Error: Unexpected error during connection: {e}")
            self.is_connected = False
            return False

    def disconnect(self):
        """Closes the connection safely."""
        if self.psu:
            try:
                # Ensure output is OFF before disconnecting
                self.psu.write("OUTP OFF")
                self.psu.close()
            except pyvisa.errors.VisaIOError as e:
                print(f"SCPI Warning: Could not close safely: {e}")
            self.psu = None

        self.is_connected = False
        self.output_on = False
        print("SCPI: Disconnected.")

    def send_command(self, command):
        """Sends an SCPI command (APPLY V A, OUTP ON/OFF)."""
        if not self.is_connected or not self.psu:
            print(f"SCPI Error: Cannot send command '{command}'. Not connected.")
            return False

        command = command.strip().upper()

        if command.startswith("APPLY"):
            # Command format: APPLY V A (e.g., APPLY 5.0 0.5)
            try:
                parts = command.split()
                if len(parts) == 3:
                    V = float(parts[1])
                    A = float(parts[2])
                    # Send voltage and current limit commands sequentially
                    self.psu.write(f"VOLTage {V:.2f}")
                    self.psu.write(f"CURRent {A:.3f}")
                    print(f"SCPI: Set V={V:.2f}, A={A:.3f}")
                    return True
            except (ValueError, pyvisa.errors.VisaIOError) as e:
                print(f"SCPI Error: Failed to set APPLY parameters: {e}")
                return False

        elif command == "OUTP ON":
            try:
                self.psu.write("OUTPut:STATe ON")
                self.output_on = True
                print("SCPI: Output ON.")
                return True
            except pyvisa.errors.VisaIOError as e:
                print(f"SCPI Error: Failed to turn output ON: {e}")
                return False

        elif command == "OUTP OFF":
            try:
                self.psu.write("OUTPut:STATe OFF")
                self.output_on = False
                print("SCPI: Output OFF.")
                return True
            except pyvisa.errors.VisaIOError as e:
                print(f"SCPI Error: Failed to turn output OFF: {e}")
                return False

        print(f"SCPI Warning: Unhandled command '{command}'")
        return False

    def read_data(self):
        """
        Reads the actual voltage and current from the instrument.

        Returns: (Voltage_Actual, Current_Actual, Status_Message)
        """
        status = "PLATING ACTIVE"
        V = 0.0
        A = 0.0

        if not self.is_connected or not self.psu:
            return 0.0, 0.0, "NOT CONNECTED"

        if not self.output_on:
            return 0.0, 0.0, "OUTPUT OFF (Connected)"

        try:
            # Query the actual measured values
            V = float(self.psu.query("MEASure:VOLTage?").strip())
            A = float(self.psu.query("MEASure:CURRent?").strip())

            # Query system error register (optional, helps check device health)
            try:
                error_state = self.psu.query("SYSTem:ERRor?").strip()
                if "No error" not in error_state:
                    status = f"ALERT: PSU Error ({error_state})"
            except pyvisa.errors.VisaIOError:
                # Ignore if SYSTem:ERRor is not supported
                pass

        except pyvisa.errors.VisaIOError as e:
            # Handle communication failure mid-operation
            print(f"SCPI Read Error: {e}")
            status = "COMMS ERROR - PSU OFFLINE"
            # Attempt a full disconnect on comms failure
            self.disconnect()

        except ValueError:
            # Handle case where measurement returns non-numeric string
            status = "MEASUREMENT READ FAIL"

        return V, A, status
