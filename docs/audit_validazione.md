# BIGCHATGPT — audit iniziale della validazione

Data revisione: 2026-11-13  
Ambito: revisione statica e controlli automatici sul codice presente nel repository BIGCHATGPT. Non sono stati eseguiti test quantitativi completi su tutti gli ETF.

## Stato delle correzioni

- **Look-ahead ZigZag/SMR:** corretto il 13/11/2026; il test sintetico di causalita' e' passato nel workflow del 13/11/2026. Resta da verificare su casi storici reali e con test specifici del pivot.
- **Indipendenza della classifica:** corretto il 13/11/2026; un'esecuzione del workflow ha completato download, calcolo e deploy di BIGCHATGPT senza ricalcolare la classifica. Il sito clone ha pubblicato i propri dati.
- **Priorita' Core BUY3/BUY2:** difetto individuato e corretto il 13/11/2026; aggiunto test di regressione dedicato, in attesa di esecuzione nel workflow.

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


### 10. Filtro Hurst: stima approssimata, soglie non validate — da verificare

File: `scripts/az_engine.py`, funzioni `calc_hurst()` e `az_serie()`.

Il filtro Hurst viene stimato su 60 osservazioni, usando soltanto cinque lag (2, 4, 8, 16 e 32); la stima e' poi limitata artificialmente all'intervallo 0,1–0,9 e aggiornata ogni 5 barre, mantenendo il valore precedente nei giorni intermedi. Le soglie 0,55 per i sistemi trend e 0,45 per Mean Reversion sono quindi euristiche, non una classificazione certa del regime. Con finestre brevi e pochi lag la stima puo' essere rumorosa e instabile: puo' escludere segnali validi o ammetterne di casuali. Prima di attribuire valore predittivo al filtro, occorre misurarne la stabilita' e confrontare i risultati con e senza Hurst in walk-forward, senza scegliere le soglie sulla stessa finestra usata per valutarle.

### 9. Il test di causalita' controllava gli ingressi, non ancora le uscite — esteso

File: `scripts/test_causality.py`.

Il primo test confrontava gli ingressi storici, ma non verificava esplicitamente che le uscite gia' avvenute (segnali di uscita e stop) restassero identiche aggiungendo barre future. E' stato aggiunto un controllo sui trade chiusi entro ciascuna data di taglio: sistema, data/prezzo di ingresso e data/prezzo/motivo di uscita devono coincidere tra serie completa e prefisso. Il test e' stato aggiunto il 13/11/2026 e deve essere eseguito nel workflow.

### 8. BUY3 del sistema Core irraggiungibile — corretto, test dedicato in attesa

File: `scripts/core_engine.py`, funzione `calc_segnale_array()`.

La condizione BUY2 (prezzo sopra KAMA e almeno 2 barre sopra) veniva verificata prima della BUY3. Poiche' ogni BUY3 soddisfa anche le condizioni meno restrittive di BUY2, il ramo BUY3 non poteva essere raggiunto. Il controllo e' stato riordinato: BUY1, poi BUY3, poi BUY2. E' stato aggiunto un test che verifica entrambe le uscite su casi costruiti appositamente; deve ancora essere eseguito nel workflow prima di considerare la correzione verificata.

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
- calcola segnali e posizioni su tutta la serie;
- ricalcola gli stessi risultati usando soltanto i primi 250, 400, 600, 800 e 1.000 giorni;
- confronta data, sistema e prezzo degli ingressi gia' maturati;
- confronta anche le uscite dei trade gia' chiusi entro ciascuna data di taglio;
- verifica che siano registrati esattamente 12 sistemi distinti;
- verifica la priorita' di BUY3 rispetto a BUY2 nel motore Core.

Criterio: un segnale gia' emesso non deve cambiare soltanto perche' sono state aggiunte barre successive. Se il test fallisce, il workflow si ferma prima della pubblicazione.

**Stato:** il workflow del 13/11/2026 ha eseguito con successo i due test iniziali: invariabilita' degli ingressi passati sui prefissi sintetici e registrazione dei 12 sistemi. In seguito sono stati aggiunti test per le uscite storiche e per la priorita' BUY3/BUY2. L'intero gruppo aggiornato deve ancora essere eseguito. Il superamento dei test sintetici non e' una prova di redditivita' o di robustezza statistica.


## Seconda revisione tecnica — 13/11/2026

### Esito del primo workflow completo dopo le correzioni

Run: https://github.com/Giorgiogoldoni/BIGCHATGPT/actions/runs/43408492609

Il workflow e' terminato con successo e ha pubblicato il sito. Nel log risultano superati tutti e quattro i test:
- registrazione dei 12 sistemi;
- priorita' e raggiungibilita' di Core BUY3 e BUY2;
- invariabilita' degli ingressi storici aggiungendo barre future;
- invariabilita' delle uscite gia' chiuse aggiungendo barre future.

Il run ha usato `CLASSIFICA=0`: non ha ricalcolato la classifica. Il deploy riuscito e i test di causalita' non dimostrano che i sistemi siano profittevoli o statisticamente validi. I download di alcuni ticker non sono riusciti; il build e' proseguito e ha registrato 10 ticker senza dati/calcolo nel file `data/errori.json`. Il file generato non e' presente nel repository sorgente, quindi l'elenco dei 10 ticker va recuperato dall'artefatto/log del run prima di classificarli come cessati, temporaneamente indisponibili o errori tecnici.

### Verifiche aggiuntive sul codice

- **ZigZag:** nel codice esaminato la funzione e' richiamata da `az_serie()`; i pivot sono consumati usando il quarto elemento, indice di conferma. Non sono emersi altri consumatori del vecchio formato a tre elementi nei file esaminati. La correzione impedisce al Super Mean Reversion di usare un massimo prima della barra in cui il pivot e' confermato.
- **Parabolic SAR:** `parabolic_sar()` inizializza la direzione della barra zero usando anche la chiusura della barra uno. E' una dipendenza dal futuro per il solo valore iniziale della serie. Nel flusso attuale non appare generare un ingresso negoziabile sulla barra zero: KAMA/Hurst non sono ancora pronti e il trigger Super Best Buy richiede AO in miglioramento. Resta comunque opportuno eliminare questa dipendenza con un'inizializzazione neutra e un test dedicato, per rendere l'indicatore rigorosamente causale fin dall'inizio.
- **Ordini PSAR e Momentum:** gli ordini stop vengono calcolati alla chiusura di una barra e possono scattare soltanto sulla barra successiva. Questa sequenza e' coerente con l'uso di dati OHLC giornalieri; restano da verificare casi di gap e ambiguita' intraday.
- **Warm-up:** diversi indicatori hanno periodi iniziali non validi o valori di ripiego. Il test a prefissi verifica la stabilita' storica, ma non dimostra che ogni sistema eviti segnali nella fase di warm-up. Serve un test specifico sui primi valori validi.
- **Formato ZigZag:** la modifica a quattro elementi e' letta nel consumatore presente in `az_engine.py`; prima di ulteriori riusi della funzione va mantenuto questo contratto.

### Ulteriore limite della statistica t in rank.py

La formula corrente calcola una t dividendo la differenza tra la media dei rendimenti dei segnali selezionati e la media di tutti i rendimenti di riferimento per l'errore standard dei soli rendimenti selezionati. Tratta quindi la media di riferimento come se fosse nota senza errore. Inoltre la selezione di finestre non sovrapposte riduce la sovrapposizione diretta, ma non garantisce indipendenza: i rendimenti possono restare correlati per regime di mercato. Infine la ricerca simultanea tra numerosi ETF, sistemi e orizzonti non e' corretta per confronti multipli. Di conseguenza `t >= 2` e l'etichetta `affidabile` sono criteri esplorativi, non un test inferenziale conclusivo.

### Correzione documentale

Il testo di `rank.py` menziona 9 sistemi, mentre il registro attuale ne contiene 12. Va allineato il testo visibile e va mantenuta la distinzione tra i 12 sistemi registrati e il numero di sistemi effettivamente presenti in ciascun risultato con dati sufficienti.

### Prossimi passi, senza costruire ancora lo score

1. Rendere causale anche l'inizializzazione del Parabolic SAR e aggiungere test di warm-up.
2. Chiarire l'elenco dei 10 ticker segnalati dal workflow.
3. Correggere e documentare il calcolo statistico, includendo confronti multipli e dipendenza temporale.
4. Preparare una serie di rendimento total-return per la valutazione, mantenendo coerenti i prezzi d'esecuzione.
5. Solo dopo, passare a test walk-forward e backtest operativo separati.
