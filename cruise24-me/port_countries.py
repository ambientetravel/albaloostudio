"""
port_countries.py — which country a CruiseHost or Variety port name is in.

Architecture credit: Albaloo Studio — albaloostudio.com

Used by build_journeys.py after its exact-name table. The visa lines on every sailing page
depend on this, so the rules are explicit word lists per country, never loose substrings:
«Vienna» is Austria and «Vienne» is France; «Sydney, Nova Scotia» is Canada before
«Sydney» is Australia; «Marigot Bay» is St Lucia. Order matters: first match wins.

NOT_A_PORT marks route entries that are scenery, not a place anyone goes ashore
("Cruising in the Aegean Sea", "Border Crossing"); they are skipped, not "unknown".
"""
import re

RULES = [
    # ── explicit country words first ──
    (r"\b(turkey|türkiye)\b|dardanelles|gallipoli peninsula", "TR"), (r"\bitaly\b", "IT"), (r"\bgreece\b", "GR"), (r"\bcroatia\b", "HR"),
    (r"\bmontenegro\b", "ME"), (r"\bmalta\b", "MT"), (r"\bdenmark\b", "DK"), (r"\bnorway\b", "NO"),
    (r"\bscotland\b|shetland|\bengland\b", "GB"), (r"nova scotia|newfoundland|prince edward island|british columbia|\bquebec\b|\(b\.c\.\)", "CA"),
    (r"\balaska\b|\bhawaii\b|\bflorida\b|\bcalifornia\b|\bmaine\b|rhode island", "US"),
    (r"\bchile\b|chilean", "CL"), (r"\bcorsica\b", "FR"), (r"\bsenegal\b", "SN"), (r"\bgambia\b", "GM"),
    # ── Europe ──
    (r"\bparis\b|bordeaux|strasbourg|\bnice\b|\blyon\b|\bvienne\b|honfleur|rouen|caudebec|\bvernon\b|roche guyon|les andelys|conflans|m[aâ]con|\bbourg\b|avignon|\barles\b|viviers|tournon|ch[aâ]teauneuf|tarascon|libourne|cadillac|\bblaye\b|m[ée]doc|pauillac|s[èe]te\b|toulon|sanary|cassis|menton|calvi|bonifacio|bastia|porticcio|collioure|port vendres|st\.? malo|dinard|bayonne|h[üu]ningen|huningue", "FR"),
    (r"\bmonaco\b|monte carlo", "MC"),
    (r"passau|r[üu]desheim|regensburg|cologne|n[üu]rnberg|nuremberg|bamberg|w[üu]rzburg|mannheim|koblenz|breisach|\bbonn\b|d[üu]sseldorf|wertheim|miltenberg|rastatt|bernkastel|cochem|middle rhine|\bkehl\b|\bmainz\b|munich|m[üu]nchen|berlin|frankfurt|dresden|schwangau|hamburg|warnem[üu]nde|warnemuende|kiel\b|rostock", "DE"),
    (r"\bvienna\b|d[üu]rnstein|duernstein|\bkrems\b|\bmelk\b|\blinz\b|schl[öo]gen|wachau|brandstatt|salzburg", "AT"),
    (r"budapest|moh[aá]cs|kalocsa|\bordas\b", "HU"), (r"bratislava", "SK"), (r"prague|praha|[čc]esk[ýy] krumlov", "CZ"),
    (r"amsterdam|dordrecht|\bveere\b|nijmegen|arnh(ei)?m|\bhoorn\b|bruinisse|rotterdam|kinderdijk", "NL"),
    (r"antwerp|bruges|br[üu]gge|brussels|ghent|zeebr[üu]gge", "BE"),
    (r"z[üu]rich|basel|\bbern(e)?\b|montreux|lucerne|luzern|engelberg|lugano|zermatt|interlaken|lausanne|geneva", "CH"),
    (r"madrid|sevill[ae]|seville|jerez|almer[ií]a|\bvigo\b|ferrol|avil[ée]s|santander|huelva|pe[ñn][ií]scola|menorca|alc[uú]dia|\broses\b|puerto ban[uú]s|las palmas|melilla|vega de terr[oó]n|bilbao|c[aá]diz|m[aá]laga|cartagena|tenerife|lanzarote|fuerteventura|la palma|la gomera|ibiza|mallorca|palma", "ES"),
    (r"r[ée]gua|pinh[aã]o|pocinho|portim[aã]o|leix[õo]es|barca d.?alva|porto santo|lisbon|lisboa|funchal|madeira|\bporto\b", "PT"),
    (r"\boslo\b|trondheim|geiranger|\bolden\b|\bmolde\b|leknes|lofoten|[åa]lesund|[åa]ndalsnes|\bmandal\b|troms[øo]|br[øo]nn?[øo]ysund|broennoeysund|lofthus|rosendal|hardanger|m[åa]l[øo]y|maloy|skarsv[åa]g|north cape|nordfjord|bergen|stavanger|fl[åa]m|honningsv[åa]g|hammerfest", "NO"),
    (r"g[öo]teborg|gothenburg|stockholm|visby|lysekil", "SE"), (r"skagen|aalborg|copenhagen|aarhus|r[øo]nne", "DK"),
    (r"warsaw|krak[óo]w|danzig|gda[ńn]sk|gdynia", "PL"), (r"klaip[ėe]da", "LT"), (r"\briga\b|liep[āa]ja", "LV"), (r"tallinn", "EE"), (r"helsinki", "FI"),
    (r"ljubljana|koper|piran", "SI"), (r"vukovar|osijek|zagreb|plitvice|komi[žz]a|vodice", "HR"),
    (r"belgrade|novi sad|golubac|donji milanovac|iron gate", "RS"),
    (r"bucharest|giurgiu|bra[șs]ov|sibiu|sighi[șs]oara|constan[tț]a|konstanza|cernavod[ăa]|tulcea", "RO"),
    (r"\bru(s)?se\b|rousse|silistra|svishtov|vidin", "BG"),
    (r"porto venere|portovenere|ponza|palmarola|porto empedocle|reggio calabria|agropoli|golfo aranci|viareggio|piombino|marina di carrara|porto ercole", "IT"),
    (r"monemvas|galaxid|spetsai|fiskardh|igoumenitsa", "GR"),
    (r"limassol|larnaca", "CY"),
    (r"london|southampton|\byork\b|\bbath\b|edinburgh|inverness|stornoway|lerwick|\bdover\b|falmouth|tilbury|rosyth|leith|dundee|aberdeen|newcastle|berwick|great yarmouth|\biona\b|st\.? kilda|fair isle|isle of may|lindisfarne|farne|loch lomond|loch ewe|shiant|lunga|\bbelfast\b|portsmouth|liverpool|holyhead", "GB"),
    (r"st\.? peter port|guernsey", "GG"),
    (r"dublin|killarney|galway|greencastle|cobh|cork\b|waterford", "IE"),
    (r"reykjav[ií]k|akureyri|[íi]saf[jj]?[öo]r[ðd]ur|isafjordur|grundarfj|siglufj|sey[ðd]isfj|seydisfj|flatey|vigur|dynjandi|golden circle|kirkjub|\bvik\b|sau[ðd][áa]rkr|sky lagoon|husav[ií]k", "IS"),
    (r"t[óo]rshavn|vestmanna|faroe", "FO"),
    (r"svalbard|spitsbergen|longyearbyen|bear island", "SJ"),
    (r"nuuk|qaqortoq|paamiut|ilulissat|sisimiut|scoresby|scorebysund|evighedsfjord|prins christian|hvalsey|kong oscar|ittoqqortoormiit|ittopportoormiit|qeqertarsua|ella island|eqip sermia|crown prince|greenland", "GL"),
    # ── Americas ──
    (r"new york|boston|key west|san francisco|san diego|los angeles|portland|newport|cape cod|juneau|sitka|seward|ketchikan|wrangell|skagway|hoonah|haines|valdez|kodiak|klawock|icy bay|hubbard|tracy arm|endicott arm|inside passage|ward cove|honolulu|hilo|nawiliwili|kahului|kailua|kona|miami|fort lauderdale|galveston", "US"),
    (r"charlotte amalie|st\.? thomas|frederiksted|st\.? croix|cruz bay", "VI"),
    (r"vancouver|montr[ée]al|halifax|sept-[îi]les|havre st|saguen|prince rupert|victoria \(b|lower savage|monumental island|lady franklin|charlottetown|gasp[ée]|madeleine|bay of fundy|saint john, new brunswick", "CA"),
    (r"cozumel|costa maya|progreso|puerto vallarta|huatulco|cabo san lucas|ensenada", "MX"),
    (r"belize", "BZ"), (r"puerto lim[oó]n|costa rica", "CR"), (r"roat[aá]n", "HN"), (r"puerto quetzal|santo tom[aá]s", "GT"),
    (r"\bcol[oó]n\b|san blas|bocas del toro|fuerte amador|dari[ée]n|panama|playa del muerto", "PA"),
    (r"cabo de la vela|utr[ií]a|santa marta|cartagena de indias", "CO"),
    (r"\bmanta\b|gal[aá]pagos|san crist[oó]bal", "EC"),
    (r"\blima\b|callao|cusco|cuzco|machu pic|paracas|salaverr?y|sacred valley", "PE"),
    (r"punta arenas|valpara[ií]so|puerto montt|torres del paine|puerto williams|pio xi|puerto ed[ée]n|niebla|valdivia|tortel|puerto cisnes|aguila|english narrows|santiago de chile|easter island|robinson crusoe|magellan|cape ho(rn|orn)|admiralty sound|tucker islands|whiteside|\bsantiago\b$|isla ping[üu]ino", "CL"),
    (r"buenos aires|ushuaia|el calafate|igua[zç][uú]|puerto madryn|punta pir[aá]mides|beagle", "AR"),
    (r"montevideo|punta del este", "UY"),
    (r"rio de janeiro|ilha grande|parat[yi]|cambori[uú]|ilhabela|ihebela|paranagu[aá]|s[aã]o francisco do sul|salvador|recife|porto belo|macei[oó]|amazon|manaus|santar[ée]m|parint", "BR"),
    (r"falkland|port stanley|stanley \(|new island|west point", "FK"), (r"south georgia", "GS"),
    (r"antarc|drake passage|south shetland|king george island|elephant island", "AQ"),
    (r"philipsburg|st\.? maarten", "SX"), (r"marigot bay|soufri[èe]re|castries", "LC"), (r"\bmarigot\b|saint-martin", "MF"),
    (r"terre-de-haut|pointe?-[àa]-pitre|point-[àa]-pitre|deshaies|les saintes|guadeloupe", "GP"), (r"fort-de-france|martinique|trois-[îi]lets", "MQ"),
    (r"roseau|dominica\b", "DM"), (r"canouan|mayreau|tobago cays|bequia|kingstown", "VC"),
    (r"puerto plata|saman[aá]|cayo levantado|la romana|isla catalina", "DO"),
    (r"nassau|exuma|bimini|staniel cay|ocean cay|bahamas", "BS"), (r"providenciales|grand turk", "TC"),
    (r"kralendijk|bonaire", "BQ"), (r"royal naval dockyard|bermuda", "BM"), (r"anguilla|road bay", "AI"),
    (r"tortola|jost van dyke|soper.?s hole|virgin gorda|spanish town", "VG"), (r"little bay|montserrat", "MS"),
    # ── Asia, Oceania, Africa ──
    (r"tokyo|kobe|nagasaki|hiroshima|kagoshima|naha|okinawa|osaka|shimizu|hakodate|kanazawa|nagoya|ishigaki|aomori|sakaiminato|amami|shimonoseki|m[iy]{1,2}ako|kushiro|otaru|fukuoka|hakata|beppu|aburatsu|yokohama|sasebo|miyanoura|yakushima|kyoto", "JP"),
    (r"busan|jeju|inchon|incheon|seoul", "KR"), (r"shanghai|tianjin|beijing", "CN"), (r"hong ?kong", "HK"), (r"keelung|kaohsiung|taipei", "TW"),
    (r"ho chi minh|saigon|phu quoc|hanoi|ha ?long|hoi an|\bhue\b|da ?nang|nha trang|phu my|chan may|tan chau|sa dec|cai be", "VN"),
    (r"siem reap|phnom penh|angkor|kampong cham|oudong|silk island|sihanoukville", "KH"),
    (r"bangkok|laem chabang|phuket|ko samui|krabi", "TH"), (r"singapore", "SG"),
    (r"port klang|kuala lumpur|malak+a|melaka|penang|langkawi|sandakan|sabah", "MY"), (r"benoa|bali|komodo|\btoba\b|semarang|java|lombok", "ID"), (r"manila", "PH"),
    (r"kochi|cochin|kolkata|calcutta|mumbai|bombay|delhi|jaipur|agra|ranthambore|mayapur|matiari|chandernagore|kalna|murshidab|serampore|khushbagh|plassey", "IN"),
    (r"colombo|hambantota", "LK"), (r"luang prabang|vang vieng|vientiane", "LA"), (r"port louis|mauritius", "MU"),
    (r"alexandria|cairo|giza|luxor|aswan|nile", "EG"), (r"\btunis\b", "TN"), (r"annaba", "DZ"),
    (r"cape ?town|capetown", "ZA"), (r"bijag", "GW"),
    (r"sydney|melbourne|darwin|cairns|brisbane|fremantle|broome|hobart|tasmania|airlie beach|mooloolaba|adelaide|port lincoln|fraser island|willis island|kangaroo island|\beden\b|buccaneer archipelago|koolama|hunter river|dampier|houtman abrolhos|ashmore reef|kimberley", "AU"),
    (r"milford sound|doubtful sound|dunedin|tauranga|auckland|napier|gisborne|wellington|stewart island|lyttle?ton", "NZ"),
    (r"lautoka|fiji", "FJ"), (r"tahuata|fatu hiva|atuona|hanavave|mangareva|nuku hiva", "PF"), (r"pitcairn", "PN"),
]
NOT_A_PORT = re.compile(r"^(cruis(e|ing)\b|cruise ahead|crossing\b|border crossing|morning swim|solar eclipse|passage\b)|"
                        r"\b(cruising in|crossing in|crossing the|border crossing|swim stop|solar eclipse|international date line)\b", re.I)
_COMPILED = [(re.compile(p, re.I), c) for p, c in RULES]


def country(port: str):
    for rx, cc in _COMPILED:
        if rx.search(port):
            return cc
    return None


def is_scenery(port: str) -> bool:
    return bool(NOT_A_PORT.search(port))
