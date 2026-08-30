"""Keep PyTorch's NumPy compatibility modules outside PyInstaller's archive.

Some supported Python/PyTorch combinations corrupt module-scope loop names
when ``vars()`` is evaluated from frozen bytecode. Shipping this small package
as normal Python source lets the release builder apply its focused compatibility
rewrite without modifying the developer's installed PyTorch distribution.
"""

module_collection_mode = "py"
