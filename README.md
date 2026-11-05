# Motorvärmare för Home Assistant

Motorvärmare är en anpassad integration för att styra en brytare per bil inför en avresa. Du väljer brytare och utetemperatursensor för varje bil. Integrationen beräknar när värmaren ska starta och skickar ett avstängningskommando vid avresan. Avresan kan anges som en engångstid, ingå i ett veckoschema eller hämtas från en kalenderhändelse med en viss titel, ett ord eller en tagg.

Det här är en **integration**, inte ett Home Assistant-tillägg som körs som en separat tjänst. Zigbee-brytarna och temperatursensorn ska redan finnas i Home Assistant.

## Installera

### Via Marketplace eller HACS

1. Öppna Marketplace/HACS i Home Assistant och välj **Anpassade repositories** i menyn.
2. Lägg till `https://github.com/DanneG/ha-motorvarmare` med kategorin **Integration**.
3. Sök efter **Motorvärmare**, ladda ned integrationen och starta om Home Assistant.
4. Gå till **Inställningar → Enheter och tjänster → Lägg till integration**, sök efter **Motorvärmare** och följ stegen.
5. Lägg till en separat instans för varje bil. Välj bilens brytare och en utetemperatursensor, och välj eventuellt en kalender. Anpassa gångtiderna efter behov. Samma temperatursensor kan användas för båda bilarna, men varje bil behöver en egen brytare. Sensorn måste ange temperaturen i °C eller °F.

För att ändra valen senare, öppna integrationens inställningar under **Inställningar → Enheter och tjänster**. Kalenderfältet kan tömmas för att stänga av kalenderstyrning.

### Manuell installation

Kopiera mappen `custom_components/motorvarmare` till Home Assistant-konfigurationens `config/custom_components/motorvarmare/`, behåll alla filer i mappen och starta om Home Assistant. Lägg därefter till integrationen enligt steg 4–5 ovan.

### Om fältnamn eller ikon inte uppdateras

Kopiera hela mappen `custom_components/motorvarmare`, inklusive undermapparna `translations` och `brand`, när du uppdaterar integrationen. Starta om Home Assistant helt och uppdatera därefter webbläsaren. Om äldre fältnamn fortfarande visas, prova att ladda om sidan utan cache eller rensa appens webbdata. Den lokala integrationsikonen stöds i Home Assistant 2026.3 och senare.

## Kort på översikten

Det separata [Motorvärmare-kortet](https://github.com/DanneG/ha-motorvarmare-card) visar status, temperatur och planering och gör det möjligt att ändra avresetider och veckoschema direkt i översikten. Följ kortets egna installationsanvisningar. Att installera integrationen installerar inte kortet automatiskt.

Brytare, utetemperatursensor, kalender, tagg och gångtider ändras i integrationens inställningar under **Enheter och tjänster**. Kortet ställer in avresetider och veckoschema men ändrar inte dessa grundinställningar.

## Google Kalender

1. Lägg först till Home Assistants vanliga [Google Calendar-integration](https://www.home-assistant.io/integrations/google/). Följ anvisningarna där för Google-konto och behörigheter.
2. Välj den kalenderentitet som skapats när du ställer in Motorvärmare. Kalender är valfri.
3. I bilens inställningar kan du ange **exakta händelsetitlar** och/eller **ord och taggar**. Separera flera alternativ med kommatecken eller radbrytning. Exempelvis kan du ange titeln `Till jobbet` och orden/taggarna `#bil1, verkstad`. För en kalender ska minst en titel eller ett ord/en tagg anges. Samma kalender kan användas för båda bilarna med olika inställningar.
4. Skapa en **tidsbestämd** kalenderhändelse. Händelsen räknas om hela titeln stämmer med någon av de exakta titlarna, **eller** om något av orden/taggarna finns i titeln eller beskrivningen. `Till jobbet` matchar till exempel `TILL JOBBET`, men inte `Till jobbet möte` som exakt titel. Jämförelsen skiljer inte mellan stora och små bokstäver. Händelsens starttid är avresetiden. Heldagshändelser ignoreras.

Om du uppdaterar från en tidigare version fortsätter den befintliga taggen att fungera. Den visas bland orden/taggarna nästa gång du öppnar och sparar bilens inställningar. Ta bort eller ändra den om du inte längre vill att den ska ge en matchning.

Exempel: Händelsen `Jobbet #bil1` börjar 07.30. Vid −5 °C är standardgångtiden 60 minuter och brytaren planeras att slås på 06.30 och stängas av 07.30.

Kalenderändringar kan ta tid att nå Home Assistant. Lägg därför in eller ändra resor i god tid, och kontrollera den planerade tiden i Home Assistant. Home Assistant och kalendern behöver vara rätt inställda för din tidszon; Home Assistants inställning finns under **Inställningar → System → Allmänt**.

## Manuell avresa

Ange datum och klockslag i bilens entitet **Manuell avresa** i Home Assistant. Det är en enskild avresa med ett bestämt datum, inte ett automatiskt återkommande dagligt schema. Den manuella tiden rensas automatiskt när den har passerat. Knappen **Rensa manuell avresa** tar bort den tidigare om planerna ändras.

Bilens entitet **Status** visar planeringen. Dess attribut innehåller bland annat nästa avresa, planerad start, temperatur, gångtid, källa och eventuellt fel. Du hittar entiteterna via bilens enhet under **Inställningar → Enheter och tjänster**.

## Veckoschema

Varje bil får ett eget schema med ett klockslag och ett på/av-reglage för var och en av veckans sju dagar, exempelvis **Måndag avresetid** och **Måndag veckoschema**. Dagarna är avstängda från början och standardtiden är 07.00. Aktivera de dagar bilen ska användas och ställ in avresetiden för respektive dag. Tiderna tolkas i Home Assistants lokala tidszon. Engångsavresa och kalender kan användas tillsammans med veckoschemat; den närmaste framtida avresan styr.

Vid övergången till sommartid hoppas en veckotid som inte finns över den dagen. Vid övergången till vintertid, när en lokal tid förekommer två gånger, används den första förekomsten.

## Temperatur och gångtid

Standardvärdena kan justeras för respektive bil, mellan 0 och 240 minuter:

| Utetemperatur | Gångtid före avresa |
| --- | ---: |
| −15 °C eller kallare | 90 minuter |
| Över −15 °C till och med 0 °C | 60 minuter |
| Över 0 °C och under 10 °C | 30 minuter |
| 10 °C eller varmare | 0 minuter |

Tiderna är ett utgångsläge, inte en garanti för att motorn har uppnått en viss temperatur. Behovet beror bland annat på motor, värmare och väder. Följ rekommendationerna från bilens och värmarens tillverkare. [Energimyndigheten](https://www.energimyndigheten.se/effektiv-energianvandning/flerbostadshus/dialog-med-boende/) anger att det oftast räcker att starta motorvärmaren en timme före avresa; tabellen ovan är integrationens valbara standard, inte en tabell från myndigheten.

## Så fungerar styrningen vid ändringar och fel

- Integrationen kontrollerar planeringen ungefär en gång i minuten och försöker läsa kalendern var femte minut. Om läsningen misslyckas, till exempel för att kalendern inte är klar vid uppstart, försöker den igen ungefär en gång i minuten. Ändringar i Google Kalender kan dessutom dröja innan de är tillgängliga i Home Assistant.
- Om utetemperaturen eller brytaren är otillgänglig kan en ny uppvärmning inte starta. Fel visas i bilens status. Om kalendern inte kan läsas startas ingen ny kalenderstyrd uppvärmning utifrån ett gammalt kalendersvar; manuella avresor och veckoschema kan fortfarande användas. Status kan visa kalenderfel även när en manuell avresa fungerar.
- Om integrationen redan har startat värmaren fortsätter den att försöka stänga av vid avresan, även om ett senare kalenderanrop misslyckas. Den försöker också stänga av om den aktuella avresan tas bort. Som skydd finns en maximal sammanhängande gångtid på fyra timmar för en uppvärmning som integrationen har startat.
- Om brytaren redan var påslagen när en uppvärmning skulle ha börjat tar integrationen inte över den och stänger inte av den för den avresan. Om du själv stänger av brytaren under en pågående uppvärmning startar integrationen inte om den för samma avresa.

## Drift och elsäkerhet

- Integrationen har testats med isolerade tester men är ännu inte verifierad i en riktig Home Assistant- och Zigbee-miljö.
- Använd brytare, uttag, kablar och anslutningar som är avsedda för miljön och för värmarens belastning. Följ utrustningens anvisningar.
- Home Assistant, Zigbee-nätverket och brytaren måste fungera och kunna kommunicera för att en planerad avstängning ska nå fram. Avbrott kan göra att värmaren förblir påslagen.
- Använd gärna en separat, oberoende maxtimer som kan bryta strömmen även om Home Assistant eller Zigbee slutar fungera.
- Prova varje bils konfiguration och kontrollera både start och avstängning innan lösningen används utan uppsikt. Kontrollera även att rätt utetemperatur och kalender visas.

