import os
import unittest
import ast


class ImportModelTests(unittest.TestCase):
    @staticmethod
    def _import_api_source():
        path = os.path.join(
            os.path.dirname(__file__), "..", "app", "api", "import_api.py"
        )
        with open(path, "r", encoding="utf-8") as source_file:
            return source_file.read()

    @staticmethod
    def _analysis_score_bounds():
        path = os.path.join(
            os.path.dirname(__file__), "..", "app", "api", "import_api.py"
        )
        tree = ast.parse(ImportModelTests._import_api_source(), filename=path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or node.name != "AnalysisItem":
                continue
            bounds = {}
            for statement in node.body:
                if not isinstance(statement, ast.AnnAssign):
                    continue
                if not isinstance(statement.target, ast.Name):
                    continue
                if not isinstance(statement.value, ast.Call):
                    continue
                if not isinstance(statement.value.func, ast.Name):
                    continue
                if statement.value.func.id != "Field":
                    continue
                for keyword in statement.value.keywords:
                    if keyword.arg == "ge" and isinstance(keyword.value, ast.Constant):
                        bounds[statement.target.id] = keyword.value.value
            return bounds
        raise AssertionError("AnalysisItem 未定义")

    def test_analysis_scores_accept_zero_for_nontechnical_content(self):
        bounds = self._analysis_score_bounds()

        self.assertEqual(bounds["score_tech_depth"], 0.0)
        self.assertEqual(bounds["score_engineering"], 0.0)

    def test_reanalysis_updates_existing_article_batch_reference(self):
        source = self._import_api_source()

        self.assertIn(
            "existing_article.import_batch_id = batch.id",
            source,
        )


if __name__ == "__main__":
    unittest.main()
