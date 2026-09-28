TAGLINE="Ocean, river and luxury small-ship cruises from the Middle East, with the real price and the visa position up front."
OVERVIEW="""Cruise24 brings the world of cruising to travellers from the Middle East: ocean cruises, river weeks and luxury small-ship journeys, planned and booked by one person who stays on your file from the first question to the last evening on board.

We work with the lines we know best. Our focus is Explora Journeys, Silversea, Variety Cruises and Scenic. In the Mediterranean we also book Seabourn, Regent Seven Seas, Ponant, SeaDream, Sea Cloud and Star Clippers, and on request Celestyal, AROYA, MSC Cruises, A-ROSA, nicko cruises and Amadeus. From the Greek islands and the Turkish coast to the Red Sea, the Persian Gulf, the Danube and the Norwegian fjords.

Every offer states the real price, with what the fare includes and what it does not, and the visa position for every port on the route and the passport you hold. Any Greek, Italian, Spanish or French port puts a sailing under Schengen rules, and we say so before anyone pays.

For companies, MICE at sea: incentives, leadership off-sites, product launches and client events, from a block of suites on a scheduled sailing to a full-ship charter. With Explore Orient, our group's MICE and DMC company, land and sea are one brief to one team.

Cruise24 is a brand of Ambiente Group: Ambiente Tours GmbH in Rennerod, Germany, for the DACH region, and Ambiente Turizm Seyahat in Kuşadası, Türkiye, for the Middle East, North Africa and Türkiye."""
SPECIALTIES=["Luxury cruises","Small-ship cruises","Yacht cruises","River cruises","Ocean cruises","Expedition cruises","Mediterranean cruises","Greek islands cruises","Red Sea cruises","Persian Gulf cruises","MICE at sea","Incentive travel","Ship charters","Group cruises","Corporate events at sea","Celebrations at sea","Cruise visa advice","Explora Journeys","Silversea"]
if __name__=="__main__":
    print("tagline",len(TAGLINE),"/120"); print("overview",len(OVERVIEW),"/2000"); print("specialties",len(SPECIALTIES),"/20", max(len(s) for s in SPECIALTIES))
    assert "Arabian Gulf" not in OVERVIEW
