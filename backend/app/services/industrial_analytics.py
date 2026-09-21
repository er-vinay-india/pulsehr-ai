"""Industrial People Analytics & Workforce Science Engine.

Re-exports formula-grounded industrial HR models:
1. Bradford Factor Absenteeism Disruption Index (B = S^2 * D)
2. McKinsey / GE 9-Box Talent Performance-Potential & Risk Matrix
3. Workforce Workload & Burnout Strain Index
4. Cross-Sheet Statistical Elasticity & Tipping Point Regression
5. Automated Ingestion Pipeline Execution
"""

from .industrial import (
    clean_num,
    calculate_bradford_factor,
    calculate_9box_matrix,
    calculate_burnout_strain_index,
    calculate_cross_sheet_elasticity,
    run_ingestion_industrial_pipeline,
)

__all__ = [
    "clean_num",
    "calculate_bradford_factor",
    "calculate_9box_matrix",
    "calculate_burnout_strain_index",
    "calculate_cross_sheet_elasticity",
    "run_ingestion_industrial_pipeline",
]
