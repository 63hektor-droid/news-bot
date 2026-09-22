# -*- coding: utf-8 -*-
# =====================================================================
#  data.py  -  all lists used by bot.py (edit freely, one place)
# =====================================================================

# ---------------------------------------------------------------------
# 1) 20 foreign (non-Persian) news agencies, graded by world credibility.
#    rank | tier | name | Persian name | feed URLs (space separated)
#    tier A = top (US/UK wire + flagship papers), B = strong, C = good.
#    Feeds come from my own knowledge (NOT verified live): the bot logs
#    which feeds work in every run and simply skips the broken ones.
#    Reuters and AP have no official RSS anymore, so they go through
#    Google News RSS restricted to their site.
# ---------------------------------------------------------------------
SOURCES = """
1|A|Reuters|رویترز|https://news.google.com/rss/search?q=site:reuters.com+Iran+when:1d&hl=en-US&gl=US&ceid=US:en https://news.google.com/rss/search?q=site:reuters.com+(oil+OR+sanctions+OR+nuclear+OR+Hormuz+OR+Israel+OR+Gulf)+when:1d&hl=en-US&gl=US&ceid=US:en
2|A|Associated Press|آسوشیتدپرس|https://news.google.com/rss/search?q=site:apnews.com+Iran+when:1d&hl=en-US&gl=US&ceid=US:en https://news.google.com/rss/search?q=site:apnews.com+(oil+OR+sanctions+OR+nuclear+OR+Hormuz+OR+Israel+OR+Gulf)+when:1d&hl=en-US&gl=US&ceid=US:en
3|A|BBC News|بی‌بی‌سی|https://feeds.bbci.co.uk/news/world/middle_east/rss.xml https://feeds.bbci.co.uk/news/world/rss.xml https://feeds.bbci.co.uk/news/business/rss.xml
4|A|The New York Times|نیویورک‌تایمز|https://rss.nytimes.com/services/xml/rss/nyt/MiddleEast.xml https://rss.nytimes.com/services/xml/rss/nyt/World.xml
5|A|The Wall Street Journal|وال‌استریت‌ژورنال|https://feeds.a.dj.com/rss/RSSWorldNews.xml https://feeds.a.dj.com/rss/RSSMarketsMain.xml
6|A|Financial Times|فایننشال‌تایمز|https://www.ft.com/world?format=rss https://www.ft.com/markets?format=rss
7|A|The Washington Post|واشنگتن‌پست|https://feeds.washingtonpost.com/rss/world https://feeds.washingtonpost.com/rss/national
8|A|Bloomberg|بلومبرگ|https://feeds.bloomberg.com/politics/news.rss https://feeds.bloomberg.com/markets/news.rss
9|B|The Guardian|گاردین|https://www.theguardian.com/world/iran/rss https://www.theguardian.com/world/middleeast/rss https://www.theguardian.com/world/rss
10|B|The Economist|اکونومیست|https://www.economist.com/middle-east-and-africa/rss.xml https://www.economist.com/international/rss.xml
11|B|CNN|سی‌ان‌ان|http://rss.cnn.com/rss/edition_meast.rss http://rss.cnn.com/rss/edition_world.rss
12|B|NPR|ان‌پی‌آر|https://feeds.npr.org/1004/rss.xml
13|B|Sky News|اسکای‌نیوز|https://feeds.skynews.com/feeds/rss/world.xml
14|B|Politico|پولیتیکو|https://rss.politico.com/politics-news.xml https://rss.politico.com/defense.xml
15|C|Al Jazeera English|الجزیره انگلیسی|https://www.aljazeera.com/xml/rss/all.xml
16|C|France 24|فرانس ۲۴|https://www.france24.com/en/middle-east/rss https://www.france24.com/en/rss
17|C|Deutsche Welle|دویچه‌وله|https://rss.dw.com/xml/rss-en-all https://rss.dw.com/xml/rss-en-world
18|C|Euronews|یورونیوز|https://www.euronews.com/rss?format=mrss&level=theme&name=news
19|C|Al-Monitor|المانیتور|https://www.al-monitor.com/rss
20|C|The Times of Israel|تایمز اسرائیل|https://www.timesofisrael.com/feed/
"""

# ---------------------------------------------------------------------
# 2) Keywords (English).  "## category weight" starts a section.
#    weight 3 = explicitly Iranian, 2 = Iran-specific concept,
#    weight 1 = generic (only counts together with a 3 or a 2).
#    Matching is case-insensitive, whole words.
# ---------------------------------------------------------------------
KEYWORDS = """
## iran 3
iran, iranian, iranians, iran's, islamic republic, islamic republic of iran, tehran, persian gulf
irgc, islamic revolutionary guard corps, revolutionary guard, revolutionary guards
revolutionary guard corps, quds force, basij, basiji, khamenei, supreme leader, ayatollah
ayatollahs, mullahs, majlis, guardian council, assembly of experts, expediency council
supreme national security council, khatam al-anbiya, iranian regime, iranian government
iranian officials, iranian foreign ministry, iranian president, iranian parliament, iranian army
iranian navy, iranian military, iranian forces, iranian drone, iranian drones, iranian missile
iranian missiles, iranian oil, iranian crude, iranian economy, iranian rial, iranian nuclear
iranian people, iranian protesters, iranian women, iranian embassy, iranian consulate
iranian ambassador, iranian delegation, iranian negotiators, iranian tanker, iranian tankers
iranian airspace, iranian territory, iranian waters, iranian coast, iranian-backed, iran-backed
iran-linked, iranian-linked, iran-aligned, iran-supported, iran-israel, israel-iran, iran-us
us-iran, iran-saudi, saudi-iran, iran-russia, russia-iran, iran-china, china-iran, iran-europe
iran-e3, iran-iaea, isfahan, esfahan, shiraz, tabriz, mashhad, qom, ahvaz, bandar abbas
kish island, chabahar, bushehr, kharg island, abadan, asaluyeh, south pars, zahedan, kermanshah
urmia, rasht, karaj, arak, natanz, fordow, fordo, parchin, khondab, bonab, saghand, gachin
lavizan, semnan, shahroud, bandar imam khomeini, bandar mahshahr, qeshm, lavan island
sirri island, abu musa, greater tunb, lesser tunb, tunb islands, jask, konarak, khuzestan
sistan and baluchestan, hormozgan, evin prison, ghezel hesar, qezelhesar, tehran stock exchange
imam khomeini airport, azadi tower, pasdaran, sepah, artesh, khatam-al anbia, shahid beheshti
sharif university, tehran university, kharg terminal, jask terminal, goreh-jask pipeline
bandar-e jask, lavan oil terminal, siri island, hengam, kharg, hormuz island, larak island
abadan refinery, bandar abbas refinery, persian gulf star refinery, tabriz refinery
isfahan refinery, tehran refinery, arak refinery, shiraz refinery, lavan refinery
bushehr nuclear plant, bushehr reactor, tehran research reactor, arak heavy water reactor
khondab reactor, isfahan nuclear, natanz enrichment, fordow enrichment, parchin military complex
taleghan 2, shahid meisami, shahid rajaee port, shahid rajaee, chabahar port, imam khomeini port
bandar lengeh, bandar khamir, bandar bushehr, kharg oil terminal, mashhad airport, mehrabad
imam khomeini international airport

## nuclear 2
enrichment, uranium enrichment, enriched uranium, 60% enriched, 60 percent enriched
highly enriched uranium, low-enriched uranium, uranium stockpile, breakout time, breakout capacity
weaponization, weaponisation, nuclear inspectors, nuclear watchdog, nuclear threshold
nuclear fatwa, nuclear breakout, nuclear-armed iran, nuclear iran, iaea, rafael grossi, grossi
iaea board of governors, board of governors, safeguards agreement, comprehensive safeguards
additional protocol, npt withdrawal, withdraw from the npt, jcpoa, snapback, snap-back
snapback sanctions, trigger mechanism, dispute resolution mechanism, resolution 2231, e3
e3 powers, e3 statement, p5+1, centrifuge, centrifuges, ir-6, ir-2m, ir-4, ir-1, cascade, cascades
heavy water, plutonium, plutonium reprocessing, uranium metal, uranium hexafluoride
uranium conversion, yellowcake, uranium mine, uranium mines, fuel enrichment plant
pilot fuel enrichment plant, enrichment plant, enrichment site, undeclared sites
undeclared nuclear material, undeclared nuclear activities, uranium traces, particles of uranium
iaea inspectors, iaea inspection, iaea access, iaea report, iaea quarterly report, iaea resolution
monitoring cameras, surveillance cameras, snap inspections, inspector access, aeoi
atomic energy organization of iran, atomic energy organisation, nuclear negotiator, nuclear file
nuclear dossier, sunset clause, termination day, transition day, implementation day
enrichment cap, 20 percent enrichment, 20% enrichment, 90% enrichment, weapons-grade
weapons grade, bomb-grade, underground nuclear test, underground tunnels, deeply buried
bunker buster, gbu-57, massive ordnance penetrator, mop bomb, b-2 bomber, b-2 bombers
operation midnight hammer, midnight hammer, operation rising lion, rising lion, twelve-day war
12-day war

## nuclear 1
nuclear weapon, nuclear weapons, nuclear bomb, nuclear deal, nuclear talks, nuclear negotiations
nuclear program, nuclear programme, nuclear facility, nuclear facilities, nuclear site
nuclear sites, nuclear agreement, nuclear accord, nuclear scientist, nuclear scientists
nuclear physicist, nuclear doctrine, nuclear armed, nuclear capable
international atomic energy agency, non-proliferation treaty, joint comprehensive plan of action
5+1, censure resolution, nuclear talks in oman, nuclear talks in geneva, nuclear talks in vienna
3.67 percent, 3.67%, dirty bomb, radiological, radioactive, radiation leak, nuclear safety
nuclear accident, nuclear plant, nuclear power plant, nuclear reactor, nuclear fuel, nuclear waste
nuclear test, nuclear tests

## military 2
fattah missile, sejjil, shahab, shahab-3, khorramshahr, emad missile, ghadr, kheibar shekan
zolfaghar, dezful, haj qassem, fateh-110, fateh-313, shahed, shahed-136, shahed-129, shahed drones
mohajer, arash drone, ababil, bavar-373, khordad-15, us central command, centcom, us fifth fleet
fifth fleet, tanker seizure, tanker seized, ship seizure, vessel seized, seized vessel
seized tanker, seized ship, hijacked tanker, hijacked ship, limpet mine, limpet mines, ukmto
operation prosperity guardian, aspides, al udeid, al asad, ain al-asad, tower 22, al-tanf
tanf garrison, nevatim, dimona, iran attack, attack on iran, strike on iran, strikes on iran
strike on iranian, strikes on iranian, martyrdom, martyrs, martyred, funeral of commander
funeral of martyrs, soleimani, qassem soleimani, qasem soleimani, abu mahdi al-muhandis, muhandis

## military 1
missile, missiles, ballistic missile, ballistic missiles, cruise missile, hypersonic missile
kamikaze drone, kamikaze drones, drone strike, drone strikes, drone attack, drone attacks
drone swarm, missile attack, missile attacks, missile launch, missile launches, missile test
missile program, missile programme, missile stockpile, missile arsenal, missile defense
missile defence, air defense, air defence, air defenses, air defences, s-300, s-400, iron dome
david's sling, arrow 3, arrow-3, thaad, patriot battery, patriot missiles, f-35, f-14, f-15, su-35
mig-29, tomcat, radar, air raid, air raids, airstrike, airstrikes, air strike, air strikes
aerial attack, aerial bombardment, bombing, bombardment, shelling, retaliation, retaliatory
retaliate, reprisal, escalation, escalate, de-escalation, ceasefire, cease-fire, truce, armistice
war, wartime, warfare, conflict, proxy war, shadow war, covert war, covert operation
covert operations, sabotage, saboteurs, assassination, assassinated, assassinate, targeted killing
targeted killings, commander killed, general killed, top commander, senior commander
military commander, military leadership, chief of staff, armed forces general staff, joint chiefs
pentagon, us navy, carrier strike group, aircraft carrier, uss gerald ford, uss nimitz
uss abraham lincoln, uss carl vinson, uss eisenhower, uss harry truman, uss vinson, uss cole
destroyer, warship, warships, frigate, submarine, submarines, midget submarine, fast attack craft
fast boats, speedboats, swarm tactics, naval mines, sea mines, mine-laying, minesweeper
minesweepers, coast guard, maritime security, maritime incident, maritime incidents
vessels seized, boarding, boarded, ship attack, ship attacks, vessel attack, vessel attacks
uk maritime trade operations, combined maritime forces, sentinel operation
international maritime security construct, imsc, eunavfor, us bases, us base, us troops, us forces
us personnel, us soldiers killed, service members killed, camp victory, erbil air base, harir base
incirlik, diego garcia, ramon air base, ramat david, negev, tel nof, hatzerim, israeli air force
israeli air strike, israeli airstrike, israeli strike, israeli strikes, israeli attack
israeli attacks, israeli military, israeli army, idf, israel defense forces, israel defence forces
mossad, shin bet, unit 8200, attack on israel, strike on israel, us strike, us strikes, us attack
us airstrikes, us military, us military action, military action, military option, military options
military strike, military strikes, military escalation, military buildup, military build-up
military drills, military exercise, military exercises, naval drills, naval exercise
naval exercises, joint exercise, joint exercises, war games, wargames

## military 1
weapons, arms, arms deal, arms sale, arms sales, arms shipment, arms shipments, arms smuggling
weapons smuggling, weapons shipment, weapons shipments, weapons transfer, weapons transfers
munitions, ammunition, explosives, warhead, warheads, payload, interceptor, interceptors
intercept, intercepted, shot down, shoot down, downed drone, downed aircraft, fighter jet
fighter jets, fighter aircraft, bomber, bombers, stealth, stealth bomber, tanker aircraft
refueling, aerial refueling, surveillance flight, reconnaissance, spy plane, spy drone, spy ship
intelligence sharing, intelligence assessment, intelligence agencies, intelligence officials, cia
mi6, dni, national intelligence

## sanctions 2
iran sanctions, sanctions on iran, sanctions against iran, sanctions snapback, maximum pressure
max pressure, maximum pressure campaign, shadow fleet, dark fleet, ghost fleet
ship-to-ship transfer, ship-to-ship transfers, ship to ship transfer, ais transponder
ais spoofing, unfrozen funds, frozen funds, frozen assets, iranian assets, iranian funds
waiver on iraqi electricity, iraqi electricity waiver, oil waiver, oil waivers, teapot refineries
teapot refinery, shandong refineries, shandong refinery, fatf, fatf blacklist, procurement network
procurement networks, front companies, front company, shell companies, shell company
exchange houses, exchange house, hawala, instex

## sanctions 1
sanctions relief, sanctions waiver, sanctions waivers, secondary sanctions, sanctions evasion
sanctions evaders, sanctions busting, sanctions-busting, turned off transponder, un sanctions
un security council resolution, security council resolution, arms embargo, independent refiners
ofac, office of foreign assets control, treasury sanctions, treasury department sanctions
designation, designations, designated, sdn list, specially designated nationals, blacklist
blacklisted, terrorist designation, foreign terrorist organization, state sponsor of terrorism
state sponsor of terror, terror list, terrorist list, anti-money laundering
counter-terrorism financing, money laundering, illicit finance, illicit oil, illicit oil trade
illicit oil sales, oil smuggling, fuel smuggling, gasoline smuggling, export controls, dual-use
dual use goods, cryptocurrency exchange, crypto exchange, crypto sanctions, swift, swift ban, cips
spv, special purpose vehicle, barter, barter trade, oil for goods, payment channel
payment channels, banking channel, banking channels, humanitarian channel, humanitarian channels
humanitarian exemption, humanitarian exemptions, sanctions exemption, sanctions exemptions
general license, general licence, specific license, delisting, delisted, lifted sanctions
lift sanctions, lifting of sanctions, easing sanctions, sanctions easing, ease sanctions
tighten sanctions, tightening sanctions, new sanctions, fresh sanctions, additional sanctions
sanctions package, sanctions packages, sanctioned entities, sanctioned individuals
sanctioned vessels, sanctioned tankers, sanctioned oil

## sanctions 1
sanctions, sanction, sanctioned, sanctioning, embargo, embargoes, tariff, tariffs, trade war
trade restrictions, trade ban, export ban, import ban, asset freeze, asset freezes, travel ban
visa ban, visa restrictions, visa bans, entry ban, unilateral sanctions, multilateral sanctions
international sanctions, western sanctions, us sanctions, eu sanctions, uk sanctions
un security council, unsc, security council

## oil 2
strait of hormuz, hormuz, hormuz strait, closure of the strait, close the strait
closing the strait, blockade of hormuz, chokepoint, choke point, chokepoints, bab el-mandeb
bab al-mandab, gulf of oman, persian gulf shipping, gulf shipping, shipping lanes, shipping lane
tanker traffic, tanker attack, tanker attacks, war risk premium, war risk insurance
war-risk insurance, red sea shipping, red sea attacks, red sea crisis, oil facilities attack
abqaiq, khurais, ras tanura, fujairah, fujairah port, kharg oil, south pars gas, iran oil exports
iran oil output, iran oil production, iran crude exports, iran crude, iran oil, iran gas
iran gas exports, iran lng, iran petrochemical, iran petrochemicals, iran refinery
iran refineries, iranian gas, iranian lng, iranian petrochemicals, iranian refineries
national iranian oil company, nioc, national iranian gas company, nigc
national iranian tanker company, nitc, irisl, islamic republic of iran shipping lines
national petrochemical company, iranian offshore oil company, iranian oil ministry
iranian oil minister, javad owji, mohsen paknejad, paknejad, owji

## oil 1
blockade, naval blockade, bab-el-mandeb, gulf of aden, arabian sea, insurance premiums, sohar
duqm, jebel ali, ras laffan, north dome, oil ministry, oil minister

## oil 1
oil price, oil prices, crude oil, crude prices, crude futures, brent, brent crude, wti
west texas intermediate, opec, opec+, opec plus, oil exports, oil export, oil production
oil output, oil supply, oil supplies, oil market, oil markets, oil demand, oil inventories
oil stockpiles, strategic petroleum reserve, spr, oil tanker, oil tankers, tanker, tankers
supertanker, supertankers, vlcc, lng, liquefied natural gas, lng tanker, lng tankers, natural gas
gas prices, gas exports, gas pipeline, pipeline, pipelines, refinery, refineries, petrochemical
petrochemicals, energy crisis, energy security, energy prices, energy market, energy markets
energy infrastructure, energy facilities, oil facilities, oil infrastructure, oil field
oil fields, oilfield, oilfields, gas field, gas fields, offshore platform, offshore platforms
oil platform, oil platforms, oil terminal, oil terminals, oil refinery, oil depot, oil depots
fuel depot, fuel depots, gasoline, diesel, jet fuel, fuel prices, fuel shortage, fuel shortages
fuel subsidy, fuel subsidies, fuel rationing, gasoline rationing, petrol prices, petrol shortage
power outage, power outages, blackout, blackouts, rolling blackouts, electricity shortage
electricity shortages, electricity imports, power shortage, power shortages, power grid
gas shortage, gas shortages, energy shortage, energy shortages, shipping insurance, freight rates
tanker rates, shipping costs, container shipping, supply chain, supply chains, global supply chain
commodity prices, commodities, safe haven, safe-haven, gold price, gold prices, gold rally
dollar index, dollar strength, risk premium, geopolitical risk, geopolitical tension
geopolitical tensions, market volatility, stock markets, stock market, equities, bond yields
treasury yields, inflation fears, recession fears, energy stocks, defense stocks, defence stocks

## economy 3
toman, tomans, iranian rial, rial exchange rate, rial devaluation, rial record low, rial plunge
rial plummets, tehran stock, tehran bourse, tehran securities exchange, iran fara bourse
central bank of iran, cbi governor, bank melli, bank mellat, bank saderat, bank sepah
bank tejarat, bank refah, bank keshavarzi, parsian bank, pasargad bank, post bank of iran
ayandeh bank, karafarin bank, iran khodro, ikco, saipa, pars khodro, bahman group, kerman motor
iran air, mahan air, iran aseman, aseman airlines, qeshm air, iran airtour, iran airports company
ports and maritime organization, iran railways, tehran metro, mapna, iranian aluminium
mobarakeh steel, esfahan steel, khuzestan steel, sarcheshmeh, national iranian copper
national iranian steel, iran mining, imidro, iranian mines, kish free zone, qeshm free zone
chabahar free zone, arvand free zone, bonyad mostazafan, mostazafan foundation, astan quds razavi
setad, execution of imam khomeini's order, eiko, imam khomeini relief foundation
khatam al-anbia construction headquarters, khatam al-anbiya construction headquarters
iranian privatization, iran privatization, iran budget, iran inflation, iran unemployment
iran gdp, iran economy, iran currency, iran currency crisis, iran banking, iran bank

## economy 1
special economic zone, special economic zones

## economy 2
rial, rial falls, rial drops, rial slump, rial slides, dollar rate in tehran, free market rate
emami coin, import ban iran, north-south corridor, north south transport corridor
international north-south transport corridor, instc, rasht-astara railway, rasht-astara, astara
chabahar-zahedan railway, zahedan railway, gwadar, gwadar port, 25-year agreement
25-year cooperation agreement, china-iran agreement, china iran deal, russia-iran treaty
shanghai cooperation organisation, shanghai cooperation organization, brics summit
brics membership, brics expansion, eurasian economic union
free trade agreement with eurasian economic union, gas swap, gas swap deal, iraq gas debt
iraq electricity debt, iraqi debt, iraqi funds, iraq dollar auction, dollar smuggling iraq
lake urmia, urmia lake, zayandeh rud, zayandeh-rud

## economy 1
open market rate, currency crisis, currency collapse, currency devaluation, hyperinflation
stagflation, capital flight, gold coins, gold coin, bitcoin mining ban, crypto mining ban
illegal crypto mining, cryptocurrency mining, foreign currency reserves, foreign exchange reserves
forex reserves, foreign reserves, external reserves, budget deficit, fiscal deficit
government debt, public debt, subsidy reform, subsidy cuts, price hikes, price hike, bread prices
food prices, food inflation, food shortages, medicine shortages, drug shortages, medicine prices
import restrictions, export earnings, non-oil exports, non-oil trade, trade with china
trade with russia, trade with iraq, trade with turkey, trade with india, trade with uae
trade with pakistan, trade with afghanistan, barter with russia, belt and road
belt and road initiative, comprehensive strategic partnership, strategic partnership treaty
sco summit, eaeu, gas pipeline to turkey, gas exports to turkey, gas exports to iraq
iraqi dollar restrictions, water crisis, water shortage, water shortages, water scarcity
water stress, drought, severe drought, land subsidence, subsidence, sinking land, dust storms
sandstorms, air pollution, air pollution in tehran, toxic smog, smog, heatwave, heat wave
extreme heat, office closures, government offices closed, dams, dam levels, reservoirs
groundwater, aquifers

## region 2
hezbollah, hizballah, hizbullah, hezbollah leader, hezbollah commander, hezbollah chief
hezbollah secretary-general, houthis, houthi, houthi rebels, houthi attack, houthi attacks
houthi missile, houthi drone, ansar allah, ansarullah, kataib hezbollah, kata'ib hezbollah
kataib sayyid al-shuhada, nujaba, harakat al-nujaba, badr organization, asaib ahl al-haq
popular mobilization forces, popular mobilisation forces, popular mobilization units, pmf
hashd al-shaabi, hashd, iraqi militias, iraqi militia, iran-backed militias, iran-backed militia
iran-backed groups, iran-backed group, iran-aligned militias, iran-aligned groups
axis of resistance, resistance axis, palestinian islamic jihad, islamic jihad
islamic resistance in iraq, fatemiyoun, fatemiyoun brigade, zainabiyoun, zainabiyoun brigade
liwa fatemiyoun, liwa zainabiyoun, jaish al-adl, jaish ul-adl, jundallah, baluch militants
baluch insurgents, baloch militants, baloch insurgents, pjak, pdki, komala, kurdish militants
kurdish groups, kurdish opposition, kurdish fighters, iranian kurdish, iranian kurdistan, mek
mujahedin-e khalq, mujahedin-e-khalq, mujahedeen khalq, mko, pmoi, ncri
national council of resistance of iran, maryam rajavi, ashraf 3, camp ashraf, reza pahlavi
crown prince reza pahlavi, pahlavi, prince reza pahlavi, iranian opposition, iranian exiles
iranian diaspora, opposition in exile, monarchists, regime collapse, regime's collapse
regime survival, regime stability, post-khamenei, after khamenei, khamenei's death
khamenei's health, khamenei's successor, khamenei successor, successor to khamenei
mojtaba khamenei, saudi-iran rapprochement, saudi-iranian, saudi iran talks, saudi-iran talks
beijing-brokered, china-brokered, iran-saudi deal, iran-saudi agreement, iran-gcc, iran-iraq
iran-turkey, iran-pakistan, iran-afghanistan, iran-azerbaijan, iran-armenia, iran-uae, iran-oman
iran-qatar, iran-kuwait, iran-bahrain, iran-egypt, iran-syria, iran-lebanon, iran-yemen
iran-india, iran-japan, iran-south korea, iran-venezuela, iran-north korea, iran-belarus, iran-eu
iran-nato, three islands dispute, disputed islands, zangezur corridor, zangezur, syunik
trump route for international peace and prosperity, trips corridor

## region 1
iraqi kurdistan, kurdistan regional government, krg, kurdistan region, regime change
transition of power, power transition, gulf states, gulf arab states, gulf cooperation council
gcc, arab league, arab summit, organisation of islamic cooperation
organization of islamic cooperation, oic, oic summit, islamic summit, abraham accords
normalization with israel, normalisation with israel, israel-saudi normalization
israel saudi normalization, saudi normalization, saudi-israel, saudi israel normalization
armenia azerbaijan peace, south caucasus, caucasus corridor

## region 1
israel, israeli, israelis, netanyahu, benjamin netanyahu, gallant, yoav gallant, israel katz
herzi halevi, eyal zamir, ben-gvir, smotrich, knesset, jerusalem, tel aviv, haifa, eilat, golan
golan heights, west bank, gaza, gaza strip, gaza war, gaza ceasefire, hostage deal, hostages
hamas, hamas leader, hamas chief, sinwar, haniyeh, ismail haniyeh, yahya sinwar, khaled meshaal
lebanon, lebanese, beirut, southern lebanon, litani, litani river, unifil, lebanese army
nasrallah, hassan nasrallah, naim qassem, hashem safieddine, syria, syrian, damascus, aleppo
idlib, assad, bashar al-assad, al-assad, hts, hayat tahrir al-sham, jolani, al-sharaa
ahmed al-sharaa, syrian army, syrian regime, fall of assad, post-assad, sdf
syrian democratic forces, deir ez-zor, deir ezzor, albukamal, abu kamal, palmyra, yemen, yemeni
sanaa, sana'a, hodeidah, hodeida, aden, marib, red sea, iraq, iraqi, baghdad, erbil, basra, mosul
kirkuk, najaf, karbala, sadr, muqtada al-sadr, sistani, al-sudani, sudani, iraqi prime minister
iraqi government, iraqi parliament, iraqi elections, afghanistan, afghan, kabul, taliban
taliban government, taliban regime, isis-k, isis-khorasan, islamic state, isis, daesh, al-qaeda
al qaeda, pakistan, pakistani, islamabad, balochistan, baluchistan, karachi, saudi arabia, saudi
riyadh, jeddah, mbs, mohammed bin salman, crown prince mohammed bin salman, uae, emirati
abu dhabi, dubai, qatar, qatari, doha, oman, omani, muscat, kuwait, kuwaiti, bahrain, bahraini
manama, egypt, egyptian, cairo, jordan, jordanian, amman, turkey, turkish, ankara, erdogan
istanbul, azerbaijan, azerbaijani, baku, aliyev, armenia, armenian, yerevan, pashinyan, russia
russian, moscow, putin, kremlin, lavrov, ukraine war, china, chinese, beijing, xi jinping, wang yi
india, indian, new delhi, modi, north korea, pyongyang, kim jong un, venezuela, maduro, cuba
belarus, lukashenko

## diplomacy 1
talks, negotiations, negotiator, negotiators, envoy, special envoy, witkoff, steve witkoff
indirect talks, direct talks, indirect negotiations, direct negotiations, muscat talks
oman mediation, omani mediation, mediation, mediator, mediators, geneva talks, vienna talks
doha talks, rome talks, istanbul talks, oslo talks, back channel, backchannel, back-channel
secret talks, secret negotiations, ultimatum, deadline, red line, red lines, diplomatic solution
diplomatic path, diplomatic push, diplomacy, diplomatic, diplomats, diplomat, ambassador
ambassadors, embassy, consulate, expelled diplomats, expel diplomats, expulsion of diplomats
recall ambassador, recalled ambassador, summoned ambassador, summon ambassador, cut ties
sever ties, severed ties, restore ties, restored ties, restoring ties, normalize relations
normalise relations, un general assembly, unga, un secretary-general, guterres, antonio guterres
un security council meeting, emergency meeting, emergency session, un human rights council
special rapporteur, un special rapporteur, un fact-finding mission, un investigators, un experts
un report, un resolution, joint statement, joint communique, communique, statement of condemnation
condemned, condemns, condemnation, warns, warned, warning, threatens, threatened, threat, threats
vows, vowed, pledges, pledged, promises, demands, demanded, urges, urged, calls on, called on
prisoner swap, prisoner exchange, hostage swap, hostage release, released prisoners
released detainees, detained, detainee, detainees, dual national, dual nationals, dual-national
dual-nationals, wrongfully detained, arbitrarily detained, arbitrary detention, travel warning
travel advisory, do not travel, evacuation, evacuate, evacuated, evacuees, airlift
flights suspended, flights canceled, flights cancelled, airspace closed, airspace closure
airspace reopened, no-fly zone, no fly zone

## politics 2
majlis election, majlis elections, reform front, principlists, principlist, ultraconservatives
ultra-conservatives, paydari, paydari front, jebhe paydari, stability front
front of islamic revolution stability, endurance front, successor to the supreme leader
supreme leader succession, leader's health, leader's succession, supreme leader's office
office of the supreme leader, supreme leader's representative, friday prayer leader
friday prayers, friday prayer, imam of friday prayers, seminary, seminaries, qom seminary, hawza
marja, marjaa, marja'iyya, wilayat al-faqih, velayat-e faqih, velayat-e-faqih
guardianship of the jurist, islamic revolution anniversary, revolution anniversary, 22 bahman
22nd of bahman, quds day, quds day rally, al-quds day, ghadir, arbaeen, arbaeen pilgrimage
hajj quota, imam reza shrine, imam reza, fatima masumeh shrine, jamkaran, jamkaran mosque
iran impeachment, majlis speaker, foreign minister of iran, guards commander, irgc commander
irgc chief, irgc general, irgc spokesman, basij commander, quds force commander, naja, faraja
morality police, guidance patrol, gasht-e ershad, gasht e ershad

## politics 1
presidential election, presidential elections, presidential candidate, presidential candidates
parliamentary election, parliamentary elections, voter turnout, low turnout, election boycott
boycott of the election, disqualified candidates, disqualification of candidates
vetting of candidates, hardliners, hardliner, hard-liners, hardline, hard-line, reformists
reformist, reformist camp, moderates, moderate camp, conservative camp, pragmatists, pragmatist
succession crisis, leadership succession, grand ayatollah, grand ayatollahs, clerics, cleric
clerical establishment, shia clerics, shiite clerics, shi'ite clerics, muharram, ashura
hajj pilgrims, umrah, pilgrims, pilgrimage, mahdi, imam mahdi, twelfth imam
impeachment of minister, impeachment motion, impeachment of the minister, no-confidence vote
vote of confidence, confidence vote, cabinet reshuffle, cabinet nominees, cabinet nominee
cabinet ministers, cabinet minister, first vice president, vice president, vice presidents
speaker of parliament, parliament speaker, judiciary chief, head of the judiciary, chief justice
judiciary spokesman, government spokesperson, government spokeswoman, government spokesman
foreign ministry spokesman, foreign ministry spokesperson, intelligence minister
interior minister, defense minister, defence minister, economy minister, oil minister
foreign minister, central bank governor, army commander, army chief, navy commander
air force commander, aerospace force commander, chief of general staff, chief of the general staff
armed forces chief, armed forces spokesman, armed forces general staff, police chief
police commander, law enforcement commander, cyber police, fata

## politics 1
election, elections, voters, ballot, ballots, polls, polling, turnout, candidate, candidates
campaign, campaigning, cabinet, minister, ministers, parliament, lawmakers, lawmaker, legislature
legislation, bill, bills, law, laws, decree, decrees, judiciary, courts, court, trial, trials
sentence, sentenced, verdict, verdicts, appeal, appeals, indictment, indicted, charges, charged
arrest, arrested, arrests, detention, detentions, detained, released, pardon, pardoned, amnesty
clemency, resignation, resigned, resigns, dismissed, dismissal, sacked, appointed, appointment
nominated, nomination, replaced, replacement, succeed, succession, successor, coup, coup attempt
martial law, state of emergency, curfew, unrest, instability, stability, crisis, crises
political crisis, government crisis, political prisoners, political detainees

## rights 2
national information network, halal internet, blocked instagram, blocked whatsapp
blocked telegram, blocked google, hijab, mandatory hijab, hijab law, hijab bill
chastity and hijab law, hijab and chastity law, hijab enforcement, compulsory hijab
morality police, guidance patrols, mahsa amini, jina amini, woman life freedom, women life freedom
zan zendegi azadi, mahsa, narges mohammadi, nasrin sotoudeh, shirin ebadi, masih alinejad
jamshid sharmahd, ahmadreza djalali, evin, evin prison, gohardasht, rajaee shahr
ghezel hesar prison, qarchak, qarchak prison, revolutionary court, revolutionary courts
special clerical court, iran human rights, iran human rights ngo, hengaw, hrana
human rights activists news agency, center for human rights in iran
un fact-finding mission on iran, fact-finding mission on iran, un special rapporteur on iran
javaid rehman, mai sato, gonabadi, ahwazi arabs, ahwazi, afghan refugees, afghan migrants
afghans in iran, afghan deportations, deportation of afghans, schoolgirls poisoning
school poisonings, poisoning of schoolgirls, girls' schools poisoning, toomaj salehi, toomaj
jafar panahi, mohammad rasoulof, rasoulof, panahi, tehran book fair

## rights 1
protests, protest, protesters, protester, demonstrations, demonstrators, unrest, uprising
uprisings, riot, riots, rioters, crackdown, crackdowns, security forces, riot police, tear gas
live ammunition, live fire, rubber bullets, birdshot, pellets, shot dead, killed protesters
protesters killed, protester killed, death toll, protest death toll, internet shutdown
internet blackout, internet restrictions, internet disruption, internet disruptions
internet throttling, national internet, filtering, internet filtering, censorship, vpn, vpns
blocked websites, blocked apps, blocked platforms, social media ban, social media blocked
social media restrictions, executions, execution, executed, hanged, hanging, hangings
public execution, public executions, death penalty, death sentence, death sentences
sentenced to death, death row, death row inmates, political prisoners, prisoner of conscience
prisoners of conscience, nobel peace prize, nobel peace laureate, hunger strike, hunger strikes
prison conditions, prison abuse, torture, tortured, forced confession, forced confessions
televised confessions, coerced confessions, fair trial, unfair trial, unfair trials
journalist arrested, arrested journalists, journalists arrested, journalist jailed
jailed journalists, press freedom, freedom of the press, freedom of expression, human rights
human rights watch, hrw, amnesty international, ethnic minorities, religious minorities, baha'i
bahai, baha'is, bahais, christian converts, christians arrested, sufi, sufis, dervishes, kurds
kurdish, baluch, baloch, azeri, azeris, turkmen, lur, lurs, deportations, refugees, asylum seekers
migrants, illegal migrants, women's rights, women's protests, girls schools, women drivers
women athletes, women in stadiums, women banned, female athletes, female singers, female singer
concert ban, concert banned, musicians arrested, rapper, rapper sentenced, artists arrested
filmmaker arrested, filmmakers arrested, oscar, cannes, cannes film festival, film festival
banned film, banned films, banned books, book ban, book fair

## rights 1
activists, activist, dissidents, dissident, opposition, opposition figures, opposition leaders
opponents, critics, critic, lawyers, lawyer, human rights lawyer, human rights lawyers, students
university students, student protests, student unrest, strikes, strike, strikers, labor strikes
labour strikes, labor protests, labour protests, truckers strike, truckers' strike, bazaar strike
bazaar strikes, bazaar merchants, bazaaris, merchants strike, shopkeepers strike, teachers protest
teachers' protests, retirees protest, pensioners protest, pensioners' protest, nurses protest
oil workers strike, oil workers' strike, petrochemical workers strike, steelworkers protest
farmers protest, farmers' protests, water protests, electricity protests, power cuts protests
gasoline protests, fuel protests, bread protests, inflation protests, economic protests
cost of living protests, cost-of-living protests, price protests

## tech 2
predatory sparrow, gonjeshke darande, stuxnet, flame malware, duqu, apt33, apt34, apt35, apt42
charming kitten, phosphorus, mint sandstorm, oilrig, muddywater, cyber av3ngers, cyberav3ngers
handala, handala hack, homeland justice, cotton sandstorm, emennet pasargad, emennet
bank sepah hack, nobitex, nobitex hack, simorgh, safir, qaem-100, qaem 100, qased, noor satellite
noor-3, khayyam satellite, khayyam, kowsar, hodhod, nahid satellite, zafar satellite, pars-1
chamran, fajr satellite, iranian space agency, russian launch, soyuz launch, starlink in iran
hijab surveillance, nazer app, nazer, drones to russia, missiles to russia, russian shahed
geran-2, geran 2, alabuga, alabuga plant, ballistic missile transfer, ballistic missiles to russia
fateh-360, fath-360

## tech 1
cyberattack, cyber attack, cyberattacks, cyber attacks, cyber warfare, cyber war, cyber operation
cyber operations, cyber espionage, cyber threat, cyber threats, hack, hacked, hackers, hacking
hacktivist, hacktivists, hacker group, hacking group, malware, ransomware, wiper, wiper malware
data breach, data leak, leaked documents, leaked data, leaked emails, leaked files, cyber command
uscybercom, cisa, cisa warning, cisa advisory, fbi warning, fbi advisory, critical infrastructure
critical infrastructure attack, scada, plc, industrial control systems, water utilities
water systems hack, fuel station hack, gas station hack, fuel stations cyberattack
banking cyberattack, bank hack, exchange hack, crypto exchange hack, satellite launch
satellite launches, space launch, space launches, space program, space programme, space agency
spy satellite, reconnaissance satellite, military satellite, military satellites, gps jamming
gps spoofing, gnss jamming, gnss spoofing, electronic warfare, jamming, radar jamming
communications jamming, starlink, starlink terminals, starlink smuggling, satellite internet
direct-to-cell, artificial intelligence, ai chips, nvidia chips, chip smuggling, semiconductor
semiconductors, surveillance technology, facial recognition, face recognition
surveillance cameras hijab, smart surveillance, drone technology, drone production, drone factory
drone factories, drone transfer, drone transfers to russia, russian drone plant

## trade 1
teapot, oil to china, china oil imports, chinese oil imports, chinese imports of iranian oil
iranian oil to china, china's oil imports, indian oil imports, india oil imports
india's oil imports, turkish oil imports, korean oil imports, japan oil imports, oil discount
oil discounts, discounted oil, discounted crude, russian oil, russian oil price cap, oil price cap
price cap, g7 price cap, eu oil embargo, russia oil embargo, urals, urals crude, espo, espo crude
iranian light, iranian heavy, iran light, iran heavy, basrah, basrah crude, basrah medium
kurdish oil, kurdistan oil, kurdistan oil exports, iraq-turkey pipeline, ceyhan, ceyhan port
kirkuk-ceyhan, kirkuk ceyhan pipeline, iraqi oil exports, iraq oil exports, saudi oil exports
saudi oil production, saudi production cut, opec+ cut, opec+ cuts, opec+ output, opec+ meeting
opec meeting, opec output, opec production, opec cut, opec cuts, opec supply, opec demand, iea
international energy agency, iea report, iea oil market report, opec monthly report, eia
energy information administration, eia report, eia weekly, api inventories, baker hughes
rig count, us shale, shale production, shale output, us crude exports, us crude production
us production record, us gasoline prices, us gas prices, gas prices at the pump, aaa gas prices
national average gas price, trump gas prices, trump oil prices, drill baby drill, energy dominance
energy independence
"""

# ---------------------------------------------------------------------
# 3) Iranian officials (past + present, English spellings).
#    Comma separated. A leading "~" = ambiguous surname (weak, weight 1).
# ---------------------------------------------------------------------
OFFICIALS = """
ali khamenei, ayatollah ali khamenei, ayatollah khamenei, mojtaba khamenei, masoud pezeshkian, pezeshkian, abbas araghchi, araghchi, araqchi, mohammad javad zarif, javad zarif, zarif, hassan rouhani, rouhani, ebrahim raisi, raisi, mohammad bagher ghalibaf, mohammad baqer qalibaf, ghalibaf, qalibaf, ali larijani, larijani, sadegh larijani, sadeq amoli larijani, mohammad javad larijani, gholamhossein mohseni-ejei, mohseni-ejei, mohseni ejei, mohseni-eje'i, esmaeil baghaei, esmail baghaei, baghaei, baqaei, kazem gharibabadi, gharibabadi, majid takht-ravanchi, takht-ravanchi, takht ravanchi, mohammad eslami, ali akbar salehi, ali shamkhani, shamkhani, saeed jalili, jalili, ahmad vahidi, esmail qaani, esmail ghaani, esmail qa'ani, qaani, ghaani, hossein salami, mohammad bagheri, mohammad hossein bagheri, amir ali hajizadeh, hajizadeh, abdolrahim mousavi, amir hatami, mohammad pakpour, pakpour, ali abdollahi, gholam ali rashid, abolfazl shekarchi, hossein dehghan, yahya rahim safavi, rahim safavi, mohsen rezaei, ali akbar velayati, velayati, mohammad mokhber, mokhber, mohammad reza aref, abdolnaser hemmati, hemmati, masoumeh ebtekar, ebtekar, mohammad khatami, ahmadinejad, mahmoud ahmadinejad, mir hossein mousavi, mehdi karroubi, karroubi, ali bagheri kani, bagheri kani, hossein amir-abdollahian, amir-abdollahian, amirabdollahian, behrouz kamalvandi, kamalvandi, ali akbar ahmadian, amir saeid iravani, iravani, majid takht ravanchi, alireza tangsiri, tangsiri, ali fadavi, mohammad ali jafari, hossein taeb, esmail khatib, mahmoud alavi, ezzatollah zarghami, zarghami, kamal kharrazi, kharrazi, hossein shariatmadari, shariatmadari, ahmad alamolhoda, alamolhoda, ahmad khatami, alireza arafi, mohammad mohammadi golpayegani, golpayegani, sadegh amoli larijani, hossein nejat, mohammad reza naqdi, naqdi, ebrahim zolghadr, zolghadr, mohammad kowsari, mohsen paknejad, javad owji, farzaneh sadegh, farzaneh sadegh, abbas akhoundi, akhoundi, mohammad atabak, mohammad reza farzin, farzin, ali asghar hejazi, hejazi, seyed ali khamenei, sayyid ali khamenei, sayyed ali khamenei, khamenei's office, mohammad mehdi esmaili, esmaili, hojatoleslam, hojatoleslam raisi, hojjatoleslam, ali motahari, motahari, ali akbar nategh-nouri, nategh-nouri, hassan khomeini, hassan khomeini, ahmad khomeini, ruhollah khomeini, ayatollah khomeini, imam khomeini, khomeini, akbar hashemi rafsanjani, rafsanjani, hashemi rafsanjani, mohsen hashemi, faezeh hashemi, hossein mousavian, seyed hossein mousavian, mohammad marandi, marandi, nasser kanaani, kanaani, nasser kanani, kanani, hossein jaberi ansari, jaberi ansari, sayyid abbas araghchi, mohammad hossein tehrani, amir saeed iravani, iravani mission, hamid abutalebi, abutalebi, ali rabiei, rabiei, ali bahadori jahromi, bahadori jahromi, fatemeh mohajerani, mohajerani, mehdi sanaei, sanaei, reza salehi amiri, salehi amiri, hamid nouri, ahmad zeidabadi, zeidabadi, mostafa tajzadeh, tajzadeh, mohammad nourizad, nourizad, mohammad javad azari jahromi, azari jahromi, ~mousavi, ~salami, ~vahidi, ~bagheri, ~salehi, ~aref, ~eslami, ~najafi, ~rezaei, ~hosseini, ~ahmadi, ~jafari, ~karimi, ~rahimi
"""

# ---------------------------------------------------------------------
# 4) Iranian organizations, companies, media, ministries.
# ---------------------------------------------------------------------
ORGANIZATIONS = """
atomic energy organization of iran, aeoi, organization of defensive innovation and research, spnd, iranian space agency, iran electronics industries, defense industries organization, defence industries organization, shahid hemmat industrial group, shahid bakeri industrial group, shahid bagheri industrial group, hesa, iran aircraft manufacturing industrial company, aerospace industries organization, iran aviation industries organization, sanam industrial group, shiraz electronics industries, iran communication industries, mindex, iran helicopter support, panha, ministry of intelligence, mois, vevak, vaja, ministry of defense and armed forces logistics, modafl, iranian ministry of defense, iranian defense ministry, iranian interior ministry, iranian oil ministry, iranian economy ministry, iranian energy ministry, iranian roads ministry, iranian health ministry, iranian culture ministry, iranian ministry of culture and islamic guidance, ministry of culture and islamic guidance, ministry of guidance, iranian judiciary, judiciary of iran, iranian courts, revolutionary court, special court for the clergy, iran's supreme court, iran supreme court, general inspection organization, general inspectorate, prosecutor general, tehran prosecutor, tehran's prosecutor, tehran public prosecutor, sepah pasdaran, khatam al-anbiya central headquarters, khatam al-anbia central headquarters, irgc ground forces, irgc aerospace force, irgc navy, irgc intelligence organization, irgc intelligence, irgc cyber, irgc cooperative foundation, irgc cooperative, sepah cooperative foundation, basij organization, basij resistance force, basij force, iranian law enforcement, law enforcement command of iran, faraja, naja, iran's cyber police, cyber police, iran's police, islamic republic of iran broadcasting, irib, press tv, presstv, hispantv, al-alam, al alam, sahar tv, irna, islamic republic news agency, fars news, fars news agency, tasnim, tasnim news, mehr news, mehr news agency, isna, iranian students news agency, ilna, mizan, mizan news, kayhan, javan, javan newspaper, hamshahri, etemad, shargh, sazandegi, ham-mihan, hammihan, tehran times, iran daily, iran news agency, iran international, iran international news, iranwire, radio farda, manoto, bbc persian, voice of america persian, iran international tv, iran international network, ilam, iran press, iran front page, khabar online, khabaronline, entekhab, entekhab news, tabnak, jahan news, mashregh, mashregh news, raja news, asr iran, asriran, nour news, nournews, aftab news, didban iran, didbaniran, fararu, ecoiran, eghtesad news, donya-e-eqtesad, donya e eqtesad, tejarat news, bourse news, rokna, ana, ana news, tehran chamber of commerce, iran chamber of commerce, chamber of commerce industries mines and agriculture, iran chamber, iran export promotion, trade promotion organization of iran, tpo, iran customs, iranian customs administration, customs administration of iran, iran tax, iranian tax affairs organization, tax affairs organization, national tax administration, social security organization, sso, iran social security, retirement fund, pension fund, civil servants pension, iran insurance, iran insurance company, bimeh iran, asia insurance, alborz insurance, dana insurance, iran's insurance, central insurance of iran, capital market, securities and exchange organization, seo, sepah bank, sepah investment, tose'e, tosee, tose'e saderat, export development bank of iran, edbi, bank of industry and mine, boim, agricultural bank, bank keshavarzi, maskan bank, bank maskan, refah bank, ansar bank, mehr iran bank, mehr eqtesad, gharzolhasaneh mehr iran, gharzolhasane, karafarin, sina bank, shahr bank, dey bank, saman bank, sarmayeh bank, iran zamin bank, middle east bank, tourism bank, hekmat iranian bank, day bank, iran venezuela bank, iran-venezuela bank, europaisch-iranische handelsbank, eihb, bank melli iran, bank melli iran zurich, bank saderat iran, bank saderat plc, bank mellat, persia international bank, ir trade, iranian trade, iran trade, iran export, iran import, iranian exports, iranian imports
"""

# ---------------------------------------------------------------------
# 5) Glossary: fixed Persian spelling for names/terms, applied around the
#    free translator so names are never mangled.  "English => Persian".
# ---------------------------------------------------------------------
GLOSSARY = """
Islamic Revolutionary Guard Corps => سپاه پاسداران انقلاب اسلامی
Revolutionary Guard Corps => سپاه پاسداران
Revolutionary Guards => سپاه پاسداران
Revolutionary Guard => سپاه پاسداران
IRGC => سپاه پاسداران
Quds Force => نیروی قدس
Basij => بسیج
Supreme Leader => رهبر جمهوری اسلامی
Islamic Republic of Iran => جمهوری اسلامی ایران
Islamic Republic => جمهوری اسلامی
Persian Gulf => خلیج فارس
Strait of Hormuz => تنگه هرمز
Hormuz => هرمز
Gulf of Oman => دریای عمان
Caspian Sea => دریای خزر
Guardian Council => شورای نگهبان
Assembly of Experts => مجلس خبرگان رهبری
Expediency Council => مجمع تشخیص مصلحت نظام
Supreme National Security Council => شورای عالی امنیت ملی
Majlis => مجلس شورای اسلامی
Atomic Energy Organization of Iran => سازمان انرژی اتمی ایران
International Atomic Energy Agency => آژانس بین‌المللی انرژی اتمی
IAEA => آژانس بین‌المللی انرژی اتمی
JCPOA => برجام
snapback => مکانیسم ماشه
snap-back => مکانیسم ماشه
National Iranian Oil Company => شرکت ملی نفت ایران
Central Bank of Iran => بانک مرکزی ایران
Tehran Stock Exchange => بورس تهران
Bank Melli => بانک ملی
Bank Saderat => بانک صادرات
Bank Mellat => بانک ملت
Bank Sepah => بانک سپه
Iran Khodro => ایران‌خودرو
Saipa => سایپا
Mahan Air => ماهان‌ایر
Iran Air => ایران‌ایر
Press TV => پرس‌تی‌وی
IRNA => ایرنا
Tasnim => تسنیم
Fars News => فارس
Hezbollah => حزب‌الله
Hamas => حماس
Houthis => حوثی‌ها
Houthi => حوثی
Kataib Hezbollah => کتائب حزب‌الله
Palestinian Islamic Jihad => جهاد اسلامی فلسطین
Popular Mobilization Forces => حشد الشعبی
Axis of Resistance => محور مقاومت
Natanz => نطنز
Fordow => فردو
Fordo => فردو
Isfahan => اصفهان
Esfahan => اصفهان
Bushehr => بوشهر
Parchin => پارچین
Arak => اراک
Khondab => خنداب
Bandar Abbas => بندرعباس
Kharg Island => جزیره خارک
Chabahar => چابهار
Kish Island => جزیره کیش
Qeshm => قشم
Abu Musa => ابوموسی
South Pars => پارس جنوبی
Asaluyeh => عسلویه
Tehran => تهران
Tabriz => تبریز
Mashhad => مشهد
Shiraz => شیراز
Qom => قم
Ahvaz => اهواز
Khuzestan => خوزستان
Sistan and Baluchestan => سیستان و بلوچستان
Evin Prison => زندان اوین
Mojtaba Khamenei => مجتبی خامنه‌ای
Ali Khamenei => علی خامنه‌ای
Khamenei => خامنه‌ای
Masoud Pezeshkian => مسعود پزشکیان
Pezeshkian => پزشکیان
Abbas Araghchi => عباس عراقچی
Araghchi => عراقچی
Araqchi => عراقچی
Mohammad Javad Zarif => محمدجواد ظریف
Zarif => ظریف
Hassan Rouhani => حسن روحانی
Rouhani => روحانی
Ebrahim Raisi => ابراهیم رئیسی
Raisi => رئیسی
Mohammad Bagher Ghalibaf => محمدباقر قالیباف
Ghalibaf => قالیباف
Qalibaf => قالیباف
Ali Larijani => علی لاریجانی
Larijani => لاریجانی
Mohseni-Ejei => محسنی‌اژه‌ای
Esmaeil Baghaei => اسماعیل بقایی
Baghaei => بقایی
Kazem Gharibabadi => کاظم غریب‌آبادی
Gharibabadi => غریب‌آبادی
Takht-Ravanchi => تخت‌روانچی
Ali Shamkhani => علی شمخانی
Shamkhani => شمخانی
Saeed Jalili => سعید جلیلی
Esmail Qaani => اسماعیل قاآنی
Qaani => قاآنی
Hossein Salami => حسین سلامی
Ahmad Vahidi => احمد وحیدی
Mohammad Eslami => محمد اسلامی
Mohammad Mokhber => محمد مخبر
Mokhber => مخبر
Mohammad Reza Aref => محمدرضا عارف
Ali Akbar Velayati => علی‌اکبر ولایتی
Velayati => ولایتی
Ahmadinejad => احمدی‌نژاد
Reza Pahlavi => رضا پهلوی
Narges Mohammadi => نرگس محمدی
Masih Alinejad => مسیح علی‌نژاد
Mahsa Amini => مهسا امینی
Qassem Soleimani => قاسم سلیمانی
Qasem Soleimani => قاسم سلیمانی
Soleimani => سلیمانی
Rafael Grossi => رافائل گروسی
Grossi => گروسی
Steve Witkoff => استیو ویتکاف
Witkoff => ویتکاف
Donald Trump => دونالد ترامپ
Trump => ترامپ
Benjamin Netanyahu => بنیامین نتانیاهو
Netanyahu => نتانیاهو
Israel Defense Forces => ارتش اسرائیل
IDF => ارتش اسرائیل
Mossad => موساد
CENTCOM => سنتکام
OFAC => اوفک (اداره کنترل دارایی‌های خارجی آمریکا)
OPEC+ => اوپک‌پلاس
OPEC => اوپک
FATF => گروه ویژه اقدام مالی (FATF)
BRICS => بریکس
Toman => تومان
"""
