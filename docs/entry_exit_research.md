# Ricerca indipendente ingressi e uscite

Issue di riferimento: https://github.com/Giorgiogoldoni/BIGCHATGPT/issues/5

## Scopo

Costruire un motore di ricerca separato dal motore di produzione per individuare:
- i segnali d'ingresso con migliore capacità predittiva;
- le regole d'uscita che gestiscono meglio coorti di ingresso identiche;
- le combinazioni ingresso × uscita più robuste.

Non modificare Top 20, score, segnali correnti o benchmark esistente durante questa ricerca.

## Audit preliminare del codice

- `scripts/systems.py` contiene il catalogo dei sistemi e genera gli eventi.
- `scripts/benchmark.py` contiene già le uscite `original`, Chandelier 2/2.5/3/4 ATR, stop -8%, EMA20/50 e time stop 20/40/60.
- Il benchmark attuale confronta le uscite condizionandole ai segnali dei sistemi: non è ancora una classifica indipendente delle uscite.
- `scripts/reversion_audit.py` è specifico per MR/SMR e non va riutilizzato come se rappresentasse tutte le famiglie d'ingresso.
- Il codice attuale usa prezzi Close non rettificati e costi round-trip di 10 bps in varie simulazioni: il nuovo motore deve rendere queste ipotesi esplicite e uniformi.

## Architettura proposta

### 1. Entry research

Per ogni sistema/candidato, osservare il segnale a Close t e simulare l'acquisto a Open t+1. Misurare a 5/10/20/40/60 sedute:
- rendimento netto e lordo;
- win rate, media, mediana e dispersione;
- MAE e MFE;
- numerosità e frequenza;
- edge rispetto a baseline non condizionata.

Produrre ranking primario su segnali non sovrapposti per ticker/orizzonte e analisi secondaria su tutti i segnali. Conservare risultati per ticker e anno.

### 2. Exit research

Definire coorti standardizzate di ingresso. Ogni regola d'uscita deve ricevere esattamente gli stessi ticker, timestamp e prezzi d'ingresso. La prima famiglia include le regole già presenti in `benchmark.py`; ulteriori varianti vanno aggiunte solo con test.

Distinguere:
- uscita close-based: il segnale nasce alla Close e l'esecuzione avviene non prima dell'Open successivo;
- stop intraday: se il livello è attraversato, eseguire al livello; se il mercato apre oltre lo stop, gestire il gap all'Open.

Non usare High/Low della barra per simulare un'uscita prima che la barra sia terminata, salvo la semantica esplicita degli stop intraday. Registrare trade aperti e mark-to-market.

### 3. Entry × exit matrix

Incrociare i migliori 10 ingressi con le migliori 10 uscite. Regole identiche per universo, costi, slippage, esecuzione e gestione delle posizioni sovrapposte. Il ranking combinato deve essere distinto dalle classifiche marginali.

## Validazione

- Split temporale train / validation / test, senza mescolare date.
- Parametri selezionati sul train soltanto.
- Walk-forward e risultati per anno.
- Sensibilità a costi/slippage e parametri vicini.
- Metriche pooled sui trade e metriche mediane per ticker sempre separate.
- Copertura e download falliti sempre visibili.
- Nessun aggiornamento automatico della Top 20.

## Output

- `data/entry_research.json` e workbook;
- `data/exit_research.json` e workbook;
- `data/entry_exit_matrix.json` e workbook;
- pagina di consultazione separata.

Ogni artefatto deve contenere timestamp, universo, periodo, costi, convenzioni di esecuzione, copertura, errori e limiti.

## Test minimi

Causalità; ingresso Open t+1; uscita close-based all'Open successivo; stop e gap; costi applicati una sola volta; trade aperti; non sovrapposizione; identità delle coorti fra uscite; split cronologico senza leakage.

## Sequenza di lavoro

1. Verificare e normalizzare interfacce/eventi già presenti.
2. Implementare il modulo indipendente senza toccare produzione.
3. Aggiungere test unitari e workflow manuale dedicato.
4. Eseguire build completa e ispezionare JSON/XLSX.
5. Pubblicare una dashboard separata e sottoporre i risultati a revisione prima di qualunque promozione.
