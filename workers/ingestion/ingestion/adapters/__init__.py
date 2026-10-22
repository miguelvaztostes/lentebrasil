from ingestion.adapters.cnes import CnesAdapter
from ingestion.adapters.education import InepCensoEscolarAdapter, InepIdebAdapter
from ingestion.adapters.ibge import IbgePopulationAdapter
from ingestion.adapters.siconfi import SiconfiRreoAdapter

ADAPTERS = {
    "ibge": IbgePopulationAdapter,
    "siconfi": SiconfiRreoAdapter,
    "cnes": CnesAdapter,
    "censo_escolar": InepCensoEscolarAdapter,
    "ideb": InepIdebAdapter,
}

__all__ = [
    "ADAPTERS",
    "CnesAdapter",
    "IbgePopulationAdapter",
    "InepCensoEscolarAdapter",
    "InepIdebAdapter",
    "SiconfiRreoAdapter",
]
