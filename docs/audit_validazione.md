# BIGCHATGPT — audit iniziale della validazione

Data revisione: 2026-11-13  
Ambito: revisione statica e controlli automatici sul codice presente nel repository BIGCHATGPT. Non sono stati eseguiti test quantitativi completi su tutti gli ETF.

## Stato delle correzioni

- **Look-ahead ZigZag/SMR:** corretto il 13/11/2026; il test sintetico di causalita' e' passato nel workflow del 13/11/2026. Resta da verificare su casi storici reali e con test specifici del pivot.
- **Indipendenza della classifica:** corretto il 13/11/2026; un'esecuzione del workflow ha completato download, calcolo e deploy di BIGCHATGPT senza ricalcolare la classifica. Il sito clone ha pubblicato i propri dati.
- **Priorita' Core BUY3/BUY2:** difetto corretto il 13/11/2026; test di regressione superato nel workflow run 43408492609.

## Sintesi

La classifica attuale è un'analisi descrittiva dei rendimenti successivi ai segnali, non un backtest di portafoglio. È utile come prima esplorazione, ma l'etichetta "affidabile" non deve ancora essere interpretata come prova statistica sufficiente per selezionare o acquistare ETF.

## Rilievi da risolvere, in ordine di priorità

### 1. Look-ahead nel Super Mean Reversion — corretto, test sintetici superati

File: `scripts/az_engine.py`, funzioni `calc_zigzag()` e `az_serie()`.

`calc_zigzag()` conferma un pivot soltanto quando una successiva oscillazione supera la soglia ATR, ma restituisce il pivot con l'indice storico dell'estremo (`tmp_max_idx` / `tmp_min_idx`). In `az_serie()`, `ultimo_pivot_h_per_barra` rende quel massimo disponibile già dalla data dell'estremo, non dalla data in cui il pivot è diventato conoscibile.

Il motore Super Mean Reversion usa il massimo soltanto dalla barra di conferma. La correzione e' presente nel codice; i test sintetici di invariabilita' degli ingressi e delle uscite sono passati nel run 43408492609. Resta da confrontare il comportamento su serie storiche reali e casi mirati di pivot ZigZag.

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

### 7. Recupero della classifica dal sito originale — corretto

File: `scripts/build.py`, costante `LIVE` e funzione `recupera_classifica()`.

Nei run in cui `CLASSIFICA=0`, BIGCHATGPT recupera i file della classifica dal proprio sito Pages (`https://giorgiogoldoni.github.io/BIGCHATGPT/data/`). La modifica e' stata pubblicata e verificata nel run 43408492609, che ha completato il deploy con `CLASSIFICA=0`.


### 10. Filtro Hurst: stima approssimata, soglie non validate — da verificare

File: `scripts/az_engine.py`, funzioni `calc_hurst()` e `az_serie()`.

Il filtro Hurst viene stimato su 60 osservazioni, usando soltanto cinque lag (2, 4, 8, 16 e 32); la stima e' poi limitata artificialmente all'intervallo 0,1–0,9 e aggiornata ogni 5 barre, mantenendo il valore precedente nei giorni intermedi. Le soglie 0,55 per i sistemi trend e 0,45 per Mean Reversion sono quindi euristiche, non una classificazione certa del regime. Con finestre brevi e pochi lag la stima puo' essere rumorosa e instabile: puo' escludere segnali validi o ammetterne di casuali. Prima di attribuire valore predittivo al filtro, occorre misurarne la stabilita' e confrontare i risultati con e senza Hurst in walk-forward, senza scegliere le soglie sulla stessa finestra usata per valutarle.

### 9. Il test di causalita' controlla ingressi e uscite — superato

File: `scripts/test_causality.py`.

Il primo test confrontava gli ingressi storici, ma non verificava esplicitamente che le uscite gia' avvenute (segnali di uscita e stop) restassero identiche aggiungendo barre future. E' stato aggiunto un controllo sui trade chiusi entro ciascuna data di taglio: sistema, data/prezzo di ingresso e data/prezzo/motivo di uscita devono coincidere tra serie completa e prefisso. Il test e' stato aggiunto il 13/11/2026 ed e' stato superato nel workflow run 43408492609.

### 8. BUY3 del sistema Core irraggiungibile — corretto, test superato

File: `scripts/core_engine.py`, funzione `calc_segnale_array()`.

La condizione BUY2 (prezzo sopra KAMA e almeno 2 barre sopra) veniva verificata prima della BUY3. Poiche' ogni BUY3 soddisfa anche le condizioni meno restrittive di BUY2, il ramo BUY3 non poteva essere raggiunto. Il controllo e' stato riordinato: BUY1, poi BUY3, poi BUY2. Il test dedicato, con casi costruiti appositamente, e' stato superato nel workflow run 43408492609.

## Piano di lavoro proposto

1. Verificare su casi storici reali la correzione ZigZag/SMR gia' introdotta e mantenere i test di causalita'.
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

**Stato:** il workflow del 13/11/2026 ha eseguito con successo tutti e quattro i test presenti in quel commit: invariabilita' degli ingressi passati, invariabilita' delle uscite gia' chiuse, registrazione dei 12 sistemi e priorita' BUY3/BUY2. Successivamente e' stato aggiunto un quinto test per l'inizializzazione causale del PSAR; questo test e la correzione PSAR attendono ancora il prossimo workflow. Il superamento dei test sintetici non e' una prova di redditivita' o di robustezza statistica.


## Seconda revisione tecnica — 13/11/2026

### Esito del primo workflow completo dopo le correzioni

Run: https://github.com/Giorgiogoldoni/BIGCHATGPT/actions/runs/43408492609

Il workflow e' terminato con successo e ha pubblicato il sito. Nel log risultano superati tutti e quattro i test:
- registrazione dei 12 sistemi;
- priorita' e raggiungibilita' di Core BUY3 e BUY2;
- invariabilita' degli ingressi storici aggiungendo barre future;
- invariabilita' delle uscite gia' chiuse aggiungendo barre future.

Il run ha usato `CLASSIFICA=0`: non ha ricalcolato la classifica. Il deploy riuscito e i test di causalita' non dimostrano che i sistemi siano profittevoli o statisticamente validi. Il precedente conteggio di 2.328 strumenti con dati e 381 senza dati era errato e viene ritirato. L'estrazione diretta dei log del job 131828684479 ha individuato 63 ticker distinti con messaggio Yahoo 'No data found'. Il parametro `error_count: 10` mostrato nei log appartiene alla configurazione dell'azione di deploy e non rappresenta il numero di ticker mancanti. I 63 casi non possono essere classificati automaticamente come strumenti cessati: il messaggio può indicare ticker non riconosciuto, copertura Yahoo assente, simbolo errato o strumento di recente emissione.

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


### Correzione PSAR — 13/11/2026 (in attesa di workflow)

E' stata rimossa la dipendenza della direzione iniziale del Parabolic SAR dalla chiusura della seconda barra: la barra zero ora parte da uno stato rialzista convenzionale, usando soltanto massimo e minimo della prima barra. E' stato aggiunto un test che cambia la chiusura futura e verifica che i valori PSAR della barra zero restino invariati.

**Stato:** codice e test sono stati aggiornati, ma questa nuova modifica non e' ancora stata eseguita nel workflow GitHub Actions. Fino al superamento del prossimo workflow, la correzione resta non verificata automaticamente.


## Anagrafica dei 63 ticker senza dati Yahoo — prima verifica ISIN

Le date fornite dall'utente sono **date di emissione/lancio**, non date di cessazione. La dicitura "cripto" identifica gli strumenti legati a cripto-attività. Non eliminare questi strumenti dall'universo sulla sola base dell'errore Yahoo.

### ISIN identificati con riscontro documentale

| Ticker | Strumento / categoria | ISIN | Riscontro |
|---|---|---|---|
| ACSW.MI | iShares MSCI All Country World Swap UCITS ETF | IE000CYC2B65 | iShares e Borsa Italiana |
| ASUI.MI | 21shares Sui Staking ETP | CH1360612159 | 21shares |
| ATAO.MI | 21shares Bittensor ETP | CH1495416971 | Borsa Italiana |
| BUNDS5.MI | SG ETN Daily Short -5x Bund Future | XS2425321713 | Borsa Italiana |
| CANTN.MI | 21shares Canton Network ETP | CH1503127917 | Borsa Italiana |
| CASHE.MI | BNP Paribas Easy EUR Overnight UCITS ETF Acc | LU3025345516 | justETF |
| CBTC.MI | 21shares Bitcoin Core ETP | CH1199067674 | Borsa Italiana |
| ESWP.MI | iShares MSCI EM Swap UCITS ETF USD Acc | IE000S3N6R34 | Borsa Italiana |
| HDRA.MI | 21shares Hedera Staking ETP | CH1456607683 | 21shares |
| IB36.MI | iShares iBonds Dec 2036 Term € Corp UCITS ETF | IE000AD2AYN2 | BlackRock e Borsa Italiana |
| MORPH.MI | 21shares Morpho ETP | CH1506167027 | Stock Events; da confermare con emittente |
| SYRUP.MI | 21shares Maple Finance ETP | CH1495416989 | Borsa Italiana |
| TEND.MI | iShares US Large Cap Moderate Buffer Dec UCITS ETF | IE000Z5YU8X3 | BlackRock / justETF |
| USMID.MI | Franklin ClearBridge US Smaller Companies UCITS ETF | IE000XJA2OU4 | justETF |
| VEZU.MI | Vanguard FTSE Eurozone UCITS ETF EUR Acc | IE000Q4J3CW6 | Borsa Italiana |
| VESC.MI | Vanguard FTSE Developed Europe Small-Cap UCITS ETF EUR Acc | IE00069H3LK0 | Vanguard |
| WBLD.MI | WisdomTree Europe Infrastructure UCITS ETF | IE000AFVONT7 | WisdomTree |
| WDAF.MI | WisdomTree Asia Defence UCITS ETF | IE000017NMH7 | WisdomTree |
| WDGF.MI | WisdomTree Global Defence UCITS ETF | IE000KLC2EN9 | WisdomTree |
| WEM.MI | WisdomTree True Emerging Markets UCITS ETF | IE000Q1M7HB8 | WisdomTree |
| WETH.MI | WisdomTree Physical Ethereum | GB00BJYDH394 | WisdomTree |

### Da verificare / ISIN non ancora identificato

| Ticker | Nota |
|---|---|
| Tutti gli altri ticker della lista dei 63 non riportati nella tabella ISIN | Da completare con verifica individuale, soprattutto dove Yahoo non restituisce dati |

**Attenzione alle categorie:** ATAO, ASUI, CANTN, CBTC, HDRA, MORPH, SYRUP e WETH sono prodotti cripto/ETP, anche se alcuni non erano marcati "cripto" nella tabella iniziale. BUNDS5 è un ETN a leva -5 sul Bund future, non un ETF azionario. WEM, VESC e VEZU sono ETF azionari non cripto.

**Fonti primarie e schede consultate:** [Borsa Italiana ACSW](https://www.borsaitaliana.it/borsa/etf/scheda/IE000CYC2B65-ETFP.html), [iShares ACSW](https://www.ishares.com/it/investitori-professionali/it/prodotti/345835/ishares-msci-all-country-world-swap-ucits-etf), [21shares ASUI](https://www.21shares.com/it-eu/product/asui), [Borsa Italiana ATAO](https://www.borsaitaliana.it/borsa/etc-etn/scheda/CH1495416971-ETFP.html), [Borsa Italiana CANTN](https://www.borsaitaliana.it/borsa/etc-etn/scheda/CH1503127917-ETFP.html), [Borsa Italiana BUNDS5](https://www.borsaitaliana.it/borsa/etc-etn/scheda/XS2425321713-ETFP.html), [justETF CASHE](https://www.justetf.com/it/etf-profile.html?isin=LU3025345516), [Borsa Italiana CBTC](https://www.borsaitaliana.it/borsa/etc-etn/listino-ufficiale.html?isin=CH1199067674&lang=it), [Borsa Italiana ESWP](https://www.borsaitaliana.it/borsa/etf/scheda/IE000S3N6R34-ETFP.html), [21shares HDRA](https://www.21shares.com/it-eu/product/hdra), [Borsa Italiana IB36](https://www.borsaitaliana.it/borsa/etf/scheda/IE000AD2AYN2-ETFP.html), [Borsa Italiana SYRUP](https://www.borsaitaliana.it/borsa/etc-etn/scheda/CH1495416989-ETFP.html), [BlackRock TEND](https://www.blackrock.com/it/investitori-privati/products/345078/ishares-us-large-cap-moderate-buffer-dec-ucits-etf), [justETF USMID](https://www.justetf.com/en-it/etf-profile.html?isin=IE000XJA2OU4), [Borsa Italiana VEZU](https://www.borsaitaliana.it/borsa/etf/scheda/IE000Q4J3CW6-ETFP.html), [Vanguard VESC](https://www.it.vanguard/investitori-privati/prodotti/etf/azionario/E151/ftse-developed-europe-small-cap-ucits-etf-eur-acc), [WisdomTree WBLD](https://www.wisdomtree.com/it/products/equities/wbld---wisdomtree-europe-infrastructure-ucits-etf---eur-acc), [WisdomTree WDAF](https://www.wisdomtree.com/it/products/equities/wdaf---wisdomtree-asia-defence-ucits-etf---usd-acc), [WisdomTree WDGF](https://www.wisdomtree.com/it/products/equities/wdgf---wisdomtree-global-defence-ucits-etf---usd-acc), [WisdomTree WEM](https://www.wisdomtree.com/it/products/equities/wem----wisdomtree-true-emerging-markets-ucits-etf---usd-acc), [WisdomTree WETH](https://www.wisdomtree.com/it/products/digital-assets/wisdomtree-physical-ethereum).

**Prossimo controllo:** confrontare gli ISIN identificati con il file dell'universo di BIGCHATGPT; poi verificare se Yahoo richiede un simbolo alternativo o se lo strumento è stato emesso troppo recentemente per avere uno storico sufficiente. Nessun ticker va rimosso automaticamente.


### Integrazione ISIN — ticker inizialmente senza data nella tabella utente

La ricerca ha identificato anche i due strumenti che erano rimasti senza ISIN nella prima stesura:

| Ticker | Strumento | ISIN | Nota |
|---|---|---|---|
| MDB1Y.MI | UBS Sustainable Development Bank Bonds 1-5 UCITS ETF HJPY Acc | LU3333848920 | ETF obbligazionario in JPY; quotazione Borsa Italiana |
| UST5S.MI | SG ETN Daily Short -5x US Treasury 10Y Future | XS2425318925 | ETN a leva -5 sul future Treasury USA 10 anni |

Fonti: [Borsa Italiana MDB1Y](https://www.borsaitaliana.it/borsa/etf/scheda/LU3333848920-ETFP.html), [Borsa Italiana UST5S](https://www.borsaitaliana.it/borsa/etc-etn/dettaglio.html?isin=XS2425318925&lang=it), [documento KID UST5S](https://kid.sgmarkets.com/public/api/kid/isin/XS2425318925?lang=ita).

**Esito della prima richiesta:** per tutti i 15 ticker che nella tabella utente erano privi di data o indicazione cripto è stato ora individuato un ISIN. Per MORPH l'identificazione è supportata da una fonte secondaria e va confermata con il documento ufficiale dell'emittente. Gli ISIN identificano lo strumento, ma non dimostrano che Yahoo Finance debba necessariamente offrire uno storico per il suffisso .MI.


## Perimetro operativo della validazione — scelta del 13/11/2026

Su indicazione dell'utente, la prima validazione storica viene concentrata sugli strumenti non cripto con anzianità sufficiente. Sono temporaneamente messi fuori dal campione di validazione:
- tutti i ticker indicati come cripto dall'utente;
- gli ETP cripto identificati durante la verifica ISIN anche se non erano stati marcati come cripto nella tabella iniziale (ASUI, ATAO, CANTN, CBTC, HDRA, MORPH, SYRUP, WETH);
- gli strumenti con data di emissione nel 2026 indicata dall'utente: ACSW, ESWP, EUTA, IB36, IB37, VEZU, WBLD, WDAF, WDGF e WETFE.

Questa è un'esclusione **dal campione della validazione**, non una cancellazione dall'universo o dal sito. Non modificare il file master dei ticker e non eliminare le schede degli strumenti.

### Candidati residui da verificare

In base alle informazioni attualmente disponibili, i ticker da esaminare per primi sono:
BUNDS5.MI, CASHE.MI, IG35.MI, MAXD.MI, MAXS.MI, MDB1Y.MI, TEND.MI, UST5S.MI, USMID.MI, VESC.MI e WEM.MI.

Prima di considerarli tutti idonei, verificare data effettiva di prima quotazione, disponibilità dello storico e corrispondenza ticker/ISIN. BUNDS5 e UST5S sono ETN a leva e vanno valutati separatamente; non aggregarli agli ETF ordinari. CASHE, MDB1Y e TEND richiedono particolare attenzione alla data di lancio effettiva.

Gli strumenti con emissione 2025 (IG35, MAXD, MAXS, USMID) non vengono esclusi automaticamente: si verifica quante sedute reali sono disponibili. La soglia minima per una specifica analisi resta quella richiesta dal test, non la sola data di emissione.

**Regola:** l'assenza di dati Yahoo non equivale a delisting. Un ticker entra nel campione soltanto quando sono verificati identità, ISIN, quotazione e numero di barre disponibili. Fino ad allora resta in stato "da verificare".


## Verifica puntuale di rank.py — 13/11/2026

La lettura diretta della versione corrente di `scripts/rank.py` conferma questi punti:

1. Per ogni orizzonte N, il rendimento di base è calcolato come `Close[i+N] / Close[i] - 1` su tutte le barre disponibili. Il riferimento complessivo usato per la t è la **media** di questi rendimenti, mentre l'eccesso principale sottrae la **mediana** di base alla mediana dei rendimenti successivi ai segnali. Sono due confronti diversi e vanno descritti distintamente.
2. La statistica è `(media(rendimenti_segnali_selezionati) - media(rendimenti_base)) / (deviazione_standard_segnali / sqrt(n_segnali))`. Il denominatore misura solo l'incertezza della media dei segnali e tratta la media di base come se fosse priva di errore. Inoltre i rendimenti di base e quelli dei segnali non sono campioni indipendenti. Il valore non va interpretato come un t-test standard valido o come probabilità di successo.
3. Il filtro di non sovrapposizione seleziona un segnale ogni N barre, ma non elimina la dipendenza seriale e di regime. La mediana, la percentuale positiva e gli eccessi nelle due metà sono invece calcolati sull'intero insieme dei segnali misurabili, inclusi quelli con finestre sovrapposte.
4. `MIN_SEGNALI=10` è una soglia minima descrittiva, non una garanzia di potenza statistica. Le due metà richiedono almeno 3 segnali ciascuna; anche questo è un requisito minimo, non una prova di stabilità.
5. Il commento di calibrazione su 150 serie casuali e sui regimi simulati è riportato come testo statico in `REGOLE`: in questo file non è presente il codice che genera le 150 serie né quello che riproduce la calibrazione. La calibrazione non è quindi riproducibile dalla sola implementazione esaminata.
6. La funzione `migliore()` sceglie il massimo eccesso tra i sistemi che superano le regole definite. La selezione del massimo fra 12 sistemi e molti ETF introduce un effetto di selezione del vincitore; la soglia `T_MIN=2.0` non corregge i confronti multipli.

**Intervento consigliato, non ancora applicato:** mantenere separati i risultati descrittivi attuali e una futura validazione inferenziale. Per quest'ultima usare rendimenti non sovrapposti con confronto coerente contro un benchmark, errori standard robusti alla dipendenza temporale o bootstrap a blocchi, correzione per confronti multipli e una finestra out-of-sample mai usata per scegliere il sistema. Non cambiare ora le etichette o la classifica prima di aver definito e testato il nuovo metodo.
