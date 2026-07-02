from abc import ABCMeta, abstractmethod
from typing import Optional

from pylabrobot.capabilities.capability import CapabilityBackend
from pylabrobot.resources import Plate, PlateHolder
from pylabrobot.resources.resource_stack import ResourceStack


class AutomatedRetrievalBackend(CapabilityBackend, metaclass=ABCMeta):
  """Abstract backend for random-access automated plate retrieval/storage devices."""

  @property
  def default_tray_index(self) -> int:
    """0-based index of the loading tray used when ``tray_index`` is ``None``.

    Single-tray devices use tray 0. Multi-tray devices override this to point at
    whichever tray they treat as the default; the capability resolves ``None`` to
    this same index for its resource bookkeeping, so both sides always agree on
    which physical tray a ``None`` request targets.
    """
    return 0

  @abstractmethod
  async def fetch_plate_to_loading_tray(self, plate: Plate, tray_index: Optional[int] = None):
    """Retrieve a plate from storage and place it on a loading tray.

    Args:
      plate: The plate to retrieve.
      tray_index: 0-based index of the loading tray to deliver the plate to. ``None``
        selects the device's default tray. Devices with a single loading tray
        accept ``None``/``0`` and reject any other value.
    """

  @abstractmethod
  async def store_plate(self, plate: Plate, site: PlateHolder, tray_index: Optional[int] = None):
    """Store a plate from a loading tray into the given site.

    Args:
      plate: The plate to store.
      site: The destination storage site.
      tray_index: 0-based index of the loading tray the plate is currently on. ``None``
        selects the device's default tray.
    """


class StackerBackend(CapabilityBackend, metaclass=ABCMeta):
  """Abstract backend for a sequential ("stacking access") plate stacker.

  A stacker stores plates in one or more single-ended LIFO stacks; only the accessible (top) plate
  of a stack can be moved without first moving the plates above it. The device exposes two
  transfers between a stack and the loading tray.
  """

  @property
  def default_tray_index(self) -> int:
    """0-based index of the loading tray used when ``tray_index`` is ``None`` (see
    :attr:`AutomatedRetrievalBackend.default_tray_index`)."""
    return 0

  @abstractmethod
  async def downstack(self, stack: ResourceStack, tray_index: Optional[int] = None):
    """Move the accessible (top) plate of ``stack`` onto a loading tray.

    ``tray_index=None`` selects the device's default tray.
    """

  @abstractmethod
  async def upstack(self, stack: ResourceStack, plate: Plate, tray_index: Optional[int] = None):
    """Move a plate from a loading tray onto ``stack``.

    ``tray_index=None`` selects the device's default tray.
    """
