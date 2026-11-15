# Audit tecnico — Mean Reversion e Super Mean Reversion

**Stato:** pipeline di audit storico implementata e testata in CI; manca l'esecuzione quinquennale completa dopo il merge. Fino alla pubblicazione dei nuovi file, i risultati quantitativi non sono ancora validati. Non cambia i segnali, i parametri, la classifica operativa o la Top 20.

## Perimetro

- Repository: BIGCHATGPT.
- Sistemi: `mr` (Mean Reversion) e `smr` (Super Mean Reversion).
- Prezzi: OHLC non rettificati; dividendi esclusi.
- Esecuzione di riferimento: segnale calcolato alla chiusura della seduta t, acquisto all'Open di t+1.
- Costi di riferimento: 10 bp round-trip, come nel benchmark.
- Universo: ETF non a leva e non inversi, come nel benchmark precedente.
- Nessuna modifica alla Top 20 o al calcolo dello score.

## Anomalie e rischi individuati

### A1 — Prezzo di ingresso e uscita non omogenei nel benchmark operativo

In `scripts/benchmark.py`, `_one_system()` apre al prezzo Open di t+1. La modalità `original`, però, recupera data e prezzo di uscita da `meta["tr"]`. Queste posizioni sono prodotte da `scripts/systems.py` con ingresso al prezzo Close del segnale t. Perciò l'uscita originale (inclusi stop e Chandelier) è stata determinata rispetto a un prezzo d'ingresso diverso da quello usato dal benchmark.

**Conseguenza:** il rendimento della modalità `original` non rappresenta una singola simulazione coerente Open(t+1) → uscita.

### A2 — Le posizioni ancora aperte sono escluse dalle metriche originali

In `_one_system()`, quando la posizione in `original_map` non ha una data di uscita, il trade viene saltato. Non è contato né tra i chiusi né come posizione aperta/mark-to-market.

**Conseguenza:** campione dei trade chiusi potenzialmente distorto, soprattutto per sistemi con tempi di permanenza lunghi.

### A3 — Mean Reversion ha due regole di uscita

Il motore MR esce quando Close raggiunge/supera la Bollinger superiore; `USCITE["mr"]` abilita inoltre lo stop Chandelier comune a 3 ATR. Non è quindi una strategia con sola uscita Bollinger.

**Conseguenza:** i risultati dipendono da quale delle due uscite scatta per prima e dal corretto ricalcolo rispetto all'effettivo ingresso.

### A4 — Stop Super Mean Reversion close-based

Il motore SMR controlla `Close / entry_price - 1 <= -15%`. Non simula uno stop intraday eseguito esattamente a -15%. Se la chiusura supera al ribasso la soglia (ad esempio dopo un gap), il prezzo contabilizzato è la chiusura e la perdita può superare il 15%.

**Conseguenza:** il nome “Stop -15%” descrive una soglia di uscita verificata in chiusura, non una garanzia di perdita massima.

### A5 — Hurst è aggiornato ogni cinque barre

`rolling_hurst` ricalcola Hurst a intervalli di `HURST_STRIDE=5` e mantiene il valore fino al ricalcolo successivo. Il filtro MR usa quindi un Hurst 60 non ricalcolato quotidianamente. Questo è un disegno del motore da misurare, non prova di look-ahead.

### A6 — ZigZag: il pivot massimo è disponibile solo alla conferma

`calc_zigzag()` restituisce sia indice dell'estremo sia indice di conferma. `az_serie()` aggiorna il massimo di riferimento solo quando la conferma è disponibile. Il test generale di causalità copre gli ingressi storici; l'audit conserva un test dedicato di esecuzione e invita a non usare la data dell'estremo retroattivamente.

## Simulatore indipendente di audit

`scripts/reversion_audit.py` simula i due sistemi a partire dal prezzo effettivo Open(t+1), ricalcolando le uscite rispetto a tale prezzo:

- MR: prima tra Close >= Bollinger superiore e Close sotto il massimo High dall'ingresso meno 3 × ATR14.
- SMR: prima tra Close >= Bollinger superiore e Close <= ingresso effettivo × 0,85.
- L'ingresso è all'Open di t+1 e la prima verifica delle uscite avviene alla Close della stessa seduta t+1: non si perde una giornata di controllo.
- Gli stop restano close-based, coerenti con il codice attuale: un gap può produrre una perdita superiore alla soglia.
- Le posizioni non chiuse sono conservate come `status=open` e valorizzate all'ultima chiusura; non entrano nel campione dei trade chiusi.
- Il costo round-trip è applicato ai trade chiusi; per le posizioni aperte è esposto separatamente come stima mark-to-market.

Questo modulo è deliberatamente separato da `benchmark.py`: l'audit non cambia ancora la classifica benchmark né la Top 20.

## Test automatici

Da `scripts/`:

```bash
python -m unittest test_reversion_audit.py -v
python -m unittest test_causality.py test_score.py test_benchmark.py test_reversion_audit.py -v
```

I test verificano: ingresso Open t+1, Chandelier MR ricalcolato sull'ingresso effettivo, uscita Bollinger, stop SMR close-based e gap, conservazione delle posizioni aperte, costi round-trip e validazione del sistema richiesto.

## Esecuzione storica automatizzata

Con il parametro `CLASSIFICA=1`, `build.py` applica l'audit a ogni ETF del medesimo universo quinquennale del benchmark, escludendo strumenti a leva e inversi. Per ogni ETF e per MR/SMR confronta:
- posizioni BIG originali, entrata al Close della data segnale;
- simulazione corretta, entrata all'Open della seduta successiva e uscite ricalcolate rispetto al prezzo effettivo.

L'output `data/reversion_audit.json` conserva le statistiche per ETF, i trade ricalcolati, le posizioni ancora aperte mark-to-market e il riepilogo annuale per anno d'ingresso. `data/reversion_audit.xlsx` presenta quattro fogli: Sintesi, Confronto ETF, Per anno, Trade Open T+1, oltre alle note metodologiche.

L'aggregazione usa la mediana per ETF, così gli strumenti con molti più segnali non pesano automaticamente di più. Le posizioni aperte sono conteggiate separatamente e non entrano nel profit factor dei trade chiusi. Il riepilogo per anno è descrittivo e non va confuso con un walk-forward fuori campione.

## Cosa resta da fare prima di riaprire la classifica

1. Eseguire il workflow quinquennale dopo il merge e verificare che i due nuovi file siano pubblicati.
2. Leggere i risultati effettivi e confrontare vecchia esecuzione Close e nuova esecuzione Open(t+1).
3. Valutare trade chiusi/aperti, win rate, profit factor, rendimento mediano, durata, drawdown, concentrazione per ETF e risultati annuali.
4. Solo dopo, progettare test separati per Hurst (filtro attuale, senza filtro e soglie alternative) e validazione walk-forward/out-of-sample senza ottimizzare sul campione finale.

**Decisione provvisoria:** nessuna modifica ai parametri o alla classifica operativa finché i punti sopra non sono stati misurati.
