# Target Site Demo Design

## Objetivo

Transformar o target-site em uma vitrine visual do laboratorio de scraping, mantendo as rotas e seletores usados pelo worker.

## Escopo

- Criar uma home em `/` com visual de simulador anti-bot e links para cenarios.
- Exibir cards ricos em `/items` e `/protected/items`, preservando `.item-card`, `.item-title`, `.detail-link` e `.next-page`.
- Adicionar massa fake em escala com registros locais deterministicos e uma fonte externa opcional baseada em RandomUser.
- Evitar dependencia obrigatoria de internet: se a fonte externa falhar, a pagina continua funcionando com fallback local.
- Adicionar testes unitarios para paginacao, normalizacao e preservacao dos seletores.

## Arquitetura

`apps/target_site/app/fake_data.py` concentra geracao local, paginacao e normalizacao de payload externo. `apps/target_site/app/views.py` concentra HTML/CSS compartilhado. `apps/target_site/app/main.py` fica responsavel por rotas, anti-bot e escolha de fonte.

## Dados

Os registros exibidos representam dados sinteticos de catalogo publico. A integracao RandomUser serve como fonte fake externa em massa, mas a UI nao expoe e-mail, telefone ou documento. O conteudo e normalizado para registros publicos com titulo, categoria, score, localidade ampla e detalhes de auditoria.

## Testes

Os testes devem validar que a massa local tem volume, que a paginacao retorna a quantidade esperada, que payload RandomUser e normalizado sem depender da rede e que o HTML renderizado ainda contem os seletores esperados pelo Playwright.
