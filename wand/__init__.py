"""
WAND - Wavemeter Analysis 'N' Display
"""
from pkg_resources import get_distribution, DistributionNotFound

try:
    __version__ = get_distribution(__package__).version
except DistributionNotFound:
    print("Please install WAnD using pip for full functionality")
    raise
else:
    VERSION = __package__ + '-' + __version__
