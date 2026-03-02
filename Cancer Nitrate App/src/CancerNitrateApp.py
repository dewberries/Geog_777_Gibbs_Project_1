import arcpy
from .ui import App

if __name__ == "__main__":
    try:
        arcpy.GetInstallInfo()
    except Exception:
        raise RuntimeError("ArcPy not available. Run using ArcGIS Pro Python environment.")
    App().mainloop()