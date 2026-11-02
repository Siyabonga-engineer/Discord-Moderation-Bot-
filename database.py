import os 
import asyncpg
from pathlib import Path
from dotenv import load_dotenv


load_dotenv(r"C:\Users\themb\Desktop\Discord Bot Project\discord.env", override = True)


async def create_pool():
    return await asyncpg.create_pool(
        host=os.getenv("db_host", "localhost"),
        port=os.getenv("db_port"),
        database=os.getenv("db_name"),
        user=os.getenv("db_user"),
        password=os.getenv("db_password"),

        min_size = 1,
        max_size = 10,

    )