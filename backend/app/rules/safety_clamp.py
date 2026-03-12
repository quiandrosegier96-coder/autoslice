"""
AutoSlice — Safety clamp: enforce all values within printer rated specs.
"""

from app.models.print_settings import PrintSettings
from app.models.printer import PrinterProfile


def clamp_to_printer_limits(settings: PrintSettings, printer: PrinterProfile) -> PrintSettings:
    nd = printer.nozzle_diameter_mm

    settings.layer_height_mm       = round(max(0.05, min(settings.layer_height_mm, nd * 0.8)), 3)
    settings.first_layer_height_mm = round(max(0.1,  min(settings.first_layer_height_mm, nd)), 3)
    settings.wall_count            = max(2, min(settings.wall_count, 8))
    settings.top_layers            = max(3, min(settings.top_layers, 12))
    settings.bottom_layers         = max(3, min(settings.bottom_layers, 12))
    settings.infill_percent        = max(5, min(settings.infill_percent, 80))
    settings.print_speed_mm_s      = max(10, min(settings.print_speed_mm_s, printer.max_speed_mm_s))
    settings.first_layer_speed_mm_s = max(10, min(settings.first_layer_speed_mm_s, 50))
    settings.fan_speed_percent     = max(0, min(settings.fan_speed_percent, 100))
    settings.support_density_percent = max(5, min(settings.support_density_percent, 50))
    settings.nozzle_temp_c         = max(170, min(settings.nozzle_temp_c, 300))
    settings.bed_temp_c            = max(0,   min(settings.bed_temp_c, 120))

    return settings
