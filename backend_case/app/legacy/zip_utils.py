"""
Adaptador de compatibilidad legacy para utilidades de compresión ZIP.
Importa desde backend_case.app.shared.utils sin depender de Django.
"""

from backend_case.app.shared.utils.zip_utils import compress_folder_to_zip

__all__ = ["compress_folder_to_zip"]

