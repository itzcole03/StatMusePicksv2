import json
import os

from backend.services.calibration_service import CalibrationService


def test_calibration_report_written(tmp_path, monkeypatch):
    # Ensure ModelRegistry uses tmp_path as model_dir so reports go there
    monkeypatch.setenv("MODEL_STORE_DIR", str(tmp_path))
    # The CalibrationService default registry reads environment? It uses ModelRegistry default,
    # so override registry.model_dir after construction.
    svc = CalibrationService()
    svc.registry.model_dir = str(tmp_path)

    # create simple synthetic probabilistic data
    y_true = [0, 1, 1, 0, 1]
    y_pred = [0.1, 0.9, 0.8, 0.2, 0.7]

    res = svc.fit_and_save("Report Test Player", y_true, y_pred, method="isotonic")
    # find reports dir
    reports_dir = os.path.join(svc.registry.model_dir, "calibrator_reports")
    assert os.path.isdir(reports_dir)
    files = [f for f in os.listdir(reports_dir) if f.endswith(".json")]
    assert len(files) >= 1
    # load the latest report
    files.sort()
    path = os.path.join(reports_dir, files[-1])
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    assert data.get("player") == "Report Test Player"
    assert "before" in data and "after" in data
