"""
formulas.py: Utility module for calculating electroplating metrics
and formatting time values.
"""

import math


def format_time(seconds):
    """Converts seconds into HH:MM:SS format."""
    try:
        seconds = int(seconds)
        if seconds < 0:
            return "00:00:00"

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        sec = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{sec:02d}"
    except (TypeError, ValueError):
        return "N/A"


class PlatingCalculator:
    # Conceptual constants for a generic plating material (e.g., Gold/Nickel blend)
    # These constants are for simulation purposes.
    MOLAR_MASS_G_MOL = 150.0  # g/mol
    DENSITY_G_CM3 = 10.0  # g/cm^3 (10,000 kg/m^3)
    CHARGE_VALENCE = 2  # Assumed charge for ions
    CURRENT_EFFICIENCY = 0.95  # 95% efficiency

    # Faraday constant (C/mol)
    F = 96485.0

    # Recommended Current Density (mA/cm^2) based on complexity
    # Higher complexity requires lower current density to ensure even coverage
    CURRENT_DENSITY_MAP = {
        1: 5.0,  # Basic (5.0 mA/cm^2)
        2: 4.0,  # Simple
        3: 3.0,  # Moderate
        4: 2.5,  # Complex
        5: 2.0,  # Highly Detailed
    }

    @staticmethod
    def calculate_metrics(thickness_um, area_cm2, complexity_level):
        """
        Calculates required current and estimated time based on inputs.

        Inputs:
        - thickness_um (float): Target thickness in micrometers ($\mu$m).
        - area_cm2 (float): Surface area in square centimeters ($\text{cm}^2$).
        - complexity_level (int): 1-5, determines current density and voltage factor.

        Returns:
        - dict: Contains 'target_current_A', 'target_voltage_V', 'estimated_time_sec'
        """
        try:
            # 1. Calculate Target Current (Amps)
            density_mA_cm2 = PlatingCalculator.CURRENT_DENSITY_MAP.get(
                complexity_level, PlatingCalculator.CURRENT_DENSITY_MAP[1]
            )
            # Convert mA/cm^2 to A
            target_current_A = (density_mA_cm2 / 1000.0) * area_cm2

            # 2. Calculate Plating Mass (grams)
            thickness_cm = thickness_um / 10000.0  # $\mu$m to cm
            volume_cm3 = thickness_cm * area_cm2
            target_mass_g = volume_cm3 * PlatingCalculator.DENSITY_G_CM3

            # 3. Calculate Estimated Time (Seconds) based on Faraday's Law
            # Time (s) = (Mass * n * F) / (M * I * E)
            # where:
            #   Mass (g) = target_mass_g
            #   n = CHARGE_VALENCE
            #   F = Faraday constant
            #   M = MOLAR_MASS_G_MOL
            #   I = target_current_A
            #   E = CURRENT_EFFICIENCY

            numerator = (
                target_mass_g * PlatingCalculator.CHARGE_VALENCE * PlatingCalculator.F
            )
            denominator = (
                PlatingCalculator.MOLAR_MASS_G_MOL
                * target_current_A
                * PlatingCalculator.CURRENT_EFFICIENCY
            )

            estimated_time_sec = numerator / denominator

            # 4. Calculate Target Voltage (Simple scaling for simulation)
            # Base voltage (e.g., 2.0V) + complexity factor
            voltage_factor = 1.0 + (complexity_level - 1) * 0.2
            target_voltage_V = 2.0 * voltage_factor

            return {
                "target_current_A": target_current_A,
                "target_voltage_V": target_voltage_V,
                "estimated_time_sec": estimated_time_sec,
            }

        except (ValueError, ZeroDivisionError, TypeError):
            # Return safe zeros on invalid input
            return {
                "target_current_A": 0.0,
                "target_voltage_V": 0.0,
                "estimated_time_sec": 0,
            }


if __name__ == "__main__":
    # Simple test case
    metrics = PlatingCalculator.calculate_metrics(10.0, 50.0, 3)
    print(f"Target Current: {metrics['target_current_A']:.3f} A")
    print(f"Target Voltage: {metrics['target_voltage_V']:.2f} V")
    print(f"Estimated Time: {format_time(metrics['estimated_time_sec'])}")
