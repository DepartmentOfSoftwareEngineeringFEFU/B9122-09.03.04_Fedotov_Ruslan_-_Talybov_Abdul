# app/services/ml_service.py
import numpy as np
import logging
from typing import Dict, Any, Tuple
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.svm import SVR
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, ConstantKernel
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

logger = logging.getLogger(__name__)


class AdaptiveRKHSModel(BaseEstimator, RegressorMixin):
    """
    Адаптивная модель прогнозирования на основе RKHS (Раздел 1.7 курсовой работы).

    Логика работы:
    1. Вычисляет стандартное отклонение (sigma) для каждого входного вектора.
    2. Если sigma < threshold -> использует SVR с RBF ядром (для стабильных участков).
    3. Если sigma >= threshold -> использует GPR с ядром Матерна (для волатильных участков).
    """

    def __init__(self, volatility_threshold=0.8, svr_params=None, gpr_params=None):
        self.volatility_threshold = volatility_threshold
        self.svr_params = svr_params if svr_params else {'C': 1.0, 'epsilon': 0.1, 'gamma': 'scale'}
        self.gpr_params = gpr_params if gpr_params else {'nu': 1.5, 'length_scale': 1.0}

        # Инициализация под-моделей
        self.svr_model = SVR(kernel='rbf', **self.svr_params)

        # GPR использует ядро Матерна
        kernel = ConstantKernel(1.0) * Matern(
            length_scale=self.gpr_params.get('length_scale', 1.0),
            nu=self.gpr_params.get('nu', 1.5)
        )
        self.gpr_model = GaussianProcessRegressor(
            kernel=kernel,
            alpha=1e-10,
            normalize_y=False,
            random_state=42
        )

        self.scaler_X = StandardScaler()
        self.scaler_y = StandardScaler()
        self.is_fitted = False

    def fit(self, X, y):
        """
        Обучает обе модели (SVR и GPR) на полной выборке.
        """
        try:
            X = np.asarray(X, dtype=float)
            y = np.asarray(y, dtype=float)

            # Масштабирование данных
            X_scaled = self.scaler_X.fit_transform(X)
            y_scaled = self.scaler_y.fit_transform(y.reshape(-1, 1)).ravel()

            logger.info("Adaptive Model: Обучение SVR компонента...")
            self.svr_model.fit(X_scaled, y_scaled)

            logger.info("Adaptive Model: Обучение GPR компонента...")
            self.gpr_model.fit(X_scaled, y_scaled)

            self.is_fitted = True
            return self

        except Exception as e:
            logger.error(f"Ошибка обучения адаптивной модели: {str(e)}")
            raise

    def predict(self, X):
        """
        Выполняет прогноз с динамическим переключением моделей в зависимости от волатильности.
        """
        if not self.is_fitted:
            raise ValueError("Модель не обучена.")

        X = np.asarray(X, dtype=float)

        # 1. Вычисляем локальную волатильность (σ) для каждого входного вектора
        sigmas = np.std(X, axis=1)

        # 2. Нормализуем входные данные для подачи в модели
        X_scaled = self.scaler_X.transform(X)

        # 3. Получаем прогнозы от обеих моделей
        pred_svr_scaled = self.svr_model.predict(X_scaled)
        pred_gpr_scaled, _ = self.gpr_model.predict(X_scaled, return_std=True)

        # 4. Комбинируем прогнозы по пороговому значению
        final_preds_scaled = np.zeros_like(pred_svr_scaled)

        # Маска для низкой волатильности (используем SVR)
        mask_stable = sigmas < self.volatility_threshold
        # Маска для высокой волатильности (используем GPR)
        mask_volatile = ~mask_stable

        final_preds_scaled[mask_stable] = pred_svr_scaled[mask_stable]
        final_preds_scaled[mask_volatile] = pred_gpr_scaled[mask_volatile]

        # Обратное масштабирование
        return self.scaler_y.inverse_transform(final_preds_scaled.reshape(-1, 1)).ravel()


def train_adaptive_model(X, y, threshold=0.8, svr_config=None, gpr_config=None) -> Tuple[Any, Dict[str, float]]:
    """
    Функция-обертка для обучения адаптивной модели и расчета метрик.
    """
    X = np.asarray(X)
    if X.ndim == 1:
        raise ValueError("Адаптивная модель требует X в формате (samples, lags)")

    model = AdaptiveRKHSModel(
        volatility_threshold=threshold,
        svr_params=svr_config,
        gpr_params=gpr_config
    )

    model.fit(X, y)
    y_pred = model.predict(X)

    metrics = {
        "MAE": float(mean_absolute_error(y, y_pred)),
        "MSE": float(mean_squared_error(y, y_pred)),
        "RMSE": float(np.sqrt(mean_squared_error(y, y_pred))),
        "R2": float(r2_score(y, y_pred)),
        "volatility_threshold": threshold
    }

    return model, metrics


# --- Вспомогательные функции для SVR/GPR (для совместимости) ---

def train_svr(X, y, C=1.0, epsilon=0.1, gamma='scale'):
    try:
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        if X.ndim == 1: X = X.reshape(-1, 1)

        scaler_X = StandardScaler()
        X_scaled = scaler_X.fit_transform(X)
        scaler_y = StandardScaler()
        y_scaled = scaler_y.fit_transform(y.reshape(-1, 1)).ravel()

        model = SVR(kernel='rbf', C=C, epsilon=epsilon, gamma=gamma)
        model.fit(X_scaled, y_scaled)

        y_pred_scaled = model.predict(X_scaled)
        y_pred = scaler_y.inverse_transform(y_pred_scaled.reshape(-1, 1)).ravel()

        metrics = {
            "MAE": float(mean_absolute_error(y, y_pred)),
            "RMSE": float(np.sqrt(mean_squared_error(y, y_pred))),
            "R2": float(r2_score(y, y_pred))
        }
        return model, metrics
    except Exception as e:
        logger.error(f"SVR training failed: {str(e)}")
        raise


def train_gpr(X, y, nu=1.5, length_scale=1.0):
    try:
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        if X.ndim == 1: X = X.reshape(-1, 1)

        scaler_X = StandardScaler()
        X_scaled = scaler_X.fit_transform(X)
        scaler_y = StandardScaler()
        y_scaled = scaler_y.fit_transform(y.reshape(-1, 1)).ravel()

        kernel = ConstantKernel(1.0) * Matern(length_scale=length_scale, nu=nu)
        model = GaussianProcessRegressor(kernel=kernel, alpha=1e-10, normalize_y=False)

        model.fit(X_scaled, y_scaled)

        y_pred_scaled = model.predict(X_scaled)
        y_pred = scaler_y.inverse_transform(y_pred_scaled.reshape(-1, 1)).ravel()

        metrics = {
            "MAE": float(mean_absolute_error(y, y_pred)),
            "RMSE": float(np.sqrt(mean_squared_error(y, y_pred))),
            "R2": float(r2_score(y, y_pred))
        }
        return model, metrics
    except Exception as e:
        logger.error(f"GPR training failed: {str(e)}")
        raise