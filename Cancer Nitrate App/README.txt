Project was created by Darbie Gibbs for University of Wisconsin GEOG 777 Spring 2026. 

The input datasets included in this project are mock / demonstration data created for academic purposes.
They are not intended to represent real-world health outcomes or environmental measurements and should 
not be used for policy, medical, or scientific decision-making.


Cancer–Nitrate Spatial Analysis Tool:
   
    - ArcPy + Tkinter application
    - Wisconsin Data is included
    - Runs IDW interpolation on well nitrate values
    - Calculates mean nitrate per census tract
    - Performs OLS regression (canrate ~ mean_nitrate)
    - Exports a regression report and static PNG map


Requirements:

    - ArcGIS Pro installed
    - Spatial Analyst extension enabled
    - Run using ArcGIS Pro Python environment

    If needed, install Pillow:
        python -m pip install pillow


How to Run:

    From the project root folder:
        python -m src.CancerNitrateApp

    Or use your ArcGIS Pro clone path:
        "C:\Users\<you>\AppData\Local\ESRI\conda\envs\arcgispro-py3-clone\python.exe" -m src.CancerNitrateApp

How to Use:

    - Enter k (> 1)
    - Select an output folder
    - Click Run

Output:

    - A new folder is created
    - GDB containing:
        - Copy of input layers
        - IDW raster
        - Joined tract feature class
    - Summary & Regression report (.txt)
    - Static map preview (.png)
