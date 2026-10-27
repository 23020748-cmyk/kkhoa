"""Separate process prevents FastDDS context recreation from affecting other tests."""
from pathlib import Path
import subprocess
import sys
import pytest


def test_timer_exception_publishes_zero_before_reraise():
    pytest.importorskip('rclpy')
    result = subprocess.run([sys.executable, str(Path(__file__).with_name('exception_probe.py'))],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout+result.stderr
    assert 'EXCEPTION_DDS_ZERO_VERIFIED' in result.stdout
