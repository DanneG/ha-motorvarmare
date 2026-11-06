# Motorvärmare för Home Assistant

[English](../README.md) · Svenska

Motorvärmare planerar en elektrisk motorvärmare utifrån en utetemperatursensor och en avresetid. Varje bil har en egen smartplugg eller brytare som fungerar i Home Assistant samt egna avresor. Inställningsformulär, entiteter och tillhörande kort stöder svenska och engelska.

## Installera

Lägg till `https://github.com/DanneG/ha-motorvarmare` som eget förråd i Marketplace eller HACS med kategorin **Integration** och installera det. Starta om Home Assistant vid uppdatering. Lägg sedan till **Motorvärmare** under **Inställningar → Enheter och tjänster** en gång per bil. Välj bilens brytare och en utetemperatursensor i °C eller °F. En Google-kalender kan väljas separat.

Installera också det separata [Motorvärmare-kortet](https://github.com/DanneG/ha-motorvarmare-card) som förråd med kategorin **Dashboard**. Lägg till kortet på en kontrollpanel och välj bilens statusentitet. Följ kortets installationsanvisningar.

För manuell installation: kopiera `custom_components/motorvarmare` till Home Assistants konfigurationsmapp under `custom_components`, inklusive `translations` och `brand`, och starta om Home Assistant. Kortet installeras separat.

## Avresor och kalender

Kortet visar de kommande sju lokala kalenderdagarna med avresor samt uppskattad start och avstängning för värmaren. Starttiderna är en **uppskattning med aktuell utetemperatur**, inte en väderprognos, och kan ändras när temperaturen ändras. En avresa från veckoschema, Google-kalender eller den egna kalendern kan visas här.

Välj en dag i kortets kalender och lägg till en eller flera avresetider. De sparas i bilens egen Home Assistant-kalender och går att ta bort var för sig. De skrivs inte till Google Kalender. Veckoschemat och den tidigare entiteten för en manuell avresa finns kvar. Den närmaste framtida avresan styr.

För Google Kalender: installera först [Google Calendar-integrationen](https://www.home-assistant.io/integrations/google/), välj kalendern i bilens inställningar och ange exakta händelsetitlar och/eller ord eller taggar. Separera flera alternativ med kommatecken eller radbrytning. En händelse matchar om hela titeln stämmer med en vald titel, **eller** om något av orden/taggarna finns i titel eller beskrivning. Versaler och gemener behandlas lika. Händelsens start är avresetiden; heldagshändelser ignoreras. Kalenderändringar kan dröja innan de syns i Home Assistant.

## Gångtid och start nu

Gångtiden i minuter beräknas som **30 − 1,5 × utetemperaturen i °C**. Resultatet avrundas uppåt till hela minuter och begränsas till minst 0 och högst 240 minuter. Exempel: +10 °C → 15 minuter, 0 °C → 30 minuter, −10 °C → 45 minuter och −20 °C → 60 minuter. Vid +20 °C eller varmare är resultatet 0 minuter. Temperaturen omvandlas först till °C om sensorn visar °F.

**Starta nu** använder samma formel och stänger av när den beräknade tiden har gått. **Stoppa** avbryter en uppvärmning som integrationen själv styr. Om brytaren redan är påslagen när den planerade uppvärmningen ska börja tar integrationen inte över den. Gångtider som ställdes in i tidigare versioner används inte längre.

## Valfri effekt- och energiövervakning

I inställningarna för varje bil kan du välja smartpluggens effektsensor i W eller kW och dess ackumulerade energisensor i Wh eller kWh. Energisensorn behöver ha tillståndsklassen `total` eller `total_increasing`. Spara inställningarna mellan körningarna: när de sparas laddas integrationen om och en körning som den styr avbryts. Kortet kan visa aktuell effekt och förbrukningen under den pågående eller senaste körningen. Förbrukningen bygger på senast rapporterade mätvärden; om pluggen rapporterar slutvärdet för sent kan värdet bli för lågt. Om körningens förbrukning inte kan beräknas tillförlitligt visas den som otillgänglig i stället för att gissas.

Om du har valt en effektsensor och aktiverat lågeffektslarmet kan integrationen varna när brytaren är på men effekten ligger under gränsen. Förvalet är 10 W under fem minuter, och båda värdena går att ändra. Larmet kan stängas av separat. En notis visas i Home Assistant. Du kan även välja en notisentitet, till exempel en telefon med Home Assistant-appen, för att få notisen dit. Varje kanal meddelar högst en gång per påslag. Ett saknat eller otillgängligt mätvärde räknas inte som noll watt. Låg effekt kan även ha andra orsaker, till exempel en termostat; kontrollera kabeln och utrustningen.

## Historik över värmningar

Integrationen sparar de 100 senaste perioderna då brytaren varit på separat för varje bil. I kortet kan du se start, stopp, gångtid och uppmätt energi när den finns tillgänglig. Att brytaren varit på betyder inte säkert att värmaren dragit effekt. Historiken börjar samlas in från version 0.7.0; äldre körningar återskapas inte. Körningar sparas även utan energisensor, och saknade eller ofullständiga värden visas inte som noll.

## Drift och säkerhet

Testa start och avstängning med den faktiska brytaren och värmaren innan lösningen används utan uppsikt. Home Assistant måste kunna kommunicera med brytaren för att avstängningskommandot ska nå fram. Använd en separat oberoende maxtimer och utrustning som är avsedd för belastningen och miljön. Följ även bilens och värmarens tillverkaranvisningar.

Integrationen har isolerade tester och har ännu inte verifierats fullt ut på verklig utrustning. Tidpunkter kontrolleras ungefär varje minut och kan påverkas av avbrott eller fördröjd kalendersynkronisering.

## Licens

[MIT](../LICENSE).
