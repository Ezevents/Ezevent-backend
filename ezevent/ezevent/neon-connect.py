import os
import asyncio
import asyncpg
from dotenv import load_dotenv

async def main():
    load_dotenv()

    connection_string = os.getenv('DATABASE_URL')

    pool = await asyncpg.create_pool(connection_string)

    async with pool.acquire() as conn:
        time = await conn.fetchval('SELECT NOW();')
        version = await conn.fetchval('SELECT version();')

    await pool.close()

    print('Current time:', time)
    print('PostgreSQL version:', version)

asyncio.run(main())