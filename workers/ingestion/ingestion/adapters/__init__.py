from ingestion.adapters.cnes import CnesAdapter
from ingestion.adapters.education import InepCensoEscolarAdapter, InepIdebAdapter
from ingestion.adapters.federal_education import FndePnaeAdapter, InepSaebAdapter
from ingestion.adapters.ibge import IbgePopulationAdapter
from ingestion.adapters.siconfi import SiconfiRreoAdapter
from ingestion.adapters.transparency import (
    PncpContractAdapter,
    PncpProcurementAdapter,
    SiconfiStatementAdapter,
    TceSpRevenueAdapter,
)

ADAPTERS = {
    "ibge": IbgePopulationAdapter,
    "siconfi": SiconfiRreoAdapter,
    "cnes": CnesAdapter,
    "censo_escolar": InepCensoEscolarAdapter,
    "ideb": InepIdebAdapter,
    "saeb": InepSaebAdapter,
    "fnde_pnae": FndePnaeAdapter,
    "pncp": PncpProcurementAdapter,
    "pncp_contracts": PncpContractAdapter,
    "tcesp_revenues": TceSpRevenueAdapter,
    "siconfi_rgf": SiconfiStatementAdapter,
    "siconfi_dca": SiconfiStatementAdapter,
}

__all__ = [
    "ADAPTERS",
    "CnesAdapter",
    "FndePnaeAdapter",
    "IbgePopulationAdapter",
    "InepCensoEscolarAdapter",
    "InepIdebAdapter",
    "InepSaebAdapter",
    "PncpContractAdapter",
    "PncpProcurementAdapter",
    "SiconfiRreoAdapter",
    "SiconfiStatementAdapter",
    "TceSpRevenueAdapter",
]
