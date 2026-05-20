from prometheus_client import Counter, Gauge, Histogram

SCRAPE_JOBS_SUCCESS = Counter("scrape_jobs_success_total", "Jobs finalizados com sucesso")
SCRAPE_JOBS_FAILED = Counter("scrape_jobs_failed_total", "Jobs finalizados com erro")
SCRAPE_JOBS_BLOCKED = Counter("scrape_jobs_blocked_total", "Jobs bloqueados")
SCRAPE_JOBS_DEAD_LETTER = Counter("scrape_jobs_dead_letter_total", "Jobs enviados para DLQ")
SCRAPE_ITEMS = Counter("scrape_items_total", "Itens coletados")
CAPTCHA_DETECTED = Counter("captcha_detected_total", "Captchas detectados")
CAPTCHA_SOLVED = Counter("captcha_solved_total", "Captchas resolvidos")
CAPTCHA_FAILED = Counter("captcha_failed_total", "Falhas de captcha")
CAPTCHA_SOLVE_DURATION = Histogram(
    "captcha_solve_duration_seconds", "Duracao da resolucao de captcha"
)
PROXY_SELECTED = Counter("proxy_selected_total", "Proxies selecionados")
PROXY_COOLDOWN = Counter("proxy_cooldown_total", "Proxies em cooldown")
PROXY_ACTIVE_JOBS = Gauge("proxy_active_jobs", "Jobs ativos por proxy", ["proxy"])

