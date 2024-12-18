from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import asyncpg
import os
import logging
import asyncio

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s]: %(message)s", handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)

app = FastAPI()

class Message(BaseModel):
    message: str

async def get_db_connection():
    conn = await asyncpg.connect(
        user=os.getenv('POSTGRES_USER', '-'),
        password=os.getenv('POSTGRES_PASSWORD', '-'),
        database=os.getenv('POSTGRES_DB', '-'),
        host=os.getenv('POSTGRES_HOST', '-')
    )
    return conn

async def create_table():
    try:
        conn = await get_db_connection()
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL
            );
        ''')
        await conn.close()
        logger.info("Таблица 'messages' успешно создана (если не существовала).")
    except Exception as e:
        logger.error(f"Ошибка при создании таблицы: {e}")
        raise

async def wait_for_postgres():
    for _ in range(30):
        try:
            conn = await get_db_connection()
            await conn.close()
            logger.info("PostgreSQL готов к подключению!")
            return
        except Exception as e:
            logger.warning(f"Ожидание PostgreSQL... Ошибка: {e}")
            await asyncio.sleep(30)
    logger.error("Не удалось дождаться готовности PostgreSQL.")
    raise Exception("Не удалось дождаться готовности PostgreSQL.")

@app.on_event("startup")
async def startup():
    logger.info("Запуск FastAPI-приложения...")
    await wait_for_postgres()
    await create_table() 

@app.post("/message")
async def receive_message(message: Message):
    try:
        conn = await get_db_connection()
        await conn.execute("INSERT INTO messages (content) VALUES ($1)", message.message)
        await conn.close()
        logger.info(f"Сообщение успешно добавлено в базу данных: {message.message}")
        return {"status": "Message received"}
    except Exception as e:
        logger.error(f"Ошибка при вставке сообщения: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "alive"}

@app.get("/ready")
async def ready():
    try:
        conn = await get_db_connection()
        await conn.close()
        return {"status": "ready"}
    except Exception as e:
        logger.warning(f"Проверка готовности не прошла: {e}")
        raise HTTPException(status_code=500, detail="Database not ready")
