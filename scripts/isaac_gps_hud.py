"""
In-viewport GPS readout for Isaac Sim (same idea as Autoware off-road sim HUD).

Reference: https://github.com/autowarefoundation/autoware_off-road_sim
  launch_sim.py builds an omni.ui overlay and fills GNSS lat/lon from the
  vehicle pose each tick.

Run inside Isaac Sim after opening your stage (e.g. progress3_latest.usd):

  Window → Script Editor → Open this file → Run

Or from the Script Editor REPL:

  import runpy
  runpy.run_path(r"/home/you/Downloads/isaac_sim/scripts/isaac_gps_hud.py")

Uses the same WGS-84 conversion as gps_bridge.py. World position of
the tracked prim is treated as ENU metres from the map origin — match this to
how your OmniGraph odometry frame is defined.

Stop / restart: run stop_gps_hud() then run show_gps_hud() again.
"""

from __future__ import annotations

import math

# Match gps_bridge.py defaults (single-file — no gps_geo module required)
ORIGIN_LAT = 40.4432
ORIGIN_LON = -86.9427
ORIGIN_ALT = 190.0

_WGS84_A = 6378137.0
_WGS84_E2 = 0.00669437999014


def meters_to_gps(x_east, y_north, z_up, origin_lat, origin_lon, origin_alt):
    """ENU offset in metres → (latitude_deg, longitude_deg, altitude_m)."""
    lat_rad = math.radians(origin_lat)
    n = _WGS84_A / math.sqrt(1 - _WGS84_E2 * math.sin(lat_rad) ** 2)
    m_per_deg_lat = math.radians(1) * n * (1 - _WGS84_E2) / (1 - _WGS84_E2 * math.sin(lat_rad) ** 2)
    m_per_deg_lon = math.radians(1) * n * math.cos(lat_rad)
    lat = origin_lat + (y_north / m_per_deg_lat)
    lon = origin_lon + (x_east / m_per_deg_lon)
    alt = origin_alt + z_up
    return lat, lon, alt

# Default: README scene hierarchy — change if your Body prim path differs
DEFAULT_BODY_PRIM = "/World/kart/Body"


class _GpsHudController:
    def __init__(
        self,
        body_prim_path: str = DEFAULT_BODY_PRIM,
        origin_lat: float = ORIGIN_LAT,
        origin_lon: float = ORIGIN_LON,
        origin_alt: float = ORIGIN_ALT,
    ):
        import omni.kit.app
        import omni.timeline
        import omni.ui as ui
        from pxr import Usd

        self._body_path = body_prim_path
        self._origin_lat = origin_lat
        self._origin_lon = origin_lon
        self._origin_alt = origin_alt
        self._Usd = Usd
        self._omni_timeline = omni.timeline

        self._window = ui.Window(
            "GPSReadout",
            width=320,
            height=118,
            position_x=70,
            position_y=95,
            flags=(
                ui.WINDOW_FLAGS_NO_TITLE_BAR
                | ui.WINDOW_FLAGS_NO_SCROLLBAR
                | ui.WINDOW_FLAGS_NO_RESIZE
                | ui.WINDOW_FLAGS_NO_MOVE
            ),
        )
        self._window.frame.set_style({"background_color": 0x00000000})

        C_WHITE = 0xFFFFFFFF
        C_CYAN = 0xFFFFFF00
        with self._window.frame:
            with ui.ZStack(width=320, height=118):
                ui.Rectangle(style={"background_color": 0x55383838, "border_radius": 8})
                with ui.VStack(spacing=4, margin=10):
                    ui.Label(
                        "GPS (WGS-84)",
                        alignment=ui.Alignment.CENTER,
                        style={"color": C_CYAN, "font_size": 16, "font_style": "Bold"},
                    )
                    with ui.HStack():
                        ui.Label("Lat:", width=44, style={"color": C_WHITE, "font_size": 14})
                        self._lat_lbl = ui.Label(
                            "--", style={"color": C_WHITE, "font_size": 14}, width=ui.Fraction(1)
                        )
                    with ui.HStack():
                        ui.Label("Lon:", width=44, style={"color": C_WHITE, "font_size": 14})
                        self._lon_lbl = ui.Label(
                            "--", style={"color": C_WHITE, "font_size": 14}, width=ui.Fraction(1)
                        )
                    with ui.HStack():
                        ui.Label("Alt:", width=44, style={"color": C_WHITE, "font_size": 14})
                        self._alt_lbl = ui.Label(
                            "--", style={"color": C_WHITE, "font_size": 14}, width=ui.Fraction(1)
                        )

        def _on_update(_evt):
            self._tick()

        self._sub = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(
            _on_update, name="isaac_sim_gps_hud_tick"
        )

    def _tick(self):
        try:
            import omni.usd
            from pxr import UsdGeom

            stage = omni.usd.get_context().get_stage()
            if not stage:
                return
            prim = stage.GetPrimAtPath(self._body_path)
            if not prim.IsValid():
                self._lat_lbl.text = f"(no prim {self._body_path})"
                self._lon_lbl.text = ""
                self._alt_lbl.text = ""
                return

            tiface = self._omni_timeline.get_timeline_interface()
            try:
                t_sec = float(tiface.get_current_time())
                tps = float(stage.GetTimeCodesPerSecond())
                tcode = self._Usd.TimeCode(t_sec * tps)
            except Exception:
                tcode = self._Usd.TimeCode.Default()

            xf = UsdGeom.Xformable(prim)
            world = xf.ComputeLocalToWorldTransform(tcode)
            t = world.ExtractTranslation()
            x_e, y_n, z_u = float(t[0]), float(t[1]), float(t[2])

            lat, lon, alt = meters_to_gps(
                x_e, y_n, z_u,
                self._origin_lat, self._origin_lon, self._origin_alt,
            )
            self._lat_lbl.text = f"{lat:.7f} deg"
            self._lon_lbl.text = f"{lon:.7f} deg"
            self._alt_lbl.text = f"{alt:.2f} m"
        except Exception:
            pass

    def destroy(self):
        if self._sub is not None:
            unsub = getattr(self._sub, "unsubscribe", None)
            if callable(unsub):
                unsub()
            self._sub = None
        if self._window is not None:
            self._window.visible = False
            self._window.destroy()
            self._window = None


_instance: _GpsHudController | None = None


def show_gps_hud(
    body_prim_path: str = DEFAULT_BODY_PRIM,
    origin_lat: float = ORIGIN_LAT,
    origin_lon: float = ORIGIN_LON,
    origin_alt: float = ORIGIN_ALT,
) -> None:
    """Create or replace the GPS overlay window."""
    global _instance
    stop_gps_hud()
    _instance = _GpsHudController(
        body_prim_path=body_prim_path,
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        origin_alt=origin_alt,
    )
    print(f"[GPS HUD] Started — prim={body_prim_path!r} origin=({origin_lat}, {origin_lon}, {origin_alt})")


def stop_gps_hud() -> None:
    global _instance
    if _instance is not None:
        _instance.destroy()
        _instance = None
        print("[GPS HUD] Stopped.")


# Running the file from Script Editor executes show_gps_hud()
if __name__ in ("__main__", "__script__"):
    show_gps_hud()
