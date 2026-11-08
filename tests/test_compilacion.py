import glob
import os
import py_compile
import warnings

import pytest

RAIZ = os.path.join(os.path.dirname(__file__), os.pardir)
ARCHIVOS = sorted(p for carpeta in ("scripts", "evaluacion") for p in glob.glob(os.path.join(RAIZ, carpeta, "**", "*.py"), recursive=True))


def test_hay_archivos_para_compilar():
    assert len(ARCHIVOS) > 10


@pytest.mark.parametrize("ruta", ARCHIVOS, ids=lambda r: os.path.relpath(r, RAIZ))
def test_compila_sin_errores_ni_advertencias_de_sintaxis(ruta, tmp_path):
    """Un error de sintaxis, o una secuencia de escape inválida, no puede pasar los tests."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")   # SyntaxWarning / DeprecationWarning del compilador pasan a ser errores
        py_compile.compile(ruta, cfile=str(tmp_path / "salida.pyc"), doraise=True)
