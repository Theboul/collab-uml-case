"""
Utilidades de compresión y empaquetado ZIP para backend_case.
"""

import shutil
import tempfile
from pathlib import Path


def compress_folder_to_zip(folder_path: str | Path) -> Path:
    """
    Comprime una carpeta en un archivo ZIP temporal y devuelve su ruta.
    """
    base_name = tempfile.mktemp()
    zip_path = shutil.make_archive(base_name, "zip", str(folder_path))
    return Path(zip_path)
