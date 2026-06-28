# app/routes/routes_backtest.py
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.backtest_result import BacktestResult
from app.models.ml_model import MLModel
from app.models.user import User
from app.schemas.backtest import BacktestRequest, BacktestResultResponse
from app.services.backtest_service import BacktestModelUnavailableError, run_backtest_with_model
from app.services.stock_service import StockService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/backtest", tags=["Backtest"])


@router.post("/run", response_model=BacktestResultResponse)
def run_backtest(
    request: BacktestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run backtest with a trained model.

    Random demo predictions are intentionally forbidden. Until model artifacts or
    deterministic predictions are persisted, the endpoint returns 501.
    """
    try:
        model = db.query(MLModel).filter(
            MLModel.id == request.ml_model_id,
            MLModel.user_id == current_user.id,
            MLModel.is_active.is_(True),
        ).first()
        if not model:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

        stock_service = StockService(db)
        all_prices = {}
        all_features = {}
        for symbol in request.stock_symbols:
            prices = stock_service.get_stock_prices_dataframe(symbol, request.start_date, request.end_date)
            if prices.empty:
                continue
            features_df = stock_service.calculate_features(prices)
            if features_df.empty:
                continue
            missing = [col for col in model.feature_columns if col not in features_df.columns]
            if missing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Feature columns are missing for {symbol}: {', '.join(missing)}",
                )
            all_prices[symbol] = prices
            all_features[symbol] = features_df[model.feature_columns]

        if not all_prices:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid price data found for the given symbols and period",
            )

        backtest_result = run_backtest_with_model(
            model.model_type,
            model.model_params,
            all_prices,
            all_features,
            request.threshold,
            request.initial_balance,
        )

        db_result = BacktestResult(
            user_id=current_user.id,
            ml_model_id=model.id,
            name=request.name,
            description=request.description,
            stock_symbols=request.stock_symbols,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_balance=request.initial_balance,
            threshold=request.threshold,
            final_balance=backtest_result["final_balance"],
            total_return=backtest_result["roi"],
            total_trades=backtest_result["total_trades"],
            win_rate=backtest_result.get("win_rate"),
            sharpe_ratio=backtest_result.get("sharpe_ratio"),
            max_drawdown=backtest_result.get("max_drawdown"),
            trades=backtest_result["trades"],
            backtest_config=request.model_dump(),
        )
        db.add(db_result)
        db.commit()
        db.refresh(db_result)
        return db_result
    except HTTPException:
        db.rollback()
        raise
    except BacktestModelUnavailableError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("Unexpected backtest failure user_id=%s", current_user.id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Backtest failed") from exc


@router.get("/results", response_model=List[BacktestResultResponse])
def get_backtest_results(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(BacktestResult).filter(
        BacktestResult.user_id == current_user.id,
    ).order_by(BacktestResult.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/results/{result_id}", response_model=BacktestResultResponse)
def get_backtest_result(
    result_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = db.query(BacktestResult).filter(
        BacktestResult.id == result_id,
        BacktestResult.user_id == current_user.id,
    ).first()
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backtest result not found")
    return result


@router.delete("/results/{result_id}")
def delete_backtest_result(
    result_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = db.query(BacktestResult).filter(
        BacktestResult.id == result_id,
        BacktestResult.user_id == current_user.id,
    ).first()
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backtest result not found")
    db.delete(result)
    db.commit()
    return {"status": "ok"}
