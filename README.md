# BIGCHATGPT

Clone di lavoro di BIG, dedicato all'evoluzione della selezione degli ETF con orizzonte operativo di 20–60 sedute.

Repository originale: https://github.com/Giorgiogoldoni/big

In questa prima fase i workflow automatici sono mantenuti disattivati per evitare esecuzioni duplicate. L'aggiornamento si avvia manualmente da Actions → Aggiorna BIGCHATGPT. Attivando l'input `classifica` vengono scaricati 5 anni di dati e ricalcolati classifica e score.


## Score e Top 20

La pagina `top20.html` mostra lo score tecnico 0–100 per orizzonti +20/+40/+60 sedute. I dati sono generati da `scripts/score.py` e pubblicati in `data/score.json`. Per la prima classifica completa, avvia il workflow manuale con `classifica=true`.


## Bollettino quotidiano

La pagina `bollettino.html` integra i dati geografici del repository RAPTOR GEOGRAFIA con BIG, TOP20 e audit MR/SMR. Il generatore `scripts/bollettino.py` crea `data/bollettino.json` e aggiorna `data/bollettino_storico.json`, mantenendo un archivio fino a 365 edizioni. Le aree geografiche sono separate da Global e fattori; i segnali positivi richiedono conferme multi-indicatore. La pagina viene pubblicata dal workflow `Aggiorna BIGCHATGPT`.
