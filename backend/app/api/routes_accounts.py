# app/api/routes_accounts.py
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from app.core.tinkoff_client import AccountType, TinkoffClient
from app.core.auth import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/accounts", tags=["Accounts"])


class PayInRequest(BaseModel):
    account_id: Optional[str] = Field(default=None, max_length=128)
    amount: float = Field(gt=0, le=1_000_000_000)
    currency: str = Field(default="RUB", pattern="^[A-Z]{3}$")


class OpenAccountRequest(BaseModel):
    account_type: str = Field(default="ACCOUNT_TYPE_TINKOFF", max_length=64)


@router.get("/")
def get_accounts(current_user: User = Depends(get_current_user)):
    """Получение списка всех счетов пользователя"""
    logger.info(f"Получение списка счетов для пользователя {current_user.id} ({current_user.username})")

    try:
        client = TinkoffClient(user_id=current_user.id)
        # ИСПРАВЛЕНИЕ: используем существующий метод get_accounts()
        accounts = client.get_accounts()  # ← было get_sandbox_accounts()

        logger.info(f"Успешно получено {len(accounts)} счетов для пользователя {current_user.id}")
        return {"status": "success", "accounts": accounts}
    except Exception as e:
        logger.error(f"Ошибка при получении счетов для пользователя {current_user.id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching accounts: {str(e)}")


@router.post("/open")
def open_account(request: OpenAccountRequest, current_user: User = Depends(get_current_user)):
    """Открытие нового счёта (только sandbox)"""
    logger.info(f"Получен запрос на открытие счёта: {request.dict()}")

    try:
        client = TinkoffClient(user_id=current_user.id)

        if not client.use_sandbox:
            logger.warning(f"Попытка открыть счёт в не-sandbox режиме для пользователя {current_user.id}")
            raise HTTPException(status_code=400, detail="Открытие счетов доступно только в sandbox режиме")

        # ИСПРАВЛЕНИЕ: используем фиксированный тип или парсим из строки
        account_type = AccountType.ACCOUNT_TYPE_TINKOFF  # ← исправлено

        logger.debug(f"Открытие счёта с типом: {account_type}")
        account_id = client.open_account(account_type)  # ← исправлено название метода

        logger.info(f"Счёт {account_id} успешно открыт для пользователя {current_user.id}")

        return {"status": "success", "account_id": account_id, "message": "Счёт успешно открыт"}
    except Exception as e:
        logger.error(f"Ошибка при открытии счёта для пользователя {current_user.id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error opening account: {str(e)}")


@router.post("/payin")
def pay_in_account(request: PayInRequest, current_user: User = Depends(get_current_user)):
    """Пополнение счёта (только sandbox)"""
    logger.info(
        f"Запрос на пополнение счёта {request.account_id} на сумму {request.amount} {request.currency} для пользователя {current_user.id}")

    try:
        client = TinkoffClient(user_id=current_user.id)

        if not client.use_sandbox:
            logger.warning(f"Попытка пополнения счёта в не-sandbox режиме для пользователя {current_user.id}")
            raise HTTPException(status_code=400, detail="Пополнение счёта доступно только в sandbox режиме")

        if request.amount <= 0:
            logger.warning(f"Попытка пополнения счёта неположительной суммой: {request.amount}")
            raise HTTPException(status_code=400, detail="Сумма пополнения должна быть положительной")

        logger.debug(f"Выполнение пополнения счёта {request.account_id} на {request.amount} {request.currency}")
        success = client.pay_in(request.account_id, request.amount, request.currency)

        if success:
            logger.info(
                f"Счёт {request.account_id} успешно пополнен на {request.amount} {request.currency} для пользователя {current_user.id}")
            return {"status": "success", "message": f"Счёт пополнен на {request.amount} {request.currency}"}
        else:
            logger.error(f"Не удалось пополнить счёт {request.account_id} для пользователя {current_user.id}")
            raise HTTPException(status_code=500, detail="Failed to pay in account")

    except Exception as e:
        logger.error(f"Ошибка при пополнении счёта {request.account_id} для пользователя {current_user.id}: {str(e)}",
                     exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error paying in: {str(e)}")


@router.get("/balance")
def get_balance(account_id: Optional[str] = None, current_user: User = Depends(get_current_user)):
    """Получение баланса счёта"""
    logger.info(f"Запрос баланса для счёта {account_id} пользователя {current_user.id}")

    try:
        client = TinkoffClient(user_id=current_user.id)
        balance = client.get_account_balance(account_id)

        logger.info(f"Баланс для счёта {account_id}: {balance} для пользователя {current_user.id}")
        logger.debug(f"Детали баланса: {balance}")

        return {"status": "success", "balance": balance}
    except Exception as e:
        logger.error(f"Ошибка при получении баланса для счёта {account_id} пользователя {current_user.id}: {str(e)}",
                     exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching balance: {str(e)}")


@router.delete("/{account_id}")
def close_account(account_id: str, current_user: User = Depends(get_current_user)):
    """Закрытие счёта (только sandbox)"""
    logger.info(f"Запрос на закрытие счёта {account_id} для пользователя {current_user.id}")

    try:
        client = TinkoffClient(user_id=current_user.id)

        if not client.use_sandbox:
            logger.warning(f"Попытка закрытия счёта в не-sandbox режиме для пользователя {current_user.id}")
            raise HTTPException(status_code=400, detail="Закрытие счетов доступно только в sandbox режиме")

        logger.debug(f"Выполнение закрытия счёта {account_id}")
        success = client.close_account(account_id)

        if success:
            logger.info(f"Счёт {account_id} успешно закрыт для пользователя {current_user.id}")
            return {"status": "success", "message": "Счёт успешно закрыт"}
        else:
            logger.error(f"Не удалось закрыть счёт {account_id} для пользователя {current_user.id}")
            raise HTTPException(status_code=500, detail="Failed to close account")

    except Exception as e:
        logger.error(f"Ошибка при закрытии счёта {account_id} для пользователя {current_user.id}: {str(e)}",
                     exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error closing account: {str(e)}")


@router.get("/portfolio")
def get_portfolio(account_id: Optional[str] = None, current_user: User = Depends(get_current_user)):
    """Получение портфеля по счёту"""
    logger.info(f"Запрос портфеля для счёта {account_id} пользователя {current_user.id}")

    try:
        client = TinkoffClient(user_id=current_user.id)
        portfolio = client.get_portfolio(account_id)

        logger.info(f"Портфель для счёта {account_id} успешно получен для пользователя {current_user.id}")
        logger.debug(f"Детали портфеля: {portfolio}")

        return {"status": "success", "portfolio": portfolio}
    except Exception as e:
        logger.error(f"Ошибка при получении портфеля для счёта {account_id} пользователя {current_user.id}: {str(e)}",
                     exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching portfolio: {str(e)}")


@router.get("/operations")
def get_operations(account_id: str, from_date: str, to_date: str, current_user: User = Depends(get_current_user)):
    """Получение операций по счёту за период"""
    logger.info(f"Запрос операций для счёта {account_id} с {from_date} по {to_date} для пользователя {current_user.id}")

    try:
        client = TinkoffClient(user_id=current_user.id)
        operations = client.get_operations(account_id, from_date, to_date)

        logger.info(f"Получено {len(operations)} операций для счёта {account_id} пользователя {current_user.id}")
        logger.debug(f"Операции: {operations}")

        return {"status": "success", "operations": operations}
    except Exception as e:
        logger.error(f"Ошибка при получении операций для счёта {account_id} пользователя {current_user.id}: {str(e)}",
                     exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching operations: {str(e)}")
