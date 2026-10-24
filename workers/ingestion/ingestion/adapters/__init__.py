from ingestion.adapters.cnes import CnesAdapter
from ingestion.adapters.datasus_health import (
    AnsBeneficiariesAdapter,
    CnesServicesAdapter,
    SiaProductionAdapter,
    SihProductionAdapter,
)
from ingestion.adapters.education import InepCensoEscolarAdapter, InepIdebAdapter
from ingestion.adapters.federal_education import FndePnaeAdapter, InepSaebAdapter
from ingestion.adapters.health import (
    CnesBedsAdapter,
    SimMortalityAdapter,
    SinascBirthsAdapter,
    SiopsHealthExpenseAdapter,
)
from ingestion.adapters.ibge import IbgePopulationAdapter
from ingestion.adapters.sectors import (
    IbgePibAdapter,
    NovoCagedAdapter,
    SenatranFleetAdapter,
)
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
    "siops_health_expenses": SiopsHealthExpenseAdapter,
    "sih_production": SihProductionAdapter,
    "sia_production": SiaProductionAdapter,
    "cnes_services": CnesServicesAdapter,
    "ans_beneficiaries": AnsBeneficiariesAdapter,
    "ibge_pib": IbgePibAdapter,
    "novo_caged": NovoCagedAdapter,
    "senatran_fleet": SenatranFleetAdapter,
}

__all__ = [
    "ADAPTERS",
    "AnsBeneficiariesAdapter",
    "CnesAdapter",
    "CnesBedsAdapter",
    "CnesServicesAdapter",
    "FndePnaeAdapter",
    "IbgePibAdapter",
    "IbgePopulationAdapter",
    "InepCensoEscolarAdapter",
    "InepIdebAdapter",
    "InepSaebAdapter",
    "NovoCagedAdapter",
    "PncpContractAdapter",
    "PncpProcurementAdapter",
    "SenatranFleetAdapter",
    "SiaProductionAdapter",
    "SiconfiRreoAdapter",
    "SiconfiStatementAdapter",
    "SihProductionAdapter",
    "SimMortalityAdapter",
    "SinascBirthsAdapter",
    "SiopsHealthExpenseAdapter",
    "TceSpExpenseAdapter",
    "TceSpRevenueAdapter",
]
