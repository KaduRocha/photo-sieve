"""
Suporte opcional a formatos adicionais (HEIC/HEIF).

HEIC é o formato padrão de fotos de iPhone. O suporte exige a dependência
opcional `pillow-heif` (`pip install "photo-sieve[heic]"`). Sem ela, arquivos
.heic/.heif são simplesmente ignorados pela varredura.
"""

BASE_EXTENSIONS = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".gif"}
)
HEIC_EXTENSIONS = frozenset({".heic", ".heif"})

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIC_SUPPORTED = True

except ImportError:
    HEIC_SUPPORTED = False

SUPPORTED_EXTENSIONS = (
    BASE_EXTENSIONS | HEIC_EXTENSIONS if HEIC_SUPPORTED else BASE_EXTENSIONS
)
