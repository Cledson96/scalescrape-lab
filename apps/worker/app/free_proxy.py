import asyncio
import urllib.request
import logging
from typing import Optional

logger = logging.getLogger(__name__)

async def fetch_proxy_list() -> list[str]:
    """Busca uma lista de proxies HTTP brasileiros públicos gratuitos."""
    url = "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=BR&ssl=all&anonymity=all"
    logger.info("Buscando lista de proxies gratuitos na API proxyscrape...")
    try:
        def _fetch():
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.read().decode('utf-8')
                
        data = await asyncio.to_thread(_fetch)
        proxies = []
        for line in data.splitlines():
            line = line.strip()
            if line:
                proxies.append(f"http://{line}")
        return proxies
    except Exception as e:
        logger.error(f"Erro ao buscar lista de proxies: {e}")
        return []

async def test_single_proxy(proxy_url: str, target_url: str = "https://www.betano.bet.br/") -> Optional[str]:
    """Testa um único proxy para ver se ele resolve a URL em tempo hábil."""
    def _test():
        proxy_handler = urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url})
        opener = urllib.request.build_opener(proxy_handler)
        req = urllib.request.Request(target_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        try:
            response = opener.open(req, timeout=8) # timeout restrito para 8s
            if response.status == 200:
                return proxy_url
        except Exception:
            pass
        return None

    return await asyncio.to_thread(_test)

async def get_free_working_proxy() -> str:
    """
    Busca e testa proxies gratuitos concorrentemente.
    Retorna o primeiro que funcionar. Lança exceção se nenhum funcionar.
    """
    proxies = await fetch_proxy_list()
    if not proxies:
        raise RuntimeError("Nenhum proxy retornado pela API pública.")
        
    logger.info(f"{len(proxies)} proxies encontrados. Iniciando corrida de testes...")
    
    # Testa em lotes de 20 para evitar sobrecarga de threads
    batch_size = 20
    for i in range(0, min(60, len(proxies)), batch_size): # Testa no máximo 60 proxies
        batch = proxies[i:i+batch_size]
        logger.info(f"Testando lote de {len(batch)} proxies...")
        
        # Cria as tasks
        tasks = [asyncio.create_task(test_single_proxy(p)) for p in batch]
        
        # Espera a primeira terminar com sucesso (ou todas falharem)
        pending = tasks
        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                result = task.result()
                if result:
                    # Encontramos um válido! Cancela o resto do lote
                    for t in pending:
                        t.cancel()
                    logger.info(f"🚀 Proxy funcionando encontrado: {result}")
                    return result
                    
    raise RuntimeError("Nenhum proxy gratuito respondeu a tempo para a Betano.")
