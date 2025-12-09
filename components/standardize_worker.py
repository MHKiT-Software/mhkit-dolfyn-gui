"""
Background worker for ADCP file conversion
"""

from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal


class ConversionWorker(QThread):
    """Background thread for file conversion to keep GUI responsive"""

    progress = pyqtSignal(str)  # Status messages
    finished = pyqtSignal(bool, str, object)  # Success flag, message, dataset

    def __init__(self, input_file, output_file, use_userdata, nens_value):
        super().__init__()
        self.input_file = input_file
        self.output_file = output_file
        self.use_userdata = use_userdata
        self.nens_value = nens_value

    def run(self):
        try:
            self.progress.emit("Importing mhkit.dolfyn...")
            import mhkit.dolfyn.io.api as dolfyn

            self.progress.emit(f"Reading ADCP file: {Path(self.input_file).name}")

            # Prepare kwargs
            kwargs = {}
            if self.nens_value > 0:
                kwargs['nens'] = self.nens_value

            # Read the ADCP file
            ds = dolfyn.read(
                self.input_file,
                userdata=self.use_userdata,
                **kwargs
            )

            self.progress.emit("Converting to NetCDF...")

            # Save as NetCDF
            dolfyn.save(ds, self.output_file)

            # Get dataset info
            dims_info = ", ".join([f"{k}={v}" for k, v in ds.dims.items()])
            vars_info = f"{len(ds.data_vars)} variables"

            success_msg = (
                f"✓ Conversion successful!\n\n"
                f"Output: {self.output_file}\n"
                f"Dimensions: {dims_info}\n"
                f"Variables: {vars_info}"
            )

            self.finished.emit(True, success_msg, ds)

        except Exception as e:
            error_msg = f"✗ Conversion failed:\n\n{str(e)}"
            self.finished.emit(False, error_msg, None)