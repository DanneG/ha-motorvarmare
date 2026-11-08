# Motorvärmare för Home Assistant

[English](../README.md) · Svenska

Motorvärmare planerar en elektrisk motorvärmare utifrån en utetemperatursensor och en avresetid. Varje bil har en egen smartplugg eller brytare som fungerar i Home Assistant samt egna avresor. Inställningsformulär, entiteter och tillhörande kort stöder svenska och engelska.

## Installera

Lägg till `https://github.com/DanneG/ha-motorvarmare` som eget förråd i Marketplace eller HACS med kategorin **Integration** och installera det. Starta om Home Assistant vid uppdatering. Lägg sedan till **Motorvärmare** under **Inställningar → Enheter och tjänster** en gång per bil. Välj bilens brytare och en utetemperatursensor i °C eller °F. En Google-kalender kan väljas separat.

Installera också det separata [Motorvärmare-kortet](https://github.com/DanneG/ha-motorvarmare-card) som förråd med kategorin **Dashboard**. Lägg till kortet på en kontrollpanel och välj bilens statusentitet. Följ kortets installationsanvisningar.

För manuell installation: kopiera `custom_components/motorvarmare` till Home Assistants konfigurationsmapp under `custom_components`, inklusive `translations` och `brand`, och starta om Home Assistant. Kortet installeras separat.

## Avresor och kalender

Kortet visar sju lokala kalenderdagar i taget, med möjlighet att bläddra framåt. Här syns avresor samt uppskattad start och avstängning för värmaren. Starttiderna är **uppskattningar** och kan ändras när temperaturen ändras. En avresa från veckoschema, Google-kalender eller den egna kalendern kan visas här.

Välj en dag i kortets kalender och lägg till en eller flera avresetider. Välj engångsavresa eller upprepning dagligen, veckovis, månadsvis eller årligen, med intervall och valfritt slutdatum. För veckovis upprepning kan flera veckodagar väljas. Avresorna sparas i bilens egen Home Assistant-kalender och skrivs inte till Google Kalender. En enskild avresa eller hela serien kan tas bort. Veckoschemat och den tidigare entiteten för en manuell avresa finns kvar. Den närmaste framtida avresan styr. Återkommande avresor följer Home Assistants lokala tid: klockslag som inte finns vid övergången till sommartid hoppas över och vid dubbel klocktid på hösten används den första förekomsten.

Du kan ändra en enskild lokal avresa eller en hel serie. Ändras seriens start eller upprepningsregel tas dess enskilda ändringar och undantag bort; kortet varnar innan ändringen genomförs. Månadsvis upprepning följer det ursprungliga datumet och hoppar över månader där det datumet saknas. De upprepningar som stöds är de som anges ovan; exempelvis stöds inte ”andra måndagen” eller ändring av ”denna och följande”.

För Google Kalender: installera först [Google Calendar-integrationen](https://www.home-assistant.io/integrations/google/), välj kalendern i bilens inställningar och ange exakta händelsetitlar och/eller ord eller taggar. Separera flera alternativ med kommatecken eller radbrytning. En händelse matchar om hela titeln stämmer med en vald titel, **eller** om något av orden/taggarna finns i titel eller beskrivning. Versaler och gemener behandlas lika. Händelsens start är avresetiden; heldagshändelser ignoreras. Kalenderändringar kan dröja innan de syns i Home Assistant.

Du kan välja en väderentitet med timprognoser. Kalendern visar då uppskattade tider baserade på prognosen och märker ut källan. Saknas prognos används aktuell uppmätt temperatur. Prognosen påverkar bara visningen: den faktiska styrningen använder fortfarande temperatursensorn. Användarens behörighet till väderentiteten kontrolleras.

Med **Hoppa över nästa** hoppar du över nästa avresa utan att ändra kalendern. Du kan även pausa automatisk värmning per bil och återuppta manuellt eller vid en vald tid. Paus stoppar en schemalagd körning som integrationen styr; en manuellt startad körning styrs separat. Valfria driftlarm varnar för problem med brytare, sensor och kalender i Home Assistant och via vald notismottagare. Gränsen för gammalt temperaturvärde kan ändras; saknad rapporteringstid räknas inte som ett gammalt värde.

## Gångtid och start nu

Gångtiden utgår från [M Sveriges rekommendationer för motorns bästa enligt Calix](https://msverige.se/allt-om-bilen/service-och-underhall/motorvarmare/): +10 °C och 0 °C → 60 minuter, −5 °C → 90 minuter, −10 °C → 120 minuter och −20 °C → 180 minuter. Mellan temperaturerna beräknas tiden linjärt och avrundas uppåt till hela minuter. M Sverige anger inga tider utanför detta intervall: integrationen väljer ingen uppvärmning över +10 °C och begränsar tiden till 180 minuter under −20 °C. Temperaturen omvandlas först till °C om sensorn visar °F.

**Starta nu** använder samma beräkning och stänger av när den beräknade tiden har gått. En pågående värmning stoppas också om utetemperaturen stiger över +10 °C. Efter ett temperaturstopp kan schemalagd värmning starta igen vid +9,5 °C eller kallare om avresan fortfarande är aktuell, även efter omstart av Home Assistant. En manuellt startad värmning startar inte om automatiskt. En tillfälligt otillgänglig temperatursensor stoppar inte en pågående värmning. Ett val per bil (avstängt som standard) kan låta schemalagd värmning fortsätta i 30 minuter efter avresan, utöver den beräknade uppvärmningen före avresan. Det förlänger inte körningar med **Starta nu**; temperaturspärren gäller fortfarande. **Stoppa** avbryter en uppvärmning som integrationen själv styr. Om brytaren redan är påslagen när den planerade uppvärmningen ska börja tar integrationen inte över den. Gångtider som ställdes in i tidigare versioner används inte längre.

## Valfri effekt- och energiövervakning

I inställningarna för varje bil kan du välja smartpluggens effektsensor i W eller kW. Integrationen uppskattar energiförbrukningen utifrån effekten över tid; du behöver ingen separat energisensor. Kortet visar aktuell effekt och uppskattad energi för den pågående eller senaste körningen. Det senast rapporterade effektvärdet antas gälla tills nästa värde kommer, så hur exakt beräkningen blir beror på hur ofta sensorn rapporterar förändringar. Om en körnings förbrukning inte kan beräknas tillförlitligt visas den som otillgänglig. Spara inställningarna mellan körningarna: när de sparas laddas integrationen om och en körning som den styr avbryts.

Om du har valt en effektsensor och aktiverat lågeffektslarmet kan integrationen varna när brytaren är på men effekten ligger under gränsen. Förvalet är 10 W under fem minuter, och båda värdena går att ändra. Larmet kan stängas av separat. En notis visas i Home Assistant. Du kan även välja en notisentitet, till exempel en telefon med Home Assistant-appen, för att få notisen dit. Varje kanal meddelar högst en gång per påslag. Ett saknat eller otillgängligt mätvärde räknas inte som noll watt. Låg effekt kan även ha andra orsaker, till exempel en termostat; kontrollera kabeln och utrustningen.

Du kan även aktivera ett separat larm för avvikande effekt och ange en undre gräns, en övre gräns eller båda. Det kräver en effektsensor. Effekten måste ligga utanför intervallet under den valda fördröjningen, som är fem minuter som standard. Det vanliga lågeffektslarmet fungerar separat. Även en termostat eller annan ansluten last kan orsaka en avvikelse.

Välj vid behov ett fast elpris per kWh eller en prissensor och valuta. Med effektsensor summeras den uppskattade kostnaden löpande utifrån effekten och priset, där senast rapporterade värden antas gälla tills de ändras. Saknade mätvärden, avbrott eller omstart under körningen kan göra kostnaden otillgänglig. En vald prissensor går före fast pris, och fast pris används inte som tyst reserv om sensorn saknas. Äldre konfigurationer med enbart en ackumulerande energisensor uppskattar fortfarande kostnaden med priset vid körningens slut. Kostnaden är en uppskattning, inte en elräkning; gamla körningar prissätts inte i efterhand och saknade värden eller blandade valutor markeras som ofullständiga.

## Historik över värmningar

Integrationen sparar de 1 000 senaste perioderna då brytaren varit på separat för varje bil. För nya körningar sparas även uppmätt utetemperatur vid starten när den är tillgänglig. I kortet kan du se start, stopp, gångtid och uppskattad energi när den finns tillgänglig. Att brytaren varit på betyder inte säkert att värmaren dragit effekt. Historiken börjar samlas in från version 0.7.0; äldre körningar återskapas inte. Körningar sparas även utan effektsensor, och saknade eller ofullständiga energiberäkningar visas inte som noll.

Summor per dag, vecka och månad utgår från de registrerade, avslutade körningarna och grupperas efter lokalt slutdatum. Om en körning passerar en periodgräns går energin inte att dela upp tillförlitligt; berörda perioder markeras som ofullständiga och summan för slutperioden kan bli för hög. Även saknade mätvärden och ofullständig historik markeras. Upp till 366 dags-, 104 vecko- och 36 månadssummor visas.

## Fler sensorer

Varje bil får separata sensorer för nästa avresa, planerad start, återstående värmetid, energi för aktuell eller senaste körning, registrerad energi för dag/vecka/månad samt uppskattad energi och kostnad för nästa värmning. De kan användas i andra kort och automationer. Periodvärdena gäller registrerad historik, inte pluggens totala livstidsförbrukning; ofullständiga perioder visas som otillgängliga med partiell information i attribut.

Uppskattningen för nästa värmning använder medeleffekten från en tidigare fullständig körning och den aktuellt beräknade gångtiden, inklusive eventuell eftervärmning. Kostnaden använder aktuellt pris, inte framtida elpriser. Resultatet är en uppskattning som kan påverkas av väder, termostat och hur ofta mätvärden rapporteras. Det visas som otillgängligt utan en fullständig körning för den valda brytaren och mätkällan, eller utan en lämplig kommande värmning. Äldre historik utan denna märkning finns kvar men kan inte ge en prognos förrän en ny fullständig körning har registrerats.

## Drift och säkerhet

Testa start och avstängning med den faktiska brytaren och värmaren innan lösningen används utan uppsikt. Home Assistant måste kunna kommunicera med brytaren för att avstängningskommandot ska nå fram. Använd en separat oberoende maxtimer och utrustning som är avsedd för belastningen och miljön. Följ även bilens och värmarens tillverkaranvisningar.

Integrationen har isolerade tester och har ännu inte verifierats fullt ut på verklig utrustning. Tidpunkter kontrolleras ungefär varje minut och kan påverkas av avbrott eller fördröjd kalendersynkronisering.

Statusentiteten innehåller kalenderbaserade uppgifter om avresor. Den som får läsa statusentiteten kan se uppgifterna; skydda den därför på samma sätt som kalendern.

## Licens

[MIT](../LICENSE).
