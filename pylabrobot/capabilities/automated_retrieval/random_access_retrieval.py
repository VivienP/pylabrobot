import random
from typing import List, Literal, Optional, Union, cast

from pylabrobot.capabilities.automated_retrieval.automated_retrieval import AutomatedRetrieval
from pylabrobot.capabilities.capability import need_capability_ready
from pylabrobot.resources import (
  Plate,
  PlateCarrier,
  PlateHolder,
  ResourceNotFoundError,
)

from .backend import AutomatedRetrievalBackend


class NoFreeSiteError(Exception):
  pass


class RandomAccessRetrieval(AutomatedRetrieval):
  """Automated plate retrieval/storage capability (random access).

  Owns the storage racks and the loading tray(s), and implements the site
  bookkeeping (free-site counting, lookup and selection) shared by all
  random-access automated storage systems so devices composing this capability
  do not have to reimplement it. The loading tray and the shared plate-movement
  plumbing live on :class:`~pylabrobot.capabilities.automated_retrieval.AutomatedRetrieval`,
  which the sequential :class:`~pylabrobot.capabilities.automated_retrieval.StackerRetrieval`
  also uses (including the single/multi loading-tray handling and ``tray_index`` resolution).

  See :doc:`/user_guide/capabilities/automated-retrieval` for a walkthrough.
  """

  def __init__(
    self,
    backend: AutomatedRetrievalBackend,
    racks: Optional[List[PlateCarrier]] = None,
    loading_tray: Optional[PlateHolder] = None,
    loading_trays: Optional[List[PlateHolder]] = None,
  ):
    super().__init__(backend=backend, loading_tray=loading_tray, loading_trays=loading_trays)
    self.backend: AutomatedRetrievalBackend = backend
    self._racks: List[PlateCarrier] = racks if racks is not None else []

  @property
  def racks(self) -> List[PlateCarrier]:
    return self._racks

  # -- site bookkeeping --

  def get_num_free_sites(self) -> int:
    return sum(len(rack.get_free_sites()) for rack in self._racks)

  def get_site_by_plate_name(self, plate_name: str) -> PlateHolder:
    for rack in self._racks:
      for site in rack.sites.values():
        if site.resource is not None and site.resource.name == plate_name:
          return site
    raise ResourceNotFoundError(f"Plate {plate_name} not found in automated storage")

  def _find_available_sites_sorted(self, plate: Plate) -> List[PlateHolder]:
    """Find all sites that are free and fit the plate, sorted by size."""

    def _plate_height(p: Plate):
      if p.has_lid():
        # TODO: we can use plr nesting height
        # lid.location.z + lid.get_anchor(z="t").z
        return p.get_size_z() + 3
      return p.get_size_z()

    available = [
      site
      for rack in self._racks
      for site in rack.get_free_sites()
      if site.get_size_z() >= _plate_height(plate)
    ]
    if len(available) == 0:
      raise NoFreeSiteError(f"No free site found for plate '{plate.name}'")
    return sorted(available, key=lambda site: site.get_size_z())

  def find_smallest_site_for_plate(self, plate: Plate) -> PlateHolder:
    return self._find_available_sites_sorted(plate)[0]

  def find_random_site(self, plate: Plate) -> PlateHolder:
    return random.choice(self._find_available_sites_sorted(plate))

  # -- storage operations --

  @need_capability_ready
  async def fetch_plate_to_loading_tray(
    self, plate_name: str, tray_index: Optional[int] = None
  ) -> Plate:
    """Retrieve the named plate from storage onto loading tray ``tray_index``.

    ``tray_index=None`` uses the backend's default tray.
    """
    tray = self._loading_tray(tray_index)
    site = self.get_site_by_plate_name(plate_name)
    plate = cast(Plate, site.resource)
    await self.backend.fetch_plate_to_loading_tray(plate, tray_index=tray_index)
    plate.unassign()
    tray.assign_child_resource(plate)
    return plate

  @need_capability_ready
  async def take_in_plate(
    self,
    site: Union[PlateHolder, Literal["random", "smallest"]] = "smallest",
    tray_index: Optional[int] = None,
  ):
    """Take the plate from loading tray ``tray_index`` and store it into storage.

    `site` may be an explicit free `PlateHolder`, or `"smallest"`/`"random"` to
    let the capability pick a fitting free site. ``tray_index=None`` uses the
    backend's default tray.
    """
    plate = self._plate_on_loading_tray(tray_index)

    if site == "random":
      site = self.find_random_site(plate)
    elif site == "smallest":
      site = self.find_smallest_site_for_plate(plate)
    elif isinstance(site, PlateHolder):
      if site not in self._find_available_sites_sorted(plate):
        raise ValueError(f"Site {site.name} is not available for plate {plate.name}")
    else:
      raise ValueError(f"Invalid site: {site}")

    await self.backend.store_plate(plate, site, tray_index=tray_index)
    plate.unassign()
    site.assign_child_resource(plate)

  def summary(self) -> str:
    header = [f"Rack {i}" for i in range(len(self._racks))]
    sites = [
      [site.resource.name if site.resource else "<empty>" for site in reversed(rack.sites.values())]
      for rack in self._racks
    ]
    return self._pretty_table(header, *sites)

  async def _on_stop(self):
    await super()._on_stop()
