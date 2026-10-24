from models.orm import (
    Base,
    User,
    LabReport,
    BiomarkerRegistryModel,
    DrugRuleModel,
    DrugInteractionRule,
    SimulationCoefficient,
    HealthRecord,
    ChatLog,
    StressLog
)

# Backwards-compatibility aliases for routes expecting HealthReport / BiomarkerRecord
HealthReport = LabReport
BiomarkerRecord = HealthRecord