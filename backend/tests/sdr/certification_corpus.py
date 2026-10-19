"""
HighView Semantic Data Refinery — Phase SDR-1
Certification Corpus Definition
"""

from typing import Any, NamedTuple
from app.services.ingestion_v2.contracts.semantics import (
    MeasureClass,
    SemanticColumnRole,
    SemanticConcept,
)
from app.services.sdr.contracts.decomposition import CompositePatternType
from app.services.sdr.contracts.profiles import (
    PrivacyClassification,
    SemanticDtype,
)


class CorpusColumn(NamedTuple):
    column_id: str
    column_name: str
    physical_dtype: str
    raw_values: list[Any]
    expected_semantic_dtype: SemanticDtype
    expected_semantic_role: SemanticColumnRole
    expected_concept: SemanticConcept
    expected_measure_class: MeasureClass | None
    expected_privacy: PrivacyClassification
    should_be_composite: bool
    expected_pattern_type: CompositePatternType | None
    is_false_split_target: bool  # If True, must NEVER be decomposed


CERTIFICATION_CORPUS: list[CorpusColumn] = [
    # 1. Simple numeric measure
    CorpusColumn(
        column_id="col_01",
        column_name="headcount",
        physical_dtype="int64",
        raw_values=[12, 15, 8, 22, 19, 45, 14, 30, 25, 18],
        expected_semantic_dtype=SemanticDtype.INTEGER_NUMBER,
        expected_semantic_role=SemanticColumnRole.MEASURE,
        expected_concept=SemanticConcept.MEASURE,
        expected_measure_class=MeasureClass.HEADCOUNT,
        expected_privacy=PrivacyClassification.GENERAL_ATTRIBUTE,
        should_be_composite=False,
        expected_pattern_type=None,
        is_false_split_target=False,
    ),

    # 2. Percentage
    CorpusColumn(
        column_id="col_02",
        column_name="attrition_rate",
        physical_dtype="float64",
        raw_values=["12.5%", "8.2%", "15.0%", "5.4%", "9.1%", "11.0%", "7.8%", "14.2%"],
        expected_semantic_dtype=SemanticDtype.PERCENTAGE_RATE,
        expected_semantic_role=SemanticColumnRole.MEASURE,
        expected_concept=SemanticConcept.MEASURE,
        expected_measure_class=MeasureClass.PERCENTAGE,
        expected_privacy=PrivacyClassification.GENERAL_ATTRIBUTE,
        should_be_composite=False,
        expected_pattern_type=None,
        is_false_split_target=False,
    ),

    # 3. Currency
    CorpusColumn(
        column_id="col_03",
        column_name="base_salary",
        physical_dtype="string",
        raw_values=["$85,000", "$92,000", "$110,000", "$78,500", "$125,000", "$95,000", "$88,000", "$105,000"],
        expected_semantic_dtype=SemanticDtype.CURRENCY_AMOUNT,
        expected_semantic_role=SemanticColumnRole.MEASURE,
        expected_concept=SemanticConcept.MEASURE,
        expected_measure_class=MeasureClass.FINANCIAL,
        expected_privacy=PrivacyClassification.SENSITIVE_ATTRIBUTE,
        should_be_composite=False,
        expected_pattern_type=None,
        is_false_split_target=False,
    ),

    # 4. Date/Time
    CorpusColumn(
        column_id="col_04",
        column_name="hire_date",
        physical_dtype="string",
        raw_values=["2022-03-15", "2021-08-01", "2023-01-10", "2020-11-20", "2022-06-18", "2023-04-05", "2019-09-12", "2021-12-01"],
        expected_semantic_dtype=SemanticDtype.DATE,
        expected_semantic_role=SemanticColumnRole.TIME,
        expected_concept=SemanticConcept.TIME_SPAN,
        expected_measure_class=None,
        expected_privacy=PrivacyClassification.GENERAL_ATTRIBUTE,
        should_be_composite=False,
        expected_pattern_type=None,
        is_false_split_target=True,  # Crucial: Must NEVER split ISO date on '-'
    ),

    # 5. Identifier-like column
    CorpusColumn(
        column_id="col_05",
        column_name="employee_id",
        physical_dtype="string",
        raw_values=["EMP-1001", "EMP-1002", "EMP-1003", "EMP-1004", "EMP-1005", "EMP-1006", "EMP-1007", "EMP-1008"],
        expected_semantic_dtype=SemanticDtype.IDENTIFIER_CODE,
        expected_semantic_role=SemanticColumnRole.ENTITY_IDENTIFIER,
        expected_concept=SemanticConcept.IDENTIFIER,
        expected_measure_class=None,
        expected_privacy=PrivacyClassification.DIRECT_IDENTIFIER,
        should_be_composite=False,
        expected_pattern_type=None,
        is_false_split_target=True,  # Crucial: Must NOT split single identifier token
    ),

    # 6. Categorical dimension
    CorpusColumn(
        column_id="col_06",
        column_name="department",
        physical_dtype="string",
        raw_values=["Engineering", "Sales", "Marketing", "Engineering", "HR", "Sales", "Engineering", "Finance", "Sales", "HR"],
        expected_semantic_dtype=SemanticDtype.CATEGORICAL_CODE,
        expected_semantic_role=SemanticColumnRole.DIMENSION,
        expected_concept=SemanticConcept.CATEGORICAL,
        expected_measure_class=None,
        expected_privacy=PrivacyClassification.GENERAL_ATTRIBUTE,
        should_be_composite=False,
        expected_pattern_type=None,
        is_false_split_target=False,
    ),

    # 7. Boolean
    CorpusColumn(
        column_id="col_07",
        column_name="is_remote",
        physical_dtype="string",
        raw_values=["true", "false", "true", "true", "false", "false", "true", "false"],
        expected_semantic_dtype=SemanticDtype.BOOLEAN_FLAG,
        expected_semantic_role=SemanticColumnRole.BOOLEAN,
        expected_concept=SemanticConcept.STATUS,
        expected_measure_class=None,
        expected_privacy=PrivacyClassification.GENERAL_ATTRIBUTE,
        should_be_composite=False,
        expected_pattern_type=None,
        is_false_split_target=False,
    ),

    # 8. Free text
    CorpusColumn(
        column_id="col_08",
        column_name="performance_notes",
        physical_dtype="string",
        raw_values=[
            "Exceeded quarterly delivery targets across all backend pipeline projects.",
            "Demonstrated excellent cross-functional collaboration with the design and product teams.",
            "Consistently delivers high quality, reliable code with zero regression bugs reported.",
            "Strong team player who actively mentors junior developers and improves team documentation.",
        ],
        expected_semantic_dtype=SemanticDtype.NATURAL_LANGUAGE_TEXT,
        expected_semantic_role=SemanticColumnRole.FREE_TEXT,
        expected_concept=SemanticConcept.FREE_TEXT,
        expected_measure_class=None,
        expected_privacy=PrivacyClassification.GENERAL_ATTRIBUTE,
        should_be_composite=False,
        expected_pattern_type=None,
        is_false_split_target=False,
    ),

    # 9. Geographic-looking column
    CorpusColumn(
        column_id="col_09",
        column_name="office_city",
        physical_dtype="string",
        raw_values=["London", "Bengaluru", "New York", "San Francisco", "Tokyo", "Berlin", "Singapore", "Sydney"],
        expected_semantic_dtype=SemanticDtype.GEOGRAPHIC_LOCATION,
        expected_semantic_role=SemanticColumnRole.LOCATION,
        expected_concept=SemanticConcept.LOCATION_ATTRIBUTE,
        expected_measure_class=None,
        expected_privacy=PrivacyClassification.GENERAL_ATTRIBUTE,
        should_be_composite=False,
        expected_pattern_type=None,
        is_false_split_target=True,  # Crucial: "New York" / "San Francisco" must not split on whitespace
    ),

    # 10. Composite Code + Label
    CorpusColumn(
        column_id="col_10",
        column_name="dept_assignment",
        physical_dtype="string",
        raw_values=[
            "ENG | Engineering",
            "SAL | Sales",
            "MKT | Marketing",
            "FIN | Finance",
            "OPS | Operations",
            "HRS | Human Resources",
        ],
        expected_semantic_dtype=SemanticDtype.COMPOSITE_TEXT,
        expected_semantic_role=SemanticColumnRole.DIMENSION,
        expected_concept=SemanticConcept.CATEGORICAL,
        expected_measure_class=None,
        expected_privacy=PrivacyClassification.GENERAL_ATTRIBUTE,
        should_be_composite=True,
        expected_pattern_type=CompositePatternType.CODE_LABEL_PAIR,
        is_false_split_target=False,
    ),

    # 11. Composite Geography String
    CorpusColumn(
        column_id="col_11",
        column_name="office_location",
        physical_dtype="string",
        raw_values=[
            "Bengaluru - Karnataka - India",
            "Mumbai - Maharashtra - India",
            "Austin - Texas - USA",
            "London - England - UK",
            "Berlin - Brandenburg - Germany",
            "Tokyo - Kanto - Japan",
        ],
        expected_semantic_dtype=SemanticDtype.COMPOSITE_TEXT,
        expected_semantic_role=SemanticColumnRole.LOCATION,
        expected_concept=SemanticConcept.LOCATION_ATTRIBUTE,
        expected_measure_class=None,
        expected_privacy=PrivacyClassification.GENERAL_ATTRIBUTE,
        should_be_composite=True,
        expected_pattern_type=CompositePatternType.GEOGRAPHIC_HIERARCHY,
        is_false_split_target=False,
    ),

    # 12. Compound Category (False Split Protection Target)
    CorpusColumn(
        column_id="col_12",
        column_name="business_unit",
        physical_dtype="string",
        raw_values=[
            "R&D / Innovation",
            "R&D / Innovation",
            "Sales / Marketing",
            "Sales / Marketing",
            "Strategy & Ops",
            "R&D / Innovation",
        ],
        expected_semantic_dtype=SemanticDtype.CATEGORICAL_CODE,
        expected_semantic_role=SemanticColumnRole.DIMENSION,
        expected_concept=SemanticConcept.CATEGORICAL,
        expected_measure_class=None,
        expected_privacy=PrivacyClassification.GENERAL_ATTRIBUTE,
        should_be_composite=False,
        expected_pattern_type=None,
        is_false_split_target=True,  # Crucial: Must NOT split compound category
    ),

    # 13. Phone Number (False Split Protection Target)
    CorpusColumn(
        column_id="col_13",
        column_name="contact_number",
        physical_dtype="string",
        raw_values=[
            "+91-9876543210",
            "+91-9876543211",
            "+1-800-555-0199",
            "+44-20-7946-0919",
            "+91-9876543214",
        ],
        expected_semantic_dtype=SemanticDtype.UNKNOWN,
        expected_semantic_role=SemanticColumnRole.UNKNOWN,
        expected_concept=SemanticConcept.UNKNOWN,
        expected_measure_class=None,
        expected_privacy=PrivacyClassification.GENERAL_ATTRIBUTE,
        should_be_composite=False,
        expected_pattern_type=None,
        is_false_split_target=True,  # Crucial: Must NEVER split phone on '-'
    ),

    # 14. Formatted Number with Commas (False Split Protection Target)
    CorpusColumn(
        column_id="col_14",
        column_name="monthly_volume",
        physical_dtype="string",
        raw_values=["1,250.50", "2,400.00", "850.75", "10,120.25", "5,500.00", "3,100.50"],
        expected_semantic_dtype=SemanticDtype.DECIMAL_NUMBER,
        expected_semantic_role=SemanticColumnRole.MEASURE,
        expected_concept=SemanticConcept.MEASURE,
        expected_measure_class=MeasureClass.QUANTITY,
        expected_privacy=PrivacyClassification.GENERAL_ATTRIBUTE,
        should_be_composite=False,
        expected_pattern_type=None,
        is_false_split_target=True,  # Crucial: Must NEVER split numeric comma
    ),

    # 15. Unknown Column (Responsible Abstention Target)
    CorpusColumn(
        column_id="col_15",
        column_name="zz_blob_payload",
        physical_dtype="string",
        raw_values=["qx88_9", "pl01_4", "mk77_2", "zx99_1", "bb44_8", "tr22_6"],
        expected_semantic_dtype=SemanticDtype.UNKNOWN,
        expected_semantic_role=SemanticColumnRole.UNKNOWN,
        expected_concept=SemanticConcept.UNKNOWN,
        expected_measure_class=None,
        expected_privacy=PrivacyClassification.GENERAL_ATTRIBUTE,
        should_be_composite=False,
        expected_pattern_type=None,
        is_false_split_target=False,
    ),
]
