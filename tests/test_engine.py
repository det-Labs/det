"""Tests for the DataFusion-backed pipeline primitives."""

import tempfile
import unittest
from pathlib import Path

import pyarrow as pa

from det.engine import (
    analyze_dataframe,
    create_session_context,
    register_dataframe,
    run_sql,
    scan_file,
)


class DataFusionEngineTests(unittest.TestCase):
    def test_lazy_scans_and_registers_prior_sql_stages(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            sales_path = Path(temporary_directory) / "sales.csv"
            sales_path.write_text(
                "customer_id,amount\n1,100\n1,50\n2,30\n",
                encoding="utf-8",
            )

            context = create_session_context()
            sales = scan_file(context, sales_path)
            register_dataframe(context, "sales", sales)

            filtered_sales = run_sql(
                context,
                "SELECT customer_id, amount FROM sales WHERE amount >= 50",
            )
            register_dataframe(context, "filtered_sales", filtered_sales)

            totals = run_sql(
                context,
                "SELECT customer_id, SUM(amount) AS total "
                "FROM filtered_sales GROUP BY customer_id",
            )
            analysis = analyze_dataframe(totals)
            self.assertEqual(analysis.schema.names, ["customer_id", "total"])
            self.assertIsNotNone(analysis.logical_plan)
            self.assertIsNotNone(analysis.optimized_logical_plan)
            self.assertIsNotNone(analysis.execution_plan)

            result = pa.Table.from_batches(totals.collect())
            self.assertEqual(result.to_pydict(), {"customer_id": [1], "total": [150]})


if __name__ == "__main__":
    unittest.main()
