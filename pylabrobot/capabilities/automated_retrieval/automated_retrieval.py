from typing import List, Optional

from pylabrobot.capabilities.capability import Capability, CapabilityBackend
from pylabrobot.resources import Plate, PlateHolder, ResourceNotFoundError


class AutomatedRetrieval(Capability):
  """Shared base for storage-retrieval capabilities that move plates to and from one or more
  transfer positions -- the "loading tray(s)".

  Concrete capabilities differ only in how storage locations are addressed:

  * :class:`~pylabrobot.capabilities.automated_retrieval.RandomAccessRetrieval` is *random access*
    -- individually addressable rack sites.
  * :class:`~pylabrobot.capabilities.automated_retrieval.StackerRetrieval` is *sequential* --
    single-ended LIFO stacks.

  This base owns the loading tray(s) and the small amount of plate-movement plumbing the two share
  (loading-tray resolution and the summary table), so the concrete capabilities only implement
  their location-addressing logic.

  Most devices have a single loading tray (pass ``loading_tray``). Devices with several transfer
  nests pass ``loading_trays`` -- one :class:`PlateHolder` per nest -- and address them by
  ``tray_index`` (0-based). ``tray_index=None`` resolves to the backend's ``default_tray_index``
  (falling back to the first tray), the same index the backend resolves ``None`` to, so the
  resource tree and the hardware always agree on which tray a ``None`` request targets.
  """

  def __init__(
    self,
    backend: CapabilityBackend,
    loading_tray: Optional[PlateHolder] = None,
    loading_trays: Optional[List[PlateHolder]] = None,
  ):
    super().__init__(backend=backend)
    if loading_tray is not None and loading_trays is not None:
      raise ValueError("Pass either loading_tray or loading_trays, not both.")
    if loading_trays is None:
      loading_trays = [loading_tray] if loading_tray is not None else []
    self.loading_trays: List[PlateHolder] = loading_trays

  @property
  def loading_tray(self) -> Optional[PlateHolder]:
    """The default loading tray (single-tray convenience accessor)."""
    if not self.loading_trays:
      return None
    return self.loading_trays[self._default_tray_index()]

  def _default_tray_index(self) -> int:
    # Tray-having backends expose ``default_tray_index``; fall back to the first tray.
    return getattr(self.backend, "default_tray_index", 0)

  def _loading_tray(self, tray_index: Optional[int] = None) -> PlateHolder:
    """Resolve a (possibly ``None``) ``tray_index`` to a configured loading tray.

    ``None`` maps to the backend's ``default_tray_index`` -- the same index the backend resolves
    ``None`` to -- so bookkeeping and motion stay in sync.
    """
    if not self.loading_trays:
      raise RuntimeError("No loading tray configured for this capability.")
    idx = self._default_tray_index() if tray_index is None else tray_index
    if not 0 <= idx < len(self.loading_trays):
      raise ValueError(
        f"tray_index {idx} out of range; this device has "
        f"{len(self.loading_trays)} loading tray(s)."
      )
    return self.loading_trays[idx]

  def _require_loading_tray(self, tray_index: Optional[int] = None) -> PlateHolder:
    return self._loading_tray(tray_index)

  def _plate_on_loading_tray(self, tray_index: Optional[int] = None) -> Plate:
    tray = self._loading_tray(tray_index)
    plate = tray.resource
    if not isinstance(plate, Plate):
      raise ResourceNotFoundError("No plate on the loading tray.")
    return plate

  @staticmethod
  def _pretty_table(header, *columns) -> str:
    col_widths = [
      max(len(str(item)) for item in [header[i]] + list(columns[i])) for i in range(len(header))
    ]

    def format_row(row, border="|") -> str:
      return (
        f"{border} "
        + " | ".join(f"{str(row[i]).ljust(col_widths[i])}" for i in range(len(row)))
        + f" {border}"
      )

    def separator_line(cross: str = "+", line: str = "-") -> str:
      return cross + cross.join(line * (width + 2) for width in col_widths) + cross

    table = [separator_line(), format_row(header), separator_line()]
    for row in zip(*columns):
      table.append(format_row(row))
    table.append(separator_line())
    return "\n".join(table)
