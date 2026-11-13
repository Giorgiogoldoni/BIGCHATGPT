# BIGCHATGPT

Clone di lavoro di BIG, dedicato all'evoluzione della selezione degli ETF con orizzonte operativo di 20–60 sedute.

Repository originale: https://github.com/Giorgiogoldoni/big

In questa prima fase i workflow automatici sono mantenuti disattivati per evitare esecuzioni duplicate. L'aggiornamento si avvia manualmente da Actions → Aggiorna BIGCHATGPT. Attivando l'input `classifica` vengono scaricati 5 anni di dati e ricalcolati classifica e score.


## Score e Top 20

La pagina `top20.html` mostra lo score tecnico 0–100 per orizzonti +20/+40/+60 sedute. I dati sono generati da `scripts/score.py` e pubblicati in `data/score.json`. Per la prima classifica completa, avvia il workflow manuale con `classifica=true`.


## Top 20 BIG potenziata (sperimentale)

Il branch `big-tools-top20-experiment` aggiunge una seconda classifica parallela, senza modificare lo score base. Integra lo score tecnico con la qualità storica dei sistemi BIG attivi, per +20/+40/+60 sedute. La prima esecuzione completa richiede `classifica=true` per rigenerare le statistiche dei sistemi includendo anche +40. Il workflow completo con `classifica=true` esegue anche un primo holdout temporale: calcola i punteggi usando solo i dati fino a 12 mesi prima dell'ultima data e misura i rendimenti successivi a +20/+40/+60. Il confronto è pubblicato in `confronto_big.html`. È una sola finestra fuori campione, non ancora una validazione walk-forward multi-finestra; non include costi, spread o slippage.
