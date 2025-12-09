#!/usr/bin/env python
"""
Pytest test suite for MHKiT DOLFyN ADCP Converter

Tests the bundled application to verify:
1. The app executable launches successfully
2. The app runs without crashing (validates library bundling)

Run with: pytest tests/gui/test_conversion.py -v
"""

import sys
import os
import subprocess
import tempfile
from pathlib import Path

import pytest


# Project root directory (two levels up from this file)
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Test data path
TEST_DATA_DIR = PROJECT_ROOT / "data" / "test"
TEST_FILE = TEST_DATA_DIR / "Sig1000_tidal.ad2cp"


def get_app_executable():
    """Find the bundled application executable based on platform"""
    if sys.platform == "darwin":
        return PROJECT_ROOT / "dist/MHKiT-DOLFyN.app/Contents/MacOS/MHKiT-DOLFyN"
    elif sys.platform == "win32":
        return PROJECT_ROOT / "dist/MHKiT-DOLFyN/MHKiT-DOLFyN.exe"
    else:  # Linux
        return PROJECT_ROOT / "dist/MHKiT-DOLFyN/MHKiT-DOLFyN"


class TestBundledApp:
    """Tests for the bundled application"""

    def test_app_executable_exists(self):
        """Test that the bundled app executable exists"""
        app_path = get_app_executable()
        assert app_path.exists(), f"App not found at: {app_path}"

    def test_app_launches_successfully(self):
        """Test that the bundled app launches and runs without crashing"""
        app_path = get_app_executable()

        if not app_path.exists():
            pytest.skip(f"App not built yet: {app_path}")

        # Set environment for headless operation
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"

        # Launch app
        proc = subprocess.Popen(
            [str(app_path)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        try:
            # Wait to see if it crashes on startup
            proc.wait(timeout=10)

            # If it exited within 10 seconds, it likely crashed
            if proc.returncode != 0:
                stderr = proc.stderr.read().decode("utf-8", errors="replace")
                pytest.fail(f"App exited with code {proc.returncode}: {stderr[:500]}")

        except subprocess.TimeoutExpired:
            # App is still running after 10 seconds - success!
            proc.terminate()
            proc.wait(timeout=5)

    def test_test_data_exists(self):
        """Test that test data file exists"""
        assert TEST_FILE.exists(), f"Test file not found: {TEST_FILE}"


class TestConversionLibrary:
    """Tests for the conversion library (mhkit.dolfyn)

    These tests run against the development environment, not the bundled app.
    They may be skipped if there are library compatibility issues.
    """

    @pytest.fixture(autouse=True)
    def check_library_available(self):
        """Skip tests if mhkit.dolfyn is not importable"""
        try:
            import mhkit.dolfyn.io.api
        except ImportError as e:
            pytest.skip(f"mhkit.dolfyn not available: {e}")

    def test_import_dolfyn(self):
        """Test that mhkit.dolfyn can be imported"""
        import mhkit.dolfyn.io.api as dolfyn

        assert dolfyn is not None

    def test_read_adcp_file(self):
        """Test reading an ADCP file"""
        if not TEST_FILE.exists():
            pytest.skip(f"Test file not found: {TEST_FILE}")

        import mhkit.dolfyn.io.api as dolfyn

        ds = dolfyn.read(str(TEST_FILE), userdata=False)

        assert ds is not None
        assert len(ds.dims) > 0
        assert len(ds.data_vars) > 0

    def test_convert_to_netcdf(self):
        """Test full conversion from ADCP to NetCDF"""
        if not TEST_FILE.exists():
            pytest.skip(f"Test file not found: {TEST_FILE}")

        import mhkit.dolfyn.io.api as dolfyn

        # Read the file
        ds = dolfyn.read(str(TEST_FILE), userdata=False)

        # Create temp output file
        with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as tmp:
            output_file = Path(tmp.name)

        try:
            # Save as NetCDF
            dolfyn.save(ds, str(output_file))

            # Verify output
            assert output_file.exists(), "Output file was not created"
            assert output_file.stat().st_size > 0, "Output file is empty"

        finally:
            # Cleanup
            if output_file.exists():
                output_file.unlink()


# Allow running as a script for backwards compatibility
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
