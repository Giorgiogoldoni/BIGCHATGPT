# Secondo audit Entry/Exit — 17 novembre 2026

## Perimetro

Analisi dell'artifact del workflow del 17/11/2026 (periodo 5 anni; 2.148 ETF coperti; codice di ricerca invariato rispetto al commit che ha prodotto i risultati). Il report riguarda esclusivamente il ramo sperimentale `research/entry-exit-engine`. Non modifica Top 20, score, segnali o logica di produzione.

## Esito sintetico

- La sequenza causale principale appare corretta: segnale a Close t, ingresso a Open t+1; stop intraday gap-aware con ATR e massimo noti prima della seduta; regole basate sulla chiusura eseguite all'Open successiva. I test automatici benchmark/entry-exit e audit Mean Reversion risultano superati.
- MR + Target +10% è il candidato più equilibrato tra quelli esaminati: mediana per ticker +4,127%, train +3,486%, test +2,942%, PF mediano 2,172, 4.982 operazioni su 1.665 ETF.
- SMR + Target +10% mostra rendimenti mediani più alti (+10,178%; test +9,477%), ma PF mediano solo 1,093 e campione molto più piccolo (614 operazioni su 316 ETF). Non è ancora robusto abbastanza per essere promosso.
- MR + Bollinger superiore è una seconda alternativa (mediana +2,935%; test +1,272%; PF mediano 2,135).
- SMR + time stop 60 è da scartare allo stato attuale: test -2,481%, PF mediano 0,46. Anche SMR + stop -8% è debole (test -8,10%, PF 0,289).

## Problemi metodologici da correggere prima della selezione definitiva

1. **Split temporali non omogenei.** Train/validation/test sono calcolati per posizione relativa nelle barre di ciascun ETF (60/20/20), non su date di calendario comuni. ETF con date di quotazione differenti hanno periodi train/test differenti.
2. **Possibile contaminazione tra split.** Le operazioni vengono assegnate allo split in base alla data del segnale; un trade aperto vicino al confine può terminare nello split successivo e contribuire al rendimento del precedente. Serve purging: includere nello split solo trade interamente conclusi al suo interno.
3. **Posizioni aperte escluse dai risultati chiusi.** Con MR + Target +10% risultano 523 posizioni aperte su 5.505 ingressi (9,5%); con SMR 55 su 669 (8,2%). Il loro mark-to-market è riportato separatamente, ma non entra nelle metriche principali.
4. **Win rate aggregato assente.** Il ranking mostra soprattutto la mediana dei win rate per ETF. Non equivale al win rate di tutte le operazioni; servono conteggi globali di trade vincenti/perdenti e win rate ponderato.
5. **Costi poco realistici.** È applicato un costo fisso round-trip di 10 bps. Non c'è ancora una sensitivity completa a 20/30/50 bps, spread, slippage e commissioni.
6. **Dividendi esclusi.** Sono usati OHLC non rettificati e il rendimento total-return non è ricostruito. Ciò può penalizzare o alterare il confronto tra ETF distributivi e ad accumulazione.
7. **Survivorship bias.** L'universo è quello attuale; non include in modo sistematico ETF cessati/delistati durante i cinque anni.
8. **Copertura incompleta.** 2.148 strumenti con dati su 2.499 selezionati (circa 86%); 351 ticker non hanno prodotto dati. Gli errori sono elencati nell'artifact ma non classificati in modo sufficiente per distinguere esclusioni strutturali e veri buchi dati.
9. **Ranking uscite aggregate.** Il ranking generale delle uscite somma 13 coorti di ingresso; non va letto come confronto autonomo delle uscite. Per decidere bisogna usare la matrice entry × exit e confrontare sistemi omogenei.
10. **PF e drawdown non sono di portafoglio.** Sono statistiche per ticker/coorte; il drawdown è una sequenza di trade del singolo ticker, non un portafoglio multi-ETF con capitale, pesi, liquidità e sovrapposizioni.

## Top 21 MR — uscita Target +10%

Criterio: ranking per mediana del rendimento **train**, solo ETF con almeno 3 operazioni chiuse e almeno 2 operazioni train. Il test è mostrato ma non usato per ordinare. I valori tra parentesi indicano il numero di operazioni nello split. PF e drawdown sono calcolati sull'intero campione chiuso del singolo ETF.

| # | ETF | Operazioni | Win rate | PF | DD trade | Train | Test |
|--:|---|--:|--:|--:|--:|--:|--:|
| 1 | DAPP.MI | 4 | 100% | ∞ | 0,0% | +16,1% (2) | +10,0% (1) |
| 2 | ENIK.MI | 4 | 100% | ∞ | 0,0% | +15,4% (2) | — |
| 3 | ECRD.MI | 3 | 100% | ∞ | 0,0% | +14,9% (2) | — |
| 4 | NUCL.MI | 4 | 100% | ∞ | 0,0% | +14,5% (2) | +10,5% (2) |
| 5 | CITE.MI | 5 | 80% | 13,03 | -3,7% | +13,9% (3) | -3,7% (1) |
| 6 | EMQQ.MI | 5 | 80% | 4,39 | -14,4% | +13,7% (3) | -14,4% (1) |
| 7 | WCLD.MI | 4 | 50% | 1,86 | -15,3% | +12,8% (3) | -14,6% (1) |
| 8 | XCS7.MI | 3 | 67% | 15,30 | -1,7% | +12,8% (2) | — |
| 9 | CLMA.MI | 4 | 75% | 3,35 | -10,8% | +12,6% (3) | — |
| 10 | ITWN.MI | 4 | 100% | ∞ | 0,0% | +12,6% (2) | +10,8% (1) |
| 11 | HSXD.MI | 3 | 100% | ∞ | 0,0% | +12,4% (2) | — |
| 12 | EQQJ.MI | 3 | 100% | ∞ | 0,0% | +12,2% (2) | — |
| 13 | XMAS.MI | 4 | 75% | 46,58 | -0,8% | +12,0% (3) | — |
| 14 | XLBS.MI | 3 | 67% | 2,17 | -11,1% | +12,0% (2) | — |
| 15 | EBRT.MI | 3 | 100% | ∞ | 0,0% | +11,9% (2) | — |
| 16 | ROE.MI | 6 | 100% | ∞ | 0,0% | +11,9% (4) | +7,6% (1) |
| 17 | SXLB.MI | 4 | 75% | 8,06 | -4,3% | +11,8% (2) | — |
| 18 | IS05.DE | 5 | 60% | 3,00 | -9,3% | +11,8% (3) | -7,6% (1) |
| 19 | VEVE.MI | 3 | 67% | 9,51 | -2,5% | +11,8% (2) | — |
| 20 | N400.MI | 3 | 100% | ∞ | 0,0% | +11,7% (2) | — |
| 21 | WLDC.MI | 3 | 67% | 10,60 | -2,2% | +11,7% (2) | — |

## Top 21 SMR — uscita Target +10%

Stesso criterio di selezione. Il campione SMR è più piccolo e la presenza di PF infinito deriva spesso dall'assenza di perdite nel piccolo campione, non da rischio nullo.

| # | ETF | Operazioni | Win rate | PF | DD trade | Train | Test |
|--:|---|--:|--:|--:|--:|--:|--:|
| 1 | WBLK.MI | 6 | 100% | ∞ | 0,0% | +20,0% (5) | — |
| 2 | URAM.MI | 4 | 100% | ∞ | 0,0% | +17,9% (3) | — |
| 3 | DMAT.MI | 3 | 100% | ∞ | 0,0% | +14,9% (2) | — |
| 4 | CO2.MI | 3 | 100% | ∞ | 0,0% | +14,8% (2) | +10,1% (1) |
| 5 | CHINE.MI | 3 | 100% | ∞ | 0,0% | +14,7% (3) | — |
| 6 | HYGN.MI | 7 | 57% | 1,11 | -23,0% | +12,6% (5) | -21,7% (1) |
| 7 | WCLD.MI | 5 | 80% | 3,56 | -10,9% | +12,1% (3) | +7,2% (1) |
| 8 | CARB.MI | 5 | 100% | ∞ | 0,0% | +11,8% (3) | +10,8% (1) |
| 9 | TINM.MI | 3 | 67% | 1,32 | -19,9% | +11,8% (3) | — |
| 10 | BKCH.MI | 8 | 75% | 2,43 | -15,9% | +11,7% (5) | +9,2% (1) |
| 11 | SEME.MI | 5 | 100% | ∞ | 0,0% | +11,7% (2) | +12,4% (2) |
| 12 | URNJ.MI | 3 | 100% | ∞ | 0,0% | +11,6% (2) | +13,3% (1) |
| 13 | PHPD.MI | 5 | 60% | 1,09 | -22,0% | +11,4% (3) | -0,1% (2) |
| 14 | ENIK.MI | 4 | 100% | ∞ | 0,0% | +11,3% (4) | — |
| 15 | HSTE.MI | 4 | 100% | ∞ | 0,0% | +11,0% (3) | — |
| 16 | SMH.MI | 4 | 100% | ∞ | 0,0% | +10,8% (2) | +13,2% (1) |
| 17 | INRG.MI | 3 | 67% | 2,69 | -8,0% | +10,7% (2) | -8,0% (1) |
| 18 | KSTR.MI | 5 | 60% | 0,81 | -34,9% | +10,5% (3) | -5,7% (2) |
| 19 | SOLR.MI | 5 | 60% | 1,48 | -18,9% | +10,3% (3) | -18,9% (1) |
| 20 | WCBR.MI | 4 | 100% | ∞ | 0,0% | +10,2% (3) | +10,5% (1) |
| 21 | FDNI.MI | 3 | 67% | 0,96 | -21,0% | +9,6% (3) | — |

## Interpretazione e decisioni

- Queste sono shortlist di ricerca, non segnali di acquisto. Il ranking train è costruito su campioni molto piccoli: anche il requisito di 2 trade train è solo un filtro minimo.
- Tra i Top 21 MR, solo 8 hanno almeno un trade nel test; tra i Top 21 SMR, 13. Le mediane test dei singoli ETF sono quindi spesso assenti e, quando presenti, possono dipendere da una sola operazione.
- Un PF infinito e un drawdown pari a zero con 3–4 operazioni non dimostrano robustezza.
- Prima di selezionare strumenti o integrare le regole, correggere split a date comuni con purging, includere mark-to-market delle posizioni aperte, aggiungere win/loss globali, sensitivity costi e rendimento total-return con dividendi.
- Mantenere PR #6 in draft; nessun merge e nessuna modifica alla produzione fino a nuova validazione.
