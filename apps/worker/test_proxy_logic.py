import asyncio
import logging
from app.proxy.free_proxy import get_free_working_proxy

logging.basicConfig(level=logging.INFO)

async def main():
    try:
        proxy = await get_free_working_proxy()
        print(f"PROXY ENCONTRADO: {proxy}")
    except Exception as e:
        print(f"FALHA: {e}")

if __name__ == "__main__":
    asyncio.run(main())
