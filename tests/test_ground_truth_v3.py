import os
import shutil
import subprocess
import sys

AQUI = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "evaluacion")


def test_build_gt_v3_regenerado_es_identico_al_csv_versionado(tmp_path):
    """Se corre una COPIA del script en una carpeta temporal (escribe junto a __file__), así que ground_truth_v3.csv no se toca."""
    copia = tmp_path / "build_gt_v3.py"
    shutil.copy(os.path.join(AQUI, "build_gt_v3.py"), copia)
    r = subprocess.run([sys.executable, str(copia)], capture_output=True, text=True, cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr
    regenerado = (tmp_path / "ground_truth_v3.csv").read_bytes().replace(b"\r\n", b"\n")
    versionado = open(os.path.join(AQUI, "ground_truth_v3.csv"), "rb").read().replace(b"\r\n", b"\n")
    assert regenerado == versionado, "ground_truth_v3.csv no coincide con lo que genera build_gt_v3.py (¿se editó uno a mano?)"
