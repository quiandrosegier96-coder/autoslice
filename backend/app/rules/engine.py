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
from app.rules.nozzle_profiles import apply_nozzle_profile
from app.rules.safety_clamp import clamp_to_printer_limits


def generate_settings(
    intent: ModelIntent,
    printer: PrinterProfile,
    filament: FilamentType,
    nozzle_size_mm: float = 0.4,
) -> PrintSettings:
    """
    Rules engine pipeline:
      Pass 1 — Load base profile for selected printer
      Pass 2 — Apply geometry-driven adjustments (overhangs, bridges, thin walls, infill pattern)
      Pass 3 — Apply filament-specific adjustments (temps, cooling, forced brim/no-supports)
      Pass 4 — Apply nozzle-size profile (layer height, speed, wall count for fine nozzles)
      Pass 5 — Safety clamp: enforce all values within printer rated specs
    """
    settings = load_base_profile(printer)
    settings = apply_geometry_rules(settings, intent)
    settings = apply_filament_rules(settings, filament)
    settings = apply_nozzle_profile(settings, nozzle_size_mm)
    settings = clamp_to_printer_limits(settings, printer)
    return settings
