import os
import random
import json
import numpy as np
from sklearn.ensemble import RandomForestRegressor

from backend.services.model_registry import ModelRegistry
from backend.services.feature_engineering import FeatureEngineering


def synth_player_data():
    # create a synthetic player_data dict with recentGames of variable length
    n = random.randint(5, 12)
    recent = []
    base = random.uniform(10, 35)
    for i in range(n):
        # add some trend/noise
        val = base + (i * random.uniform(-0.5, 0.7)) + random.normalvariate(0, 3)
        recent.append({"gameDate": f"2025-11-{1+i:02d}", "statValue": float(round(val, 2))})
    seasonAvg = float(np.mean([g['statValue'] for g in recent]))
    return {
        'recentGames': recent,
        'seasonAvg': seasonAvg,
        'rollingAverages': {'last5Games': float(np.mean([g['statValue'] for g in recent[-5:]]))}
    }


def synth_opponent():
    return {'defensiveRating': float(random.uniform(95, 115)), 'pace': float(random.uniform(90, 105))}


def build_dataset(n_samples=200):
    X_list = []
    y_list = []
    fe = FeatureEngineering()
    for _ in range(n_samples):
        pd = synth_player_data()
        od = synth_opponent()
        df = fe.engineer_features(pd, od)
        # target is next-game stat: simulate as last game value plus noise
        last = pd['recentGames'][-1]['statValue']
        target = float(last + random.normalvariate(0, 2))
        X_list.append(df.iloc[0].values.astype(float))
        y_list.append(target)

    X = np.vstack(X_list)
    y = np.array(y_list)
    # return feature names too
    feature_names = list(df.columns)
    return X, y, feature_names


def main():
    random.seed(42)
    np.random.seed(42)

    print('Building dataset...')
    X, y, feature_names = build_dataset(300)
    print('Feature columns:', feature_names)
    print('Training RandomForest on engineered features...')
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X, y)

    # Save via ModelRegistry
    registry = ModelRegistry()
    player_name = os.environ.get('TOY_PLAYER_NAME', 'LeBron James')
    version = 'v1.real-features'
    notes = 'RandomForest trained on FeatureEngineering outputs (synthetic dataset)'
    registry.save_model(player_name, model, version=version, notes=notes)

    out = {
        'player': player_name,
        'version': version,
        'model_path': os.path.abspath(registry._model_path(player_name)),
        'feature_count': len(feature_names),
        'feature_names': feature_names,
    }
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    main()
