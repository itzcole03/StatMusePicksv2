# Prediction API Examples

This document contains quick examples for calling the prediction API (`/api/predict`) using `curl` and a minimal Postman collection.

## curl

Simple POST with JSON body:

```bash
curl -X POST "http://localhost:8000/api/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "player": "LeBron James",
    "stat": "points",
    "line": 25.5,
    "player_data": { "rollingAverages": { "last5Games": 27.0 }, "seasonAvg": 27.0 },
    "opponent_data": {}
  }'
```

Sample successful response (wrapper + merged top-level keys):

```json
{
  "ok": true,
  "prediction": {
    "player": "LeBron James",
    "stat": "points",
    "line": 25.5,
    "predicted_value": 27.3,
    "over_probability": 0.68,
    "under_probability": 0.32,
    "recommendation": "OVER",
    "expected_value": 0.18,
    "confidence": 68.0
  },
  "player": "LeBron James",
  "stat": "points",
  "line": 25.5,
  "predicted_value": 27.3,
  "over_probability": 0.68,
  "under_probability": 0.32,
  "recommendation": "OVER",
  "expected_value": 0.18,
  "confidence": 68.0
}
```

If your backend is configured with an API key or different host/port, update the URL and headers accordingly.

## Postman

Below is a minimal Postman collection JSON you can import into Postman. It contains a single request for `/api/predict`.

Save this as `postman_predict_collection.json` and import into Postman (File → Import).

```json
{
  "info": {
    "name": "StatMusePicks - Predict",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Predict",
      "request": {
        "method": "POST",
        "header": [
          { "key": "Content-Type", "value": "application/json" }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"player\": \"LeBron James\",\n  \"stat\": \"points\",\n  \"line\": 25.5,\n  \"player_data\": { \"rollingAverages\": { \"last5Games\": 27.0 }, \"seasonAvg\": 27.0 },\n  \"opponent_data\": {}\n}"
        },
        "url": {
          "raw": "http://localhost:8000/api/predict",
          "protocol": "http",
          "host": ["localhost"],
          "port": "8000",
          "path": ["api","predict"]
        }
      }
    },
    {
      "name": "Batch Predict",
      "request": {
        "method": "POST",
        "header": [
          { "key": "Content-Type", "value": "application/json" }
        ],
        "body": {
          "mode": "raw",
          "raw": "[\n  { \"player\": \"LeBron James\", \"stat\": \"points\", \"line\": 25.5 },\n  { \"player\": \"Stephen Curry\", \"stat\": \"points\", \"line\": 29.5 }\n]"
        },
        "url": {
          "raw": "http://localhost:8000/api/batch_predict",
          "protocol": "http",
          "host": ["localhost"],
          "port": "8000",
          "path": ["api","batch_predict"]
        }
      }
    }
  ]
}
```

## Batch predict example

Curl example for batch predictions:

```bash
curl -X POST "http://localhost:8000/api/batch_predict" \
  -H "Content-Type: application/json" \
  -d '[
    { "player": "LeBron James", "stat": "points", "line": 25.5 },
    { "player": "Stephen Curry", "stat": "points", "line": 29.5 }
  ]'
```

Sample batch response:

```json
{
  "predictions": [
    {
      "player": "LeBron James",
      "stat": "points",
      "line": 25.5,
      "predicted_value": 27.3,
      "over_probability": 0.68,
      "under_probability": 0.32,
      "recommendation": "OVER",
      "expected_value": 0.18,
      "confidence": 68.0
    },
    {
      "player": "Stephen Curry",
      "stat": "points",
      "line": 29.5,
      "predicted_value": 28.1,
      "over_probability": 0.42,
      "under_probability": 0.58,
      "recommendation": "UNDER",
      "expected_value": -0.08,
      "confidence": 42.0
    }
  ]
}
```

## Notes

- The OpenAPI docs are available at `http://localhost:8000/docs` when the backend is running. The request example is embedded in the schema and will show up in the Try-It UI.
- For CI or scripted tests, prefer `curl` or `pytest` tests as shown in the repo's `backend/tests/` directory.
