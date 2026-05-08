# models/crypto_model.py
# CRYPTOEDGE - ML Ensemble Model
# XGBoost + LightGBM + RandomForest + CatBoost

import numpy as np
import pandas as pd
import joblib
import os
import logging
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_selection import SelectKBest, mutual_info_classif
import xgboost as xgb
import lightgbm as lgb

logger = logging.getLogger(__name__)

CACHE_DIR = 'model_cache'


class CryptoEnsemble:
    """
    4-model ensemble for crypto prediction.
    XGBoost + LightGBM + RandomForest + CatBoost
    """

    def __init__(self):
        self.models   = {}
        self.selector = None
        self.selected_features = []
        self.trained  = False

    def train(self, X, y):
        """Train all models."""
        logger.info(f"Training crypto ensemble on {len(X)} samples")

        if len(y.unique()) < 2:
            logger.warning("Only one class in target!")
            return self

        min_class = y.value_counts().min()
        n_folds   = max(2, min(5, min_class))

        # Feature selection
        self.selector = SelectKBest(
            score_func = mutual_info_classif,
            k          = min(20, X.shape[1])
        )
        self.selector.fit(X, y)
        mask = self.selector.get_support()
        self.selected_features = [
            f for f, m in zip(X.columns, mask) if m
        ]
        X_sel = X[self.selected_features]

        # XGBoost
        try:
            xgb_base = xgb.XGBClassifier(
                n_estimators     = 200,
                max_depth        = 3,
                learning_rate    = 0.01,
                subsample        = 0.8,
                colsample_bytree = 0.8,
                random_state     = 42,
                n_jobs           = 1,
                eval_metric      = 'logloss',
                verbosity        = 0,
            )
            if min_class >= 5:
                self.models['xgboost'] = CalibratedClassifierCV(
                    xgb_base, cv=n_folds, method='isotonic'
                )
            else:
                self.models['xgboost'] = xgb_base
            self.models['xgboost'].fit(X_sel, y)
            logger.info("XGBoost trained ✅")
        except Exception as e:
            logger.warning(f"XGBoost failed: {e}")

        # LightGBM
        try:
            lgb_base = lgb.LGBMClassifier(
                n_estimators     = 200,
                max_depth        = 4,
                learning_rate    = 0.01,
                subsample        = 0.8,
                colsample_bytree = 0.8,
                random_state     = 42,
                n_jobs           = 1,
                verbose          = -1,
            )
            if min_class >= 5:
                self.models['lightgbm'] = CalibratedClassifierCV(
                    lgb_base, cv=n_folds, method='isotonic'
                )
            else:
                self.models['lightgbm'] = lgb_base
            self.models['lightgbm'].fit(X_sel, y)
            logger.info("LightGBM trained ✅")
        except Exception as e:
            logger.warning(f"LightGBM failed: {e}")

        # RandomForest
        try:
            rf_base = RandomForestClassifier(
                n_estimators   = 200,
                max_depth      = 5,
                min_samples_leaf= 10,
                random_state   = 42,
                n_jobs         = 1,
            )
            if min_class >= 5:
                self.models['random_forest'] = CalibratedClassifierCV(
                    rf_base, cv=n_folds, method='isotonic'
                )
            else:
                self.models['random_forest'] = rf_base
            self.models['random_forest'].fit(X_sel, y)
            logger.info("RandomForest trained ✅")
        except Exception as e:
            logger.warning(f"RandomForest failed: {e}")

        # CatBoost
        try:
            from catboost import CatBoostClassifier
            cat_model = CatBoostClassifier(
                iterations    = 200,
                depth         = 4,
                learning_rate = 0.01,
                random_seed   = 42,
                verbose       = 0,
                thread_count  = 1,
            )
            cat_model.fit(X_sel, y)
            self.models['catboost'] = cat_model
            logger.info("CatBoost trained ✅")
        except Exception as e:
            logger.warning(f"CatBoost failed: {e}")

        self.trained = True
        logger.info(f"Ensemble complete: {len(self.models)} models")
        return self

    def predict(self, X):
        """Get ensemble prediction probability."""
        if not self.trained or not self.models:
            return 0.5

        try:
            X_sel = X[self.selected_features]
            probs = []

            for name, model in self.models.items():
                try:
                    prob = model.predict_proba(X_sel)[:, 1]
                    probs.append(prob)
                except Exception as e:
                    logger.warning(f"{name} prediction failed: {e}")

            if not probs:
                return 0.5

            return float(np.mean(probs))

        except Exception as e:
            logger.warning(f"Prediction failed: {e}")
            return 0.5

    def save(self, symbol):
        """Save models to cache."""
        os.makedirs(CACHE_DIR, exist_ok=True)
        safe_sym = symbol.replace('/', '_')
        try:
            joblib.dump(self.models, f'{CACHE_DIR}/{safe_sym}_models.joblib')
            joblib.dump(self.selected_features, f'{CACHE_DIR}/{safe_sym}_features.joblib')
            logger.info(f"Models saved for {symbol}")
        except Exception as e:
            logger.warning(f"Save failed for {symbol}: {e}")

    def load(self, symbol):
        """Load models from cache."""
        safe_sym = symbol.replace('/', '_')
        try:
            models_path   = f'{CACHE_DIR}/{safe_sym}_models.joblib'
            features_path = f'{CACHE_DIR}/{safe_sym}_features.joblib'

            if not os.path.exists(models_path):
                return False

            self.models            = joblib.load(models_path)
            self.selected_features = joblib.load(features_path)
            self.trained           = True
            logger.info(f"Models loaded for {symbol}")
            return True

        except Exception as e:
            logger.warning(f"Load failed for {symbol}: {e}")
            return False