/* Motorvärmare Lovelace card. No external dependencies. */
const MV_DAYS = {sv:["Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag", "Lördag", "Söndag"], en:["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]};
const MV_I18N = {
  sv:{choose:"Välj bilens statusentitet i kortets inställningar.", noStatus:"Status otillgänglig", on:"På", off:"Av", unknown:"Okänd", heater:"Värmare", departure:"Nästa avresa", plannedStart:"Planerad start", temperature:"Utetemperatur", duration:"Gångtid", from:"Avresa från", runNow:"Starta nu", stopNow:"Stoppa nu", plannedStop:"Planerat stopp", owned:"Styrd av Motorvärmare", external:"Brytaren var redan på och styrs separat.", autoOff:"Stängs av automatiskt efter beräknad gångtid.", unknownSwitch:"Brytarens tillstånd är inte tillgängligt.", seven:"Kommande 7 dagar", estimate:"Beräknade tider utifrån aktuell utetemperatur. Starttiden kan ändras när temperaturen ändras.", updateCalendar:"Uppdatera integrationen för att visa kalendern.", updateAdd:"Uppdatera integrationen för att lägga till avresor i kalendern.", today:"I dag", tomorrow:"I morgon", add:"Lägg till", addDay:"Lägg till avresa", noDeparture:"Ingen avresa", noHeat:"Ingen värmning", depShort:"avresa", startShort:"Start", stopShort:"av", missingStart:"Starttid saknas", remove:"Ta bort", removeDeparture:"Ta bort avresa", cancel:"Avbryt", depTime:"Avresetid", single:"Enstaka avresa", dateTime:"Datum och tid", save:"Spara", clear:"Rensa", weekly:"Veckoschema", hide:"Dölj", show:"Visa", enable:"Aktivera", unavailable:"Ej tillgänglig", missingEntities:"Bilens entiteter kunde inte hittas. Kontrollera att integrationen har uppdaterats och startats om.", configBefore:"Kalender, brytare och temperatur ändras i ", configLink:"integrationens inställningar", configAfter:".", chooseDate:"Välj datum och tid för avresan", future:"Välj en framtida avresetid", chooseTime:"Välj en avresetid", actionError:"Kunde inte utföra åtgärden", cardTitle:"Kortets namn", statusEntity:"Bilens statusentitet", editorHint:"Välj bilens statusentitet. Kortet hittar bilens övriga entiteter automatiskt.", cardDescription:"Avresetider och veckoschema för motorvärmaren", addLabel:"Lägg till avresa"},
  en:{choose:"Select the car's status entity in the card settings.", noStatus:"Status unavailable", on:"On", off:"Off", unknown:"Unknown", heater:"Heater", departure:"Next departure", plannedStart:"Planned start", temperature:"Outdoor temperature", duration:"Heating time", from:"Departure from", runNow:"Start now", stopNow:"Stop now", plannedStop:"Planned stop", owned:"Controlled by Motorvärmare", external:"The switch was already on and is controlled separately.", autoOff:"Turns off automatically after the calculated heating time.", unknownSwitch:"The switch state is unavailable.", seven:"Next 7 days", estimate:"Times are estimated using the current outdoor temperature. The start time can change with temperature.", updateCalendar:"Update the integration to show the calendar.", updateAdd:"Update the integration to add calendar departures.", today:"Today", tomorrow:"Tomorrow", add:"Add", addDay:"Add departure", noDeparture:"No departure", noHeat:"No heating", depShort:"departure", startShort:"Start", stopShort:"off", missingStart:"Start time unavailable", remove:"Remove", removeDeparture:"Remove departure", cancel:"Cancel", depTime:"Departure time", single:"One-time departure", dateTime:"Date and time", save:"Save", clear:"Clear", weekly:"Weekly schedule", hide:"Hide", show:"Show", enable:"Enable", unavailable:"Unavailable", missingEntities:"The car's entities could not be found. Check that the integration has been updated and Home Assistant restarted.", configBefore:"Change the calendar, switch and temperature sensor in the ", configLink:"integration settings", configAfter:".", chooseDate:"Choose a departure date and time", future:"Choose a future departure time", chooseTime:"Choose a departure time", actionError:"Could not complete the action", cardTitle:"Card title", statusEntity:"Car status entity", editorHint:"Select the car's status entity. The card finds its other entities automatically.", cardDescription:"Departure times and weekly schedule for the engine heater", addLabel:"Add departure"}
};
MV_I18N.sv.suppressed = "Avstängd för den här avresan";
MV_I18N.en.suppressed = "Turned off for this departure";
MV_I18N.sv.selectEntity = "Välj entitet"; MV_I18N.en.selectEntity = "Select entity";
MV_I18N.sv.missing = "saknas"; MV_I18N.en.missing = "missing";
MV_I18N.sv.from = "Källa:"; MV_I18N.en.from = "Source:";
MV_I18N.sv.heaterControl = "Styr värmaren"; MV_I18N.en.heaterControl = "Heater control";
Object.assign(MV_I18N.sv,{activeHeating:"Pågående värmning",activeStart:"Start",activeNow:"Nu",activeStop:"Planerat stopp",activeRemaining:"kvar",activeFinished:"Stopptiden har passerat",activeProgressUnavailable:"Tid för pågående värmning saknas.",extend30:"Förläng 30 min",extendLimit:"Maximal värmetid har nåtts.",activeEnergy:"Energi hittills",activeCost:"Kostnad hittills",powerGraph:"Effekt över tid",powerGraphShow:"Visa effektgraf",powerGraphHide:"Dölj effektgraf",powerGraphEmpty:"Väntar på effektvärden.",powerGraphMissing:"Effektsensor saknas – välj en i integrationens inställningar.",powerGraphUnit:"Effekt i watt",powerGraphGap:"Avbrott i mätningen visas som luckor.",activeCostEstimate:"Uppskattad kostnad"});
Object.assign(MV_I18N.en,{activeHeating:"Heating in progress",activeStart:"Start",activeNow:"Now",activeStop:"Planned stop",activeRemaining:"remaining",activeFinished:"The planned stop has passed",activeProgressUnavailable:"The current heating time is unavailable.",extend30:"Extend 30 min",extendLimit:"Maximum heating time reached.",activeEnergy:"Energy so far",activeCost:"Cost so far",powerGraph:"Power over time",powerGraphShow:"Show power graph",powerGraphHide:"Hide power graph",powerGraphEmpty:"Waiting for power readings.",powerGraphMissing:"No power sensor – select one in the integration settings.",powerGraphUnit:"Power in watts",powerGraphGap:"Gaps indicate missing measurements.",activeCostEstimate:"Estimated cost"});
MV_I18N.sv.extendMax="Förläng till max"; MV_I18N.en.extendMax="Extend to maximum";
MV_I18N.sv.maximumStop="Fyratimmarsgräns – senast"; MV_I18N.en.maximumStop="Four-hour limit – latest stop";
MV_I18N.sv.measurementSince="Mätning sedan"; MV_I18N.en.measurementSince="Measurement since";
MV_I18N.sv.measurementStartMissing="Mätningens starttid saknas"; MV_I18N.en.measurementStartMissing="Measurement start time unavailable";
MV_I18N.sv.departurePassed = "Avresa passerad"; MV_I18N.en.departurePassed = "Departure passed";
MV_I18N.sv.estimatedHeating = "Beräknad värmning"; MV_I18N.en.estimatedHeating = "Estimated heating";
Object.assign(MV_I18N.sv,{calendarSource:"Källa",calendarHistory:"Registrerade värmningar",calendarHistoryNote:"Registrerade körningar visas separat från kalenderns beräknade tider. Energi och kostnad är uppskattningar.",calendarHistoryDay:"Visa värmningar för"});
Object.assign(MV_I18N.en,{calendarSource:"Source",calendarHistory:"Recorded heating sessions",calendarHistoryNote:"Recorded sessions are shown separately from estimated calendar times. Energy and cost are estimates.",calendarHistoryDay:"Show heating sessions for"});
MV_I18N.sv.calendarHistoryEmpty="Inga registrerade värmningar den här dagen."; MV_I18N.en.calendarHistoryEmpty="No recorded heating sessions on this day.";
MV_I18N.sv.calendarHistoryCostMissing="Kostnad saknas"; MV_I18N.en.calendarHistoryCostMissing="Cost unavailable";
MV_I18N.sv.eventSummary = "Avresa"; MV_I18N.en.eventSummary = "Departure";
MV_I18N.sv.estimate = "Individuellt beräknade tider utifrån aktuell utetemperatur. Tiderna kan ändras när temperaturen ändras.";
MV_I18N.en.estimate = "Individual estimates based on the current outdoor temperature. Times can change with temperature.";
MV_I18N.sv.overlap = "Överlappande tider kan gå ihop. En säkerhetsgräns på fyra timmar gäller för en sammanhängande körning.";
MV_I18N.en.overlap = "Overlapping times may run together. A four-hour safety limit applies to a continuous session.";
MV_I18N.sv.runtimeFor = "Värmer i"; MV_I18N.en.runtimeFor = "Heats for";
MV_I18N.sv.runtimeOff = "stängs sedan av automatiskt."; MV_I18N.en.runtimeOff = "then turns off automatically.";
MV_I18N.sv.preheatDuration = "Före avresa"; MV_I18N.en.preheatDuration = "Before departure";
MV_I18N.sv.postDeparture = "Efter avresa"; MV_I18N.en.postDeparture = "After departure";
MV_I18N.sv.noRuntime = "Formeln ger ingen uppvärmning vid den här temperaturen.";
MV_I18N.en.noRuntime = "The formula gives no heating time at this temperature.";
MV_I18N.sv.tempUnavailable = "Utetemperaturen är inte tillgänglig.";
MV_I18N.en.tempUnavailable = "Outdoor temperature is unavailable.";
MV_I18N.sv.gridHint = "Klicka i kalendern eller på + för att lägga till en avresa. Tiderna visar när värmaren startar och stängs av.";
MV_I18N.en.gridHint = "Click the calendar or + to add a departure. Times show when the heater starts and turns off.";
MV_I18N.sv.scrollHint = "Bläddra i kalendern för att se alla dagar och tider."; MV_I18N.en.scrollHint = "Scroll the calendar to see all days and times.";
MV_I18N.sv.continues = "Fortsätter"; MV_I18N.en.continues = "Continues";
MV_I18N.sv.agenda = "Visa alla avresor och tider"; MV_I18N.en.agenda = "Show all departures and times";
MV_I18N.sv.selectDay = "Välj dag"; MV_I18N.en.selectDay = "Select day";
MV_I18N.sv.mobileHint = "Välj dag för att se tider eller lägga till en avresa.";
MV_I18N.en.mobileHint = "Select a day to see times or add a departure.";
MV_I18N.sv.currentPower = "Effekt just nu"; MV_I18N.en.currentPower = "Current power";
MV_I18N.sv.sessionEnergy = "Beräknad energi, pågående/senaste körning"; MV_I18N.en.sessionEnergy = "Estimated energy, current/last session";
MV_I18N.sv.powerUnavailable = "Effektsensorn är inte tillgänglig."; MV_I18N.en.powerUnavailable = "Power sensor is unavailable.";
MV_I18N.sv.energyUnavailable = "Energiberäkningen är inte tillgänglig. Visat värde är det senaste kända."; MV_I18N.en.energyUnavailable = "Energy calculation is unavailable. The displayed value is the last known reading.";
MV_I18N.sv.energyUnavailableEmpty = "Energiberäkningen är inte tillgänglig."; MV_I18N.en.energyUnavailableEmpty = "Energy calculation is unavailable.";
MV_I18N.sv.energyIncomplete = "Energimätningen för körningen är ofullständig och kan inte visas.";
MV_I18N.en.energyIncomplete = "The session's energy measurement is incomplete and cannot be displayed.";
MV_I18N.sv.energyNoSession = "Ingen energimätning för en körning ännu.";
MV_I18N.en.energyNoSession = "No session energy measurement yet.";
MV_I18N.sv.powerWaiting = "Väntar på effektmätning."; MV_I18N.en.powerWaiting = "Waiting for power measurement.";
MV_I18N.sv.powerAlarm = "Värmaren är på men effekten är låg. Kontrollera att motorvärmarkabeln är ansluten.";
MV_I18N.en.powerAlarm = "The heater is on but power is low. Check that the engine heater cable is connected.";
MV_I18N.sv.history = "Tidigare värmningar"; MV_I18N.en.history = "Heating history";
MV_I18N.sv.historyEmpty = "Inga tidigare värmningar har registrerats ännu.";
MV_I18N.en.historyEmpty = "No previous heating sessions have been recorded yet.";
MV_I18N.sv.historyUpdate = "Uppdatera integrationen för att visa historiken.";
MV_I18N.en.historyUpdate = "Update the integration to show the history.";
MV_I18N.sv.historyStartMissing = "Starttid saknas"; MV_I18N.en.historyStartMissing = "Start time unavailable";
MV_I18N.sv.historyEndMissing = "Sluttid saknas"; MV_I18N.en.historyEndMissing = "End time unavailable";
MV_I18N.sv.historyStart = "Start"; MV_I18N.en.historyStart = "Start";
MV_I18N.sv.historyEnd = "Av"; MV_I18N.en.historyEnd = "Off";
MV_I18N.sv.historyEnergy = "Energi"; MV_I18N.en.historyEnergy = "Energy";
MV_I18N.sv.historyTimeIncomplete = "Tidsuppgifter ofullständiga"; MV_I18N.en.historyTimeIncomplete = "Timing incomplete";
MV_I18N.sv.historyEnergyUnavailable = "Energi saknas"; MV_I18N.en.historyEnergyUnavailable = "Energy unavailable";
MV_I18N.sv.historyShowMore = "Visa fler"; MV_I18N.en.historyShowMore = "Show more";
MV_I18N.sv.historyLessMinute = "under 1 min"; MV_I18N.en.historyLessMinute = "under 1 min";
MV_I18N.sv.calendarPrevious="Föregående vecka"; MV_I18N.en.calendarPrevious="Previous week";
MV_I18N.sv.calendarNext="Nästa vecka"; MV_I18N.en.calendarNext="Next week";
MV_I18N.sv.calendarToday="I dag"; MV_I18N.en.calendarToday="Today";
MV_I18N.sv.calendarLoading="Hämtar kalendern…"; MV_I18N.en.calendarLoading="Loading calendar…";
MV_I18N.sv.calendarFailed="Kalendern kunde inte hämtas. Försök igen."; MV_I18N.en.calendarFailed="The calendar could not be loaded. Try again.";
MV_I18N.sv.calendarPartial="Den externa kalendern kunde inte läsas; vissa avresor kan saknas."; MV_I18N.en.calendarPartial="The external calendar could not be read; some departures may be missing.";
MV_I18N.sv.retry="Försök igen"; MV_I18N.en.retry="Retry";
MV_I18N.sv.refreshCalendar="Uppdatera"; MV_I18N.en.refreshCalendar="Refresh";
MV_I18N.sv.recurrence="Upprepning"; MV_I18N.en.recurrence="Repeat";
MV_I18N.sv.once="Ingen, en avresa"; MV_I18N.en.once="None, one departure";
MV_I18N.sv.daily="Dagligen"; MV_I18N.en.daily="Daily";
MV_I18N.sv.weeklyRepeat="Veckovis"; MV_I18N.en.weeklyRepeat="Weekly";
MV_I18N.sv.monthly="Månadsvis"; MV_I18N.en.monthly="Monthly";
MV_I18N.sv.yearly="Årligen"; MV_I18N.en.yearly="Yearly";
MV_I18N.sv.every="Upprepa var"; MV_I18N.en.every="Repeat every";
MV_I18N.sv.repeatOn="Dagar"; MV_I18N.en.repeatOn="Days";
MV_I18N.sv.until="Till och med (valfritt)"; MV_I18N.en.until="Until (optional)";
MV_I18N.sv.repeatDay="Välj minst en veckodag."; MV_I18N.en.repeatDay="Select at least one weekday.";
MV_I18N.sv.repeatInterval="Ange ett intervall mellan 1 och 99."; MV_I18N.en.repeatInterval="Enter an interval between 1 and 99.";
MV_I18N.sv.repeatEnd="Slutdatumet måste vara samma dag eller senare."; MV_I18N.en.repeatEnd="The end date must be on or after the start date.";
MV_I18N.sv.invalidLocal="Tiden finns inte i Home Assistants tidszon. Välj en annan tid."; MV_I18N.en.invalidLocal="This time does not exist in Home Assistant's time zone. Choose another time.";
MV_I18N.sv.deleteChoice="Ta bort denna avresa eller hela serien?"; MV_I18N.en.deleteChoice="Remove this departure or the entire series?";
MV_I18N.sv.deleteOne="Bara denna"; MV_I18N.en.deleteOne="Only this one";
MV_I18N.sv.deleteSeries="Hela serien"; MV_I18N.en.deleteSeries="Entire series";
MV_I18N.sv.totalEnergy="Energisumma"; MV_I18N.en.totalEnergy="Energy totals";
MV_I18N.sv.totalDay="Dag"; MV_I18N.en.totalDay="Day";
MV_I18N.sv.totalWeek="Vecka"; MV_I18N.en.totalWeek="Week";
MV_I18N.sv.totalMonth="Månad"; MV_I18N.en.totalMonth="Month";
MV_I18N.sv.totalIncomplete="ofullständigt"; MV_I18N.en.totalIncomplete="incomplete";
MV_I18N.sv.totalNote="Baserat på registrerade avslutade körningar. Hela körningens energi räknas till slutdatum; en period som passeras markeras ofullständig och summan kan vara för hög.";
MV_I18N.en.totalNote="Based on recorded completed sessions. All session energy is assigned to the end date; a crossed period is marked incomplete and its total may be too high.";
MV_I18N.sv.totalNone="Inget mätvärde"; MV_I18N.en.totalNone="No measurement";
MV_I18N.sv.totalFrom="Från"; MV_I18N.en.totalFrom="From";
MV_I18N.sv.totalOlder="Äldre perioder visas inte."; MV_I18N.en.totalOlder="Older periods are not shown.";
MV_I18N.sv.edit="Redigera"; MV_I18N.en.edit="Edit";
MV_I18N.sv.editDeparture="Redigera avresa"; MV_I18N.en.editDeparture="Edit departure";
MV_I18N.sv.editChoice="Redigera denna avresa eller hela serien?"; MV_I18N.en.editChoice="Edit this departure or the entire series?";
MV_I18N.sv.editDate="Datum"; MV_I18N.en.editDate="Date";
MV_I18N.sv.editTitle="Titel"; MV_I18N.en.editTitle="Title";
MV_I18N.sv.seriesWarning="Om du ändrar tid eller upprepning tas tidigare ändringar och undantag för enstaka avresor i serien bort."; MV_I18N.en.seriesWarning="Changing the time or recurrence removes previous changes and exceptions for individual departures in the series.";
MV_I18N.sv.seriesConfirm="Jag förstår att ändringar och undantag kan tas bort"; MV_I18N.en.seriesConfirm="I understand that changes and exceptions may be removed";
MV_I18N.sv.seriesConfirmRequired="Bekräfta informationen om serien innan du sparar."; MV_I18N.en.seriesConfirmRequired="Confirm the information about the series before saving.";
MV_I18N.sv.ruleUnsupported="Serien kan inte redigeras här. Uppdatera integrationen eller använd en kalender som stöder schemat."; MV_I18N.en.ruleUnsupported="This series cannot be edited here. Update the integration or use a calendar that supports the schedule.";
Object.assign(MV_I18N.sv,{viewNavigation:"Välj vy",moreActions:"Fler åtgärder",lessActions:"Färre åtgärder",shortEstimate:"Värmetiderna uppskattas utifrån aktuell temperatur.",shortForecast:"Prognos används när den finns. Styrningen använder uppmätt temperatur.",energyOverview:"Energianvändning",energyOverviewHint:"Energiförbrukningen uppskattas utifrån effekten över tid.",energySetup:"Välj en effektsensor i integrationens inställningar för att visa energianvändning."});
Object.assign(MV_I18N.en,{viewNavigation:"Choose view",moreActions:"More actions",lessActions:"Fewer actions",shortEstimate:"Heating times are estimated from the current temperature.",shortForecast:"Forecasts are used when available. Control uses the measured temperature.",energyOverview:"Energy use",energyOverviewHint:"Energy use is estimated from power readings over time.",energySetup:"Select a power sensor in the integration settings to see energy use."});
Object.assign(MV_I18N.sv,{periodToday:"I dag",periodWeek:"Den här veckan",periodMonth:"Den här månaden",periodSummary:"Förbrukning per period",periodHistory:"Visa per period",periodUnavailable:"Ingen uppgift",periodPartial:"Ofullständigt underlag",periodCostMissing:"Kostnad saknas eller är ofullständig"});
Object.assign(MV_I18N.en,{periodToday:"Today",periodWeek:"This week",periodMonth:"This month",periodSummary:"Energy by period",periodHistory:"View by period",periodUnavailable:"No data",periodPartial:"Incomplete data",periodCostMissing:"Cost unavailable or incomplete"});
Object.assign(MV_I18N.sv,{skipNext:"Hoppa över nästa",pause:"Pausa",resume:"Återuppta",paused:"Pausad",pauseUntil:"Pausa till",savePause:"Spara paus",forecast:"Prognos",currentTemperature:"Aktuell temperatur",cost:"Uppskattad kostnad",costIncomplete:"kostnad ofullständig",startsIn:"Startar om",heatingUntil:"Värmer till",overTen:"Ingen värmning över +10 °C",calendarTab:"Kalender",energyTab:"Energi",settingsTab:"Inställningar",carOverview:"Motorvärmare – bilar",addCars:"Välj bilarnas statusentiteter",chooseCar:"Välj bil",backToCars:"Alla bilar",noCars:"Lägg till minst en bil i kortets inställningar."});
Object.assign(MV_I18N.en,{skipNext:"Skip next",pause:"Pause",resume:"Resume",paused:"Paused",pauseUntil:"Pause until",savePause:"Save pause",forecast:"Forecast",currentTemperature:"Current temperature",cost:"Estimated cost",costIncomplete:"cost incomplete",startsIn:"Starts in",heatingUntil:"Heating until",overTen:"No heating above +10 °C",calendarTab:"Calendar",energyTab:"Energy",settingsTab:"Settings",carOverview:"Engine heaters",addCars:"Select car status entities",chooseCar:"Select car",backToCars:"All cars",noCars:"Add at least one car in the card settings."});
MV_I18N.sv.forecastHint="Tiderna uppskattas med väderprognos där den finns, annars aktuell temperatur. Värmaren styrs alltid av den uppmätta temperaturen.";
MV_I18N.en.forecastHint="Times use the weather forecast when available, otherwise the current temperature. Actual heating always uses the measured temperature.";
Object.assign(MV_I18N.sv,{summaryEmpty:"Ingen avresa planerad",summaryAdd:"Lägg till en avresa",timelineStart:"Startar",timelineDeparture:"Avresa",timelineStop:"Beräknat stopp",heatingRange:"Värmer",summaryEstimate:"Planerade tider kan ändras",summaryTemperature:"Ute",summaryDuration:"Värmetid"});
Object.assign(MV_I18N.en,{summaryEmpty:"No departure planned",summaryAdd:"Add a departure",timelineStart:"Starts",timelineDeparture:"Departure",timelineStop:"Estimated stop",heatingRange:"Heating",summaryEstimate:"Planned times may change",summaryTemperature:"Outside",summaryDuration:"Heating time"});
Object.assign(MV_I18N.sv,{openCalendar:"Öppna kalender",closeCalendar:"Stäng kalender",expandedCalendarTitle:"Värmeschema",expandedCalendarHint:"Blocken visar uppskattad uppvärmning inför dina avresor. Tryck eller klicka på en tid i rutnätet för att välja avresetid.",expandedCalendarScroll:"Bläddra i sidled för att se alla dagar och uppåt eller nedåt för fler tider."});
Object.assign(MV_I18N.en,{openCalendar:"Open calendar",closeCalendar:"Close calendar",expandedCalendarTitle:"Heating schedule",expandedCalendarHint:"Blocks show estimated heating before your departures. Click a time in the grid to choose the departure time.",expandedCalendarScroll:"Scroll sideways for all days and up or down for more times."});
Object.assign(MV_I18N.sv,{nextEnergyEstimate:"Uppskattning för nästa värmning",nextEstimateNote:"Baserat på medeleffekten från den senaste fullständiga värmningen. Kostnaden använder aktuellt elpris.",nextEstimateEnergyOnly:"Baserat på medeleffekten från den senaste fullständiga värmningen.",startTemperature:"Utetemperatur vid start",deviationLow:"Effekten har varit lägre än det inställda normalintervallet. Kontrollera utrustningen och inställningarna.",deviationHigh:"Effekten har varit högre än det inställda normalintervallet. Kontrollera utrustningen och inställningarna.",deviationUnknown:"Effekten har avvikit från det inställda normalintervallet. Kontrollera utrustningen och inställningarna."});
Object.assign(MV_I18N.en,{nextEnergyEstimate:"Estimate for next heating session",nextEstimateNote:"Based on the average power of the latest complete session. Cost uses the current electricity price.",nextEstimateEnergyOnly:"Based on the average power of the latest complete session.",startTemperature:"Outdoor temperature at start",deviationLow:"Power has been below the configured normal range. Check the equipment and settings.",deviationHigh:"Power has been above the configured normal range. Check the equipment and settings.",deviationUnknown:"Power has been outside the configured normal range. Check the equipment and settings."});
MV_I18N.sv.finishEditing="Spara eller avbryt ändringen innan du byter vecka."; MV_I18N.en.finishEditing="Save or cancel the edit before changing weeks.";
Object.assign(MV_I18N.sv,{switch_unavailable:"Brytaren är inte tillgänglig.",start_failed:"Värmaren kunde inte bekräftas påslagen.",stop_failed:"Värmaren kunde inte bekräftas avstängd.",temperature_unavailable:"Utetemperaturen är inte tillgänglig.",temperature_stale:"Temperaturgivaren verkar inte ha rapporterat på länge.",calendar_unavailable:"Kalendern kan inte läsas."});
Object.assign(MV_I18N.en,{switch_unavailable:"The switch is unavailable.",start_failed:"Could not confirm that the heater turned on.",stop_failed:"Could not confirm that the heater turned off.",temperature_unavailable:"The outdoor temperature is unavailable.",temperature_stale:"The temperature sensor may not have reported recently.",calendar_unavailable:"The calendar cannot be read."});
const MV_EN_STATES = {"Väntar":"Waiting", "Väntar på start":"Waiting to start", "Värmer":"Heating", "Avstängd":"Off", "Pausad":"Paused", "Ingen avresa":"No departure", "Ingen uppvärmning behövs":"No heating needed", "Fel":"Error", "Brytaren var redan på":"Switch was already on", "Manuellt avstängd för denna avresa":"Manually turned off for this departure", "Kalender":"Calendar", "Manuell":"Manual", "Veckoschema":"Weekly schedule", "Planerad":"Scheduled", "Lokal":"Local", "Starta nu":"Start now"};
const MV_EN_ERRORS = {"Brytaren är inte tillgänglig":"The switch is unavailable", "Värmaren är redan på eller styrs redan av integrationen":"The heater is already on or controlled by the integration", "Utetemperaturen är inte tillgänglig":"Outdoor temperature is unavailable", "Formeln ger ingen uppvärmning vid den här temperaturen":"The formula gives no heating time at this temperature", "Integrationen styr ingen pågående uppvärmning":"The integration is not controlling an active heating session", "Kunde inte slå på brytaren":"Could not turn on the switch", "Kunde inte stänga av brytaren; försöker igen":"Could not turn off the switch; retrying", "Kunde inte bekräfta att brytaren är av; försöker igen":"Could not confirm that the switch is off; retrying", "Brytarens tillstånd är okänt":"The switch state is unknown", "Utetemperaturen är inte tillgänglig eller saknar temperaturenhet":"Outdoor temperature is unavailable or has no temperature unit", "Kalendern svarade inte i tid; försöker igen":"Calendar timed out; retrying", "Kalendern kan inte läsas; se Home Assistants logg":"Calendar could not be read; check the Home Assistant log", "Kalendern kan inte läsas":"Calendar could not be read", "Kunde inte slå på brytaren; försöker stänga av":"Could not turn on the switch; trying to turn it off", "Ett oväntat fel uppstod; kontrollera loggen":"Unexpected error; check the log"};
const MV_STATUS_KEYS = {waiting:"Väntar", error:"Fel", heating:"Värmer", stopped:"Avstängd", paused:"Pausad", no_departure:"Ingen avresa", no_heating_needed:"Ingen uppvärmning behövs", waiting_to_start:"Väntar på start", already_on:"Brytaren var redan på", manually_stopped:"Manuellt avstängd för denna avresa"};
const mvEscape = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const mvUsable = (s) => s && !["unknown", "unavailable"].includes(s.state);
const mvLang = (hass) => String(hass?.locale?.language || hass?.language || "sv").toLowerCase().startsWith("sv") ? "sv" : "en";
const mvText = (hass, key) => MV_I18N[mvLang(hass)][key] || key;
const mvDuration = (hass, minutes) => {
  if (!Number.isFinite(minutes) || minutes < 0) return "–";
  const rounded = Math.round(minutes);
  if (minutes > 0 && rounded === 0) return mvText(hass, "historyLessMinute");
  const hours = Math.floor(rounded / 60), remainder = rounded % 60;
  if (!hours) return `${remainder} min`;
  return `${hours} ${mvLang(hass) === "sv" ? "tim" : "h"}${remainder ? ` ${remainder} min` : ""}`;
};
const mvStateText = (hass, value) => {
  const swedish = MV_STATUS_KEYS[value] || value;
  return mvLang(hass) === "en" ? (MV_EN_STATES[swedish] || swedish) : swedish;
};
const mvErrorText = (hass, value) => {
  if (mvLang(hass) !== "en" || typeof value !== "string") return value;
  return Object.entries(MV_EN_ERRORS).sort((a,b)=>b[0].length-a[0].length).reduce((text,[sv,en])=>text.split(sv).join(en),value);
};

// Keep stable nodes in place: replacing the entire shadow tree destroys the
// browser's scroll anchor, including the anchor of a surrounding HA view.
const mvPatch = (root, html) => {
  const template = document.createElement("template");
  template.innerHTML = html;
  const key = node => {
    if (node.nodeType !== Node.ELEMENT_NODE) return `#${node.nodeType}`;
    if (node.id) return `${node.localName}#${node.id}`;
    const data = [...node.attributes].filter(a => a.name.startsWith("data-")).map(a => `${a.name}=${a.value}`).join(";");
    return `${node.localName}.${node.getAttribute("class") || ""}|${data}`;
  };
  const sync = (existing, desired) => {
    if (existing.nodeType !== desired.nodeType || (existing.nodeType === Node.ELEMENT_NODE && existing.localName !== desired.localName)) {
      existing.replaceWith(desired.cloneNode(true)); return;
    }
    if (existing.nodeType === Node.TEXT_NODE || existing.nodeType === Node.COMMENT_NODE) {
      if (existing.nodeValue !== desired.nodeValue) existing.nodeValue = desired.nodeValue;
      return;
    }
    if (existing.nodeType === Node.ELEMENT_NODE) {
      for (const attr of [...existing.attributes]) if (!desired.hasAttribute(attr.name)) existing.removeAttribute(attr.name);
      for (const attr of [...desired.attributes]) if (existing.getAttribute(attr.name) !== attr.value) existing.setAttribute(attr.name, attr.value);
    }
    const wanted = [...desired.childNodes];
    for (let i = 0; i < wanted.length; i++) {
      let current = existing.childNodes[i], next = wanted[i];
      if (!current || key(current) !== key(next)) {
        const candidate = [...existing.childNodes].slice(i + 1).find(node => key(node) === key(next));
        const currentKey = current && key(current);
        const oldCount = current && [...existing.childNodes].slice(i).filter(node => key(node) === currentKey).length;
        const wantedCount = current && wanted.slice(i).filter(node => key(node) === currentKey).length;
        if (candidate && oldCount > wantedCount) {
          // Remove obsolete siblings instead of detaching a stable calendar or
          // other potential page scroll anchor and inserting it again.
          current.remove(); i--; continue;
        }
        if (candidate) { existing.insertBefore(candidate, current || null); current = candidate; }
        else { current = next.cloneNode(true); existing.insertBefore(current, existing.childNodes[i] || null); continue; }
      }
      sync(current, next);
    }
    while (existing.childNodes.length > wanted.length) existing.lastChild.remove();
    // Reused inputs may have a dirty value/checked property after interaction;
    // syncing attributes alone would leave the displayed value out of date.
    if (existing.nodeType === Node.ELEMENT_NODE && existing !== root.activeElement) {
      if (existing.localName === "input") {
        if (["checkbox", "radio"].includes(existing.type)) {
          if (existing.checked !== desired.checked) existing.checked = desired.checked;
        } else if (existing.value !== desired.value) existing.value = desired.value;
      } else if (existing.localName === "select" && existing.value !== desired.value) {
        existing.value = desired.value;
      }
    }
  };
  sync(root, template.content);
};

class MotorvarmareCard extends HTMLElement {
  constructor() {
    super(); this.attachShadow({mode:"open"}); this._config = {}; this._showWeek = false; this._showHistory = true; this._historyLimit = 10; this._draft = null; this._pending = false;
    this._selectedDay = null; this._calendarTime = "07:00"; this._initialCalendarScroll = null;
    this._windowOffset = 0; this._windowEvents = null; this._windowLoading = false; this._windowError = null; this._windowUnsupported = false; this._windowCalendarError = false; this._windowRequest = 0; this._windowStart = null; this._windowOverride = false; this._todayBaseSignature = null;
    this._forecastRequestSignature = null;
    this._forecastEnabled = null;
    this._repeatFreq = "NONE"; this._repeatInterval = 1; this._repeatDays = []; this._repeatUntil = ""; this._deleteRecurrence = null; this._editChoice=null; this._editContext=null; this._editDate=""; this._editSummary=""; this._editAcknowledged=false;
    this._totalPeriod = "daily"; this._totalLimit = 7;
    this._pauseDraft = null; this._showPauseDate = false; this._showMoreActions = false;
    this._activeView = "calendar"; this._showPowerGraph=true;
    this._calendarAnchored = false; this._calendarUserScrolled = false; this._desktopPosition = null;
    this._calendarExpanded = false; this._calendarPlaceholderHeight = 0;
    this._mobileDay = null; this._mobileDayChosen = false;
    this.shadowRoot.addEventListener("focusout", () => setTimeout(() => {
      const focused = this.shadowRoot.activeElement;
      if (this._refreshAfterFocus && (!focused || !["INPUT", "SELECT"].includes(focused.tagName))) {
        this._refreshAfterFocus = false; this._render();
      }
    }, 0));
  }
  connectedCallback() {
    // Update the calendar at a departure/stop boundary even if Home Assistant
    // has no other state changes; avoid periodic re-renders in between.
    if (!this._transitionTimer) this._transitionTimer=setInterval(()=>{
      this._updateActiveProgress();
      if (!(this._nextCalendarTransition <= Date.now())) return;
      const focused=this.shadowRoot.activeElement;
      if (focused && ["INPUT","SELECT"].includes(focused.tagName)) this._refreshAfterFocus=true;
      else this._render();
    },30000);
    const scroll=this.shadowRoot.querySelector(".cal-scroll");
    if (scroll?.clientHeight && this._initialCalendarScroll) {
      scroll.scrollTop=this._initialCalendarScroll.top; scroll.scrollLeft=this._initialCalendarScroll.left;
      this._desktopPosition={top:scroll.scrollTop,left:scroll.scrollLeft};
      this._initialCalendarScroll=null;
    }
    if (typeof ResizeObserver !== "undefined") {
      this._resizeObserver = new ResizeObserver(entries => {
        const width=entries[0]?.contentRect?.width;
        if (!width) return;
        const calendarWidth=this.shadowRoot.querySelector(".calendar")?.clientWidth || width-40;
        const narrow=calendarWidth <= 839;
        if (this._layoutNarrow !== undefined && narrow !== this._layoutNarrow) {
          const focused=this.shadowRoot.activeElement;
          if (focused && ["INPUT","SELECT"].includes(focused.tagName)) this._refreshAfterFocus=true;
          else this._render();
        }
        this._layoutNarrow=narrow;
      });
      this._resizeObserver.observe(this);
    }
  }
  disconnectedCallback() { this._resizeObserver?.disconnect(); this._resizeObserver=null; clearInterval(this._transitionTimer); this._transitionTimer=null; }
  static getConfigElement() { return document.createElement("motorvarmare-card-editor"); }
  static getStubConfig() { return {title:"Motorvärmare"}; }
  getCardSize() { return this._showWeek ? 8 : 4; }
  getGridOptions() { return {columns:6, min_columns:3, rows:"auto"}; }
  setConfig(config) {
    if (!config || typeof config !== "object") throw new Error("Ogiltig konfiguration");
    if (this._config.status_entity !== config.status_entity) {
      this._draft = null; this._selectedDay = null; this._editChoice=null; this._editContext=null; this._initialCalendarScroll = null;
      this._calendarAnchored = false; this._calendarUserScrolled = false; this._desktopPosition = null;
      this._mobileDay = null; this._mobileDayChosen = false; this._showHistory = true; this._historyLimit = 10;
      this._pauseDraft = null; this._showPauseDate = false; this._showMoreActions = false;
      this._activeView = "calendar"; this._showPowerGraph=true;
      this._calendarExpanded = false; this._calendarPlaceholderHeight = 0;
      this._windowOffset = 0; this._windowEvents = null; this._windowLoading = false; this._windowError = null; this._windowCalendarError = false; this._windowStart = null; this._windowOverride = false; this._todayBaseSignature = null; this._windowRequest++;
      this._forecastRequestSignature = null;
      this._forecastEnabled = null;
    }
    this._config = {...config}; this._render();
  }
  set hass(value) {
    this._hass = value;
    if (!this._windowOffset && this._windowOverride && this._todayBaseSignature !== null) {
      const latest=JSON.stringify(value?.states?.[this._config.status_entity]?.attributes?.schedule_7_days ?? null);
      if (latest !== this._todayBaseSignature) {this._windowOverride=false;this._windowRequest++;this._windowLoading=false;this._windowError=null;}
    }
    // A displayed future window shifts when the local calendar day rolls over.
    // Never keep the previous day's events under the new date headers.
    if (this._windowOffset && this._windowStart && this._dayKeys()[0] !== this._windowStart) {
      this._windowEvents=null; this._loadCalendarWindow(); return;
    }
    const currentAttributes=value?.states?.[this._config.status_entity]?.attributes;
    const forecastEnabled=!!currentAttributes?.weather_enabled;
    if (currentAttributes && this._forecastEnabled !== null && this._forecastEnabled !== forecastEnabled) {
      this._forecastRequestSignature=null;
      this._windowRequest++; this._windowEvents=null; this._windowOverride=false;
      this._windowLoading=false; this._windowError=null; this._windowCalendarError=false;
      this._forecastEnabled=forecastEnabled;
      if (this._windowOffset) {this._loadCalendarWindow();return;}
    }
    if (currentAttributes) this._forecastEnabled=forecastEnabled;
    if (!this._windowOffset && currentAttributes?.weather_enabled && currentAttributes?.schedule_query_supported === true) {
      const signature=JSON.stringify([this._config.status_entity,Math.floor(Date.now()/900000),currentAttributes.schedule_7_days]);
      if (signature !== this._forecastRequestSignature) {
        this._forecastRequestSignature=signature;
        this._loadCalendarWindow(true); return;
      }
    } else if (!currentAttributes?.weather_enabled) this._forecastRequestSignature=null;
    // Keep typed but unsaved values intact during unrelated HA updates.
    const focused = this.shadowRoot.activeElement;
    if (!focused || !["INPUT", "SELECT"].includes(focused.tagName)) this._render();
    else this._refreshAfterFocus = true;
  }
  _entities() {
    const auto = this._hass?.states?.[this._config.status_entity]?.attributes?.control_entities || {};
    return {
      manual_entity:auto.manual_departure,
      clear_entity:auto.clear_departure,
      switch_entity:auto.heater_switch,
      calendar:auto.calendar,
      start_now:auto.start_now,
      stop_now:auto.stop_now,
      extend_30:auto.extend_30,
      skip_next:auto.skip_next,
      automation_paused:auto.automation_paused,
      pause_until:auto.pause_until,
      weekly:MV_DAYS.sv.map((_, i) => ({time:auto.weekly_times?.[i], enabled:auto.weekly_enabled?.[i]})),
    };
  }
  _timeZone() { return this._hass?.config?.time_zone || undefined; }
  _activeOffsetChanged(start,end) {
    try {
      const format=new Intl.DateTimeFormat("en-GB",{timeZone:this._timeZone(),timeZoneName:"shortOffset"});
      const offset=instant=>format.formatToParts(new Date(instant)).find(part=>part.type==="timeZoneName")?.value;
      return offset(start)!==offset(end);
    } catch (_) { return false; }
  }
  _activeTick(start,end,part,ambiguous) {
    const value=new Date(start+(end-start)*part).toISOString();
    return this._clock(value,this._dayKey(value),ambiguous);
  }
  _updateActiveProgress() {
    const data=this._activeProgress;
    if (!data || !this.shadowRoot) return;
    const now=Date.now(), axisEnd=Math.max(data.end,now), duration=axisEnd-data.start;
    const ratio=Number.isFinite(duration) && duration>0 ? Math.max(0,Math.min(1,(now-data.start)/duration)) : null;
    const fill=this.shadowRoot.querySelector(".active-progress-fill");
    if (fill && ratio!==null) fill.style.width=`${(ratio*100).toFixed(2)}%`;
    const marker=this.shadowRoot.querySelector(".active-progress-dot");
    if (marker && ratio!==null) marker.style.left=`${(ratio*100).toFixed(2)}%`;
    const graphMarker=this.shadowRoot.querySelector(".active-chart-now");
    if (graphMarker && ratio!==null) graphMarker.style.left=`${(ratio*100).toFixed(2)}%`;
    const overdue=now>data.end;
    const stopRatio=Number.isFinite(duration) && duration>0 ? Math.max(0,Math.min(1,(data.end-data.start)/duration)) : null;
    this.shadowRoot.querySelectorAll(".active-stop-marker").forEach(marker=>{
      marker.hidden=!overdue;
      if (stopRatio!==null) marker.style.left=`${(stopRatio*100).toFixed(2)}%`;
    });
    const stopLegend=this.shadowRoot.querySelector(".active-stop-explanation");
    if (stopLegend) stopLegend.hidden=!overdue;
    if (overdue && Number.isFinite(data.start) && duration>0) {
      // Update just this chart and its labels; never rebuild the page or disturb focus.
      const ambiguous=this._activeOffsetChanged(data.start,axisEnd);
      this.shadowRoot.querySelector(".active-axis")?.classList.toggle("active-ambiguous",ambiguous);
      this.shadowRoot.querySelectorAll(".active-tick").forEach((tick,i)=>{tick.textContent=this._activeTick(data.start,axisEnd,[0,.5,1][i],ambiguous);});
      const chart=this.shadowRoot.querySelector(".active-chart");
      if (chart) chart.outerHTML=this._activeGraph(data.samples,data.start,axisEnd,now,data.end);
    }
    const nowLabel=this.shadowRoot.querySelector(".active-progress-now");
    if (nowLabel && ratio!==null) nowLabel.style.left=`${Math.max(7,Math.min(93,ratio*100)).toFixed(2)}%`;
    const progress=this.shadowRoot.querySelector(".active-progress");
    if (progress && ratio!==null) progress.setAttribute("aria-valuenow",String(Math.round(ratio*100)));
    const remaining=this.shadowRoot.querySelector(".active-remaining");
    if (remaining && Number.isFinite(data.end)) {
      const mins=Math.ceil((data.end-now)/60000);
      remaining.textContent=mins>0 ? `${mvDuration(this._hass,mins)} ${mvText(this._hass,"activeRemaining")}` : mvText(this._hass,"activeFinished");
    }
  }
  _date(value, includeOffset=false, includeYear=false) {
    if (!value) return "–";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "–";
    const options = {timeZone:this._timeZone(), weekday:"short", day:"numeric", month:"short", hour:"2-digit", minute:"2-digit"};
    if (includeOffset) options.timeZoneName = "shortOffset";
    if (includeYear) options.year = "numeric";
    return new Intl.DateTimeFormat(mvLang(this._hass) === "sv" ? "sv-SE" : "en-GB", options).format(date);
  }
  _inputDate(value) {
    if (!value || ["unknown", "unavailable"].includes(value)) return "";
    const date = new Date(value); if (Number.isNaN(date.getTime())) return "";
    const p = Object.fromEntries(new Intl.DateTimeFormat("sv-SE", {timeZone:this._timeZone(), year:"numeric", month:"2-digit", day:"2-digit", hour:"2-digit", minute:"2-digit", hourCycle:"h23"}).formatToParts(date).filter(x=>x.type!=="literal").map(x=>[x.type,x.value]));
    return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
  }
  _dayKey(value) {
    return this._inputDate(value).slice(0, 10);
  }
  _dayKeys() {
    const today = this._dayKey(new Date().toISOString());
    if (!today) return [];
    const [y,m,d] = today.split("-").map(Number);
    return Array.from({length:7}, (_,i) => new Date(Date.UTC(y,m-1,d+i+this._windowOffset,12)).toISOString().slice(0,10));
  }
  _dayLabel(key, i) {
    const date = new Date(`${key}T12:00:00Z`);
    const text = new Intl.DateTimeFormat(mvLang(this._hass) === "sv" ? "sv-SE" : "en-GB", {timeZone:"UTC", weekday:"short", day:"numeric", month:"short"}).format(date);
    const today=this._dayKey(new Date().toISOString());
    const tomorrow=today ? new Date(Date.parse(`${today}T12:00:00Z`)+86400000).toISOString().slice(0,10) : "";
    return key === today ? `${mvText(this._hass,"today")} · ${text}` : key === tomorrow ? `${mvText(this._hass,"tomorrow")} · ${text}` : text;
  }
  _defaultCalendarTime(key) {
    const now=new Date(), current=this._inputDate(now.toISOString());
    if (key !== current.slice(0,10)) return "07:00";
    const next=this._inputDate(new Date(now.getTime()+60000).toISOString());
    return next.slice(0,10) === key ? next.slice(11,16) : "23:59";
  }
  _localToUtc(value) {
    // Resolve wall time against Home Assistant's timezone, not the browser's.
    const m=/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value || "");
    if (!m) return null;
    const target=Date.UTC(+m[1],+m[2]-1,+m[3],+m[4],+m[5]);
    let guess=target;
    for (let i=0;i<5;i++) {
      const local=this._inputDate(new Date(guess).toISOString()), p=/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(local);
      if (!p) return null;
      const adjustment=target-Date.UTC(+p[1],+p[2]-1,+p[3],+p[4],+p[5]);
      if (!adjustment) break;
      guess+=adjustment;
    }
    if (this._inputDate(new Date(guess).toISOString()) !== value) return null;
    // The first occurrence is used for a repeated autumn wall-clock time.
    for (let minutes=30; minutes<=180; minutes+=30) {
      const earlier=guess-minutes*60000;
      if (this._inputDate(new Date(earlier).toISOString()) === value) guess=earlier;
    }
    return new Date(guess).toISOString();
  }
  _selectCalendarDay(key) {
    this._selectedDay=key; this._editDate=key; this._editSummary=""; this._editChoice=null; this._editContext=null; this._deleteRecurrence=null; this._calendarTime=this._defaultCalendarTime(key);
    this._repeatFreq="NONE"; this._repeatInterval=1; this._repeatUntil="";
    const weekday=new Date(`${key}T12:00:00Z`).getUTCDay();
    this._repeatDays=[["SU","MO","TU","WE","TH","FR","SA"][weekday]];
    this._render();
  }
  _startEditing(item, series=false) {
    const raw=series ? item.series_start : item.departure;
    if (!raw || (series && typeof item.series_summary !== "string") || Number.isNaN(new Date(raw).getTime())) {this._actionError=mvText(this._hass,"ruleUnsupported");this._editChoice=null;this._render();return;}
    const parts={};
    if (series) {
      const chunks=String(item.rrule || "").split(";");
      for (const chunk of chunks) {const [key,val,...extra]=chunk.split("=");if(!key || !val || extra.length || parts[key] || !["FREQ","INTERVAL","BYDAY","UNTIL"].includes(key)){this._actionError=mvText(this._hass,"ruleUnsupported");this._render();return;}parts[key]=val;}
      if (!["DAILY","WEEKLY","MONTHLY","YEARLY"].includes(parts.FREQ) || (parts.BYDAY && !parts.BYDAY.split(",").every(d=>["MO","TU","WE","TH","FR","SA","SU"].includes(d)))) {this._actionError=mvText(this._hass,"ruleUnsupported");this._render();return;}
    }
    const departureDay=this._dayKey(item.departure);
    this._selectedDay=this._dayKeys().includes(departureDay) ? departureDay : this._dayKeys()[0]; this._editDate=this._dayKey(raw); this._calendarTime=this._inputDate(raw).slice(11,16);
    this._editSummary=series ? item.series_summary : (item.summary || mvText(this._hass,"eventSummary")); this._editChoice=null; this._deleteRecurrence=null;
    this._editContext={uid:item.uid,recurrence_id:item.recurrence_id || null,series,occurrence:!!item.recurrence_id && !series}; this._editAcknowledged=false;
    this._repeatFreq=parts.FREQ || "NONE"; this._repeatInterval=parts.INTERVAL || 1;
    this._repeatDays=parts.BYDAY ? parts.BYDAY.split(",") : [["SU","MO","TU","WE","TH","FR","SA"][new Date(`${this._editDate}T12:00:00Z`).getUTCDay()]];
    this._repeatUntil="";
    if (parts.UNTIL) {
      const u=parts.UNTIL;
      if (/^\d{8}$/.test(u)) this._repeatUntil=`${u.slice(0,4)}-${u.slice(4,6)}-${u.slice(6,8)}`;
      else if (/^\d{8}T\d{6}Z$/.test(u)) this._repeatUntil=this._dayKey(`${u.slice(0,4)}-${u.slice(4,6)}-${u.slice(6,8)}T${u.slice(9,11)}:${u.slice(11,13)}:${u.slice(13,15)}Z`);
      else {this._editContext=null;this._selectedDay=null;this._actionError=mvText(this._hass,"ruleUnsupported");}
    }
    if (this._editContext) {
      this._editContext.originalStart=raw;
      this._editContext.originalWall=`${this._editDate}T${this._calendarTime}`;
      this._editContext.originalRule=series ? item.rrule : null;
      this._editContext.originalRepeat=JSON.stringify([this._repeatFreq,String(this._repeatInterval),this._repeatDays,this._repeatUntil]);
    }
    this._render();
  }
  _changeCalendarWindow(delta) {
    this._windowOffset=delta === null ? 0 : Math.max(0,this._windowOffset+delta);
    this._selectedDay=null; this._editChoice=null; this._editContext=null; this._deleteRecurrence=null; this._mobileDayChosen=false; this._mobileDay=null;
    this._windowEvents=null; this._windowError=null; this._windowUnsupported=false; this._windowCalendarError=false; this._windowOverride=false; this._todayBaseSignature=null;
    if (this._windowOffset) this._loadCalendarWindow();
    else if (this._hass?.states?.[this._config.status_entity]?.attributes?.weather_enabled) this._loadCalendarWindow(true);
    else { this._windowRequest++; this._windowLoading=false; this._render(); }
  }
  _renderUnlessEditing() {
    const focused=this.shadowRoot.activeElement;
    if (focused && ["INPUT","SELECT"].includes(focused.tagName)) this._refreshAfterFocus=true;
    else this._render();
  }
  async _loadCalendarWindow(forceToday=false) {
    if ((!this._windowOffset && !forceToday && !this._windowOverride) || !this._hass || !this._config.status_entity) return;
    if (this._hass.states?.[this._config.status_entity]?.attributes?.schedule_query_supported !== true) {
      if (this._windowOffset) {this._windowError="unsupported";this._windowUnsupported=true;this._windowLoading=false;this._windowStart=this._dayKeys()[0];}
      this._renderUnlessEditing(); return;
    }
    if (!this._windowOffset) {
      this._windowOverride=true;
      this._todayBaseSignature=JSON.stringify(this._hass.states?.[this._config.status_entity]?.attributes?.schedule_7_days ?? null);
    }
    const keys=this._dayKeys(), request=++this._windowRequest;
    this._windowStart=keys[0];
    const end=new Date(Date.parse(`${keys[6]}T12:00:00Z`)+86400000).toISOString().slice(0,10);
    this._windowLoading=true; this._windowError=null; this._windowUnsupported=false; this._renderUnlessEditing();
    try {
      const response=await this._hass.callWS({type:"motorvarmare/get_schedule",entity_id:this._config.status_entity,start:keys[0],end});
      if (request !== this._windowRequest) return;
      if (!Array.isArray(response?.events)) throw new Error("Invalid schedule response");
      this._windowEvents=response.events; this._windowCalendarError=!!response.calendar_error;
    } catch (err) {
      if (request !== this._windowRequest) return;
      const unsupported=err?.code === "unknown_command" || /unknown command/i.test(err?.message || "");
      this._windowEvents=null; this._windowUnsupported=unsupported;
      if (unsupported && !this._windowOffset) {this._windowOverride=false;this._windowError=null;}
      else this._windowError=err?.message || mvText(this._hass,"calendarFailed");
    } finally {
      if (request === this._windowRequest) { this._windowLoading=false; this._renderUnlessEditing(); }
    }
  }
  _clock(value, day, includeOffset=false) {
    if (!value) return "–";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "–";
    const options = {timeZone:this._timeZone(), hour:"2-digit", minute:"2-digit", hourCycle:"h23"};
    if (includeOffset) options.timeZoneName = "shortOffset";
    if (this._dayKey(value) !== day) { options.weekday = "short"; options.day = "numeric"; options.month = "short"; }
    return new Intl.DateTimeFormat(mvLang(this._hass) === "sv" ? "sv-SE" : "en-GB", options).format(date);
  }
  _activeGraph(samples, start, end, now, plannedEnd=end) {
    // A null reading breaks the line: never invent a zero or bridge an outage.
    const values=(Array.isArray(samples) ? samples : []).map(item=>({
      at:typeof item?.at==="string" ? new Date(item.at).getTime() : NaN,
      watts:Number.isFinite(item?.watts) && item.watts>=0 ? item.watts : null,
    })).filter(item=>Number.isFinite(item.at) && item.at>=start && item.at<=now && item.at<=end).sort((a,b)=>a.at-b.at);
    const readings=values.filter(item=>item.watts!==null);
    if (!readings.length) return `<div class="active-graph-empty">${mvEscape(mvText(this._hass,"powerGraphEmpty"))}</div>`;
    const peak=Math.max(1,...readings.map(item=>item.watts));
    const ceiling=Math.max(100,Math.ceil(peak/100)*100), span=Math.max(1,end-start);
    let path="", drawing=false, previousY=null;
    for (const item of values) {
      if (item.watts===null) {drawing=false;continue;}
      const x=Math.max(0,Math.min(320,(item.at-start)/span*320));
      const y=76-Math.min(1,item.watts/ceiling)*68;
      // Energy integration holds the last observation until the next one.
      // Draw the same step function instead of implying a gradual change.
      path+=drawing ? `L${x.toFixed(2)} ${previousY.toFixed(2)} L${x.toFixed(2)} ${y.toFixed(2)} ` : `M${x.toFixed(2)} ${y.toFixed(2)} `;
      drawing=true; previousY=y;
    }
    const last=readings[readings.length-1];
    const dots=values.filter((item,i)=>item.watts!==null && (item===last || ((i===0 || values[i-1].watts===null) && (i===values.length-1 || values[i+1].watts===null)))).map(item=>{
      const x=Math.max(0,Math.min(320,(item.at-start)/span*320)), y=76-Math.min(1,item.watts/ceiling)*68;
      return `<circle cx="${x.toFixed(2)}" cy="${y.toFixed(2)}" r="3"></circle>`;
    }).join("");
    const max=new Intl.NumberFormat(mvLang(this._hass)==="sv"?"sv-SE":"en-GB",{maximumFractionDigits:0}).format(ceiling);
    const nowPosition=Math.max(0,Math.min(100,(now-start)/span*100));
    const stopPosition=Math.max(0,Math.min(100,(plannedEnd-start)/span*100));
    return `<div class="active-chart" role="img" aria-label="${mvEscape(mvText(this._hass,"powerGraphUnit"))}"><div class="active-chart-scale"><span>${mvEscape(max)} W</span><span>0 W</span></div><div class="active-chart-plot"><svg viewBox="0 0 320 84" preserveAspectRatio="none" aria-hidden="true"><line x1="0" y1="8" x2="320" y2="8"></line><line x1="0" y1="42" x2="320" y2="42"></line><line x1="0" y1="76" x2="320" y2="76"></line><path d="${path.trim()}"></path>${dots}</svg><span class="active-chart-now" style="left:${nowPosition.toFixed(2)}%" aria-hidden="true"></span><span class="active-stop-marker" style="left:${stopPosition.toFixed(2)}%" ${now<=plannedEnd ? "hidden" : ""} aria-hidden="true"></span></div></div>`;
  }
  async _perform(action) {
    if (this._pending) return false;
    this._pending = true; this._actionError = null;
    this._render();
    let ok = false;
    try { await action(); ok = true; }
    catch (err) { this._actionError = mvErrorText(this._hass, err?.message) || mvText(this._hass,"actionError"); }
    finally { this._pending = false; this._render(); }
    return ok;
  }
  async _call(domain, service, data) { return this._perform(() => this._hass.callService(domain, service, data)); }
  async _callWS(data) { return this._perform(() => this._hass.callWS(data)); }
  _render() {
    if (!this.shadowRoot) return;
    this._nextCalendarTransition=Infinity;
    this._renderController?.abort();
    this._renderController = new AbortController();
    const renderSignal = this._renderController.signal;
    const focusedHistory=["history-toggle", "history-more", "total-more", "window-previous", "window-next", "window-today"].includes(this.shadowRoot.activeElement?.id) ? this.shadowRoot.activeElement.id : null;
    const focusedTotal=this.shadowRoot.activeElement?.dataset?.totalPeriod;
    const focusedMobileDay=this.shadowRoot.activeElement?.dataset?.mobileDay;
    const oldScroll=this.shadowRoot.querySelector(".cal-scroll");
    const scrollPosition=this._initialCalendarScroll || (oldScroll && this.isConnected && oldScroll.clientHeight ? {top:oldScroll.scrollTop,left:oldScroll.scrollLeft} : this._desktopPosition);
    const agendaOpen=this._calendarExpanded ? !!this.shadowRoot.querySelector("#calendar-expanded .cal-agenda")?.open : !!this.shadowRoot.querySelector(".cal-agenda")?.open;
    const h = this._hass, cfg = this._config;
    if (!h) { this.shadowRoot.innerHTML = ""; return; }
    const t = key => mvText(h,key), days = MV_DAYS[mvLang(h)];
    const status = h.states[cfg.status_entity];
    if (!cfg.status_entity || !status) {
      this.shadowRoot.innerHTML = `<ha-card><div style="padding:20px">${mvEscape(t("choose"))}</div></ha-card>`;
      return;
    }
    const e = this._entities(), a = status.attributes || {}, manual = h.states[e.manual_entity];
    const sw = h.states[e.switch_entity];
    let statusText = mvUsable(status) ? mvStateText(h,status.state) : t("noStatus");
    if (!mvUsable(status) || status.state === "error" || a.error) { /* Keep unavailable status and faults prominent. */ }
    else if (a.automation_paused) statusText=t("paused");
    else if (a.owned && a.active_until) statusText=status.state === "heating" ? `${t("heatingUntil")} ${this._date(a.active_until)}` : `${statusText} · ${t("heatingUntil")} ${this._date(a.active_until)}`;
    else if (a.temperature > 10) statusText=t("overTen");
    else if (status.state === "waiting_to_start" && a.planned_start) {
      const left=Math.ceil((new Date(a.planned_start).getTime()-Date.now())/60000);
      if (Number.isFinite(left) && left > 0) statusText+=` · ${t("startsIn")} ${mvDuration(h,left)}`;
    }
    const heating = sw?.state === "on" ? t("on") : sw?.state === "off" ? t("off") : t("unknown");
    const title = cfg.title || status.attributes?.friendly_name?.replace(/\s+status$/i, "") || "Motorvärmare";
    const temperature = mvUsable(status) && typeof a.temperature === "number" && Number.isFinite(a.temperature) ? `${new Intl.NumberFormat(mvLang(h) === "sv" ? "sv-SE" : "en-GB", {maximumFractionDigits:1}).format(a.temperature)} °C` : "–";
    const showPower = mvUsable(status) && a.power_sensor_configured === true, showEnergy = mvUsable(status) && a.energy_sensor_configured === true;
    const metricLocale = mvLang(h) === "sv" ? "sv-SE" : "en-GB";
    const measuredPower = Number.isFinite(a.power_w) ? `${new Intl.NumberFormat(metricLocale, {maximumFractionDigits:1}).format(a.power_w)} W` : "–";
    const hasSessionEnergy = a.energy_session_status !== "incomplete" && Number.isFinite(a.session_energy_kwh);
    const sessionEnergy = hasSessionEnergy ? `${new Intl.NumberFormat(metricLocale, {minimumFractionDigits:2, maximumFractionDigits:3}).format(a.session_energy_kwh)} kWh` : "–";
    const meterWarnings = [
      showPower && a.energy_monitor_status === "power_unavailable" ? t("powerUnavailable") : null,
      showEnergy && a.energy_sensor_available === false ? t(hasSessionEnergy ? "energyUnavailable" : "energyUnavailableEmpty") : null,
      showEnergy && a.energy_session_status === "incomplete" ? t("energyIncomplete") : null,
      showPower && a.energy_monitor_status === "waiting" && sw?.state === "on" ? t("powerWaiting") : null,
    ].filter(Boolean);
    const energyInfo = showEnergy && a.energy_session_status === "no_session" && a.energy_sensor_available !== false ? t("energyNoSession") : null;
    const weekRows = e.weekly.map((day, i) => {
      const t = h.states[day.time], s = h.states[day.enabled];
      const availableTime = mvUsable(t), availableSwitch = mvUsable(s) && ["on","off"].includes(s.state);
      return `<div class="day"><span>${days[i]}</span><input aria-label="${days[i]} ${mvText(h,"depTime")}" type="time" data-day-time="${i}" value="${availableTime ? mvEscape(t.state.slice(0,5)) : ""}" ${!availableTime || this._pending ? "disabled" : ""}><label class="day-toggle"><input aria-label="${mvText(h,"enable")} ${days[i]}" type="checkbox" data-day-switch="${i}" ${s?.state === "on" ? "checked" : ""} ${!availableSwitch || this._pending ? "disabled" : ""}><span>${availableSwitch ? (s.state === "on" ? mvText(h,"on") : mvText(h,"off")) : mvText(h,"unavailable")}</span></label></div>`;
    }).join("");
    const manualOk = manual && manual.state !== "unavailable";
    const clear = h.states[e.clear_entity];
    const clearOk = clear && clear.state !== "unavailable";
    const inputValue = this._draft === null ? this._inputDate(manual?.state) : this._draft;
    const startButton = h.states[e.start_now], stopButton = h.states[e.stop_now];
    const skipButton=h.states[e.skip_next], pauseSwitch=h.states[e.automation_paused], pauseDate=h.states[e.pause_until];
    const currentRuntime = mvUsable(status) && Number.isFinite(a.current_duration_minutes) ? a.current_duration_minutes : null;
    const startOk = startButton && startButton.state !== "unavailable" && sw?.state === "off" && currentRuntime > 0;
    const stopOk = mvUsable(status) && stopButton && stopButton.state !== "unavailable" && a.owned;
    const active=mvUsable(status) && a.owned === true && sw?.state === "on";
    const activeNowMs=Date.now(), startMsActive=typeof a.active_started_at==="string" ? new Date(a.active_started_at).getTime() : NaN;
    const endMsActive=typeof a.active_until==="string" ? new Date(a.active_until).getTime() : NaN;
    const limitMsActive=typeof a.active_max_until==="string" ? new Date(a.active_max_until).getTime() : NaN;
    const activeTimeValid=Number.isFinite(startMsActive) && Number.isFinite(endMsActive) && endMsActive>startMsActive;
    const axisEndActive=activeTimeValid ? Math.max(endMsActive,activeNowMs) : NaN;
    const activeRatio=activeTimeValid ? Math.max(0,Math.min(1,(activeNowMs-startMsActive)/(axisEndActive-startMsActive))) : null;
    const stopRatio=activeTimeValid ? Math.max(0,Math.min(1,(endMsActive-startMsActive)/(axisEndActive-startMsActive))) : null;
    this._activeProgress=active && Number.isFinite(endMsActive) ? {start:startMsActive,end:endMsActive,samples:a.active_power_samples} : null;
    const remainingMinutes=Number.isFinite(endMsActive) ? Math.ceil((endMsActive-activeNowMs)/60000) : null;
    const activeRemaining=remainingMinutes===null ? t("activeProgressUnavailable") : remainingMinutes>0 ? `${mvDuration(h,remainingMinutes)} ${t("activeRemaining")}` : t("activeFinished");
    const currentDay=this._dayKey(new Date(activeNowMs).toISOString());
    const activeAmbiguous=activeTimeValid && this._activeOffsetChanged(startMsActive,axisEndActive);
    const activeClock=value=>this._clock(value,currentDay,activeAmbiguous);
    const ticks=activeTimeValid ? [0,.5,1].map((part,i)=>`<span class="active-tick tick-${i}">${mvEscape(this._activeTick(startMsActive,axisEndActive,part,activeAmbiguous))}</span>`).join("") : "";
    const activeTimeline=activeTimeValid ? `<div class="active-timeline"><div class="active-times"><div><span>${t("activeStart")}</span><strong>${mvEscape(activeClock(a.active_started_at))}</strong></div><div><span>${t("activeStop")}</span><strong>${mvEscape(activeClock(a.active_until))}</strong></div></div><div class="active-plot"><div class="active-axis ${activeAmbiguous ? "active-ambiguous" : ""}">${ticks}</div><div class="active-progress" role="progressbar" aria-label="${t("activeHeating")}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(activeRatio*100)}"><div class="active-progress-fill" style="width:${(activeRatio*100).toFixed(2)}%"></div><span class="active-bar-label">${t("heater")}</span><span class="active-progress-dot" style="left:${(activeRatio*100).toFixed(2)}%" aria-hidden="true"></span><span class="active-stop-marker" style="left:${(stopRatio*100).toFixed(2)}%" ${activeNowMs<=endMsActive ? "hidden" : ""} title="${t("activeStop")}" aria-label="${t("activeStop")}"></span></div><div class="active-progress-caption"><span class="active-progress-now" style="left:${Math.max(7,Math.min(93,activeRatio*100)).toFixed(2)}%">${t("activeNow")}</span></div><div class="active-stop-explanation" ${activeNowMs<=endMsActive ? "hidden" : ""}>${t("activeStop")}</div></div></div>` : `<div class="hint active-no-time">${t("activeProgressUnavailable")}</div>`;
    const extendButton=h.states[e.extend_30];
    const canExtend=active && a.can_extend === true && extendButton && extendButton.state !== "unavailable" && !this._pending;
    const remainingExtension=Number.isFinite(limitMsActive) && Number.isFinite(endMsActive) ? (limitMsActive-endMsActive)/60000 : null;
    const extendText=remainingExtension!==null && remainingExtension<30 ? t("extendMax") : t("extend30");
    const extend=`<button id="extend-30" class="active-extend" ${!canExtend ? "disabled" : ""}>${mvEscape(extendText)}</button>`;
    const measurementStart=typeof a.active_measurement_started_at === "string" ? new Date(a.active_measurement_started_at).getTime() : NaN;
    const measuredSince=Number.isFinite(measurementStart);
    const activeCost=measuredSince && Number.isFinite(a.active_session_cost) && typeof a.active_session_currency==="string" && /^[A-Z]{3}$/.test(a.active_session_currency) ? `${new Intl.NumberFormat(metricLocale,{minimumFractionDigits:2,maximumFractionDigits:2}).format(a.active_session_cost)} ${a.active_session_currency}` : null;
    const activeMetrics=showPower || showEnergy || activeCost ? `<div class="active-metrics">${showPower ? `<div><span>${t("currentPower")}</span><strong>${mvEscape(measuredPower)}</strong></div>` : ""}${showEnergy ? `<div><span>${t("activeEnergy")}</span><strong>${measuredSince ? mvEscape(sessionEnergy) : "–"}</strong></div>` : ""}${activeCost ? `<div><span>${t("activeCostEstimate")}</span><strong>${mvEscape(activeCost)}</strong></div>` : ""}</div>${showEnergy ? `<div class="hint active-measurement-since">${measuredSince ? `${t("measurementSince")} ${mvEscape(this._clock(a.active_measurement_started_at,currentDay))}` : t("measurementStartMissing")}</div>` : ""}` : "";
    const chartStart=Number.isFinite(startMsActive) ? startMsActive : NaN;
    const chart=activeTimeValid && chartStart<=activeNowMs ? this._activeGraph(a.active_power_samples,chartStart,axisEndActive,activeNowMs,endMsActive) : `<div class="active-graph-empty">${t("powerGraphEmpty")}</div>`;
    const graph=showPower ? `<div class="active-graph-section"><button id="active-graph-toggle" class="active-graph-toggle" aria-expanded="${this._showPowerGraph}"><span>${t("powerGraph")}</span><span>${this._showPowerGraph ? t("hide") : t("show")} ${this._showPowerGraph ? "⌃" : "⌄"}</span></button>${this._showPowerGraph ? `${chart}<div class="hint active-graph-hint">${t("powerGraphGap")}</div>` : ""}</div>` : `<div class="hint active-no-sensor">${t("powerGraphMissing")}</div>`;
    const activeControl=active ? `<div class="active-header"><div class="sectionhead">${t("activeHeating")}</div><span class="active-live"><i></i>${t("on")}</span></div><div class="active-remaining">${mvEscape(activeRemaining)}</div>${activeTimeline}${graph}${activeMetrics}<div class="quick-actions active-actions"><button id="stop-now" ${!stopOk || this._pending ? "disabled" : ""}>${t("stopNow")}</button>${e.extend_30 ? extend : ""}${!activeTimeValid && Number.isFinite(endMsActive) ? `<span class="hint">${t("plannedStop")} ${mvEscape(this._date(a.active_until))}</span>` : ""}</div>${e.extend_30 && a.can_extend === false && remainingExtension!==null && remainingExtension<=0 ? `<div class="hint active-limit">${t("extendLimit")}</div>` : e.extend_30 && a.can_extend === true && remainingExtension!==null && remainingExtension<30 ? `<div class="hint active-limit">${t("maximumStop")} ${mvEscape(this._clock(a.active_max_until,currentDay))}.</div>` : ""}` : "";
    const calendar = h.states[e.calendar];
    const calendarOk = mvUsable(status) && calendar && calendar.state !== "unavailable";
    const windowData=mvUsable(status) ? ((this._windowOffset || this._windowOverride) ? this._windowEvents : a.schedule_7_days) : null;
    const hasSchedule = Array.isArray(windowData);
    const schedule = hasSchedule ? windowData.filter(item => item && item.departure && !Number.isNaN(new Date(item.departure).getTime())).map(item=>{
      if (!this._windowOffset && !this._windowOverride) return item;
      if (item.temperature_source === "forecast") return {...item,start:a.temperature_blocked === true ? null : item.start};
      // Future estimates follow the latest temperature even while viewing a week.
      const minutes=Number.isFinite(a.current_duration_minutes) ? a.current_duration_minutes : null;
      const end=Number.isFinite(a.post_departure_minutes) ? new Date(new Date(item.departure).getTime()+a.post_departure_minutes*60000).toISOString() : item.end;
      return {...item,end,duration_minutes:minutes,start:minutes>0 && a.temperature_blocked !== true ? new Date(new Date(item.departure).getTime()-minutes*60000).toISOString() : null};
    }).sort((x,y)=>new Date(x.departure)-new Date(y.departure)) : [];
    const stopTime = item => item.end && !Number.isNaN(new Date(item.end).getTime()) ? item.end : item.departure;
    const formatCost=(amount,currency)=>Number.isFinite(amount) && typeof currency === "string" && /^[A-Z]{3}$/.test(currency) ? `${new Intl.NumberFormat(metricLocale,{minimumFractionDigits:2,maximumFractionDigits:2}).format(amount)} ${currency}` : null;
    const historyAvailable=Array.isArray(a.heating_history);
    const history=historyAvailable ? a.heating_history.filter(item=>item && typeof item==="object") : [];
    const now = Date.now();
    const departurePassed = item => new Date(item.departure).getTime() <= now;
    const displaySource = item => `${departurePassed(item) ? `${t("departurePassed")} · ${t("calendarSource")}: ` : ""}${mvStateText(h,String(item.source || "Planerad"))}`;
    // A stop after departure is only meaningful for an actual heating window.
    // These are estimates, so they do not establish that the heater ran.
    const effectiveEnd = item => {
      const departure = new Date(item.departure).getTime();
      const stop = new Date(stopTime(item)).getTime();
      return !item.suppressed && item.start && stop > departure ? stop : departure;
    };
    const completed = item => effectiveEnd(item) <= now;
    this._nextCalendarTransition=schedule.reduce((next,item)=>{
      for (const boundary of [new Date(item.departure).getTime(),effectiveEnd(item)]) if (boundary > now && boundary < next) next=boundary;
      return next;
    },Infinity);
    const temperatureDetail = item => item.temperature_source === "forecast" ? ` · ${t("forecast")}${Number.isFinite(item.forecast_temperature) ? ` ${new Intl.NumberFormat(metricLocale,{maximumFractionDigits:1}).format(item.forecast_temperature)} °C` : ""}` : a.weather_enabled && item.temperature_source === "current" ? ` · ${t("currentTemperature")}` : "";
    const hasExtendedStop = item => new Date(stopTime(item)).getTime() > new Date(item.departure).getTime();
    // A repeated local hour can make consecutive instants look reversed even
    // when the complete start-to-stop interval appears to be in order.
    const wallClockReverses=(first,second)=>new Date(first).getTime()<new Date(second).getTime() && this._dayKey(first)===this._dayKey(second) && this._inputDate(first)>=this._inputDate(second);
    const heatTiming = (item,key) => {
      const end=stopTime(item);
      const ambiguous=wallClockReverses(item.start,item.departure) || wallClockReverses(item.departure,end) || wallClockReverses(item.start,end);
      return `${t(departurePassed(item) ? "estimatedHeating" : "heatingRange")} ${this._clock(item.start,key,ambiguous)}–${this._clock(end,key,ambiguous)} · ${t("timelineDeparture")} ${this._clock(item.departure,key,ambiguous)}`;
    };
    // The summary reflects the controller's measured-temperature decision, not
    // a forecast for another calendar window. Only attach a stop when the
    // current schedule confirms the same departure *and* start.
    const instant=value=>typeof value === "string" && value ? new Date(value).getTime() : NaN;
    const nextMs=mvUsable(status) ? instant(a.next_departure) : NaN, startMs=mvUsable(status) ? instant(a.planned_start) : NaN;
    const isSkipped=Number.isFinite(nextMs) && instant(a.skipped_departure)===nextMs;
    const showTimeline=status.state === "waiting_to_start" && !a.automation_paused && !a.error && !isSkipped &&
      Number.isFinite(nextMs) && Number.isFinite(startMs) && startMs <= nextMs;
    const summaryItem=showTimeline && Array.isArray(a.schedule_7_days) ? a.schedule_7_days.find(item=>
      item && !item.suppressed && instant(item.departure)===nextMs && instant(item.start)===startMs) : null;
    const endMs=summaryItem ? instant(summaryItem.end) : NaN;
    const summaryEnd=Number.isFinite(endMs) && endMs>=nextMs && endMs>=startMs ? summaryItem.end : null;
    const timelineDay=showTimeline ? this._dayKey(a.next_departure) : "";
    const timelineAmbiguous=showTimeline && (wallClockReverses(a.planned_start,a.next_departure) || (summaryEnd && (wallClockReverses(a.next_departure,summaryEnd) || wallClockReverses(a.planned_start,summaryEnd))));
    const summaryTimeline=showTimeline ? `<div class="departure-timeline ${summaryEnd ? "with-stop" : ""}" role="group" aria-label="${t("summaryEstimate")}"><div class="timeline-point" data-timeline-start><span>${t("timelineStart")}</span><strong>${mvEscape(this._clock(a.planned_start,timelineDay,timelineAmbiguous))}</strong></div><div class="timeline-point departure-point" data-timeline-departure><span>${t("timelineDeparture")}</span><strong>${mvEscape(this._clock(a.next_departure,timelineDay,timelineAmbiguous))}</strong></div>${summaryEnd ? `<div class="timeline-point" data-timeline-stop><span>${t("timelineStop")}</span><strong>${mvEscape(this._clock(summaryEnd,timelineDay,timelineAmbiguous))}</strong></div>` : ""}</div><div class="timeline-caption">${t("summaryEstimate")}</div>` : "";
    const heatingWindows = schedule.filter(item => !item.suppressed && item.start);
    const hasOverlap = heatingWindows.some((item,i) => i > 0 && new Date(item.start) < new Date(stopTime(heatingWindows[i-1])));
    // The grid uses local wall-clock days, not UTC dates. Split an interval at
    // each local midnight so heating before midnight remains visible.
    const dayKeys = this._dayKeys(), hourHeight = 64;
    const minutesOf = value => { const local=this._inputDate(value); return local ? Number(local.slice(11,13))*60+Number(local.slice(14,16)) : null; };
    const segments = [];
    for (const item of schedule) {
      const end=stopTime(item), endKey=this._dayKey(end), endMinute=minutesOf(end);
      const departureKey=this._dayKey(item.departure), departureMinute=minutesOf(item.departure);
      const startKey=item.start ? this._dayKey(item.start) : "", startMinute=item.start ? minutesOf(item.start) : null;
      const hasHeat=!item.suppressed && startKey && startMinute !== null && new Date(item.start) < new Date(end);
      for (const key of dayKeys) {
        if (hasHeat && startKey <= key && endKey >= key) {
          const from=startKey === key ? startMinute : 0, to=endKey === key ? endMinute : 1440;
          if (to > from) segments.push({item,key,from,to,heat:true});
          else if (startKey < endKey && key === endKey && endMinute === 0) segments.push({item,key,from:0,to:0,heat:false,endOnly:true});
          // A repeated local clock hour may make the wall-clock end appear
          // earlier than the start even though the real interval is positive.
          else if (startKey === endKey && key === endKey) segments.push({item,key,from:endMinute,to:endMinute,heat:true});
        } else if (!hasHeat && departureKey === key && departureMinute !== null) {
          segments.push({item,key,from:departureMinute,to:departureMinute,heat:false});
        }
      }
    }
    // Anchor to the first upcoming departure, then its earliest visible
    // segment. A later trip after midnight must not shift the view to 00:00.
    const anchorItem = schedule.find(item => !completed(item) && !item.suppressed && segments.some(s => s.item === item))
      || schedule.find(item => !completed(item) && segments.some(s => s.item === item));
    const anchorSegment = anchorItem && segments.find(s => s.item === anchorItem);
    if (!dayKeys.includes(this._mobileDay)) { this._mobileDay = null; this._mobileDayChosen = false; }
    if (!this._mobileDayChosen) this._mobileDay = anchorSegment?.key || dayKeys[0];
    const firstHour=0, lastHour=24;
    const gridHeight=(lastHour-firstHour)*hourHeight;
    const rows=Array.from({length:lastHour-firstHour+1},(_,i)=>`<div class="cal-hour" style="top:${i*hourHeight}px">${String(firstHour+i).padStart(2,"0")}:00</div>`).join("");
    const dayRows = dayKeys.map((key,i) => {
      const items=segments.filter(s=>s.key===key).map(s=>({...s,top:Math.max(0,Math.min(gridHeight,(s.from-firstHour*60)*hourHeight/60)),height:s.heat ? Math.max(1,(s.to-s.from)*hourHeight/60) : 24})).sort((a,b)=>a.top-b.top);
      // Assign lanes to visually overlapping blocks, including minimum-height
      // blocks, so each remains readable and independently removable.
      const groups=[]; let group=[], groupEnd=-1, laneEnds=[];
      for (const item of items) {
        if (group.length && item.top >= groupEnd) { groups.push(group); group=[]; groupEnd=-1; laneEnds=[]; }
        let lane=laneEnds.findIndex(end=>end<=item.top); if (lane<0) lane=laneEnds.length;
        item.lane=lane; laneEnds[lane]=item.top+item.height; groupEnd=Math.max(groupEnd,laneEnds[lane]); group.push(item);
      }
      if (group.length) groups.push(group);
      for (const g of groups) { const count=Math.max(...g.map(x=>x.lane))+1; for (const item of g) item.lanes=count; }
      const entries = items.map(({item,top,height,heat,endOnly,lane,lanes}) => {
        const title = this._calendarExpanded && typeof item.summary === "string" && item.summary.trim() ? `${item.summary.trim()} · ` : "";
        const source = `${title}${displaySource(item)}${temperatureDetail(item)}`;
        const timing = item.suppressed ? `${t("suppressed")} · ${t("depShort")} ${this._clock(item.departure,key)}` : endOnly ? `${t(hasExtendedStop(item) ? "stopShort" : "depShort")} ${this._clock(stopTime(item),key)}` : heat ? heatTiming(item,key) : `${item.duration_minutes === 0 ? t("noHeat") : t("missingStart")} · ${t("depShort")} ${this._clock(item.departure,key)}`;
        const remove = key === this._dayKey(item.departure) && item.removable === true && item.uid && calendarOk ? `<button class="remove" data-remove-uid="${mvEscape(item.uid)}" ${item.recurrence_id ? `data-recurrence-id="${mvEscape(item.recurrence_id)}"` : ""} aria-label="${t("removeDeparture")} ${mvEscape(this._clock(item.departure,key))}" title="${t("removeDeparture")}">×</button>` : "";
        const end=stopTime(item), ambiguous=heat && (wallClockReverses(item.start,item.departure) || wallClockReverses(item.departure,end) || wallClockReverses(item.start,end));
        const gridTiming=this._calendarExpanded && heat && !endOnly && !item.suppressed ? `${this._clock(item.start,key,ambiguous)}–${this._clock(end,key,ambiguous)}` : timing;
        const eventText=`<div class="cal-timing">${mvEscape(gridTiming)}</div><div class="cal-source">${mvEscape(source)}</div>`;
        const content=this._calendarExpanded && item.removable === true && item.uid && calendarOk ? `<button type="button" class="cal-event-text" data-edit-index="${schedule.indexOf(item)}" aria-label="${mvEscape(`${t("edit")} ${this._date(item.departure)} · ${timing}`)}" title="${t("edit")}">${eventText}</button>` : `<div class="cal-event-text">${eventText}</div>`;
        return `<div class="cal-event cal-entry ${heat ? "heating-event" : "marker-event"} ${completed(item) ? "is-past" : ""}" data-departure="${mvEscape(item.departure)}" data-segment-day="${key}" style="top:${top}px;height:${Math.min(height,gridHeight-top)}px;left:calc(${lane*100/lanes}% + 2px);width:calc(${100/lanes}% - 4px)" aria-label="${mvEscape(`${timing} · ${source}`)}" title="${mvEscape(`${timing} · ${source}`)}">${content}${remove}</div>`;
      }).join("");
      const dayDate=new Date(`${key}T12:00:00Z`), locale=mvLang(h)==="sv" ? "sv-SE" : "en-GB";
      const weekday=new Intl.DateTimeFormat(locale,{timeZone:"UTC",weekday:"short"}).format(dayDate);
      return `<div class="cal-day"><div class="cal-day-head"><div class="cal-weekday">${mvEscape(weekday)}</div><div class="cal-date ${key===this._dayKey(new Date().toISOString()) ? "is-today" : ""}">${dayDate.getUTCDate()}</div><button class="add-day" data-add-day="${key}" aria-label="${t("addDay")} ${mvEscape(this._dayLabel(key,i))}" title="${t("addDay")}" ${!calendarOk || this._pending ? "disabled" : ""}>＋</button></div><div class="cal-column" data-grid-day="${key}" data-first-hour="${firstHour}" style="height:${gridHeight}px">${entries}</div></div>`;
    }).join("");
    const repeatOptions=[["NONE",t("once")],["DAILY",t("daily")],["WEEKLY",t("weeklyRepeat")],["MONTHLY",t("monthly")],["YEARLY",t("yearly")]];
    const weekdayCodes=["MO","TU","WE","TH","FR","SA","SU"];
    const weekdayInputs=weekdayCodes.map((code,i)=>`<label class="repeat-day"><input type="checkbox" data-repeat-day="${code}" ${this._repeatDays.includes(code) ? "checked" : ""}>${mvEscape(days[i].slice(0,3))}</label>`).join("");
    const repeatFields=this._repeatFreq !== "NONE" ? `<label for="repeat-interval">${t("every")}</label><input id="repeat-interval" type="number" min="1" max="99" step="1" value="${mvEscape(this._repeatInterval)}">${this._repeatFreq === "WEEKLY" ? `<fieldset class="repeat-days"><legend>${t("repeatOn")}</legend>${weekdayInputs}</fieldset>` : ""}<label for="repeat-until">${t("until")}</label><input id="repeat-until" type="date" min="${mvEscape(this._editDate)}" value="${mvEscape(this._repeatUntil)}">` : "";
    const canRepeat=!this._editContext || !this._editContext.occurrence;
    const calendarEditor=dayKeys.includes(this._selectedDay) ? `<div class="cal-editor calendar-form"><strong>${this._editContext ? t("editDeparture") : t("addDay")}</strong><label for="calendar-date">${t("editDate")}</label><input id="calendar-date" type="date" value="${mvEscape(this._editDate)}"><label for="calendar-time">${t("depTime")}</label><input id="calendar-time" type="time" value="${mvEscape(this._calendarTime)}" ${this._pending ? "disabled" : ""}><label for="calendar-summary">${t("editTitle")}</label><input id="calendar-summary" type="text" value="${mvEscape(this._editSummary)}" placeholder="${t("eventSummary")}">${canRepeat ? `<label for="repeat-frequency">${t("recurrence")}</label><select id="repeat-frequency">${repeatOptions.map(([key,label])=>`<option value="${key}" ${key===this._repeatFreq ? "selected" : ""}>${label}</option>`).join("")}</select>${repeatFields}` : ""}${this._editContext?.series ? `<div class="series-warning">${t("seriesWarning")}</div><label class="series-confirm"><input id="confirm-series-change" type="checkbox" ${this._editAcknowledged ? "checked" : ""}>${t("seriesConfirm")}</label>` : ""}<button class="primary" id="add-calendar" ${!calendarOk || this._pending ? "disabled" : ""}>${this._editContext ? t("save") : t("add")}</button><button id="cancel-calendar" ${this._pending ? "disabled" : ""}>${t("cancel")}</button></div>` : "";
    const deleteEditor=this._deleteRecurrence ? `<div class="cal-editor" role="group" aria-label="${t("deleteChoice")}"><strong>${t("deleteChoice")}</strong><button id="delete-one">${t("deleteOne")}</button><button id="delete-series">${t("deleteSeries")}</button><button id="delete-cancel">${t("cancel")}</button></div>` : "";
    const editEditor=this._editChoice ? `<div class="cal-editor" role="group" aria-label="${t("editChoice")}"><strong>${t("editChoice")}</strong><button id="edit-one">${t("deleteOne")}</button><button id="edit-series">${t("deleteSeries")}</button><button id="edit-cancel">${t("cancel")}</button></div>` : "";
    const agendaRows=schedule.filter(item=>dayKeys.includes(this._dayKey(item.departure))).map(item=>{
      const key=this._dayKey(item.departure), date=this._date(item.departure);
      const state=item.suppressed ? t("suppressed") : item.start ? heatTiming(item,key) : item.duration_minutes===0 ? t("noHeat") : t("missingStart");
      const source=`${displaySource(item)}${temperatureDetail(item)}`;
      const remove=item.removable === true && item.uid && calendarOk ? `<button class="remove" data-remove-uid="${mvEscape(item.uid)}" ${item.recurrence_id ? `data-recurrence-id="${mvEscape(item.recurrence_id)}"` : ""} aria-label="${t("removeDeparture")} ${mvEscape(date)}">${t("remove")}</button>` : "";
      const edit=item.removable === true && item.uid && calendarOk ? `<button data-edit-index="${schedule.indexOf(item)}">${t("edit")}</button>` : "";
      return `<li class="${completed(item) ? "is-past" : ""}"><span><strong>${mvEscape(date)}</strong><br>${mvEscape(state)} · ${mvEscape(source)}</span>${edit}${remove}</li>`;
    }).join("");
    const mobileDays = dayKeys.map((key,i) => {
      const date=new Date(`${key}T12:00:00Z`), locale=mvLang(h)==="sv" ? "sv-SE" : "en-GB";
      const weekday=new Intl.DateTimeFormat(locale,{timeZone:"UTC",weekday:"short"}).format(date).replace(/\.$/,"");
      const hasEvents=segments.some(s=>s.key===key);
      return `<button class="mobile-day" data-mobile-day="${key}" aria-label="${mvEscape(this._dayLabel(key,i))}" aria-pressed="${key===this._mobileDay}"><span>${mvEscape(weekday)}</span><strong>${date.getUTCDate()}</strong><i class="${hasEvents ? "has-events" : ""}" aria-hidden="true"></i></button>`;
    }).join("");
    const mobileEntries=segments.filter(s=>s.key===this._mobileDay).sort((a,b)=>a.from-b.from).map(({item,heat,endOnly})=>{
      const key=this._mobileDay;
      const timing=item.suppressed ? `${t("suppressed")} · ${t("depShort")} ${this._clock(item.departure,key)}` : endOnly ? `${t(hasExtendedStop(item) ? "stopShort" : "depShort")} ${this._clock(stopTime(item),key)}` : heat ? heatTiming(item,key) : `${item.duration_minutes === 0 ? t("noHeat") : t("missingStart")} · ${t("depShort")} ${this._clock(item.departure,key)}`;
      const source=`${displaySource(item)}${temperatureDetail(item)}`;
      const end=stopTime(item), ambiguous=heat && (wallClockReverses(item.start,item.departure) || wallClockReverses(item.departure,end) || wallClockReverses(item.start,end));
      const range=heat && !item.suppressed && !endOnly ? `${t(departurePassed(item) ? "estimatedHeating" : "heatingRange")} ${this._clock(item.start,key,ambiguous)}–${this._clock(end,key,ambiguous)}` : timing;
      const departureLine=heat && !item.suppressed && !endOnly ? `${t("timelineDeparture")} ${this._clock(item.departure,key,ambiguous)} · ${source}` : source;
      const remove=item.removable===true && item.uid && calendarOk ? `<button class="mobile-remove" data-remove-uid="${mvEscape(item.uid)}" ${item.recurrence_id ? `data-recurrence-id="${mvEscape(item.recurrence_id)}"` : ""} aria-label="${t("removeDeparture")} ${mvEscape(this._date(item.departure))}">${t("remove")}</button>` : "";
      const edit=item.removable===true && item.uid && calendarOk ? `<button data-edit-index="${schedule.indexOf(item)}">${t("edit")}</button>` : "";
      return `<div class="mobile-event ${heat ? "heating-event" : "marker-event"} ${completed(item) ? "is-past" : ""}" data-mobile-departure="${mvEscape(item.departure)}"><div><strong>${mvEscape(range)}</strong><div class="mobile-source">${mvEscape(departureLine)}</div></div>${edit}${remove}</div>`;
    }).join("");
    const mobileCalendar=`<div class="mobile-calendar"><div class="mobile-days" role="group" aria-label="${t("selectDay")}">${mobileDays}</div><div class="mobile-selected"><strong>${mvEscape(this._dayLabel(this._mobileDay,dayKeys.indexOf(this._mobileDay)))}</strong><button class="mobile-add" data-add-day="${this._mobileDay}" ${!calendarOk || this._pending ? "disabled" : ""}>＋ ${t("add")}</button></div><div class="mobile-events">${mobileEntries || `<div class="mobile-empty">${t("noDeparture")}</div>`}</div></div>`;
    const agenda=`<details class="cal-agenda" ${agendaOpen ? "open" : ""}><summary>${t("agenda")}</summary>${agendaRows ? `<ul>${agendaRows}</ul>` : `<div class="cal-empty">${t("noDeparture")}</div>`}</details>`;
    const desktopCalendar=`<div class="desktop-calendar">${this._calendarExpanded ? agenda : ""}<div class="cal-scroll" role="region" tabindex="0" aria-label="${t("seven")}"><div class="cal-grid"><div class="cal-axis"><div class="cal-axis-head"></div><div class="cal-hours" style="height:${gridHeight}px">${rows}</div></div>${dayRows}</div></div><div class="cal-scroll-hint">${t("scrollHint")}</div>${!this._calendarExpanded ? agenda : ""}</div>`;
    const nextEnergy = mvUsable(status) && Number.isFinite(a.next_estimated_energy_kwh) && a.next_estimated_energy_kwh >= 0 && a.next_estimate_basis === "latest_complete_session_average" ? `${new Intl.NumberFormat(metricLocale,{minimumFractionDigits:2,maximumFractionDigits:3}).format(a.next_estimated_energy_kwh)} kWh` : null;
    const nextCost = nextEnergy ? formatCost(a.next_estimated_cost,a.next_estimated_currency) : null;
    const nextEstimate = nextEnergy ? `<div class="section next-estimate"><div class="sectionhead">${t("nextEnergyEstimate")}</div><div class="history-metrics"><strong>${mvEscape(nextEnergy)}</strong>${nextCost ? `<span>${t("cost")}: ${mvEscape(nextCost)}</span>` : ""}</div><div class="hint">${t(nextCost ? "nextEstimateNote" : "nextEstimateEnergyOnly")}</div></div>` : "";
    const historyItemContent=(item,forCalendar=false)=>{
      const valid=value=>typeof value==="string" && value.length>0 && !Number.isNaN(new Date(value).getTime());
      const hasStart=valid(item.start), hasEnd=valid(item.end), complete=item.complete === true && hasStart && hasEnd;
      const sameDay=hasStart && hasEnd && this._dayKey(item.start)===this._dayKey(item.end);
      const ambiguous=sameDay && this._inputDate(item.start)>=this._inputDate(item.end);
      const sameYear=hasStart && hasEnd && this._dayKey(item.start).slice(0,4)===this._dayKey(item.end).slice(0,4);
      const range=hasStart && hasEnd
        ? `${this._date(item.start,ambiguous,true)} – ${sameYear ? this._clock(item.end,this._dayKey(item.start),ambiguous) : this._date(item.end,ambiguous,true)}`
        : `${hasStart ? `${t("historyStart")} ${this._date(item.start,false,true)}` : t("historyStartMissing")} · ${hasEnd ? `${t("historyEnd")} ${this._date(item.end,false,true)}` : t("historyEndMissing")}`;
      let duration="";
      if (complete && Number.isFinite(item.duration_minutes) && item.duration_minutes>=0) {
        duration=`${t("duration")}: ${mvDuration(h,item.duration_minutes)}`;
      }
      const energy=Number.isFinite(item.energy_kwh) && item.energy_kwh>=0
        ? `${t("historyEnergy")}: ${new Intl.NumberFormat(metricLocale,{minimumFractionDigits:2,maximumFractionDigits:3}).format(item.energy_kwh)} kWh`
        : t("historyEnergyUnavailable");
      const cost=formatCost(item.estimated_cost,item.cost_currency);
      const startTemperature=Number.isFinite(item.temperature_at_start_c) ? `${t("startTemperature")}: ${new Intl.NumberFormat(metricLocale,{maximumFractionDigits:1}).format(item.temperature_at_start_c)} °C` : null;
      return `<div class="history-range">${mvEscape(range)}</div><div class="history-metrics">${duration ? `<span>${mvEscape(duration)}</span>` : ""}<span>${mvEscape(energy)}</span>${cost ? `<span>${t("cost")}: ${mvEscape(cost)}</span>` : forCalendar && a.cost_configured ? `<span>${t("calendarHistoryCostMissing")}</span>` : ""}${startTemperature ? `<span>${mvEscape(startTemperature)}</span>` : ""}</div>${!complete ? `<div class="history-incomplete">${t("historyTimeIncomplete")}</div>` : ""}`;
    };
    const historyRows=history.slice(0,this._historyLimit).map(item=>`<li class="history-entry">${historyItemContent(item)}</li>`).join("");
    // Recorded switch sessions have no departure identity. Group by the local
    // end date, as the energy totals do, and never attach one to a departure.
    const calendarHistoryRows=history.filter(item=>typeof item.end === "string" && Number.isFinite(new Date(item.end).getTime()) && this._dayKey(item.end)===this._mobileDay)
      .map(item=>`<li class="calendar-history-entry">${historyItemContent(item,true)}</li>`).join("");
    const historyDayOptions=dayKeys.map((key,i)=>`<option value="${key}" ${key===this._mobileDay ? "selected" : ""}>${mvEscape(this._dayLabel(key,i))}</option>`).join("");
    const calendarHistory=historyAvailable && history.length ? `<section class="calendar-history" aria-label="${t("calendarHistory")}"><div class="sectionhead">${t("calendarHistory")}</div><div class="calendar-history-day"><label for="calendar-history-day">${t("calendarHistoryDay")}</label><select id="calendar-history-day">${historyDayOptions}</select></div><div class="hint">${t("calendarHistoryNote")}</div>${calendarHistoryRows ? `<ul class="history-list">${calendarHistoryRows}</ul>` : `<div class="history-empty">${t("calendarHistoryEmpty")}</div>`}</section>` : "";
    const calendarGrid=`${calendarEditor}${deleteEditor}${editEditor}${mobileCalendar}${desktopCalendar}${calendarHistory}`;
    const historyBody=!historyAvailable ? `<div class="history-empty">${t("historyUpdate")}</div>` : !history.length ? `<div class="history-empty">${t("historyEmpty")}</div>` : `<ul class="history-list">${historyRows}</ul>${history.length>this._historyLimit ? `<button id="history-more" class="history-more">${t("historyShowMore")}</button>` : ""}`;
    const totals=mvUsable(status) ? a.history_energy_totals : null;
    // Match the actual current local period, never the newest available older one.
    const todayKey=this._dayKey(new Date().toISOString());
    const todayDate=/^\d{4}-\d{2}-\d{2}$/.test(todayKey) ? new Date(`${todayKey}T12:00:00Z`) : null;
    const weekDate=todayDate && !Number.isNaN(todayDate.getTime()) ? new Date(todayDate) : null;
    if (weekDate) weekDate.setUTCDate(weekDate.getUTCDate() - ((weekDate.getUTCDay()+6)%7));
    const periodKeys={daily:todayKey,weekly:weekDate?.toISOString().slice(0,10),monthly:todayKey?.slice(0,7)+"-01"};
    const summaryPeriods=[["daily",t("periodToday")],["weekly",t("periodWeek")],["monthly",t("periodMonth")]];
    const periodSummary=totals && summaryPeriods.some(([kind])=>Array.isArray(totals[kind])) ? `<div class="period-summary"><div class="sectionhead">${t("periodSummary")}</div><div class="period-cards">${summaryPeriods.map(([kind,label])=>{
      const item=Array.isArray(totals[kind]) ? totals[kind].find(row=>row && row.period_start===periodKeys[kind]) : null;
      const hasValue=Number.isFinite(item?.energy_kwh) && item.energy_kwh>=0;
      const value=hasValue ? `${new Intl.NumberFormat(metricLocale,{minimumFractionDigits:2,maximumFractionDigits:3}).format(item.energy_kwh)} kWh` : t("periodUnavailable");
      const cost=item ? formatCost(item.estimated_cost,item.cost_currency) : null;
      const hasSessions=hasValue || Number(item?.sessions)>0;
      const costText=a.cost_configured && item && hasSessions ? (cost ? `${t("cost")}: ${cost}${item.cost_incomplete ? ` (${t("totalIncomplete")})` : ""}` : item.cost_incomplete ? t("periodCostMissing") : "") : "";
      const showPartial=item?.incomplete && (hasSessions || item.crossed_boundary || item.truncated);
      return `<div class="period-card"><div class="period-label">${mvEscape(label)}</div><div class="period-value">${mvEscape(value)}</div>${showPartial ? `<div class="period-detail">${t("periodPartial")}</div>` : ""}${costText ? `<div class="period-detail">${mvEscape(costText)}</div>` : ""}</div>`;
    }).join("")}</div><div class="hint">${t("totalNote")}</div></div>` : "";
    const totalRows=Array.isArray(totals?.[this._totalPeriod]) ? totals[this._totalPeriod] : [];
    const totalLabels=[["daily",t("totalDay")],["weekly",t("totalWeek")],["monthly",t("totalMonth")]];
    const totalItems=totalRows.slice(0,this._totalLimit).map(item=>{
      if (!item || !/^\d{4}-\d{2}-\d{2}$/.test(item.period_start || "")) return "";
      const d=new Date(`${item.period_start}T12:00:00Z`), options={timeZone:"UTC",year:"numeric",month:"short"};
      if (this._totalPeriod !== "monthly") options.day="numeric";
      const date=new Intl.DateTimeFormat(metricLocale,options).format(d);
      const amount=Number.isFinite(item.energy_kwh) && item.energy_kwh>=0 ? `${new Intl.NumberFormat(metricLocale,{minimumFractionDigits:2,maximumFractionDigits:3}).format(item.energy_kwh)} kWh` : t("totalNone");
      const cost=formatCost(item.estimated_cost,item.cost_currency);
      return `<li><span>${this._totalPeriod === "weekly" ? `${t("totalFrom")} ` : ""}${mvEscape(date)}</span><span>${mvEscape(amount)}${item.incomplete ? ` <small>(${t("totalIncomplete")})</small>` : ""}${cost ? `<br><small>${t("cost")}: ${mvEscape(cost)}${item.cost_incomplete ? ` (${t("costIncomplete")})` : ""}</small>` : item.cost_incomplete && a.cost_configured ? `<br><small>${t("costIncomplete")}</small>` : ""}</span></li>`;
    }).join("");
    const totalsBody=totals && totalLabels.some(([key])=>Array.isArray(totals[key])) ? `<div class="history-totals"><strong>${t("periodHistory")}</strong><div class="total-tabs" role="group" aria-label="${t("totalEnergy")}">${totalLabels.map(([key,label])=>`<button data-total-period="${key}" aria-pressed="${this._totalPeriod===key}">${label}</button>`).join("")}</div><ul class="total-list">${totalItems}</ul>${totalRows.length>this._totalLimit ? `<button id="total-more" class="history-more">${t("historyShowMore")}</button>` : totals.has_older?.[this._totalPeriod] ? `<div class="hint">${t("totalOlder")}</div>` : ""}</div>` : "";
    const formatRangeDate=key=>new Intl.DateTimeFormat(metricLocale,{timeZone:"UTC",day:"numeric",month:"short",year:"numeric"}).format(new Date(`${key}T12:00:00Z`));
    const editingCalendar=!!(this._selectedDay || this._editChoice || this._deleteRecurrence);
    const calendarNav=`<div class="calendar-nav"><button id="window-previous" aria-label="${t("calendarPrevious")}" title="${t("calendarPrevious")}" ${this._windowOffset===0 || editingCalendar ? "disabled" : ""}>‹</button><span class="calendar-range">${mvEscape(formatRangeDate(dayKeys[0]))} – ${mvEscape(formatRangeDate(dayKeys[6]))}</span><button id="window-next" aria-label="${t("calendarNext")}" title="${t("calendarNext")}" ${editingCalendar ? "disabled" : ""}>›</button>${this._windowOffset ? `<button id="window-today" ${editingCalendar ? "disabled" : ""}>${t("calendarToday")}</button><button id="window-refresh" title="${t("refreshCalendar")}" aria-label="${t("refreshCalendar")}" ${editingCalendar ? "disabled" : ""}>↻</button>` : ""}</div>${editingCalendar ? `<div class="hint">${t("finishEditing")}</div>` : ""}`;
    const scheduleBody=!mvUsable(status) ? `<div class="cal-warning" role="status">${t("noStatus")}</div>` : this._windowLoading ? `<div class="hint" role="status">${t("calendarLoading")}</div>` : this._windowError ? `<div class="cal-warning" role="alert">${this._windowUnsupported ? t("updateCalendar") : `${t("calendarFailed")} <button id="window-retry">${t("retry")}</button>`}</div>` : hasSchedule ? `${this._windowCalendarError ? `<div class="cal-warning" role="status">${t("calendarPartial")}</div>` : ""}${calendarGrid}` : `<div class="cal-warning">${t("updateCalendar")}</div>`;
    const deviationMessage=mvUsable(status) && a.power_deviation_active === true ? t(a.power_deviation_direction === "low" ? "deviationLow" : a.power_deviation_direction === "high" ? "deviationHigh" : "deviationUnknown") : null;
    const expandedAlerts=this._calendarExpanded && mvUsable(status) ? [...new Set([
      a.error ? mvErrorText(h,a.error) : null,
      ...(Array.isArray(a.operational_problems) ? a.operational_problems.filter(problem=>Object.prototype.hasOwnProperty.call(MV_I18N[mvLang(h)],problem)).map(problem=>t(problem)) : []),
      a.alarm_active === true && showPower && a.energy_monitor_status === "low_power" && sw?.state === "on" ? t("powerAlarm") : null,
      deviationMessage,
    ].filter(Boolean))].map(message=>`<div class="notice" role="status">${mvEscape(message)}</div>`).join("") : "";
    const calendarContents=`<div class="calendar-title"><span>${t("seven")}</span><span class="calendar-title-actions"><button id="new-departure" ${!calendarOk || this._pending ? "disabled" : ""}>＋ ${t("addDay")}</button>${!this._calendarExpanded ? `<button id="open-calendar" ${!mvUsable(status) ? "disabled" : ""}>${t("openCalendar")}</button>` : ""}</span></div><div class="calendar-subtitle">${this._calendarExpanded ? t("expandedCalendarHint") : t(a.weather_enabled ? "shortForecast" : "shortEstimate")}${this._calendarExpanded && a.weather_enabled ? ` ${t("shortForecast")}` : ""}${hasOverlap ? ` ${t("overlap")}` : ""}</div>${mvUsable(status) ? calendarNav : ""}${expandedAlerts}${this._calendarExpanded && this._actionError ? `<div class="notice" role="alert">${mvEscape(this._actionError)}</div>` : ""}${scheduleBody}${mvUsable(status) && !calendarOk ? `<div class="hint">${t("updateAdd")}</div>` : ""}`;
    const compactCalendar=this._calendarExpanded ? `<div class="calendar-placeholder" aria-hidden="true" style="height:${this._calendarPlaceholderHeight}px"></div>` : `<div class="calendar">${calendarContents}</div>`;
    // The open attribute is retained on updates so mvPatch does not turn a
    // native modal into a closed dialog on unrelated Home Assistant events.
    const expandedCalendar=this._calendarExpanded ? `<dialog id="calendar-expanded" class="calendar-modal" aria-labelledby="calendar-expanded-title" ${this.shadowRoot.querySelector("#calendar-expanded")?.open ? "open" : ""}><div class="calendar-modal-head"><h2 id="calendar-expanded-title">${t("expandedCalendarTitle")}</h2><button id="close-calendar" aria-label="${t("closeCalendar")}" title="${t("closeCalendar")}">✕</button></div><div class="calendar expanded-calendar">${calendarContents}<p class="calendar-modal-hint">${t("expandedCalendarScroll")}</p></div></dialog>` : "";
    const newMarkup = `
      <style>
        :host{display:block;color:var(--primary-text-color);font-family:var(--paper-font-body1_-_font-family,Roboto,system-ui,sans-serif)} *{box-sizing:border-box} ha-card{overflow:hidden} .wrap{padding:20px} .head{display:flex;gap:12px;align-items:center;margin-bottom:20px} .icon{width:42px;height:42px;display:grid;place-items:center;border-radius:14px;background:rgba(var(--rgb-primary-color,3,169,244),.12);color:var(--primary-color)} ha-icon{--mdc-icon-size:22px}.headtext{flex:1;min-width:0}.title{font-size:18px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.status{font-size:13px;color:var(--secondary-text-color);margin-top:2px}.badge{font-size:12px;font-weight:600;padding:6px 10px;border-radius:20px;background:var(--secondary-background-color);color:var(--secondary-text-color);white-space:nowrap}.badge.on{background:rgba(var(--rgb-success-color,67,160,71),.14);color:var(--success-color,#278748)} .stats{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px 16px;padding:16px 0;border-top:1px solid var(--divider-color);border-bottom:1px solid var(--divider-color)} .label{font-size:12px;color:var(--secondary-text-color);margin-bottom:3px}.value{font-size:15px;font-weight:500;overflow-wrap:anywhere}.section{margin-top:18px}.sectionhead{font-weight:600;margin-bottom:10px}.manual{display:flex;gap:8px;align-items:end;flex-wrap:wrap}.field{flex:1;min-width:175px}.field label{display:block;font-size:12px;color:var(--secondary-text-color);margin-bottom:5px} input[type=datetime-local],input[type=time]{color:var(--primary-text-color);background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:8px;padding:8px;font:inherit;min-height:40px;max-width:100%} input[type=datetime-local]{width:100%} button{font:500 14px var(--paper-font-body1_-_font-family,Roboto,system-ui,sans-serif);color:var(--primary-color);background:transparent;border:0;border-radius:8px;min-height:40px;padding:8px 10px;cursor:pointer} button.primary{background:var(--primary-color);color:var(--text-primary-color,#fff)} button:disabled,input:disabled{opacity:.48;cursor:not-allowed} button:focus-visible,input:focus-visible{outline:2px solid var(--primary-color);outline-offset:2px}.expand{display:flex;align-items:center;justify-content:space-between;width:100%;padding:9px 0;text-align:left;color:var(--primary-text-color);font-weight:600}.expand .small{font-size:12px;color:var(--primary-color)} .day{display:grid;grid-template-columns:minmax(75px,1fr) auto auto;align-items:center;gap:10px;padding:7px 0;border-top:1px solid var(--divider-color)} .day input[type=time]{width:100px}.day-toggle{display:flex;align-items:center;gap:5px;font-size:12px;color:var(--secondary-text-color);min-width:50px}.day-toggle input{width:18px;height:18px;accent-color:var(--primary-color)} .notice{font-size:13px;color:var(--error-color,#c62828);margin-top:12px;overflow-wrap:anywhere}.hint{font-size:12px;color:var(--secondary-text-color);margin-top:10px}.actions{display:flex;gap:4px;align-items:center} @media(max-width:350px){.wrap{padding:15px}.day{grid-template-columns:minmax(65px,1fr) auto auto;gap:5px}.day input[type=time]{width:90px}}
        .quick-actions{display:flex;align-items:center;gap:12px;margin-top:15px;flex-wrap:wrap}.quick-actions .hint{margin:0;flex:1;min-width:150px}.calendar{margin-top:20px}.calendar-title{font-weight:600;margin-bottom:4px}.calendar-subtitle{font-size:12px;color:var(--secondary-text-color);margin-bottom:10px;line-height:1.45}.cal-day{border-top:1px solid var(--divider-color);padding:9px 0}.cal-day-head{display:flex;align-items:center;justify-content:space-between;gap:8px;font-weight:600;text-transform:none}.cal-day-head button{min-height:36px;padding:5px 6px}.cal-empty{font-size:12px;color:var(--secondary-text-color);padding:3px 0}.cal-entry{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:5px 0}.cal-timing{font-size:13px;font-weight:500}.cal-source{font-size:12px;color:var(--secondary-text-color)}.remove{font-size:12px;min-height:36px;color:var(--secondary-text-color);white-space:nowrap}.cal-editor{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:7px}.cal-editor label{font-size:12px;color:var(--secondary-text-color)}.cal-editor input{width:105px}.cal-editor button{padding:6px 9px} .cal-warning{font-size:12px;color:var(--error-color,#c62828);margin-top:8px}
        .main-tabs{display:flex;gap:4px;margin-top:18px;border-bottom:1px solid var(--divider-color)}.main-tabs button{flex:1;min-width:0;padding:8px 3px;color:var(--secondary-text-color);border-radius:6px 6px 0 0}.main-tabs button[aria-selected=true]{color:var(--primary-color);border-bottom:2px solid var(--primary-color)}.main-panel[hidden]{display:none}.schedule-actions button{font-size:12px}.pause-editor input{min-width:0;max-width:100%}
        .cal-scroll{overflow:auto;max-height:640px;border:1px solid var(--divider-color);border-radius:12px;background:var(--card-background-color);overscroll-behavior:contain}.cal-grid{display:grid;grid-template-columns:52px repeat(7,minmax(112px,1fr));min-width:836px}.cal-axis-head,.cal-day-head{height:78px;position:sticky;top:0;z-index:3;background:var(--card-background-color);border-bottom:1px solid var(--divider-color)}.cal-axis-head{z-index:4}.cal-day{border:0;padding:0;min-width:0}.cal-day-head{display:flex;position:sticky;flex-direction:column;justify-content:center;align-items:center;gap:2px;padding:4px 26px 4px 4px}.cal-weekday{font-size:11px;font-weight:600;letter-spacing:.03em;text-transform:uppercase;color:var(--secondary-text-color)}.cal-date{font-size:20px;font-weight:500;width:32px;height:32px;display:grid;place-items:center;border-radius:50%}.cal-date.is-today{background:var(--primary-color);color:var(--text-primary-color,#fff)}.cal-day-head .add-day{position:absolute;right:2px;top:22px;min-width:30px;min-height:32px;padding:3px;font-size:19px}.cal-column{position:relative;border-left:1px solid var(--divider-color);background-image:repeating-linear-gradient(to bottom,var(--divider-color) 0,var(--divider-color) 1px,transparent 1px,transparent 64px);cursor:crosshair}.cal-hours{position:relative}.cal-hour{position:absolute;right:6px;transform:translateY(-50%);font-size:11px;color:var(--secondary-text-color);white-space:nowrap}.cal-hour:first-child{transform:none}.cal-hour:last-child{transform:translateY(-100%)}.cal-event{position:absolute;z-index:1;display:flex;align-items:flex-start;gap:2px;padding:3px 2px 2px 4px;border-radius:5px;background:#e8b84f;border-left:3px solid #9b7130;color:#211906;overflow:hidden;cursor:default}.cal-event-text{min-width:0;flex:1;overflow:hidden}.cal-event .cal-timing{font-size:10px;line-height:12px;font-weight:600;color:inherit;overflow-wrap:anywhere}.cal-event .cal-source{font-size:10px;line-height:12px;color:inherit;opacity:.76;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.cal-event.marker-event{background:var(--secondary-background-color);border-left-color:var(--secondary-text-color);color:var(--primary-text-color)}.cal-event .remove{flex:none;min-width:22px;min-height:24px;padding:0;color:inherit;font-size:17px;line-height:20px}.cal-editor{margin:0 0 10px;padding:10px;border-radius:8px;background:var(--secondary-background-color)}.cal-editor strong{font-size:13px;margin-right:4px}.cal-scroll-hint{font-size:11px;color:var(--secondary-text-color);margin-top:6px}.cal-agenda{font-size:12px;color:var(--secondary-text-color);margin-top:8px}.cal-agenda summary{cursor:pointer;color:var(--primary-color);padding:6px 0}.cal-agenda ul{list-style:none;margin:0;padding:0}.cal-agenda li{display:flex;align-items:center;justify-content:space-between;gap:8px;border-top:1px solid var(--divider-color);padding:5px 0;line-height:1.5}.cal-agenda strong{color:var(--primary-text-color)}
        .history-list{list-style:none;margin:0;padding:0}.history-entry{padding:11px 0;border-top:1px solid var(--divider-color);font-size:13px;line-height:1.45}.history-range{font-weight:600;color:var(--primary-text-color);overflow-wrap:anywhere}.history-metrics{display:flex;gap:6px 18px;flex-wrap:wrap;color:var(--secondary-text-color);margin-top:3px}.history-incomplete,.history-empty{font-size:12px;color:var(--secondary-text-color);margin-top:4px}.history-more{padding-left:0}
        .calendar-nav{display:flex;align-items:center;gap:4px;margin:4px 0 10px}.calendar-nav button{min-width:40px;padding:4px 8px}.calendar-nav button:not(#window-today){font-size:22px}.calendar-range{flex:1;text-align:center;font-weight:500;font-size:12px}.cal-editor select,.cal-editor input[type=date],.cal-editor input[type=number]{color:var(--primary-text-color);background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:8px;padding:8px;min-height:40px;max-width:100%;font:inherit}.cal-editor input[type=number]{width:72px}.cal-editor input[type=date]{width:168px}.cal-editor input[type=text]{width:150px;max-width:100%;color:var(--primary-text-color);background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:8px;padding:8px;min-height:40px;box-sizing:border-box;font:inherit}.cal-editor.calendar-form{display:grid;grid-template-columns:minmax(95px,auto) minmax(0,1fr);gap:8px 10px}.calendar-form strong,.calendar-form .repeat-days,.calendar-form .series-warning,.calendar-form .series-confirm{grid-column:1 / -1}.cal-editor.calendar-form input:not([type=checkbox]),.cal-editor.calendar-form select{width:100%;max-width:100%;box-sizing:border-box}.calendar-form button{justify-self:start}.cal-editor .series-warning{width:100%;font-size:12px;line-height:1.4}.cal-editor .series-confirm{display:flex;align-items:center;gap:6px;width:100%}.cal-editor .series-confirm input{width:18px;height:18px;accent-color:var(--primary-color)}.repeat-days{display:flex;gap:2px;flex-wrap:wrap;width:100%;border:0;padding:0;margin:2px 0}.repeat-days legend{font-size:12px;color:var(--secondary-text-color)}.repeat-day{display:flex;align-items:center;gap:2px;padding:4px}.repeat-day input{width:18px;height:18px;accent-color:var(--primary-color)}.history-totals{padding:10px 0 14px;font-size:13px}.total-tabs{display:flex;gap:4px;margin-top:6px}.total-tabs button{min-height:36px;padding:5px 12px;color:var(--secondary-text-color)}.total-tabs button[aria-pressed=true]{color:var(--primary-color);background:var(--secondary-background-color)}.total-list{list-style:none;margin:4px 0;padding:0}.total-list li{display:flex;justify-content:space-between;gap:12px;padding:6px 0;border-bottom:1px solid var(--divider-color)}.total-list small{color:var(--secondary-text-color)}
        .calendar{container-type:inline-size}.mobile-calendar,.mobile-hint{display:none}
        @container (max-width: 839px){
          .desktop-calendar,.desktop-hint{display:none}.mobile-calendar,.mobile-hint{display:block}
          .mobile-calendar{border:1px solid var(--divider-color);border-radius:12px;overflow:hidden;background:var(--card-background-color)}
          .mobile-days{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:1px;padding:8px 5px;border-bottom:1px solid var(--divider-color)}
          .mobile-day{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;min-width:0;min-height:62px;padding:3px 0;color:var(--secondary-text-color);font-size:10px;text-transform:uppercase}
          .mobile-day strong{display:grid;place-items:center;width:30px;height:30px;border-radius:50%;font-size:15px;color:var(--primary-text-color)}
          .mobile-day[aria-pressed="true"] strong{background:var(--primary-color);color:var(--text-primary-color,#fff)}
          .mobile-day i{width:4px;height:4px;border-radius:50%;background:transparent}.mobile-day i.has-events{background:var(--primary-color)}
          .mobile-selected{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:6px 12px;color:var(--primary-text-color);font-size:13px}
          .mobile-add{white-space:nowrap}.mobile-events{display:grid;gap:7px;padding:0 12px 12px}.mobile-empty{padding:12px 0;color:var(--secondary-text-color);font-size:13px}
          .mobile-event{display:flex;justify-content:space-between;align-items:center;gap:8px;min-width:0;border-left:4px solid #9b7130;border-radius:7px;padding:10px 8px;background:#e8b84f;color:#211906;font-size:13px;line-height:1.35}.mobile-event>div{min-width:0;overflow-wrap:anywhere}
          .mobile-event strong{font-weight:600}.mobile-event.marker-event{background:var(--secondary-background-color);border-left-color:var(--secondary-text-color);color:var(--primary-text-color)}
          .mobile-source{font-size:11px;margin-top:3px;opacity:.8}.mobile-remove{color:inherit;min-height:40px;padding:6px;white-space:nowrap;font-size:12px}
        }

        /* A quiet, theme-aware hierarchy keeps the next trip and action first. */
        ha-card{border-radius:var(--ha-card-border-radius,16px)}
        .wrap{padding:22px;container-type:inline-size}
        .head{gap:14px;margin:0 0 20px;align-items:center}
        .icon{flex:none;width:48px;height:48px;border-radius:15px;background:rgba(var(--rgb-primary-color,3,169,244),.13)}
        .icon ha-icon{--mdc-icon-size:25px}
        .title{font-size:18px;line-height:1.25;font-weight:700;letter-spacing:-.01em}
        .status{font-size:13px;line-height:1.35;margin-top:4px;overflow-wrap:anywhere}
        .badge{display:inline-flex;align-items:center;gap:6px;padding:7px 10px;font-size:11px;letter-spacing:.01em}
        .badge::before{content:"";width:7px;height:7px;border-radius:50%;background:currentColor;flex:none}
        .stats{gap:10px;padding:0;border:0;grid-template-columns:repeat(2,minmax(0,1fr))}
        .stats>div{min-width:0;padding:10px 12px;border-radius:12px;background:var(--secondary-background-color)}
        .stats>div:nth-child(-n+2){padding:14px 12px;background:rgba(var(--rgb-primary-color,3,169,244),.10)}
        .stats .label,.energy-metrics .label{line-height:1.35;font-size:12px;margin:0 0 6px}
        .stats .value{line-height:1.35;font-weight:650;font-size:15px}
        .stats>div:nth-child(-n+2) .value{font-size:16px;letter-spacing:-.01em}
        .stats .power-stat,.stats .energy-stat{background:var(--secondary-background-color)}
        /* A single summary groups the next trip and keeps its timing readable. */
        .departure-summary{padding:17px;border:1px solid rgba(var(--rgb-primary-color,3,169,244),.20);border-radius:16px;background:rgba(var(--rgb-primary-color,3,169,244),.07)}
        .summary-label{font-size:12px;line-height:1.35;font-weight:600;color:var(--secondary-text-color)}
        .summary-date,.summary-empty{margin-top:3px;font-size:22px;font-weight:700;letter-spacing:-.025em;line-height:1.25;overflow-wrap:anywhere}
        .summary-empty{font-size:18px}.departure-summary #empty-add-departure{margin:8px 0 0 -8px;min-height:44px;padding:8px;font-weight:600}
        .departure-timeline{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));position:relative;gap:10px;margin:18px 0 0}
        .departure-timeline.with-stop{grid-template-columns:repeat(3,minmax(0,1fr))}
        .departure-timeline:before{content:"";position:absolute;top:5px;left:5px;right:calc(50% - 10px);height:2px;background:rgba(var(--rgb-primary-color,3,169,244),.28)}
        .departure-timeline.with-stop:before{right:calc(33.333% - 11.667px)}
        .timeline-point{position:relative;min-width:0;padding-top:16px;font-size:12px;line-height:1.35;color:var(--secondary-text-color)}
        .timeline-point:before{content:"";position:absolute;top:1px;left:0;width:10px;height:10px;border-radius:50%;background:var(--primary-color)}
        .timeline-point strong{display:block;margin-top:2px;font-size:14px;line-height:1.3;color:var(--primary-text-color);overflow-wrap:anywhere}
        .timeline-point.departure-point:before{box-shadow:0 0 0 3px rgba(var(--rgb-primary-color,3,169,244),.20)}
        .timeline-caption{margin-top:9px;color:var(--secondary-text-color);font-size:11px;line-height:1.4}
        .summary-metrics{display:flex;flex-wrap:wrap;gap:6px 16px;margin-top:16px;padding-top:12px;border-top:1px solid rgba(var(--rgb-primary-color,3,169,244),.20);font-size:12px;line-height:1.4;color:var(--secondary-text-color)}
        .summary-metrics strong{margin-left:3px;color:var(--primary-text-color);font-size:13px;font-weight:600}
        .notice{line-height:1.45;padding:10px 12px;border-radius:10px;background:rgba(var(--rgb-error-color,244,67,54),.1)}
        .quick-actions{gap:10px;margin-top:16px}
        .quick-actions>button:first-child:not(.mobile-add){min-height:44px;padding-inline:16px}
        .quick-actions .hint{line-height:1.4}
        #stop-now{background:var(--primary-color);color:var(--text-primary-color,#fff);font-weight:650}
        .schedule-actions{gap:2px;margin-top:7px}
        .schedule-actions button{min-height:44px;padding:8px 10px;color:var(--secondary-text-color);font-size:12px}
        .schedule-actions button:hover{color:var(--primary-color);background:rgba(var(--rgb-primary-color,3,169,244),.08)}
        .main-tabs{padding:4px;gap:4px;margin-top:20px;border:0;border-radius:12px;background:var(--secondary-background-color)}
        .main-tabs button{min-height:44px;border:0;border-radius:9px;padding:8px 5px;font-size:13px;font-weight:600;line-height:1.2}
        .main-tabs button[aria-pressed=true]{color:var(--primary-color);background:var(--card-background-color);box-shadow:0 1px 4px rgba(0,0,0,.12)}
        .main-panel{min-width:0}.calendar{margin-top:20px}
        .calendar-title{display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:15px;line-height:1.3;margin:0 0 4px}
        .calendar-title button{flex:none;min-height:44px;padding:8px 10px;font-size:13px}
        .calendar-subtitle{font-size:12px;line-height:1.5;margin-bottom:12px}
        .calendar-nav{gap:5px;margin:8px 0 12px}
        .calendar-nav button{min-height:44px;border-radius:10px;background:var(--secondary-background-color)}
        .calendar-range{font-size:13px;font-weight:650}
        .cal-scroll,.mobile-calendar{border-radius:14px}
        .cal-event,.mobile-event{background:rgba(var(--rgb-primary-color,3,169,244),.18);border-left-color:var(--primary-color);color:var(--primary-text-color)}
        .cal-event.marker-event,.mobile-event.marker-event{background:var(--secondary-background-color);border-left-color:var(--secondary-text-color)}
        .cal-editor{border-radius:12px;padding:14px}
        .energy-overview{margin-top:20px}.energy-overview .sectionhead{font-size:15px}
        .energy-metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
        .energy-metrics>div{padding:14px 12px;min-width:0;border-radius:12px;background:var(--secondary-background-color)}
        .energy-metrics .value{font-size:16px;line-height:1.35;overflow-wrap:anywhere;font-weight:650}
        .period-summary{margin-top:22px}.period-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(115px,1fr));gap:8px}.period-card{min-width:0;padding:13px 12px;border:1px solid var(--divider-color);border-radius:12px;background:var(--card-background-color)}.period-label{font-size:12px;line-height:1.3;color:var(--secondary-text-color)}.period-value{font-size:16px;font-weight:650;line-height:1.3;margin-top:6px;overflow-wrap:anywhere}.period-detail{font-size:11px;line-height:1.35;color:var(--secondary-text-color);margin-top:5px;overflow-wrap:anywhere}
        .history-section{border-top:1px solid var(--divider-color);padding-top:8px}
        button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible,a:focus-visible{outline:2px solid var(--primary-color);outline-offset:2px}
        .stats>div.post-summary{grid-column:1/-1;display:flex;gap:7px;align-items:baseline;padding:1px 2px;background:transparent}
        .post-summary .label,.post-summary .value{margin:0;font-size:12px;color:var(--secondary-text-color);font-weight:500}
        button,input[type=datetime-local],input[type=time],.cal-editor input:not([type=checkbox]),.cal-editor select{min-height:44px}
        .mobile-event button,.day-toggle{min-height:44px}
        .secondary-actions{display:flex;align-items:center;gap:8px;margin-top:5px}
        .secondary-actions button{min-height:44px;color:var(--secondary-text-color);font-size:12px;padding:8px 6px}
        .secondary-actions .resume-action{color:var(--primary-color);font-weight:650}
        @container (max-width: 340px){.mobile-days{grid-template-columns:repeat(4,minmax(0,1fr))}}
        @container (max-width: 420px){
          .head{gap:10px}.icon{width:42px;height:42px;border-radius:13px}.icon ha-icon{--mdc-icon-size:22px}
          .title{font-size:16px}.badge{font-size:10px;padding:6px 8px}.status{font-size:12px}
          .stats{gap:8px}.stats>div,.stats>div:nth-child(-n+2){padding:11px 10px}
          .stats .value,.stats>div:nth-child(-n+2) .value{font-size:14px}
          .quick-actions .hint{min-width:120px}.calendar-title{font-size:14px}
          input:not([type=checkbox]),select{font-size:16px}
        }
        .calendar-title{flex-wrap:wrap}.calendar-title-actions{display:flex;align-items:center;gap:2px;flex-wrap:wrap}.calendar-placeholder{margin-top:20px}
        .calendar-modal{width:min(1200px,calc(100vw - 24px));max-width:none;max-height:calc(100vh - 24px);max-height:calc(100dvh - 24px);padding:18px;border:1px solid var(--divider-color);border-radius:18px;background:var(--card-background-color);color:var(--primary-text-color);box-shadow:0 18px 55px rgba(0,0,0,.35);overflow:auto;overscroll-behavior:contain}
        .calendar-modal::backdrop{background:rgba(0,0,0,.65)}
        .calendar-modal-head{display:flex;align-items:center;justify-content:space-between;gap:12px}.calendar-modal-head h2{font-size:19px;line-height:1.3;margin:0;font-weight:650}.calendar-modal-head button{min-width:44px;min-height:44px;font-size:20px;color:var(--secondary-text-color)}
        .calendar-modal .calendar{margin-top:8px}.calendar-modal .calendar .desktop-calendar{display:block}.calendar-modal .calendar .mobile-calendar{display:none}
        .calendar-modal .cal-scroll{height:calc(100vh - 280px);height:calc(100dvh - 280px);min-height:240px;max-height:720px}
        .calendar-modal button.cal-event-text{min-height:0;padding:0;border-radius:0;text-align:left;color:inherit;font:inherit;display:block;cursor:pointer}
        .calendar-modal .cal-timing{font-size:12px;line-height:15px}.calendar-modal .cal-source{font-size:11px;line-height:14px;white-space:normal}
        .calendar-modal .cal-agenda{font-size:13px;margin:0 0 4px}.calendar-modal .cal-agenda summary{min-height:44px;display:flex;align-items:center;font-weight:600}.calendar-modal .cal-agenda summary:after{content:"⌄";margin-left:auto;font-size:16px}.calendar-modal .cal-agenda[open] summary:after{content:"⌃"}
        .calendar-modal-hint{font-size:12px;line-height:1.4;color:var(--secondary-text-color);margin:10px 0 0}
        @media(max-width:480px){.calendar-modal{padding:12px}.calendar-modal .calendar-title{align-items:flex-start}.calendar-modal .cal-scroll{min-height:200px}}

        /* Keep actions and the selected view in distinct, theme-aware groups. */
        .control-panel{margin-top:16px;padding:15px 16px;border:1px solid var(--divider-color);border-radius:14px;background:var(--card-background-color)}
        .control-panel .sectionhead{font-size:14px;line-height:1.3;margin:0}
        .control-panel .quick-actions{margin-top:10px}
        .control-panel .schedule-actions{margin-top:4px}
        .control-panel .secondary-actions{margin-top:8px;padding-top:4px;border-top:1px solid var(--divider-color)}
        .summary-source{margin-top:9px;font-size:12px;line-height:1.4;color:var(--secondary-text-color)}
        .main-tabs{margin-top:20px;padding:5px;border:1px solid var(--divider-color);border-bottom:0;border-radius:14px 14px 0 0}
        .main-panel:not([hidden]){min-width:0;padding:16px;border:1px solid var(--divider-color);border-radius:0 0 14px 14px;background:var(--card-background-color)}
        .main-panel .calendar,.main-panel .calendar-placeholder,.main-panel .section,.main-panel .period-summary{margin-top:0}
        .main-panel[data-main-panel="settings"] .section + .section,
        .main-panel[data-main-panel="energy"] .energy-overview ~ .section,
        .main-panel[data-main-panel="energy"] .period-summary{margin-top:16px;padding-top:16px;border-top:1px solid var(--divider-color)}
        .main-panel .sectionhead{font-size:14px;line-height:1.35}
        .main-panel .calendar-nav{flex-wrap:wrap}
        .active-header{display:flex;justify-content:space-between;align-items:center;gap:12px}
        .active-live{display:inline-flex;align-items:center;gap:6px;padding:5px 9px;border-radius:999px;background:color-mix(in srgb,var(--primary-color) 14%,transparent);color:var(--primary-color);font-size:11px;font-weight:700}
        .active-live i{width:7px;height:7px;border-radius:50%;background:currentColor}
        .active-remaining{font-size:22px;line-height:1.2;font-weight:700;margin:10px 0 14px}
        .active-timeline{padding:0}
        .active-times{display:flex;justify-content:space-between;gap:12px}.active-times>div{display:grid;gap:3px}.active-times>div:last-child{text-align:right}
        .active-times span,.active-progress-caption,.active-axis{font-size:11px;line-height:1.3;color:var(--secondary-text-color)}
        .active-times strong{font-size:14px;color:var(--primary-text-color)}
        .active-plot{min-width:0}.active-axis{position:relative;height:15px;margin:16px 0 6px;white-space:nowrap}.active-tick{position:absolute;top:0}.active-axis .tick-0{left:0}.active-axis .tick-1{left:50%;transform:translateX(-50%)}.active-axis .tick-2{right:0}
        .active-progress{position:relative;height:32px;box-shadow:inset 0 0 0 1px var(--divider-color);border-radius:7px;background:repeating-linear-gradient(to right,transparent 0,transparent calc(25% - 1px),var(--divider-color) calc(25% - 1px),var(--divider-color) 25%),var(--secondary-background-color);overflow:hidden;box-sizing:border-box}
        .active-progress-fill{height:100%;background:color-mix(in srgb,var(--primary-color) 68%,var(--card-background-color));border-radius:6px 0 0 6px}
        .active-bar-label{position:absolute;inset:0;display:flex;align-items:center;padding-left:8px;color:var(--primary-text-color);font-size:11px;font-weight:650;pointer-events:none}
        .active-progress-dot{position:absolute;top:0;bottom:0;width:2px;transform:translateX(-50%);background:var(--primary-color);box-shadow:0 0 0 1px var(--card-background-color)}
        .active-stop-marker{position:absolute;top:0;bottom:0;width:0;transform:translateX(-50%);border-left:2px dashed var(--error-color,#db4437);pointer-events:none}.active-stop-explanation{font-size:11px;color:var(--secondary-text-color);margin-top:3px}.active-stop-explanation:before{content:"";display:inline-block;height:10px;margin-right:5px;border-left:2px dashed var(--error-color,#db4437)}
        .active-progress-caption{position:relative;height:17px;margin-top:3px}.active-progress-now{position:absolute;transform:translateX(-50%);white-space:nowrap}
        .active-metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(112px,1fr));gap:8px;margin-top:12px}
        .active-metrics>div{display:grid;gap:4px;padding:11px 12px;border-radius:10px;background:var(--secondary-background-color);min-width:0}
        .active-metrics span{font-size:11px;line-height:1.3;color:var(--secondary-text-color)}.active-metrics strong{font-size:16px;overflow-wrap:anywhere}
        .active-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}.active-actions button{min-height:44px}.active-actions .active-extend{background:var(--primary-color);color:var(--text-primary-color,#fff);font-weight:650}
        .active-limit,.active-no-sensor,.active-no-time,.active-measurement-since{margin-top:9px;line-height:1.4}
        .active-graph-section{margin-top:0}
        .active-graph-toggle{width:100%;display:flex;align-items:center;justify-content:space-between;gap:10px;text-align:left;min-height:44px;padding:4px 0;font-weight:650;color:var(--primary-text-color)}
        .active-graph-toggle span:last-child{font-size:12px;color:var(--primary-color);font-weight:500;white-space:nowrap}
        /* Keep the power scale above and below the plot, not in an x-axis gutter. */
        .active-chart{position:relative;display:flex;align-items:stretch;height:128px;padding:16px 0;box-sizing:border-box}
        .active-chart-scale{position:absolute;inset:0;display:flex;flex-direction:column;align-items:flex-start;justify-content:space-between;font-size:10px;line-height:12px;color:var(--secondary-text-color);white-space:nowrap;pointer-events:none}
        .active-chart-plot{position:relative;flex:1;min-width:0;background:repeating-linear-gradient(to right,transparent 0,transparent calc(25% - 1px),var(--divider-color) calc(25% - 1px),var(--divider-color) 25%)}
        .active-chart svg{display:block;width:100%;height:100%;overflow:visible}.active-chart line{stroke:var(--divider-color);stroke-width:1;vector-effect:non-scaling-stroke}.active-chart path{stroke:var(--primary-color);stroke-width:2.5;fill:none;stroke-linejoin:round;stroke-linecap:round;vector-effect:non-scaling-stroke}.active-chart circle{fill:var(--primary-color);vector-effect:non-scaling-stroke}
        .active-chart-now{position:absolute;top:0;bottom:0;width:1px;transform:translateX(-50%);background:var(--primary-color);opacity:.65;pointer-events:none}
        .active-graph-hint{font-size:11px;margin-top:8px;line-height:1.35}.active-graph-empty{padding:15px 0 4px;color:var(--secondary-text-color);font-size:12px}
        .cal-event.is-past,.mobile-event.is-past{background:var(--secondary-background-color);border-left-color:var(--secondary-text-color);color:var(--primary-text-color)}
        .cal-agenda li.is-past strong{color:var(--secondary-text-color)}
        .calendar-history{margin-top:16px;padding-top:14px;border-top:1px solid var(--divider-color)}
        .calendar-history .hint{margin:6px 0 8px;line-height:1.4}
        .calendar-history-entry{padding:11px 0;border-top:1px solid var(--divider-color);font-size:13px;line-height:1.45}
        .calendar-history-day{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:8px;font-size:12px;color:var(--secondary-text-color)}
        .calendar-history-day select{max-width:100%;min-height:40px;padding:6px 8px;border:1px solid var(--divider-color);border-radius:8px;background:var(--card-background-color);color:var(--primary-text-color);font:inherit}
        @container (max-width:839px){.calendar-history-day{display:none}}
        .calendar-modal .calendar-history-day{display:flex}
        @container (max-width:420px){.mobile-event{flex-wrap:wrap}.mobile-event>div{flex:1 0 100%}.mobile-event [data-edit-index]{margin-left:auto}}
        @container (max-width:340px){.control-panel,.main-panel:not([hidden]){padding:12px}.calendar-range{min-width:125px}.head{flex-wrap:wrap}.headtext{flex:1 1 120px}}
        @container (max-width:400px){.active-axis.active-ambiguous .tick-1{display:none}}
        @media(max-width:350px){.wrap{padding:15px}}
      </style>
      <ha-card><div class="wrap">
        <div class="head"><div class="icon"><ha-icon icon="mdi:car-defrost-front"></ha-icon></div><div class="headtext"><div class="title">${mvEscape(title)}</div><div class="status">${mvEscape(statusText)}</div></div><span class="badge ${sw?.state === "on" ? "on" : ""}">${t("heater")} ${heating}</span></div>
        <section class="departure-summary" aria-label="${t("departure")}">
          ${Number.isFinite(nextMs) ? `<div class="summary-label">${t("departure")}</div><div class="summary-date">${mvEscape(this._date(a.next_departure))}</div>${summaryTimeline}` : `<div class="summary-label">${t("departure")}</div><div class="summary-empty">${mvUsable(status) ? t("summaryEmpty") : t("noStatus")}</div>${mvUsable(status) ? `<button id="empty-add-departure" ${!calendarOk || this._pending ? "disabled" : ""}>＋ ${t("summaryAdd")}</button>` : ""}`}
          <div class="summary-metrics"><span><span>${t("summaryTemperature")}</span> <strong>${mvEscape(temperature)}</strong></span><span><span>${t("summaryDuration")}</span> <strong>${currentRuntime !== null ? mvDuration(h,currentRuntime) : mvUsable(status) && a.next_departure && Number.isFinite(a.duration_minutes) ? mvDuration(h,a.duration_minutes) : "–"}</strong></span>${mvUsable(status) && a.post_departure_minutes > 0 ? `<span><span>${t("postDeparture")}</span> <strong>${mvDuration(h,a.post_departure_minutes)}</strong></span>` : ""}</div>
          ${mvUsable(status) && a.source ? `<div class="summary-source">${t("from")} ${mvEscape(String(mvStateText(h,a.source)).toLowerCase())}</div>` : ""}
        </section>
        ${a.alarm_active === true && showPower && a.energy_monitor_status === "low_power" && sw?.state === "on" ? `<div class="notice power-alarm" role="alert">${t("powerAlarm")}</div>` : ""}
        ${deviationMessage ? `<div class="notice power-deviation" role="alert">${mvEscape(deviationMessage)}</div>` : ""}
        ${meterWarnings.map(message => `<div class="hint meter-warning">${mvEscape(message)}</div>`).join("")}
        ${mvUsable(status) && a.error ? `<div class="notice" role="status">${mvEscape(mvErrorText(h,a.error))}</div>` : ""}
        ${mvUsable(status) && Array.isArray(a.operational_problems) ? a.operational_problems.filter(problem=>Object.prototype.hasOwnProperty.call(MV_I18N[mvLang(h)],problem)).map(problem=>`<div class="notice operational-problem" role="status">${mvEscape(t(problem))}</div>`).join("") : ""}
        ${this._actionError ? `<div class="notice" role="alert">${mvEscape(this._actionError)}</div>` : ""}
        <section class="control-panel" aria-label="${t("heaterControl")}">${active ? activeControl : `<div class="sectionhead">${t("heaterControl")}</div><div class="quick-actions">${mvUsable(status) && a.owned ? `<button id="stop-now" ${!stopOk || this._pending ? "disabled" : ""}>${t("stopNow")}</button><span class="hint">${a.active_until ? `${t("plannedStop")} ${mvEscape(this._date(a.active_until))}` : t("owned")}</span>` : `<button class="primary" id="start-now" ${!startOk || this._pending ? "disabled" : ""}>${t("runNow")}</button><span class="hint">${!mvUsable(status) ? t("noStatus") : sw?.state === "on" ? t("external") : sw?.state !== "off" ? t("unknownSwitch") : currentRuntime === null ? t("tempUnavailable") : currentRuntime <= 0 ? t("noRuntime") : `${t("runtimeFor")} ${mvDuration(h,currentRuntime)}; ${t("runtimeOff")}`}</span>`}</div>`}
        ${mvUsable(status) && (skipButton || pauseSwitch) ? `<div class="secondary-actions"><button id="more-actions" aria-expanded="${this._showMoreActions}">${this._showMoreActions ? t("lessActions") : t("moreActions")} <span aria-hidden="true">${this._showMoreActions ? "⌃" : "⌄"}</span></button>${a.automation_paused && pauseSwitch ? `<button id="pause-automation" class="resume-action" ${this._pending || pauseSwitch.state === "unavailable" ? "disabled" : ""}>${t("resume")}</button>` : ""}</div>${this._showMoreActions ? `<div class="quick-actions schedule-actions">${skipButton ? `<button id="skip-next" ${!a.next_departure || this._pending || skipButton.state === "unavailable" ? "disabled" : ""}>${t("skipNext")}</button>` : ""}${pauseSwitch && !a.automation_paused ? `<button id="pause-automation" ${this._pending || pauseSwitch.state === "unavailable" ? "disabled" : ""}>${t("pause")}</button>${pauseDate ? `<button id="show-pause-date">${t("pauseUntil")}</button>` : ""}` : ""}</div>${this._showPauseDate && pauseDate && !a.automation_paused ? `<div class="quick-actions pause-editor"><label for="pause-until">${t("pauseUntil")}</label><input id="pause-until" type="datetime-local" value="${mvEscape(this._pauseDraft ?? this._inputDate(pauseDate.state))}"><button id="save-pause">${t("savePause")}</button></div>` : ""}` : ""}${a.automation_paused && a.pause_until ? `<div class="hint">${t("pauseUntil")} ${mvEscape(this._date(a.pause_until))}</div>` : ""}` : ""}
        </section>
        <div class="main-tabs" role="group" aria-label="${t("viewNavigation")}">${[["calendar","calendarTab"],["energy","energyTab"],["settings","settingsTab"]].map(([key,label])=>`<button data-main-tab="${key}" aria-pressed="${this._activeView===key}">${t(label)}</button>`).join("")}</div>
        <div class="main-panel" data-main-panel="calendar" ${this._activeView!=="calendar" ? "hidden" : ""}>${compactCalendar}</div>
        <div class="main-panel" data-main-panel="settings" ${this._activeView!=="settings" ? "hidden" : ""}>
        <div class="section"><div class="sectionhead">${t("single")}</div><div class="manual"><div class="field"><label for="manual">${t("dateTime")}</label><input id="manual" type="datetime-local" value="${mvEscape(inputValue)}" ${!manualOk || this._pending ? "disabled" : ""}></div><div class="actions"><button class="primary" id="save" ${!manualOk || this._pending ? "disabled" : ""}>${t("save")}</button><button id="clear" ${!clearOk || this._pending ? "disabled" : ""}>${t("clear")}</button></div></div></div>
        <div class="section"><button class="expand" id="week" aria-expanded="${this._showWeek}"><span>${t("weekly")}</span><span class="small">${this._showWeek ? t("hide") : t("show")}</span></button>${this._showWeek ? weekRows : ""}</div>
        ${(!e.manual_entity || !e.weekly.some(x=>x.time && x.enabled)) ? `<div class="hint">${t("missingEntities")}</div>` : ""}
        <div class="hint">${t("configBefore")}<a href="/config/integrations/integration/motorvarmare" style="color:var(--primary-color)">${t("configLink")}</a>${t("configAfter")}</div>
        </div>
        <div class="main-panel" data-main-panel="energy" ${this._activeView!=="energy" ? "hidden" : ""}><div class="section energy-overview"><div class="sectionhead">${t("energyOverview")}</div>${showPower || showEnergy ? `<div class="energy-metrics">${showPower ? `<div class="power-stat"><div class="label">${t("currentPower")}</div><div class="value">${mvEscape(measuredPower)}</div></div>` : ""}${showEnergy ? `<div class="energy-stat"><div class="label">${t("sessionEnergy")}</div><div class="value">${mvEscape(sessionEnergy)}</div></div>` : ""}</div><div class="hint">${t("energyOverviewHint")}</div>${energyInfo ? `<div class="hint energy-info">${mvEscape(energyInfo)}</div>` : ""}` : `<div class="hint">${t(mvUsable(status) ? "energySetup" : "noStatus")}</div>`}</div>${nextEstimate}${periodSummary}<div class="section history-section"><button class="expand" id="history-toggle" aria-expanded="${this._showHistory}"><span>${t("history")}${historyAvailable && history.length ? ` (${history.length})` : ""}</span><span class="small">${this._showHistory ? t("hide") : t("show")}</span></button>${this._showHistory ? `${totalsBody}${historyBody}` : ""}</div></div>
      </div></ha-card>${expandedCalendar}`;
    mvPatch(this.shadowRoot, newMarkup);
    const expandedDialog=this.shadowRoot.querySelector("#calendar-expanded");
    if (expandedDialog && !expandedDialog.open) {
      expandedDialog.showModal();
      expandedDialog.querySelector("#close-calendar")?.focus({preventScroll:true});
    }
    const closeExpanded=()=>{
      if (!this._calendarExpanded) return;
      if (expandedDialog?.open) expandedDialog.close();
      this._calendarExpanded=false;
      this._render();
      this.shadowRoot.querySelector("#open-calendar")?.focus({preventScroll:true});
    };
    expandedDialog?.addEventListener("cancel",event=>{event.preventDefault();closeExpanded();}, {signal:renderSignal});
    expandedDialog?.addEventListener("close",closeExpanded,{signal:renderSignal});
    this.shadowRoot.querySelector("#close-calendar")?.addEventListener("click",closeExpanded,{signal:renderSignal});
    this.shadowRoot.querySelector("#open-calendar")?.addEventListener("click",()=>{
      this._calendarPlaceholderHeight=Math.ceil(this.shadowRoot.querySelector(".calendar")?.getBoundingClientRect().height || 0);
      this._calendarExpanded=true;
      this._render();
    }, {signal:renderSignal});
    const newScroll=this.shadowRoot.querySelector(".cal-scroll");
    if (newScroll) {
      const autoTop=Math.max(0,(Math.floor((anchorSegment?.from ?? 7*60)/60)-1)*hourHeight);
      const anchorNow=!!anchorSegment && !this._calendarAnchored && !this._calendarUserScrolled;
      const nextScroll={top:anchorNow ? autoTop : (scrollPosition?.top ?? autoTop),left:scrollPosition?.left ?? 0};
      if (anchorSegment && (anchorNow || this._calendarUserScrolled)) this._calendarAnchored=true;
      if (this.isConnected && newScroll.clientHeight && (newScroll !== oldScroll || anchorNow || this._initialCalendarScroll)) {
        newScroll.scrollTop=nextScroll.top;newScroll.scrollLeft=nextScroll.left;
        this._desktopPosition={top:newScroll.scrollTop,left:newScroll.scrollLeft}; this._initialCalendarScroll=null;
      } else if (!this.isConnected || !newScroll.clientHeight) this._initialCalendarScroll=nextScroll;
      const markScroll=()=>{this._calendarUserScrolled=true;};
      newScroll.addEventListener("wheel",markScroll,{passive:true,signal:renderSignal});
      newScroll.addEventListener("touchmove",markScroll,{passive:true,signal:renderSignal});
      newScroll.addEventListener("pointerdown",ev=>{if (ev.target===newScroll) markScroll();}, {signal:renderSignal});
      newScroll.addEventListener("keydown",ev=>{if (["ArrowUp","ArrowDown","PageUp","PageDown","Home","End"].includes(ev.key)) markScroll();}, {signal:renderSignal});
      newScroll.addEventListener("scroll",()=>{if (newScroll.clientHeight) this._desktopPosition={top:newScroll.scrollTop,left:newScroll.scrollLeft};}, {signal:renderSignal});
    }
    const manualInput = this.shadowRoot.querySelector("#manual");
    manualInput?.addEventListener("input", (event) => {this._draft = event.target.value;}, {signal:renderSignal});
    this.shadowRoot.querySelector("#save")?.addEventListener("click", async () => {
      const value = manualInput.value;
      if (!value) {this._actionError=t("chooseDate"); this._render(); return;}
      if (value <= this._inputDate(new Date().toISOString())) {this._actionError=t("future"); this._render(); return;}
      this._draft = value;
      if (await this._call("datetime", "set_value", {entity_id:e.manual_entity, datetime:value.length === 16 ? `${value}:00` : value})) {this._draft = null; this._render();}
    }, {signal:renderSignal});
    this.shadowRoot.querySelector("#clear")?.addEventListener("click", async () => {if (await this._call("button", "press", {entity_id:e.clear_entity})) {this._draft = null; this._render();}}, {signal:renderSignal});
    this.shadowRoot.querySelector("#start-now")?.addEventListener("click", () => this._call("button", "press", {entity_id:e.start_now}), {signal:renderSignal});
    this.shadowRoot.querySelector("#stop-now")?.addEventListener("click", () => this._call("button", "press", {entity_id:e.stop_now}), {signal:renderSignal});
    this.shadowRoot.querySelector("#extend-30")?.addEventListener("click", () => this._call("button", "press", {entity_id:e.extend_30}), {signal:renderSignal});
    this.shadowRoot.querySelector("#active-graph-toggle")?.addEventListener("click", () => {this._showPowerGraph=!this._showPowerGraph;this._render();this.shadowRoot.querySelector("#active-graph-toggle")?.focus({preventScroll:true});}, {signal:renderSignal});
    this.shadowRoot.querySelectorAll("[data-main-tab]").forEach(el=>el.addEventListener("click",()=>{this._activeView=el.dataset.mainTab;this._render();}, {signal:renderSignal}));
    this.shadowRoot.querySelector("#new-departure")?.addEventListener("click",()=>this._selectCalendarDay(this._dayKeys()[0]), {signal:renderSignal});
    this.shadowRoot.querySelector("#empty-add-departure")?.addEventListener("click",()=>{this._activeView="calendar";this._selectCalendarDay(this._dayKeys()[0]);}, {signal:renderSignal});
    this.shadowRoot.querySelector("#skip-next")?.addEventListener("click", () => this._call("button", "press", {entity_id:e.skip_next}), {signal:renderSignal});
    this.shadowRoot.querySelector("#more-actions")?.addEventListener("click", () => {this._showMoreActions=!this._showMoreActions;this._render();}, {signal:renderSignal});
    this.shadowRoot.querySelector("#pause-automation")?.addEventListener("click", async () => {if (await this._call("switch", a.automation_paused ? "turn_off" : "turn_on", {entity_id:e.automation_paused})) {this._pauseDraft=null;this._showPauseDate=false;this._render();}}, {signal:renderSignal});
    this.shadowRoot.querySelector("#show-pause-date")?.addEventListener("click", () => {this._showPauseDate=!this._showPauseDate;this._render();}, {signal:renderSignal});
    this.shadowRoot.querySelector("#pause-until")?.addEventListener("input", event => {this._pauseDraft=event.target.value;}, {signal:renderSignal});
    this.shadowRoot.querySelector("#save-pause")?.addEventListener("click", async () => {
      const value=this.shadowRoot.querySelector("#pause-until")?.value;
      const utcValue=this._localToUtc(value);
      if (!utcValue) {this._actionError=t("invalidLocal");this._render();return;}
      if (new Date(utcValue).getTime() <= Date.now()) {this._actionError=t("future");this._render();return;}
      if (await this._call("datetime","set_value",{entity_id:e.pause_until,datetime:value.length===16 ? `${value}:00` : value})) {
        if (await this._call("switch","turn_on",{entity_id:e.automation_paused})) {this._pauseDraft=null;this._showPauseDate=false;this._render();}
      }
    }, {signal:renderSignal});
    this.shadowRoot.querySelector("#window-previous")?.addEventListener("click", () => this._changeCalendarWindow(-7), {signal:renderSignal});
    this.shadowRoot.querySelector("#window-next")?.addEventListener("click", () => this._changeCalendarWindow(7), {signal:renderSignal});
    this.shadowRoot.querySelector("#window-today")?.addEventListener("click", () => this._changeCalendarWindow(null), {signal:renderSignal});
    this.shadowRoot.querySelector("#window-refresh")?.addEventListener("click", () => this._loadCalendarWindow(), {signal:renderSignal});
    this.shadowRoot.querySelector("#window-retry")?.addEventListener("click", () => this._loadCalendarWindow(), {signal:renderSignal});
    this.shadowRoot.querySelectorAll("[data-mobile-day]").forEach(el => el.addEventListener("click", () => {
      const key=el.dataset.mobileDay; this._mobileDay=key;this._mobileDayChosen=true;this._render();
      this.shadowRoot.querySelector(`[data-mobile-day="${key}"]`)?.focus({preventScroll:true});
    }, {signal:renderSignal}));
    this.shadowRoot.querySelector("#calendar-history-day")?.addEventListener("change", event => {
      this._mobileDay=event.target.value; this._mobileDayChosen=true; this._render();
      this.shadowRoot.querySelector("#calendar-history-day")?.focus({preventScroll:true});
    }, {signal:renderSignal});
    this.shadowRoot.querySelectorAll("[data-add-day]").forEach(el => el.addEventListener("click", () => this._selectCalendarDay(el.dataset.addDay), {signal:renderSignal}));
    this.shadowRoot.querySelectorAll("[data-grid-day]").forEach(el => el.addEventListener("click", event => {
      if (!calendarOk || this._pending || event.target.closest(".cal-event")) return;
      const elapsed=(event.clientY-el.getBoundingClientRect().top)/hourHeight*60;
      const minute=Math.max(0,Math.min(23*60+45,Math.round(elapsed/15)*15));
      this._selectCalendarDay(el.dataset.gridDay); this._calendarTime=`${String(Math.floor(minute/60)).padStart(2,"0")}:${String(minute%60).padStart(2,"0")}`; this._render();
    }, {signal:renderSignal}));
    this.shadowRoot.querySelector("#cancel-calendar")?.addEventListener("click", () => { this._selectedDay=null; this._editContext=null; this._render(); }, {signal:renderSignal});
    this.shadowRoot.querySelector("#calendar-date")?.addEventListener("input", event => {this._editDate=event.target.value;}, {signal:renderSignal});
    this.shadowRoot.querySelector("#calendar-summary")?.addEventListener("input", event => {this._editSummary=event.target.value;}, {signal:renderSignal});
    this.shadowRoot.querySelector("#confirm-series-change")?.addEventListener("change", event => {this._editAcknowledged=event.target.checked;}, {signal:renderSignal});
    this.shadowRoot.querySelector("#calendar-time")?.addEventListener("input", event => { this._calendarTime=event.target.value; }, {signal:renderSignal});
    this.shadowRoot.querySelector("#repeat-frequency")?.addEventListener("change", event => {this._repeatFreq=event.target.value;this._render();}, {signal:renderSignal});
    this.shadowRoot.querySelector("#repeat-interval")?.addEventListener("input", event => {this._repeatInterval=event.target.value;}, {signal:renderSignal});
    this.shadowRoot.querySelector("#repeat-until")?.addEventListener("input", event => {this._repeatUntil=event.target.value;}, {signal:renderSignal});
    this.shadowRoot.querySelectorAll("[data-repeat-day]").forEach(el=>el.addEventListener("change",()=>{
      this._repeatDays=[...this.shadowRoot.querySelectorAll("[data-repeat-day]:checked")].map(x=>x.dataset.repeatDay);
    }, {signal:renderSignal}));
    this.shadowRoot.querySelector("#add-calendar")?.addEventListener("click", async () => {
      const value=this.shadowRoot.querySelector("#calendar-time")?.value, key=this._editDate;
      if (this._editContext?.series && !this._editAcknowledged) {this._actionError=t("seriesConfirmRequired");this._render();return;}
      if (!value || !key) { this._actionError=t("chooseTime"); this._render(); return; }
      const start=`${key}T${value}`;
      const utcStart=this._editContext?.originalWall === start ? new Date(this._editContext.originalStart).toISOString() : this._localToUtc(start);
      if (!utcStart) { this._actionError=t("invalidLocal"); this._render(); return; }
      if ((!this._editContext?.series || this._repeatFreq === "NONE") && new Date(utcStart).getTime() <= Date.now()) { this._actionError=t("future"); this._render(); return; }
      const [y,m,d]=key.split("-").map(Number), [hour,minute]=value.split(":").map(Number);
      const end=new Date(Date.UTC(y,m-1,d,hour,minute+1)).toISOString().slice(0,19);
      this._calendarTime=value;
      let ok=false, rule=null;
      const summary=this._editSummary.trim() || t("eventSummary");
      if (this._repeatFreq !== "NONE") {
        const interval=Number(this._repeatInterval);
        if (!Number.isInteger(interval) || interval<1 || interval>99) {this._actionError=t("repeatInterval");this._render();return;}
        if (this._repeatFreq === "WEEKLY" && !this._repeatDays.length) {this._actionError=t("repeatDay");this._render();return;}
        if (this._repeatUntil && this._repeatUntil<key) {this._actionError=t("repeatEnd");this._render();return;}
        rule=`FREQ=${this._repeatFreq};INTERVAL=${interval}`;
        if (this._repeatFreq === "WEEKLY") rule+=`;BYDAY=${this._repeatDays.join(",")}`;
        if (this._repeatUntil) {
          const until=this._localToUtc(`${this._repeatUntil}T23:59`);
          if (!until) {this._actionError=t("invalidLocal");this._render();return;}
          const utcUntil=new Date(new Date(until).getTime()+59000).toISOString().replace(/[-:]/g,"").replace(/\.\d{3}Z$/, "Z");
          rule+=`;UNTIL=${utcUntil}`;
        }
      }
      if (this._editContext?.series && this._editContext.originalRepeat === JSON.stringify([this._repeatFreq,String(this._repeatInterval),this._repeatDays,this._repeatUntil])) rule=this._editContext.originalRule;
      const endUtc=new Date(new Date(utcStart).getTime()+60000).toISOString();
      if (this._editContext) {
        const event={summary,dtstart:utcStart,dtend:endUtc}; if (rule) event.rrule=rule;
        const message={type:"calendar/event/update",entity_id:e.calendar,uid:this._editContext.uid,event};
        if (this._editContext.occurrence) message.recurrence_id=this._editContext.recurrence_id;
        ok=await this._callWS(message);
      } else if (rule) {
        ok=await this._callWS({type:"calendar/event/create",entity_id:e.calendar,event:{summary,dtstart:utcStart,dtend:endUtc,rrule:rule}});
      } else {
        ok=await this._call("calendar","create_event",{entity_id:e.calendar,summary,start_date_time:`${start}:00`,end_date_time:end});
      }
      if (ok) { this._selectedDay=null; this._editContext=null; await this._loadCalendarWindow(true); }
    }, {signal:renderSignal});
    this.shadowRoot.querySelectorAll("[data-edit-index]").forEach(el=>el.addEventListener("click",()=>{
      const item=schedule[Number(el.dataset.editIndex)];if(!item)return;
      this._selectedDay=null;this._editContext=null;this._deleteRecurrence=null;this._actionError=null;
      if(item.recurrence_id){this._editChoice=item;this._render();}else this._startEditing(item,false);
    }, {signal:renderSignal}));
    this.shadowRoot.querySelector("#edit-one")?.addEventListener("click",()=>this._startEditing(this._editChoice,false), {signal:renderSignal});
    this.shadowRoot.querySelector("#edit-series")?.addEventListener("click",()=>this._startEditing(this._editChoice,true), {signal:renderSignal});
    this.shadowRoot.querySelector("#edit-cancel")?.addEventListener("click",()=>{this._editChoice=null;this._render();}, {signal:renderSignal});
    this.shadowRoot.querySelectorAll("[data-remove-uid]").forEach(el => el.addEventListener("click", async () => {
      if (el.dataset.recurrenceId) {this._deleteRecurrence={uid:el.dataset.removeUid,recurrence_id:el.dataset.recurrenceId};this._render();return;}
      if (await this._callWS({type:"calendar/event/delete",entity_id:e.calendar,uid:el.dataset.removeUid})) await this._loadCalendarWindow(true);
    }, {signal:renderSignal}));
    this.shadowRoot.querySelector("#delete-cancel")?.addEventListener("click",()=>{this._deleteRecurrence=null;this._render();}, {signal:renderSignal});
    const deleteRecurring=async (series)=>{
      const item=this._deleteRecurrence;if(!item)return;
      const msg={type:"calendar/event/delete",entity_id:e.calendar,uid:item.uid};
      if(!series)msg.recurrence_id=item.recurrence_id;
      if(await this._callWS(msg)){this._deleteRecurrence=null;await this._loadCalendarWindow(true);}
    };
    this.shadowRoot.querySelector("#delete-one")?.addEventListener("click",()=>deleteRecurring(false), {signal:renderSignal});
    this.shadowRoot.querySelector("#delete-series")?.addEventListener("click",()=>deleteRecurring(true), {signal:renderSignal});
    this.shadowRoot.querySelector("#week")?.addEventListener("click", () => {this._showWeek = !this._showWeek; this._render();}, {signal:renderSignal});
    this.shadowRoot.querySelector("#history-toggle")?.addEventListener("click", () => {this._showHistory = !this._showHistory; this._render();}, {signal:renderSignal});
    this.shadowRoot.querySelector("#history-more")?.addEventListener("click", () => {this._historyLimit += 10; this._render();}, {signal:renderSignal});
    this.shadowRoot.querySelectorAll("[data-total-period]").forEach(el=>el.addEventListener("click",()=>{this._totalPeriod=el.dataset.totalPeriod;this._totalLimit=7;this._render();}, {signal:renderSignal}));
    this.shadowRoot.querySelector("#total-more")?.addEventListener("click",()=>{this._totalLimit+=7;this._render();}, {signal:renderSignal});
    this.shadowRoot.querySelectorAll("[data-day-time]").forEach((el) => el.addEventListener("change", () => {if (el.value) this._call("time", "set_value", {entity_id:e.weekly[Number(el.dataset.dayTime)].time, time:`${el.value}:00`});}, {signal:renderSignal}));
    this.shadowRoot.querySelectorAll("[data-day-switch]").forEach((el) => el.addEventListener("change", () => this._call("switch", el.checked ? "turn_on" : "turn_off", {entity_id:e.weekly[Number(el.dataset.daySwitch)].enabled}), {signal:renderSignal}));
    if (focusedMobileDay) this.shadowRoot.querySelector(`[data-mobile-day="${focusedMobileDay}"]`)?.focus({preventScroll:true});
    if (focusedHistory) this.shadowRoot.querySelector(`#${focusedHistory}`)?.focus({preventScroll:true});
    if (focusedTotal) this.shadowRoot.querySelector(`[data-total-period="${focusedTotal}"]`)?.focus({preventScroll:true});
  }
}

class MotorvarmareCardEditor extends HTMLElement {
  constructor() {super(); this.attachShadow({mode:"open"}); this._config = {};}
  setConfig(config) {this._config = {...config}; this._render();}
  set hass(hass) {this._hass = hass; if (!this.shadowRoot.activeElement) this._render();}
  _set(key, value) {this._config = {...this._config, [key]:value}; this.dispatchEvent(new CustomEvent("config-changed", {detail:{config:this._config}, bubbles:true, composed:true}));}
  _options(domain, selected) {
    const states = Object.values(this._hass?.states || {}).filter(s=>s.entity_id.startsWith(`${domain}.`) && (s.attributes?.control_entities || s.entity_id === selected));
    const options = states.sort((a,b)=>(a.attributes.friendly_name || a.entity_id).localeCompare(b.attributes.friendly_name || b.entity_id, "sv")).map(s=>`<option value="${mvEscape(s.entity_id)}" ${s.entity_id === selected ? "selected" : ""}>${mvEscape(s.attributes.friendly_name || s.entity_id)} (${mvEscape(s.entity_id)})</option>`);
    if (selected && !states.some(s=>s.entity_id === selected)) options.unshift(`<option selected value="${mvEscape(selected)}">${mvEscape(selected)} (${mvText(this._hass,"missing")})</option>`);
    return `<option value="">${mvText(this._hass,"selectEntity")}</option>${options.join("")}`;
  }
  _render() {
    if (!this._hass) return;
    const c = this._config, t = key => mvText(this._hass,key);
    this.shadowRoot.innerHTML = `<style>:host{display:block} .fields{display:grid;gap:14px} label{display:grid;gap:5px;color:var(--secondary-text-color);font:14px Roboto,system-ui,sans-serif} input,select{font:14px Roboto,system-ui,sans-serif;color:var(--primary-text-color);background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:6px;padding:10px;min-height:42px;width:100%;box-sizing:border-box} p{color:var(--secondary-text-color);font:13px/1.45 Roboto,system-ui,sans-serif;margin:0}</style>
      <div class="fields"><label>${t("cardTitle")}<input id="title" value="${mvEscape(c.title || "")}" placeholder="Motorvärmare"></label><label>${t("statusEntity")}<select id="status">${this._options("sensor",c.status_entity)}</select></label><p>${t("editorHint")}</p></div>`;
    this.shadowRoot.querySelector("#title").addEventListener("change", e=>this._set("title",e.target.value));
    this.shadowRoot.querySelector("#status").addEventListener("change", e=>this._set("status_entity",e.target.value));
  }
}

if (!customElements.get("motorvarmare-card")) customElements.define("motorvarmare-card", MotorvarmareCard);
if (!customElements.get("motorvarmare-card-editor")) customElements.define("motorvarmare-card-editor", MotorvarmareCardEditor);
window.customCards = window.customCards || [];
if (!window.customCards.some(c=>c.type === "motorvarmare-card")) window.customCards.push({type:"motorvarmare-card", name:"Motorvärmare", description:"Motorvärmare / Engine heater schedule", preview:true});

/* Companion multi-car overview. Append after motorvarmare-card definitions. */
class MotorvarmareOverview extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode: "open"});
    this._config = {entities: []};
    this._selected = null;
    this._events = null;
  }
  static getConfigElement() { return document.createElement("motorvarmare-overview-editor"); }
  static getStubConfig() { return {entities: []}; }
  getCardSize() { return Math.max(2, (this._config.entities || []).length * 2); }
  getGridOptions() { return {columns: 6, min_columns: 3, rows: "auto"}; }
  setConfig(config) {
    if (!config || typeof config !== "object" || (config.entities !== undefined && !Array.isArray(config.entities))) {
      throw new Error("entities must be a list of status sensor entity IDs");
    }
    const entities = [...new Set((config.entities || []).filter(x => typeof x === "string" && x.startsWith("sensor.")))];
    this._config = {...config, entities};
    if (this._selected && !entities.includes(this._selected)) this._selected = null;
    this._render();
  }
  set hass(value) { this._hass = value; this._render(); }
  disconnectedCallback() { this._events?.abort(); }
  connectedCallback() { this._render(); }
  _format(value) {
    if (!value || Number.isNaN(new Date(value).getTime())) return mvText(this._hass, "noDeparture");
    const options = {weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit"};
    const timeZone = this._hass?.config?.time_zone;
    if (timeZone) options.timeZone = timeZone;
    try { return new Intl.DateTimeFormat(mvLang(this._hass), options).format(new Date(value)); }
    catch (_) { delete options.timeZone; return new Intl.DateTimeFormat(mvLang(this._hass), options).format(new Date(value)); }
  }
  _render() {
    if (!this.shadowRoot || !this._hass) return;
    const t = key => mvText(this._hass, key);
    const title = this._config.title || t("carOverview");
    const entries = (this._config.entities || []).map(entity => {
      const state = this._hass.states?.[entity];
      const attrs = state?.attributes || {};
      const name = attrs.friendly_name || entity;
      const status = mvUsable(state) ? mvStateText(this._hass, state.state) : t("noStatus");
      const warnings = [attrs.error ? mvErrorText(this._hass, attrs.error) : "",
        ...(Array.isArray(attrs.operational_problems) ? attrs.operational_problems.filter(problem=>Object.prototype.hasOwnProperty.call(MV_I18N[mvLang(this._hass)], problem)).map(problem=>t(problem)) : []),
        ...(attrs.alarm_active === true && attrs.energy_monitor_status === "low_power" ? [t("powerAlarm")] : [])].filter(Boolean);
      const departure = this._format(attrs.next_departure);
      const temperature = Number.isFinite(attrs.temperature)
        ? `${new Intl.NumberFormat(mvLang(this._hass), {maximumFractionDigits: 1}).format(attrs.temperature)} °C` : "";
      return `<button type="button" class="car" data-entity="${mvEscape(entity)}">
        <span class="icon"><ha-icon icon="mdi:car"></ha-icon></span>
        <span class="car-body"><span class="car-heading">${mvEscape(name)}</span>
          <span class="status">${mvEscape(status)}</span>
          <span class="departure">${mvEscape(t("departure"))}: <strong>${mvEscape(departure)}</strong>${temperature ? ` · ${mvEscape(temperature)}` : ""}</span>
          ${[...new Set(warnings)].map(warning=>`<span class="warning">${mvEscape(warning)}</span>`).join("")}</span>
        <ha-icon class="chevron" icon="mdi:chevron-right"></ha-icon></button>`;
    }).join("");
    const body = this._selected
      ? `<button type="button" class="back" id="overview-back"><ha-icon icon="mdi:arrow-left"></ha-icon> ${mvEscape(t("backToCars"))}</button><motorvarmare-card id="detail"></motorvarmare-card>`
      : `<ha-card><div class="wrap"><div class="heading"><ha-icon icon="mdi:car-multiple"></ha-icon><h2>${mvEscape(title)}</h2></div><div class="cars">${entries || `<p class="empty">${mvEscape(t("noCars"))}</p>`}</div></div></ha-card>`;
    mvPatch(this.shadowRoot, `<style>
      :host{display:block;color:var(--primary-text-color)}
      .wrap{padding:20px}.heading{display:flex;align-items:center;gap:10px;margin:0 0 16px}.heading ha-icon{color:var(--primary-color)}
      h2{font-size:18px;line-height:1.25;margin:0;font-weight:650}.cars{display:grid;gap:10px}
      .car{font:inherit;text-align:left;width:100%;display:flex;align-items:center;gap:13px;padding:14px;border:1px solid var(--divider-color);border-radius:12px;color:var(--primary-text-color);background:var(--secondary-background-color);cursor:pointer}
      .car:focus-visible,.back:focus-visible{outline:2px solid var(--primary-color);outline-offset:2px}
      .icon{display:grid;place-items:center;flex:none;width:40px;height:40px;border-radius:12px;color:var(--primary-color);background:var(--card-background-color)}
      .car-body{display:grid;gap:4px;min-width:0;flex:1}.car-heading{font-size:15px;font-weight:650;overflow-wrap:anywhere}
      .status,.departure,.empty{font-size:13px;color:var(--secondary-text-color);line-height:1.4}.departure strong{color:var(--primary-text-color);font-weight:600}
      .warning{font-size:12px;color:var(--error-color, #db4437);overflow-wrap:anywhere}.chevron{flex:none;color:var(--secondary-text-color)}
      .back{display:inline-flex;align-items:center;gap:4px;border:0;padding:10px 4px;margin:0 0 5px;color:var(--primary-color);background:transparent;font:inherit;cursor:pointer}
      .back ha-icon{--mdc-icon-size:19px}
      </style>${body}`);
    this._events?.abort();
    this._events = new AbortController();
    const signal = this._events.signal;
    this.shadowRoot.querySelectorAll("[data-entity]").forEach(button => button.addEventListener("click", () => {
      this._selected = button.dataset.entity;
      this._render();
      this.shadowRoot.querySelector("#overview-back")?.focus({preventScroll:true});
    }, {signal}));
    this.shadowRoot.querySelector("#overview-back")?.addEventListener("click", () => {
      const selected = this._selected;
      this._selected = null;
      this._render();
      [...this.shadowRoot.querySelectorAll("[data-entity]")].find(node => node.dataset.entity === selected)?.focus({preventScroll:true});
    }, {signal});
    const detail = this.shadowRoot.querySelector("#detail");
    if (detail) {
      // Never replace a detail card on ordinary HA updates: that would lose
      // its draft, selected day, focus and calendar scroll position.
      if (detail._overviewEntity !== this._selected) {
        detail.setConfig({status_entity: this._selected});
        detail._overviewEntity = this._selected;
      }
      detail.hass = this._hass;
    }
  }
}

class MotorvarmareOverviewEditor extends HTMLElement {
  constructor() { super(); this.attachShadow({mode:"open"}); this._config = {entities: []}; }
  setConfig(config) { this._config = {...config, entities: Array.isArray(config?.entities) ? [...config.entities] : []}; this._render(); }
  set hass(value) { this._hass = value; if (!this.shadowRoot.activeElement) this._render(); }
  _set(changes) {
    this._config = {...this._config, ...changes};
    this.dispatchEvent(new CustomEvent("config-changed", {detail:{config:this._config}, bubbles:true, composed:true}));
  }
  _render() {
    if (!this._hass) return;
    const t = key => mvText(this._hass,key);
    const selected = this._config.entities || [];
    const states = Object.values(this._hass.states || {}).filter(state =>
      state.entity_id?.startsWith("sensor.") && (state.attributes?.control_entities || selected.includes(state.entity_id)));
    for (const id of selected) if (!states.some(s => s.entity_id === id)) states.push({entity_id:id,attributes:{friendly_name:`${id} (${t("missing")})`}});
    states.sort((a,b) => (a.attributes?.friendly_name || a.entity_id).localeCompare(b.attributes?.friendly_name || b.entity_id, mvLang(this._hass)));
    const options = states.map(s => `<label class="option"><input type="checkbox" data-entity="${mvEscape(s.entity_id)}" ${selected.includes(s.entity_id)?"checked":""}><span>${mvEscape(s.attributes?.friendly_name || s.entity_id)}<small>${mvEscape(s.entity_id)}</small></span></label>`).join("");
    this.shadowRoot.innerHTML = `<style>:host{display:block}.fields{display:grid;gap:14px}.text-label{display:grid;gap:5px;color:var(--secondary-text-color);font:14px Roboto,system-ui,sans-serif}.title{font:14px Roboto,system-ui,sans-serif;color:var(--primary-text-color);background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:6px;padding:10px;min-height:42px;box-sizing:border-box;width:100%}.option{display:flex;align-items:center;gap:10px;padding:8px 0;color:var(--primary-text-color);font:14px Roboto,system-ui,sans-serif}.option input{width:18px;height:18px}.option span{display:grid;gap:3px}.option small{color:var(--secondary-text-color)}p{font:13px Roboto,system-ui,sans-serif;color:var(--secondary-text-color)}</style><div class="fields"><label class="text-label">${mvEscape(t("cardTitle"))}<input class="title" id="title" value="${mvEscape(this._config.title || "")}" placeholder="${mvEscape(t("carOverview"))}"></label><div><div class="text-label">${mvEscape(t("addCars"))}</div>${options || `<p>${mvEscape(t("noCars"))}</p>`}</div></div>`;
    this.shadowRoot.querySelector("#title").addEventListener("change", event => this._set({title:event.target.value}));
    this.shadowRoot.querySelectorAll("[data-entity]").forEach(box => box.addEventListener("change", () => {
      const checked = [...this.shadowRoot.querySelectorAll("[data-entity]:checked")].map(node => node.dataset.entity);
      this._set({entities: checked});
    }));
  }
}

if (!customElements.get("motorvarmare-overview")) customElements.define("motorvarmare-overview", MotorvarmareOverview);
if (!customElements.get("motorvarmare-overview-editor")) customElements.define("motorvarmare-overview-editor", MotorvarmareOverviewEditor);
window.customCards = window.customCards || [];
if (!window.customCards.some(card => card.type === "motorvarmare-overview")) window.customCards.push({type:"motorvarmare-overview", name:"Motorvärmare – översikt / Engine heaters", description:"Samlad översikt för flera bilar / Multi-car engine heater overview", preview:true});
