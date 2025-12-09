"""
Batch file processor with error and progress tracking
"""

from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from enum import Enum

from PyQt6.QtCore import QThread, pyqtSignal


class PartitionMethod(Enum):
    """Time partitioning methods for splitting datasets"""

    NONE = "none"
    DURATION = "duration"
    TIME_OF_DAY = "time_of_day"
    ENSEMBLE_COUNT = "ensemble_count"


@dataclass
class StandardizeOptions:
    """Options for file standardization"""

    # Basic options
    use_userdata: bool = True
    nens: int = 0  # 0 = read all

    # Averaging
    apply_averaging: bool = True
    averaging_window: float = 300.0  # seconds

    # Time partitioning
    partition_method: PartitionMethod = PartitionMethod.NONE
    partition_duration_hours: float = 1.0
    partition_start_hour: int = 0
    partition_end_hour: int = 24
    partition_ensemble_count: int = 1000

    # Output naming
    output_pattern: str = "{input_name}.nc"
    output_directory: Optional[str] = None

    # Turbulence statistics
    compute_velds: bool = True  # U_mag, U_dir
    turbulence_stats: Dict[str, bool] = field(
        default_factory=lambda: {
            "dudz": False,
            "dvdz": False,
            "dwdz": False,
            "shear_squared": False,
            "reynolds_stress_4beam": False,
            "reynolds_stress_5beam": False,
            "dissipation_rate_LT83": False,
            "dissipation_rate_SF": False,
            "friction_velocity": False,
        }
    )


@dataclass
class FileResult:
    """Result of processing a single file"""

    input_file: str
    output_files: List[str]
    success: bool
    message: str
    partitions: int = 1


class OutputNamer:
    """Generates output filenames from pattern with token substitution"""

    TOKENS = {
        "{input_name}": lambda ctx: ctx["input_stem"],
        "{date}": lambda ctx: ctx.get("start_time", "").strftime("%Y-%m-%d")
        if ctx.get("start_time")
        else "unknown",
        "{time}": lambda ctx: ctx.get("start_time", "").strftime("%H-%M-%S")
        if ctx.get("start_time")
        else "unknown",
        "{datetime}": lambda ctx: ctx.get("start_time", "").strftime(
            "%Y-%m-%d_%H-%M-%S"
        )
        if ctx.get("start_time")
        else "unknown",
        "{partition}": lambda ctx: f"{ctx.get('partition', 1):03d}",
        "{duration}": lambda ctx: f"{ctx.get('duration_hours', 0):.1f}h",
    }

    @classmethod
    def generate(cls, pattern: str, context: dict) -> str:
        """Generate filename from pattern and context"""
        result = pattern
        for token, fn in cls.TOKENS.items():
            if token in result:
                try:
                    result = result.replace(token, str(fn(context)))
                except Exception:
                    result = result.replace(token, "unknown")
        return result

    @classmethod
    def preview(cls, pattern: str, example_stem: str = "Sig1000_tidal") -> str:
        """Generate preview with example values"""
        from datetime import datetime

        context = {
            "input_stem": example_stem,
            "start_time": datetime(2024, 1, 15, 8, 30, 0),
            "partition": 1,
            "duration_hours": 2.5,
        }
        return cls.generate(pattern, context)


class TimePartitioner:
    """Splits xarray dataset by time criteria"""

    @staticmethod
    def by_duration(ds, hours: float):
        """Split dataset into chunks of N hours each

        Args:
            ds: xarray Dataset with 'time' coordinate
            hours: Duration of each partition in hours

        Yields:
            Tuple of (partition_number, partition_dataset, start_time)
        """
        import pandas as pd

        if "time" not in ds.coords:
            yield (1, ds, None)
            return

        times = pd.to_datetime(ds.time.values)
        if len(times) == 0:
            yield (1, ds, None)
            return

        start_time = times[0]
        end_time = times[-1]
        duration = pd.Timedelta(hours=hours)

        partition = 1
        current_start = start_time

        while current_start < end_time:
            current_end = current_start + duration
            mask = (times >= current_start) & (times < current_end)

            if mask.any():
                partition_ds = ds.isel(time=mask)
                yield (partition, partition_ds, current_start)
                partition += 1

            current_start = current_end

    @staticmethod
    def by_time_of_day(ds, start_hour: int, end_hour: int):
        """Extract daily windows between start and end hour

        Args:
            ds: xarray Dataset with 'time' coordinate
            start_hour: Start hour (0-23)
            end_hour: End hour (0-24)

        Yields:
            Tuple of (partition_number, partition_dataset, start_time)
        """
        import pandas as pd

        if "time" not in ds.coords:
            yield (1, ds, None)
            return

        times = pd.to_datetime(ds.time.values)
        if len(times) == 0:
            yield (1, ds, None)
            return

        # Group by date
        dates = times.normalize().unique()

        partition = 1
        for date in dates:
            day_start = date + pd.Timedelta(hours=start_hour)
            day_end = date + pd.Timedelta(hours=end_hour)

            mask = (times >= day_start) & (times < day_end)

            if mask.any():
                partition_ds = ds.isel(time=mask)
                yield (partition, partition_ds, day_start)
                partition += 1

    @staticmethod
    def by_ensemble_count(ds, count: int):
        """Split into fixed ensemble counts

        Args:
            ds: xarray Dataset with 'time' coordinate
            count: Number of ensembles per partition

        Yields:
            Tuple of (partition_number, partition_dataset, start_time)
        """
        import pandas as pd

        if "time" not in ds.coords:
            yield (1, ds, None)
            return

        n_times = len(ds.time)
        if n_times == 0:
            yield (1, ds, None)
            return

        times = pd.to_datetime(ds.time.values)

        partition = 1
        for i in range(0, n_times, count):
            end_idx = min(i + count, n_times)
            partition_ds = ds.isel(time=slice(i, end_idx))
            start_time = times[i] if i < len(times) else None
            yield (partition, partition_ds, start_time)
            partition += 1


class BatchStandardizeWorker(QThread):
    """Worker thread for batch file standardization"""

    # Signals
    batchStarted = pyqtSignal(int)  # total_files
    fileStarted = pyqtSignal(str, int, int)  # filename, current, total
    fileProgress = pyqtSignal(str, str)  # filename, message
    fileCompleted = pyqtSignal(
        str, bool, str, list
    )  # filename, success, message, output_files
    batchCompleted = pyqtSignal(dict)  # summary with success/failed lists

    def __init__(self, files: List[str], options: StandardizeOptions, parent=None):
        super().__init__(parent)
        self.files = files
        self.options = options
        self.results: Dict[str, FileResult] = {}
        self._cancelled = False

    def cancel(self):
        """Request cancellation of batch processing"""
        self._cancelled = True

    def run(self):
        """Process all files"""
        self.batchStarted.emit(len(self.files))

        for i, filepath in enumerate(self.files):
            if self._cancelled:
                break

            filename = Path(filepath).name
            self.fileStarted.emit(filename, i + 1, len(self.files))

            try:
                result = self._process_single_file(filepath)
                self.results[filepath] = result
                self.fileCompleted.emit(
                    filename, result.success, result.message, result.output_files
                )
            except Exception as e:
                result = FileResult(
                    input_file=filepath, output_files=[], success=False, message=str(e)
                )
                self.results[filepath] = result
                self.fileCompleted.emit(filename, False, str(e), [])

        # Compile summary
        summary = {
            "total": len(self.files),
            "success": [f for f, r in self.results.items() if r.success],
            "failed": [
                (f, r.message) for f, r in self.results.items() if not r.success
            ],
            "cancelled": self._cancelled,
        }
        self.batchCompleted.emit(summary)

    def _process_single_file(self, filepath: str) -> FileResult:
        """Process a single file with all options applied"""
        from mhkit.dolfyn.io import api as dolfyn_io
        from mhkit.dolfyn.adp import api as adp_api

        input_path = Path(filepath)
        self.fileProgress.emit(input_path.name, "Reading file...")

        # Read the file
        read_kwargs = {}
        if self.options.use_userdata:
            read_kwargs["userdata"] = True
        if self.options.nens > 0:
            read_kwargs["nens"] = self.options.nens

        ds = dolfyn_io.read(filepath, **read_kwargs)

        # Determine output directory
        if self.options.output_directory:
            output_dir = Path(self.options.output_directory)
        else:
            output_dir = input_path.parent

        # Handle partitioning
        if self.options.partition_method == PartitionMethod.NONE:
            partitions = [(1, ds, None)]
        elif self.options.partition_method == PartitionMethod.DURATION:
            partitions = list(
                TimePartitioner.by_duration(ds, self.options.partition_duration_hours)
            )
        elif self.options.partition_method == PartitionMethod.TIME_OF_DAY:
            partitions = list(
                TimePartitioner.by_time_of_day(
                    ds,
                    self.options.partition_start_hour,
                    self.options.partition_end_hour,
                )
            )
        elif self.options.partition_method == PartitionMethod.ENSEMBLE_COUNT:
            partitions = list(
                TimePartitioner.by_ensemble_count(
                    ds, self.options.partition_ensemble_count
                )
            )
        else:
            partitions = [(1, ds, None)]

        output_files = []

        for partition_num, partition_ds, start_time in partitions:
            self.fileProgress.emit(
                input_path.name,
                f"Processing partition {partition_num}/{len(partitions)}...",
            )

            processed_ds = partition_ds

            # Apply averaging if requested
            if self.options.apply_averaging:
                self.fileProgress.emit(input_path.name, "Applying bin averaging...")
                fs = float(processed_ds.fs) if hasattr(processed_ds, "fs") else 1.0
                n_bin = int(fs * self.options.averaging_window)

                binner = adp_api.ADPBinner(n_bin=n_bin, fs=fs)
                processed_ds = binner.bin_average(processed_ds)

            # Compute velocity derivatives (velds)
            if self.options.compute_velds:
                self.fileProgress.emit(
                    input_path.name, "Computing velocity magnitude/direction..."
                )
                try:
                    # Access velds to trigger computation
                    _ = processed_ds.velds.U_mag
                    _ = processed_ds.velds.U_dir
                except Exception:
                    pass  # velds may not be available for all data types

            # Compute selected turbulence statistics
            self._compute_turbulence_stats(processed_ds, input_path.name)

            # Generate output filename
            context = {
                "input_stem": input_path.stem,
                "start_time": start_time,
                "partition": partition_num,
                "duration_hours": self.options.partition_duration_hours
                if self.options.partition_method == PartitionMethod.DURATION
                else 0,
            }
            output_name = OutputNamer.generate(self.options.output_pattern, context)
            if not output_name.endswith(".nc"):
                output_name += ".nc"

            output_path = output_dir / output_name

            # Save
            self.fileProgress.emit(input_path.name, f"Saving {output_name}...")
            dolfyn_io.save(processed_ds, str(output_path))
            output_files.append(str(output_path))

        return FileResult(
            input_file=filepath,
            output_files=output_files,
            success=True,
            message=f"Standardized to {len(output_files)} file(s)",
            partitions=len(partitions),
        )

    def _compute_turbulence_stats(self, ds, filename: str):
        """Compute selected turbulence statistics"""
        from mhkit.dolfyn.adp import api as adp_api

        stats = self.options.turbulence_stats

        # Need a binner for turbulence calculations
        if not any(stats.values()):
            return

        try:
            fs = float(ds.fs) if hasattr(ds, "fs") else 1.0
            n_bin = int(fs * self.options.averaging_window)
            binner = adp_api.ADPBinner(n_bin=n_bin, fs=fs)

            if stats.get("dudz"):
                self.fileProgress.emit(filename, "Computing dudz...")
                try:
                    ds["dudz"] = binner.dudz(ds)
                except Exception:
                    pass

            if stats.get("dvdz"):
                self.fileProgress.emit(filename, "Computing dvdz...")
                try:
                    ds["dvdz"] = binner.dvdz(ds)
                except Exception:
                    pass

            if stats.get("dwdz"):
                self.fileProgress.emit(filename, "Computing dwdz...")
                try:
                    ds["dwdz"] = binner.dwdz(ds)
                except Exception:
                    pass

            if stats.get("shear_squared"):
                self.fileProgress.emit(filename, "Computing shear squared...")
                try:
                    ds["shear_squared"] = binner.shear_squared(ds)
                except Exception:
                    pass

            if stats.get("reynolds_stress_4beam"):
                self.fileProgress.emit(
                    filename, "Computing Reynolds stress (4-beam)..."
                )
                try:
                    ds["reynolds_stress_4beam"] = binner.reynolds_stress_4beam(ds)
                except Exception:
                    pass

            if stats.get("reynolds_stress_5beam"):
                self.fileProgress.emit(
                    filename, "Computing Reynolds stress (5-beam)..."
                )
                try:
                    ds["stress_tensor_5beam"] = binner.stress_tensor_5beam(ds)
                except Exception:
                    pass

            if stats.get("dissipation_rate_LT83"):
                self.fileProgress.emit(filename, "Computing dissipation rate (LT83)...")
                try:
                    ds["dissipation_rate_LT83"] = binner.dissipation_rate_LT83(ds)
                except Exception:
                    pass

            if stats.get("dissipation_rate_SF"):
                self.fileProgress.emit(filename, "Computing dissipation rate (SF)...")
                try:
                    ds["dissipation_rate_SF"] = binner.dissipation_rate_SF(ds)
                except Exception:
                    pass

            if stats.get("friction_velocity"):
                self.fileProgress.emit(filename, "Computing friction velocity...")
                try:
                    ds["friction_velocity"] = binner.friction_velocity(ds)
                except Exception:
                    pass

        except Exception:
            pass  # Turbulence stats are optional
