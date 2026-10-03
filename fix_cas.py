import h5py

case_path = r"D:\Trial1_hemisphere_files\dp0\FFF-1\Fluent\FFF-1-Setup-Output.cas.h5"
try:
    with h5py.File(case_path, "r") as f:
        print("Keys in settings:", list(f["settings"].keys()))
except Exception as e:
    print(e)

