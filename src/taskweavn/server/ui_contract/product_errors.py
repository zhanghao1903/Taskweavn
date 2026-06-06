"""UI contract re-exports for product-level error taxonomy."""

from taskweavn.product_errors import (
    ProductErrorCategory,
    ProductErrorSeverity,
    ProductRecoveryAction,
    merge_product_error_details,
    product_error_details,
    product_error_details_for_api_error,
    product_error_details_for_llm_classification,
    product_error_details_for_task_failure,
)

__all__ = [
    "ProductErrorCategory",
    "ProductErrorSeverity",
    "ProductRecoveryAction",
    "merge_product_error_details",
    "product_error_details",
    "product_error_details_for_api_error",
    "product_error_details_for_llm_classification",
    "product_error_details_for_task_failure",
]
