from ingestion.adapters.cnes import CnesAdapter
from ingestion.adapters.education import InepCensoEscolarAdapter, InepIdebAdapter
from ingestion.adapters.federal_education import FndePnaeAdapter, InepSaebAdapter
from ingestion.adapters.health import (
    CnesBedsAdapter,
    SimMortalityAdapter,
    SinascBirthsAdapter,
)
from ingestion.adapters.ibge import IbgePopulationAdapter
from ingestion.adapters.siconfi import SiconfiRreoAdapter
from ingestion.adapters.transparency import (
    PncpContractAdapter,
    PncpProcurementAdapter,
    SiconfiStatementAdapter,
    TceSpExpenseAdapter,
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
    "tcesp_expenses": TceSpExpenseAdapter,
    "siconfi_rgf": SiconfiStatementAdapter,
    "siconfi_dca": SiconfiStatementAdapter,
    "sim_mortality": SimMortalityAdapter,
    "cnes_beds": CnesBedsAdapter,
    "sinasc_births": SinascBirthsAdapter,
}

__all__ = [
    "ADAPTERS",
    "CnesAdapter",
    "CnesBedsAdapter",
    "FndePnaeAdapter",
    "IbgePopulationAdapter",
    "InepCensoEscolarAdapter",
    "InepIdebAdapter",
    "InepSaebAdapter",
    "PncpContractAdapter",
    "PncpProcurementAdapter",
    "SiconfiRreoAdapter",
    "SiconfiStatementAdapter",
    "SimMortalityAdapter",
    "SinascBirthsAdapter",
    "TceSpExpenseAdapter",
    "TceSpRevenueAdapter",
]
