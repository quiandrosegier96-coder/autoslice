"""
AutoSlice — Rules engine entry point.
Generates PrintSettings from ModelIntent + printer + filament.
"""

from app.models.intent import ModelIntent
from app.models.print_settings import PrintSettings
from app.models.printer import PrinterProfile, FilamentType
from app.rules.base_profiles import load_base_profile
from app.rules.geometry_rules import apply_geometry_rules
from app.rules.filament_rules import apply_filament_rules
from app.rules.safety_clamp import clamp_to_printer_limits


def generate_settings(
    intent: ModelIntent,
    printer: PrinterProfile,
    filament: FilamentType,
) -> PrintSettings:
    """
    Three-pass rules engine:
      Pass 1 — Load base profile for selected printer
      Pass 2 — Apply geometry-driven adjustments (overhangs, bridges, thin walls)
      Pass 3 — Apply filament-specific adjustments (temps, speed, cooling)
      Pass 4 — Safety clamp: enforce all values within printer rated specs
    """
    settings = load_base_profile(printer)
    settings = apply_geometry_rules(settings, intent)
    settings = apply_filament_rules(settings, filament)
    settings = clamp_to_printer_limits(settings, printer)
    return settings
