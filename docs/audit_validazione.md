# BIGCHATGPT — audit iniziale della validazione

Data revisione: 2026-11-13  
Ambito: revisione statica del codice presente nel repository BIGCHATGPT. Non sono stati modificati i motori né sono stati eseguiti test quantitativi su tutti gli ETF.

## Stato delle correzioni

- **Look-ahead ZigZag/SMR:** corretto nel codice il 13/11/2026. I pivot ora riportano anche la barra di conferma e il Super Mean Reversion li rende disponibili solo da quella barra. Correzione da sottoporre a test e ricalcolo dei segnali.
- **Indipendenza della classifica:** corretto nel codice il 13/11/2026. I run ordinari di BIGCHATGPT ora recuperano la classifica dal proprio sito, non più da BIG originale. Da verificare con un'esecuzione del workflow.

## Sintesi

La classifica attuale è un'analisi descrittiva dei rendimenti successivi ai segnali, non un backtest di portafoglio. È utile come prima esplorazione, ma l'etichetta "affidabile" non deve ancora essere interpretata come prova statistica sufficiente per selezionare o acquistare ETF.

## Rilievi da risolvere, in ordine di priorità

### 1. Look-ahead nel Super Mean Reversion — corretto, da testare

File: `scripts/az_engine.py`, funzioni `calc_zigzag()` e `az_serie()`.

`calc_zigzag()` conferma un pivot soltanto quando una successiva oscillazione supera la soglia ATR, ma restituisce il pivot con l'indice storico dell'estremo (`tmp_max_idx` / `tmp_min_idx`). In `az_serie()`, `ultimo_pivot_h_per_barra` rende quel massimo disponibile già dalla data dell'estremo, non dalla data in cui il pivot è diventato conoscibile.

Il motore Super Mean Reversion usa poi quel massimo per misurare il drawdown e può quindi ricevere un'informazione confermata soltanto in futuro. È una potenziale fuga di informazione futura (look-ahead). Va corretto facendo decorrere la disponibilità del pivot dalla barra di conferma, e poi ricalcolati segnali e statistiche SMR.

### 2. Rendimenti senza dividendi — priorità alta

File: `scripts/build.py`, funzioni `pulisci()` e `scarica()`; `scripts/rank.py`.

Il download usa `auto_adjust=False` e conserva `Open/High/Low/Close/Volume`, escludendo `Adj Close`. La classifica usa `Close` per misurare i rendimenti. Per ETF a distribuzione, il rendimento prezzo può ignorare i dividendi e sottostimare il rendimento totale. Occorre definire una serie coerente per analisi tecnica, prezzi d'ingresso/uscita e total return, con trattamento esplicito di dividendi e split.

### 3. Test di affidabilità e selezione del migliore — priorità alta

File: `scripts/rank.py`.

- La statistica t confronta la media dei rendimenti dei segnali non sovrapposti con la media di tutti i rendimenti giornalieri di riferimento, ma usa soltanto la deviazione standard del campione dei segnali. Non è un test completo della differenza tra due campioni e non tiene conto in modo adeguato della dipendenza temporale.
- Le mediane, le percentuali positive e gli eccessi per le due metà includono anche segnali con finestre sovrapposte; il numero di osservazioni può quindi apparire più informativo di quanto sia.
- Vengono scelti i migliori risultati tra molti sistemi e molti ETF. Il confronto multiplo aumenta la probabilità di trovare risultati positivi casuali. La soglia t >= 2, da sola, non corregge questo problema.
- La documentazione di `rank.py` parla di 9 sistemi, mentre `scripts/systems.py` registra 12 sistemi. La calibrazione dichiarata nel testo di `rank.py` non è riproducibile dal codice presente in quel file.

La classificazione "affidabile" va considerata provvisoria fino a quando non sarà sostituita o corroborata da test out-of-sample, bootstrap/permutazioni e correzione per confronti multipli.

### 4. Universo storico e survivorship bias — priorità alta

File: `scripts/build.py`, `seleziona()`.

L'universo è ricostruito dal file corrente degli strumenti di `core`: include gli ETF oggi presenti, non necessariamente quelli che esistevano in ogni data storica. ETF chiusi, fusi o rimossi possono mancare. I risultati storici sull'universo attuale possono quindi soffrire di survivorship bias. Per una validazione robusta serve un universo point-in-time, includendo gli strumenti cessati quando i dati sono disponibili.

### 5. Classifica a orizzonte fisso e simulazione di trade sono due cose diverse — priorità alta

File: `scripts/rank.py` e `scripts/systems.py`.

La classifica misura il rendimento dopo 5/10/20/60 barre da ciascun segnale. Non simula una strategia con capitale, una posizione alla volta, regole d'uscita, costi, spread, slippage e gestione dei segnali concorrenti. È una misura utile della capacità predittiva del segnale, ma non dimostra che il sistema sia negoziabile o profittevole.

Per gli obiettivi BIGCHATGPT vanno mantenuti due test separati:
1. qualità predittiva del segnale a +20/+40/+60 barre;
2. backtest operativo con entrate, uscite, costi e regole eseguibili.

### 6. Prezzi di esecuzione e tick minimo — priorità media

File: `scripts/systems.py`.

Alcuni ingressi sono ordini stop attivati da massimi/minimi giornalieri e simulati al prezzo stop o all'apertura in caso di gap: è una scelta sensata come prima approssimazione, ma va verificata su barre OHLC e con casi ambigui intraday. Inoltre `MINTICK = 0.01` è fisso per strumenti e borse differenti; non rappresenta necessariamente il tick minimo negoziabile di ogni ETF/ETC.

### 7. Recupero della classifica dal sito originale — corretto, da verificare

File: `scripts/build.py`, costante `LIVE` e funzione `recupera_classifica()`.

Nei run in cui `CLASSIFICA=0`, BIGCHATGPT scarica `classifica.json` e `classifica_sintesi.json` da `https://giorgiogoldoni.github.io/big/data/`, cioè dal sito BIG originale. Quindi il clone è separato come repository e sito, ma non è ancora completamente indipendente nei dati della classifica. Va modificato in modo che BIGCHATGPT conservi e riutilizzi la propria classifica, senza leggere quella di BIG.

## Piano di lavoro proposto

1. Correggere il look-ahead ZigZag/SMR e aggiungere test che dimostrino che una barra passata non cambia quando si aggiungono barre future.
2. Separare i prezzi usati per i segnali dai rendimenti total-return, documentando dividendi e split.
3. Rendere indipendente il recupero della classifica di BIGCHATGPT.
4. Costruire una validazione walk-forward: sviluppo su una finestra, verifica su una finestra successiva mai usata per scegliere i parametri, poi avanzamento nel tempo.
5. Confrontare ogni sistema con benchmark semplici (buy-and-hold dello stesso ETF, momentum semplice e ingresso casuale controllato), con correzione per confronti multipli.
6. Solo dopo questi controlli, creare lo score 0–100 e la pagina Top 20, separando ETF normali, leva e inversi.

## Regola prudenziale

Fino al completamento dei controlli, le etichette "affidabile", "miglior sistema" e i guadagni mostrati da BIG vanno letti come risultati storici esplorativi, non come raccomandazioni d'investimento né come rendimenti attesi.

## Nuovo controllo automatico di causalita' — 13/11/2026

E' stato aggiunto `scripts/test_causality.py` e il workflow esegue il test prima di scaricare i dati e pubblicare il sito.

Il test:
- genera una serie OHLCV sintetica e riproducibile;
- calcola i segnali su tutta la serie;
- ricalcola gli stessi segnali usando soltanto i primi 250, 400, 600, 800 e 1.000 giorni;
- confronta data, sistema e prezzo di ogni ingresso gia' maturato;
- verifica che siano registrati esattamente 12 sistemi distinti.

Criterio: un segnale gia' emesso non deve cambiare soltanto perche' sono state aggiunte barre successive. Se il test fallisce, il workflow si ferma prima della pubblicazione.

**Stato:** test aggiunto al workflow, non ancora eseguito. Il superamento del test e' un controllo di causalita' su dati sintetici, non una prova di redditivita' o di robustezza statistica.
