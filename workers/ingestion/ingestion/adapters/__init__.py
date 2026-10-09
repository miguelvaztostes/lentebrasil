from ingestion.adapters.cnes import CnesAdapter
from ingestion.adapters.ibge import IbgePopulationAdapter
from ingestion.adapters.siconfi import SiconfiRreoAdapter

ADAPTERS = {
    "ibge": IbgePopulationAdapter,
    "siconfi": SiconfiRreoAdapter,
    "cnes": CnesAdapter,
}

__all__ = ["ADAPTERS", "CnesAdapter", "IbgePopulationAdapter", "SiconfiRreoAdapter"]
