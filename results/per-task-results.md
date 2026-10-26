# Result of every task, run by run

One table per published run, newest first. Each row is copied from that run's report (linked above each table). **Steps** are the agent's turns; **time** is the agent's working time on that task.
The "why" column is the judge's reason as the report prints it. The report cuts long reasons short (marked with …); the full reasons are not published.

- **Passed / Failed**: a finished answer, judged right or wrong.
- **Blocked by a bot wall**: the site asked for a "prove you are human" check. A person can pass it; the test never tries. Counted as a miss in *Raw*, left out of the headline score.
- **Held for a person**: the product stopped on purpose and asked a person (for example to add something to a cart). Counted like blocked, by design.

Tasks left out of the headline score are marked **left out** with the reason.

## 2026-10-26 (latest), desktop app, Sonnet

Report: [webvoyager-sonnet-desktop-2-summary.md](../results/2026-10-26/webvoyager-sonnet-desktop-2-summary.md)

| Task | Result | Steps | Time (s) | Left out of headline? | Why (judge's reason) |
| :-- | :-- | --: | --: | :-- | :-- |
| Google Flights--39 | Passed | 7 | 30 | - | The answer names Tokyo as cheaper, which matches the reference. Both prices it cites appear in the page text (… |
| Cambridge Dictionary--16 | Passed | 7 | 21 | - | The definition, both pronunciations, and both example sentences all appear on the page text the agent read, an… |
| ArXiv--27 | Passed | 7 | 21 | - | The agent's answer gives all three categories with abbreviations (Econometrics econ.EM, General Economics econ… |
| Coursera--31 | Passed | 4 | 26 | - | The page the agent read shows 5 stars at 61.33%, which rounds to 61%, matching the answer. The reference of 52… |
| ArXiv--16 | Passed | 4 | 18 | - | The answer names a gr-qc new-submission listed on the page it read, and its summary matches that paper's abstr… |
| Huggingface--31 | Passed | 6 | 37 | - | the search listing the agent read shows `8e7bda18-01aa18ad-news-detector` as the newest "fake news" result, "U… |
| ESPN--1 | Passed | 12 | 180 | - | The page text shows no completed trade in the past two days (the Oct. 26 items are signings, extensions and wa… |
| Amazon--15 | Held for a person | 10 | 82 | left out: held for a person | the product held an act for the person (needs_human) and no passing answer; the bench never does it; judge: th… |
| GitHub--18 | Passed | 5 | 9 | - | the reference 'OpenCV' is in the answer |
| Wolfram Alpha--41 | Passed | 9 | 36 | - | the reference '110 bpm' is in the answer |
| Huggingface--2 | Passed | 4 | 19 | - | All three models (IndexTeam/Index-Translate-2B, CohereLabs/North-Small-Translate-1.0, IndexTeam/Index-Translat… |
| Wolfram Alpha--33 | Passed | 6 | 29 | - | The page "Itaipu Dam annual power generation" shows "89.5 TW h (terawatt hours)", which matches the answer and… |
| Huggingface--42 | Passed | 6 | 18 | - | The datasets-server first-rows page shows row 0 (complex_qa_0) with the user message content, matching the age… |
| ArXiv--4 | Passed | 6 | 16 | - | the page shows "New submissions (showing 18 of 18 entries)" for Monday, 26 October 2026, so the answer of 18 i… |
| Google Search--37 | Passed | 14 | 64 | - | The Google results snippet (Space.com "10 most Earth-like exoplanets") lists Gliese 667 Cc, Kepler-22b, and Ke… |
| Google Map--19 | Passed | 24 | 106 | - | the pages show Hilton Garden Inn Pittsburgh Airport as the closest Hilton, and the route page shows 34 min for… |
| ESPN--12 | Failed | 4 | 25 | - | The page text shows the first Top Headlines item is the McManaman story on La Liga, which the answer leaves ou… |
| GitHub--29 | Passed | 5 | 8 | - | the reference 'Unlimited' is in the answer |
| Allrecipes--32 | Passed | 10 | 42 | - | The recipe page the agent read shows 4,045 reviews, 8–12 hours on Low or 4–6 on High, and the same first five… |
| Google Map--35 | Failed | 5 | 9 | - | Every fact the answer states (4.8 rating with 6,334 reviews, 3,242 km², open 24 hours, nps.gov, Texas location… |
| BBC News--19 | Passed | 7 | 18 | - | The reference is from February 2024, but the pages the agent read show the live calendar listing Sunday 1 Nove… |
| Apple--36 | Passed | 7 | 12 | - | The page text names Olivia Rodrigo (n17 "Play Olivia Rodrigo video") and Sienna Spiro (n27 "Die On This Hill b… |
| Cambridge Dictionary--32 | Passed | 5 | 10 | - | The answer's rules and examples (less with uncountable nouns, fewer with plural nouns, "less work", "fewer car… |
| BBC News--41 | Passed | 6 | 43 | - | The page shows Japan, the United States and South Korea tied at 4 players each in the top 20 (including the ti… |
| Booking--19 | Passed | 4 | 21 | - | the three listings (Élégant Studio Paris €226, Large 50 m² €251, ROMANTIC and ZEN flat €253) all appear on the… |
| Google Search--36 | Passed | 4 | 17 | - | The pages report the 2026 Physics Nobel going to a Belgian-born IceCube researcher named Halzen, for decisive… |
| Booking--31 | Passed | 9 | 24 | - | The page lists Windsor with 15 properties (most) and Days Inn by Wyndham with 1 (fewest, the only brand at 1),… |
| BBC News--32 | Passed | 13 | 37 | - | The AI section page shows the Elvis headline first, and the summary names Anthropic as the company being sued,… |
| Google Flights--14 | Passed | 6 | 17 | - | The page's "Cheapest" tab shows €530, and the listing confirms a TAP Air Portugal 1-stop fare at 530 euros rou… |
| Google Map--14 | Failed | 5 | 18 | - | The agent's answer is a general parking garage, and the page text never mentions motorcycle parking for NYC Pa… |
| Wolfram Alpha--42 | Failed | 18 | 58 | - | The answer's value (≈192.5 MB, 1.92×10^8 bytes) appears in none of the pages read. The Wolfram/Alpha results a… |
| Coursera--6 | Passed | 12 | 136 | - | The answer names AI for Healthcare (AI CERTs), with "1 week to complete at 10 hours a week" and "Assessments 8… |
| ESPN--7 | Passed | 6 | 45 | - | The page text shows the Lakers beat the Jazz 132-123 on Sunday, the most recent game listed (17h ago), with a… |
| Amazon--26 | Passed | 4 | 17 | - | The Anker soundcore 2 listing on the page shows IPX7, 24-hour playtime, and a price of 30.37 (EUR), so it meet… |
| Allrecipes--5 | Failed | 12 | 58 | left out: not doable from the test machine's address (HTTP 402 IP block on every page, in both runs of 2026-10-11) | The task requires a rating above 4 stars, but the pages the agent read show only the rating count (1,108), not… |
| GitHub--24 | Failed | 6 | 27 | - | The three issue numbers appear only in the page text for marble-sage-17/marble-sage-17, not angular/angular. T… |
| Google Flights--19 | Passed | 4 | 19 | - | The page shows easyJet nonstop LGW 8:00 AM → CDG 10:20 AM, 1 hr 20 min, €39, matching the answer and the "Chea… |
| Google Search--3 | Passed | 6 | 45 | - | the IMDb page sorted by user rating shows The Chaos Class 9.1, Tosun Pasha 8.9, Life Is Beautiful 8.6, 777 Cha… |
| Amazon--29 | Passed | 4 | 15 | - | The pages show DenicMic 10 Pack LED solar pathway lights at 18.49 (the page shows EUR, not $), which fits the… |
| Apple--10 | Passed | 9 | 55 | - | The reference (M3 chips) is out of date. The page text shows the M5 Pro and M5 Max with 18-core CPUs, 20- or 3… |

## 2026-10-26 (earlier), desktop app, Sonnet

Report: [webvoyager-sonnet-desktop-summary.md](../results/2026-10-26/webvoyager-sonnet-desktop-summary.md)

| Task | Result | Steps | Time (s) | Left out of headline? | Why (judge's reason) |
| :-- | :-- | --: | --: | :-- | :-- |
| Google Flights--39 | Passed | 10 | 39 | - | Tokyo is the cheaper city. The Tokyo results page shows "Cheapest from €563" and the Sapporo page shows "Cheap… |
| Cambridge Dictionary--16 | Failed | 11 | 37 | - | The definition, [C] label, and both example sentences are supported by the page text, but the pronunciation's… |
| ArXiv--27 | Passed | 6 | 12 | - | The agent's answer lists Econometrics (econ.EM), General Economics (econ.GN), and Theoretical Economics (econ. |
| Coursera--31 | Passed | 5 | 26 | - | The live page shows 5-star ratings at 61.33% (rounds to 61%), which matches the agent's answer and differs fro… |
| ArXiv--16 | Passed | 4 | 15 | - | The answer names "The fate of primordial gravitational waves during domain-wall domination," which the gr-qc n… |
| Huggingface--31 | Passed | 10 | 31 | - | The live search page, sorted by recently created, lists meadow-kettle-56muril-fake-news-detector (0.2B, update… |
| ESPN--1 | Failed | 15 | 185 | - | The agent never read the body of the "NBA buzz" trades article it cites as the latest coverage, and the transa… |
| Amazon--15 | Held for a person | 9 | 75 | left out: held for a person | the product held an act for the person (needs_human) and no passing answer; the bench never does it; judge: th… |
| GitHub--18 | Passed | 4 | 12 | - | the reference 'OpenCV' is in the answer |
| Wolfram Alpha--41 | Passed | 9 | 19 | - | the reference '110 bpm' is in the answer |
| Huggingface--2 | Passed | 6 | 21 | - | All three named models appear as Translation models on the trending page, and the page shows them as updated 1… |
| Wolfram Alpha--33 | Passed | 6 | 17 | - | The answer's 89.5 TW h matches the reference, and the second Wolfram/Alpha page shows "Itaipu Dam / annual pow… |
| Huggingface--42 | Passed | 5 | 18 | - | The page text for complex_qa_0 shows the first user message content, and it matches the agent's answer and the… |
| ArXiv--4 | Passed | 5 | 12 | - | The page shows "New submissions (showing 18 of 18 entries)" for the Monday, 26 October 2026 listing, so the an… |
| Google Search--37 | Failed | 9 | 43 | - | The Google snippet the agent read ranks Gliese 667Cc first, Kepler-22b second, Kepler-69c third, and Kepler-62… |
| Google Map--19 | Passed | 22 | 123 | - | The live directions page shows "32 min" walking to ALDI (1.4 miles, walking mode), which matches the agent's a… |
| ESPN--12 | Failed | 6 | 27 | - | The page text shows the first "Top Headlines" item is the McManaman El Clásico story (LaLiga), which the answe… |
| GitHub--29 | Passed | 6 | 11 | - | the reference 'Unlimited' is in the answer |
| Allrecipes--32 | Passed | 12 | 45 | - | The recipe page supports the answer: slow cooker, 8–12 hours on Low or 4–6 on High, 4,045 reviews, and the fir… |
| Google Map--35 | Passed | 4 | 11 | - | every stated fact (4.8 rating with 6,334 reviews, 3,242 km², Texas, open 24 hours, nps.gov) appears in the pag… |
| BBC News--19 | Passed | 7 | 16 | - | The agent's answer, Sunday 1 November 2026 (New York City Marathon), appears in the page text it read, and it… |
| Apple--36 | Passed | 13 | 64 | - | The Apple Music page the agent read shows "Noah Kahan: The Zane Lowe Interview" as a featured card, which supp… |
| Cambridge Dictionary--32 | Passed | 6 | 16 | - | The answer states the fewer/less rule and gives examples that all appear on the Cambridge page ("I do less wor… |
| BBC News--41 | Passed | 20 | 90 | - | The page shows the Women's Majors leaderboard with Japan and the United States each at 4 players in the top 20… |
| Booking--19 | Passed | 5 | 22 | - | The page shows all three answered hotels with a 9.6 score under the 8.0 filter (Hôtel des Arts Montmartre, Rel… |
| Google Search--36 | Passed | 7 | 34 | - | The search results show the 2025 Physics prize went to three laureates "for the discovery of macroscopic quant… |
| Booking--31 | Passed | 10 | 41 | - | The expanded Brands list (all 20 entries) shows Windsor with 15 properties as the most and Days Inn by Wyndham… |
| BBC News--32 | Failed | 14 | 38 | - | The headline matches the page text, but the task also asks which companies are involved, and the answer gives… |
| Google Flights--14 | Passed | 6 | 22 | - | The page shows the Cheapest tab at €529 and the TAP Air Portugal 1-stop option from Newark to Gatwick at 529 e… |
| Google Map--14 | Passed | 5 | 22 | - | The results page lists NYC Parking at CBS Building first, with a 3,6 rating and "Rund um die Uhr geöffnet" (op… |
| Wolfram Alpha--42 | Passed | 16 | 50 | - | the reference '192 MB' is in the answer |
| Coursera--6 | Failed | 0 | 300 | - | no final answer |
| ESPN--7 | Passed | 4 | 26 | - | the reference is an unfilled template ("xxx"), and the answer's 132-123 win over the Utah Jazz, 3-0 record, an… |
| Amazon--26 | Passed | 5 | 21 | - | The page shows the Anker soundcore 2 with IPX7 waterproofing, 24-hour playtime, and a price of EUR 30.36, whic… |
| Allrecipes--5 | Passed | 12 | 58 | - | The answer names World's Best Pasta Sauce! with 1,108 ratings, which the search results page shows, and its in… |
| GitHub--24 | Passed | 4 | 14 | - | The three titles the agent gave are the first three entries on the closed-issues page it read, so the answer i… |
| Google Flights--19 | Passed | 4 | 19 | - | The page shows the cheapest fare from €39 and the easyJet 8:00 AM–10:20 AM nonstop, 1 hr 20 min, matching ever… |
| Google Search--3 | Passed | 7 | 33 | - | The agent's order matches the live IMDb page it read, where Modern Times (8.5, 289K votes) is listed 4th and C… |
| Amazon--29 | Passed | 5 | 27 | - | The page lists DenicMic Solar Lights Outdoor 10 Pack Pathway Lights (LED) at 20.54, which meets the 10-pack, L… |
| Apple--10 | Passed | 14 | 73 | - | The reference is out of date (it lists M3 chips), but the live pages show the MacBook Pro with M5, M5 Pro, and… |

## 2026-10-25, Chrome extension, Sonnet

Report: [webvoyager-sonnet-chrome-summary.md](../results/2026-10-25/webvoyager-sonnet-chrome-summary.md)

| Task | Result | Steps | Time (s) | Left out of headline? | Why (judge's reason) |
| :-- | :-- | --: | --: | :-- | :-- |
| Google Flights--39 | Passed | 10 | 104 | - | Tokyo is the cheaper city, matching the reference, and the Sapporo "From 603 euros" figure appears in the page… |
| Cambridge Dictionary--16 | Passed | 13 | 110 | - | The definition, UK and US pronunciations, and both example sentences all appear in the page text the agent rea… |
| ArXiv--27 | Passed | 8 | 18 | - | The agent's answer lists Econometrics (econ.EM), General Economics (econ.GN), and Theoretical Economics (econ. |
| Coursera--31 | Passed | 8 | 23 | - | The opened course page shows 5 stars at 61.33%, which rounds to 61%, so the answer matches the live page and t… |
| ArXiv--16 | Passed | 4 | 15 | - | The answer summarizes a gr-qc cross-listed paper, and every figure it states (150 mock O5 events, MeerKLASS/SK… |
| Huggingface--31 | Passed | 6 | 25 | - | the listing shows arab_fake_news_xlmr as the most recently updated fake-news-named model ("Updated 7 days ago"… |
| ESPN--1 | Failed | 8 | 61 | - | The Warriors-center claim does not appear in the visible page text, which cuts off mid-article, and the transa… |
| Amazon--15 | Held for a person | 10 | 68 | left out: held for a person | the product held an act for the person (needs_human) and no passing answer; the bench never does it; judge: Th… |
| GitHub--18 | Passed | 5 | 17 | - | the reference 'OpenCV' is in the answer |
| Wolfram Alpha--41 | Passed | 17 | 51 | - | the reference '110 bpm' is in the answer |
| Huggingface--2 | Passed | 5 | 22 | - | All three named models appear on the trending translation page, each showing "Updated 15 to 25 days ago" with… |
| Wolfram Alpha--33 | Passed | 8 | 18 | - | The answer "89.5 TWh" matches the reference and appears on the opened Wolfram/Alpha page ("89.5 TW h (terawatt… |
| Huggingface--42 | Passed | 4 | 22 | - | The page text shows the first row (complex_qa_0) with the user content matching the answer exactly, and the re… |
| ArXiv--4 | Passed | 5 | 15 | - | The live page reads "New submissions (showing 22 of 22 entries)" for Friday, 23 October 2026, which supports t… |
| Google Search--37 | Passed | 11 | 50 | - | The search snippet lists Proxima Centauri b, TRAPPIST-1e and LHS 1140 b as top super-Earths, and the LHS 1140… |
| Google Map--19 | Failed | 15 | 78 | - | The pages never show that DoubleTree is the closest Hilton; the search results were not ranked by distance, an… |
| ESPN--12 | Passed | 4 | 19 | - | The page's first three Top Headlines name Man United vs Bournemouth (Premier League), Embiid and the Sixers (N… |
| GitHub--29 | Passed | 6 | 13 | - | the reference 'Unlimited' is in the answer |
| Allrecipes--32 | Failed | 15 | 50 | left out: not doable from the test machine's address (HTTP 402 IP block on every page, in both runs of 2026-10-11) | the cook times (Low 8–12 h, High 4–6 h) and the first five ingredients match recipe 14685 in the page text, bu… |
| Google Map--35 | Passed | 5 | 17 | - | The page supports the answer's name, type, 801,163 acres, dogs allowed, 24-hour opening, nps.gov/bibe and €26. |
| BBC News--19 | Passed | 6 | 20 | - | The reference (17–18 Feb 2024) is out of date. The live calendar shows "Sunday 1 November — New York City Mara… |
| Apple--36 | Passed | 11 | 58 | - | the page text shows two "Sienna Spiro singing into a microphone" pictures in the "Get closer to your favorite… |
| Cambridge Dictionary--32 | Passed | 5 | 15 | - | every rule the answer states (less with uncountable nouns, fewer with plural nouns, the informal "less pizzas"… |
| BBC News--41 | Passed | 10 | 51 | - | The Women's Open leaderboard the agent read shows Japan, the United States and South Korea each with 4 players… |
| Booking--19 | Passed | 4 | 24 | - | The page shows the three answered hotels at the top of the review-score ordering with scores 9.6, 9.6 and 9.5,… |
| Google Search--36 | Passed | 11 | 43 | - | The 2026 press release says the prize went to the University of Wisconsin laureate "for decisive contributions… |
| Booking--31 | Passed | 9 | 21 | - | The page's Brands list (all 20 brands) shows Windsor with 15 properties as the most and Days Inn by Wyndham wi… |
| BBC News--32 | Passed | 15 | 59 | - | The headline "Meet the world's first artist robot" is the first item on the AI section page the agent read, an… |
| Google Flights--14 | Passed | 7 | 38 | - | The page shows €529 round trip for the TAP Air Portugal 1-stop via Lisbon (LIS), Newark–Gatwick, and it is the… |
| Google Map--14 | Passed | 6 | 19 | - | The page lists "69298466 Garage", marked "for motorcycles", open 24 hours, rated 4.9, near Radio City. The ref… |
| Wolfram Alpha--42 | Failed | 19 | 62 | - | the answer's 192.45 million bytes figure appears on no page the agent read. The pages only show parsed inputs… |
| Coursera--6 | Failed | 25 | 76 | - | the answer omits the required quiz count (it says none is shown), and the only assessment count visible in the… |
| ESPN--7 | Passed | 10 | 80 | - | The score 125-117 and the Clippers opponent match the ESPN schedule page the agent read (Sat, Oct 24, "vs LA 1… |
| Amazon--26 | Passed | 4 | 16 | - | The Anker soundcore 2 card on the results page shows $33.98 (under $50), IPX7 and 24-hour playtime (over 10 ho… |
| Allrecipes--5 | Failed | 9 | 31 | left out: not doable from the test machine's address (HTTP 402 IP block on every page, in both runs of 2026-10-11) | The ingredient list matches the recipe page, but the pick isn't shown to meet the conditions. The search card… |
| GitHub--24 | Passed | 7 | 40 | - | The page text lists Error 1901 (closed Oct 24), the Uzbek translation docs PR (closed Oct 24), and the Firefox… |
| Google Flights--19 | Passed | 6 | 48 | - | The pages show "Cheapest from €36" for easyJet's nonstop LGW→CDG flight, 8:00 AM–10:20 AM, 1 hr 20 min, which… |
| Google Search--3 | Failed | 8 | 48 | - | Only Life Is Beautiful matches the reference top 5, the answer includes an unreadable title, and the 9.1 and 8… |
| Amazon--29 | Passed | 6 | 25 | - | The DenicMic 10 Pack Pathway Lights card in the search results shows solar, LED, a 10-pack, and $22.99, all un… |
| Apple--10 | Passed | 12 | 50 | - | The reference's M3 chips are out of date. The pages show the MacBook Pro now uses M5, M5 Pro and M5 Max, with… |

## 2026-10-25, server browser, Sonnet

Report: [webvoyager-sonnet-summary.md](../results/2026-10-25/webvoyager-sonnet-summary.md)

| Task | Result | Steps | Time (s) | Left out of headline? | Why (judge's reason) |
| :-- | :-- | --: | --: | :-- | :-- |
| Google Flights--39 | Passed | 9 | 36 | - | The answer "Tokyo" matches the reference, and the Tokyo results page was opened, though its visible text is tr… |
| Cambridge Dictionary--16 | Passed | 7 | 16 | - | The definition, both UK and US pronunciations, and both example sentences appear on the page the agent read, a… |
| ArXiv--27 | Passed | 2 | 5 | - | The answer lists econ.EM, econ.GN, and econ.TH with their names, and the page text supports all three (Econome… |
| Coursera--31 | Passed | 3 | 14 | - | The page the agent read shows 5 stars at 61.33%, which rounds to 61%, matching the answer. The reference's 52. |
| ArXiv--16 | Passed | 6 | 19 | - | The gr-qc/new listing text the agent read contains this abstract (O(150) mock detections, MeerKLASS and SKA-Mi… |
| Huggingface--31 | Passed | 7 | 17 | - | The pages show analuciahm/tucuy-fake-news-spanish as the top "Recently created" fake-news model, and its commi… |
| ESPN--1 | Failed | 9 | 60 | - | The answer's key claims aren't supported by the pages it read. The homepage headline "Celtics' Tatum denies 'b… |
| Amazon--15 | Blocked by a bot wall | 5 | 26 | left out: bot wall | bot wall (automation_refused) and no passing answer; a person solves it, the bench does not; judge: The task r… |
| GitHub--18 | Passed | 3 | 9 | - | the reference 'OpenCV' is in the answer |
| Wolfram Alpha--41 | Passed | 17 | 30 | - | the reference '110 bpm' is in the answer |
| Huggingface--2 | Passed | 3 | 10 | - | All three named models appear on the translation page with recent update dates (14, 14 and 24 days ago) and do… |
| Wolfram Alpha--33 | Passed | 9 | 17 | - | The answer "89.5 TWh" matches the reference, and the Wolfram/Alpha page the agent read shows "89.5 TW h (teraw… |
| Huggingface--42 | Passed | 3 | 10 | - | The first-rows page shows row 0's user message as "Please provide a reasonable subgoal-based plan to solve the… |
| ArXiv--4 | Passed | 4 | 10 | - | The live page shows "New submissions (showing 22 of 22 entries)" for Friday, 23 October 2026, which supports t… |
| Google Search--37 | Passed | 12 | 44 | - | The Space.com page the agent read ranks Gliese 667Cc, Kepler-22b, and Kepler-69c as the top three, and the sup… |
| Google Map--19 | Passed | 11 | 29 | - | The answer names Hilton Garden Inn Pittsburgh Airport, matching the reference. The walking directions page sho… |
| ESPN--12 | Passed | 3 | 18 | - | The page text lists the first three Top Headlines as the BYU/UCF college football game, the Hoosiers at Michig… |
| GitHub--29 | Passed | 2 | 5 | - | the reference 'Unlimited' is in the answer |
| Allrecipes--32 | Blocked by a bot wall | 6 | 15 | left out: bot wall | bot wall (cloudflare_turnstile) and no passing answer; a person solves it, the bench does not; judge: The agen… |
| Google Map--35 | Passed | 4 | 9 | - | the answer's phone, plus code, 24-hour hours, website, and 801,163 acres all appear in the page text. The $30… |
| BBC News--19 | Passed | 5 | 13 | - | The live calendar shows Sunday 1 November 2026 (New York City Marathon) as the next event after today (25 Octo… |
| Apple--36 | Passed | 9 | 19 | - | The Entertainment page's Apple Music banner names Noah Kahan (text and screenshot), so the answer is supported… |
| Cambridge Dictionary--32 | Passed | 2 | 6 | - | Every fact in the answer appears on the page the agent read: "less" with uncountable nouns, "fewer" with plura… |
| BBC News--41 | Failed | 7 | 21 | - | The answer's Australian part matches the page (Hannah Green, T29, +4), but the top-20 count is wrong. South Ko… |
| Booking--19 | Failed | 8 | 25 | - | The visible page text shows only the first five result cards (Élégant Studio, ROMANTIC flat, Large 50 m2) with… |
| Google Search--36 | Passed | 6 | 13 | - | The nobelprize.org page the agent read lists Francis Halzen as the Nobel Prize in Physics 2026 laureate for Ic… |
| Booking--31 | Passed | 8 | 26 | - | The Brands filter on the page lists 20 brands. Windsor has the most (15), and Days Inn by Wyndham is the only… |
| BBC News--32 | Passed | 7 | 22 | - | The AI section page (bbc.com/technology/artificial-intelligence) shows "Why the charts are full of old songs -… |
| Google Flights--14 | Passed | 9 | 27 | - | The USD results page shows "Cheapest from $593" for Jan 10 to Jan 17, so the answer is supported by the screen… |
| Google Map--14 | Passed | 4 | 10 | - | The page text lists "Rising Wolf Garage" as "Motosiklet Park Yeri" (motorcycle parking) at 338 E 9th St, open… |
| Wolfram Alpha--42 | Failed | 23 | 65 | - | the 192.45 MB figure appears in no page text or screenshot. The agent computed it itself (7214.4 × 8892 × 3 by… |
| Coursera--6 | Passed | 12 | 42 | - | the task accepts any related course, and the agent's facts (Foundations of AI in Healthcare, 8 hours to comple… |
| ESPN--7 | Passed | 6 | 40 | - | The Lakers' latest game on the page is 125-117 over the Clippers, and the AP recap confirms Reaves (28 pts, 9… |
| Amazon--26 | Passed | 6 | 27 | - | The BolaButty listing shown in the page text the agent read is priced at $39.99, is IPX5 waterproof, and has u… |
| Allrecipes--5 | Blocked by a bot wall | 5 | 12 | left out: bot wall | bot wall (cloudflare_turnstile) and no passing answer; a person solves it, the bench does not; judge: The agen… |
| GitHub--24 | Passed | 3 | 10 | - | The three titles match the first three cards on the page, which is filtered to closed issues and sorted by mos… |
| Google Flights--19 | Passed | 6 | 21 | - | The cited page text shows easyJet nonstop, LGW 7:00 AM to CDG 9:20 AM, 1 hr 20 min, at TRY 2,127, the cheapest… |
| Google Search--3 | Passed | 4 | 17 | - | The agent's five titles are the top five cards on the user-rating-sorted comedy page it read, and the referenc… |
| Amazon--29 | Blocked by a bot wall | 9 | 43 | left out: bot wall | bot wall (automation_refused) and no passing answer; a person solves it, the bench does not; judge: The agent'… |
| Apple--10 | Passed | 7 | 21 | - | the pages show M5 Pro/M5 Max MacBook Pro configurations with 36GB–128GB memory and an 18-core CPU/40-core GPU,… |

## 2026-10-25, server browser, Haiku

Report: [webvoyager-haiku-summary.md](../results/2026-10-25/webvoyager-haiku-summary.md)

| Task | Result | Steps | Time (s) | Left out of headline? | Why (judge's reason) |
| :-- | :-- | --: | --: | :-- | :-- |
| Google Flights--39 | Failed | 26 | 125 | - | no final answer after 26 turns |
| Cambridge Dictionary--16 | Passed | 6 | 15 | - | The definition, both pronunciations, and both example sentences match the Cambridge page text the agent read,… |
| ArXiv--27 | Passed | 8 | 16 | - | The agent's answer gives all three categories with their abbreviations (Econometrics econ.EM, General Economic… |
| Coursera--31 | Passed | 14 | 45 | - | the page the agent read shows 5 stars at 61.33%, which rounds to the agent's 61%, while the reference (52.6%)… |
| ArXiv--16 | Passed | 6 | 20 | - | The answer names arXiv:2610.31177, a gravitational-wave paper listed on the gr-qc/new page, and its 62% shorte… |
| Huggingface--31 | Passed | 9 | 19 | - | The commit history shows the model's last update as Oct 22, and the recently-updated search lists it near the… |
| ESPN--1 | Failed | 20 | 96 | - | The claim that no trades were reported in the past 2 days, and that the latest trade is from Sept 22, is not s… |
| Amazon--15 | Blocked by a bot wall | 7 | 26 | left out: bot wall | bot wall (automation_refused) and no passing answer; a person solves it, the bench does not; judge: The agent… |
| GitHub--18 | Passed | 6 | 14 | - | the reference 'OpenCV' is in the answer |
| Wolfram Alpha--41 | Passed | 5 | 15 | - | the reference '110 bpm' is in the answer |
| Huggingface--2 | Passed | 7 | 23 | - | The trending and created-sort pages list IndexTeam/Index-Translate-2B and Index-Translate-9B (updated 14 days… |
| Wolfram Alpha--33 | Passed | 14 | 28 | - | the page shows 89.5 TW h for Itaipu annual power generation, matching the reference, though no 2023-specific v… |
| Huggingface--42 | Passed | 4 | 10 | - | The page text shows the first row's user message (complex_qa_0) with exactly the content the agent gave, match… |
| ArXiv--4 | Passed | 4 | 11 | - | The live astro-ph.GA recent page shows "Fri, 23 Oct 2026 (showing 35 of 35 entries)", which supports the agent… |
| Google Search--37 | Failed | 9 | 23 | - | The answer says it could not verify a current top 3 and offers only examples, not a ranking, so it does not do… |
| Google Map--19 | Passed | 33 | 71 | - | The hotel name matches the reference, and the page text shows a 27 dk. walking route from the Hilton Garden In… |
| ESPN--12 | Passed | 6 | 24 | - | The page text lists the Top Headlines in order: Indiana/Michigan (URL `/college-football/`, NCAAF), Ravens/Jac… |
| GitHub--29 | Passed | 3 | 8 | - | the reference 'Unlimited' is in the answer |
| Allrecipes--32 | Blocked by a bot wall | 4 | 14 | left out: bot wall | bot wall (cloudflare_turnstile) and no passing answer; a person solves it, the bench does not; judge: The agen… |
| Google Map--35 | Failed | 10 | 55 | - | The answer's facts are supported by the NPS page, but it omits the phone number, Plus Code, and ticket price t… |
| BBC News--19 | Passed | 13 | 24 | - | The reference date is out of date, and the Athletics calendar page the agent read for November 2026 shows "Sun… |
| Apple--36 | Passed | 17 | 26 | - | The Apple Music card in the homepage screenshot reads "Miley: The Zane Lowe Interview" and supports naming Mil… |
| Cambridge Dictionary--32 | Passed | 4 | 11 | - | The answer gives the uncountable/plural rule, the reference examples, the "less pizzas" warning, and the "of"… |
| BBC News--41 | Passed | 13 | 32 | - | The page shows Japan, United States and South Korea each with 4 players in the top 20 (a tie, not the single l… |
| Booking--19 | Failed | 9 | 24 | - | The three named hotels and their 9.8/9.7 scores do not appear in the page text shown. The visible sorted resul… |
| Google Search--36 | Failed | 7 | 15 | - | The agent gave no answer; it only reported that the search was blocked and asked for approval, and the pages i… |
| Booking--31 | Passed | 15 | 32 | - | The Brands section the agent read lists Windsor at 15 (the most) and Days Inn by Wyndham at 1 (the only brand… |
| BBC News--32 | Passed | 11 | 29 | - | The topic page's top "Artificial intelligence" item is the "Why the charts are full of old songs" headline, an… |
| Google Flights--14 | Passed | 17 | 38 | - | The results page shows "Cheapest from $593" and lists Tap Air Portugal EWR–LGW via LIS at $593 round trip, whi… |
| Google Map--14 | Failed | 10 | 23 | - | the answer reports that no motorcycle parking was found, which is a could-not-find result, and the reference's… |
| Wolfram Alpha--42 | Passed | 14 | 44 | - | The answer gives 192 MB (≈192.45 MB, 192,451,334 bytes), matching the reference. Wikipedia's page supports the… |
| Coursera--6 | Passed | 16 | 53 | - | The live course page shows "8 hours to complete" and "Assessments: 13 assignments" for Foundations of AI in He… |
| ESPN--7 | Passed | 10 | 57 | - | The score (Lakers 125, Clippers 117), the Reaves and Kessler stat lines, and the 2-0 start all appear in the g… |
| Amazon--26 | Blocked by a bot wall | 8 | 27 | left out: bot wall | bot wall (automation_refused, bot_challenge) and no passing answer; a person solves it, the bench does not; ju… |
| Allrecipes--5 | Blocked by a bot wall | 4 | 13 | left out: bot wall | bot wall (cloudflare_turnstile) and no passing answer; a person solves it, the bench does not; judge: The agen… |
| GitHub--24 | Passed | 16 | 57 | - | The closed-issues search page and the API results the agent read list #71601, #71592 and #71567 as the most re… |
| Google Flights--19 | Passed | 21 | 53 | - | The page shows easyJet at TRY 2,127 for the 7:00 AM–9:20 AM nonstop (1 hr 20 min) and the Cheapest tab reads "… |
| Google Search--3 | Blocked by a bot wall | 10 | 32 | left out: bot wall | bot wall (recaptcha) and no passing answer; a person solves it, the bench does not; judge: The agent gave no T… |
| Amazon--29 | Blocked by a bot wall | 5 | 21 | left out: bot wall | bot wall (automation_refused) and no passing answer; a person solves it, the bench does not; judge: The agent… |
| Apple--10 | Failed | 13 | 32 | - | the agent's specs (A18 Pro, 8GB, 256GB/512GB) do not appear in the page text shown, which cuts off before any… |

## 2026-10-24, server browser, Sonnet

Report: [webvoyager-sonnet-summary.md](../results/2026-10-24/webvoyager-sonnet-summary.md)

| Task | Result | Steps | Time (s) | Left out of headline? | Why (judge's reason) |
| :-- | :-- | --: | --: | :-- | :-- |
| Google Flights--39 | Passed | 6 | 23 | - | The live pages show Sapporo's cheapest one-way fare at TRY 29,035 and Tokyo's at TRY 29,411, so the answer is… |
| Cambridge Dictionary--16 | Passed | 12 | 30 | - | The definition, UK and US pronunciations, and both example sentences all appear in the page text the agent rea… |
| ArXiv--27 | Passed | 2 | 5 | - | The answer gives all three categories and abbreviations the reference lists. The page text confirms econ.GN (G… |
| Coursera--31 | Passed | 3 | 13 | - | The page the agent read shows 5 stars at 61.33%, which rounds to 61%, so the answer matches the live page whil… |
| ArXiv--16 | Passed | 3 | 12 | - | The answer names a paper listed on the gr-qc new-submissions page, and every stated finding appears in its abs… |
| Huggingface--31 | Passed | 10 | 20 | - | The sorted search lists analuciahm/tucuy-fake-news-spanish-onnx first ("Updated 1 day ago"), and its commit hi… |
| ESPN--1 | Failed | 8 | 52 | - | The answer's Warriors/Porzingis claim ("exploring trades," "reported Oct. 21") does not appear in the page tex… |
| Amazon--15 | Failed | 11 | 47 | - | The agent did not add any shoes to the cart. Its answer says the task was not completed because Amazon showed… |
| GitHub--18 | Passed | 3 | 10 | - | the reference 'OpenCV' is in the answer |
| Wolfram Alpha--41 | Passed | 4 | 11 | - | the reference '110 bpm' is in the answer |
| Huggingface--2 | Passed | 3 | 13 | - | All three named models appear in the page text as Translation models, updated 14–24 days ago, on a trending-so… |
| Wolfram Alpha--33 | Passed | 6 | 16 | - | the reference '89.5 TWh (terawatt hours)' is in the answer |
| Huggingface--42 | Passed | 2 | 8 | - | The viewer shows complex_qa_0, whose first user message is "Please provide a reasonable subgoal-based plan to… |
| ArXiv--4 | Passed | 4 | 10 | - | The page text shows "New submissions (showing 22 of 22 entries)", which supports the agent's answer of 22, whi… |
| Google Search--37 | Blocked by a bot wall | 6 | 20 | left out: bot wall | bot wall (recaptcha) and no passing answer; a person solves it, the bench does not; judge: The agent chose its… |
| Google Map--19 | Passed | 18 | 41 | - | The answer names Hilton Garden Inn Pittsburgh Airport, which matches the reference and is closer than the Doub… |
| ESPN--12 | Passed | 3 | 17 | - | The page's first three Top Headlines are the Beasley story (ex-NBA player), the Brewers World Series opener (M… |
| GitHub--29 | Passed | 2 | 5 | - | the reference 'Unlimited' is in the answer |
| Allrecipes--32 | Blocked by a bot wall | 5 | 14 | left out: bot wall | bot wall (cloudflare_turnstile) and no passing answer; a person solves it, the bench does not; judge: The agen… |
| Google Map--35 | Passed | 5 | 11 | - | every fact in the answer (name, Texas, 24-hour hours, phone +1 432-477-2251, nps.gov website, plus code 6PXX+W… |
| BBC News--19 | Passed | 5 | 12 | - | The reference (17-18 Feb 2024) is out of date. The live calendar, read on 2026-10-24, shows the next event aft… |
| Apple--36 | Failed | 17 | 23 | - | The screenshots support only "Sienna Spiro" (the Travis Mills Show card reads "by SIENNA SPIRO"). Olivia Rodri… |
| Cambridge Dictionary--32 | Passed | 3 | 13 | - | The answer's claims (fewer with plural countables, less with uncountables, "less of"/"fewer of" before determi… |
| BBC News--41 | Failed | 11 | 32 | - | The Australian part is supported by the page (Hannah Green, tied 29th at +4, and the reference's Grace Kim is… |
| Booking--19 | Failed | 9 | 40 | - | Only Paris j'Adore Hotel & Spa (9.2) appears in the page text. The 9.5 for Hôtel Mansart and the 9.1 for Hôtel… |
| Google Search--36 | Passed | 5 | 19 | - | The nobelprize.org page the agent read names Francis Halzen as the 2026 Physics laureate for IceCube and high-… |
| Booking--31 | Passed | 9 | 37 | - | The page lists 20 brands in the Brands filter. Windsor has 15 (most) and Days Inn by Wyndham has 1 (fewest, th… |
| BBC News--32 | Passed | 6 | 18 | - | The AI section's "Latest headlines" list shows "UK to invest £100m in 'world first' AI Biosecurity Lab" as the… |
| Google Flights--14 | Passed | 7 | 21 | - | The page shows the cheapest fare at TRY 29,412 round trip (the "Cheapest from TRY 29,412" tab), and the matchi… |
| Google Map--14 | Passed | 4 | 15 | - | the page lists Rising Wolf Garage at 338 E 9th St as "Motosiklet Park Yeri" (motorcycle parking), matching the… |
| Wolfram Alpha--42 | Failed | 29 | 58 | - | the page screenshots and text show only a loading state, "Interpreting as: picture", and a "doesn't understand… |
| Coursera--6 | Passed | 21 | 77 | - | The AI for Healthcare page shows "1 week to complete at 10 hours a week" and "Assessments 8 assignments", so t… |
| ESPN--7 | Passed | 6 | 40 | - | The score (Lakers 125, Clippers 117), Reaves's 28 points and 9 assists, Kessler's 22 points and 6 blocks, and… |
| Amazon--26 | Failed | 7 | 34 | - | The agent's answer is "Unverified" and names candidates without confirming any price under $50; the pages it r… |
| Allrecipes--5 | Blocked by a bot wall | 5 | 18 | left out: bot wall | bot wall (cloudflare_turnstile) and no passing answer; a person solves it, the bench does not; judge: The agen… |
| GitHub--24 | Passed | 7 | 18 | - | the three numbers are the top three entries in the closed-issues list the agent read (#71567, #71551, #71450,… |
| Google Flights--19 | Passed | 3 | 15 | - | The page's "Cheapest from $43" tab and the easyJet $43 flight (7:00 AM–9:20 AM, 1 hr 20 min, nonstop) support… |
| Google Search--3 | Passed | 5 | 20 | - | The answer's five titles and ratings (8.6, 8.5, 8.5, 8.5, 8.5) match the IMDb list the agent read, in the same… |
| Amazon--29 | Failed | 10 | 41 | - | The agent gave no product; it reported being blocked by Amazon's bot wall, and the pages it read show no solar… |
| Apple--10 | Passed | 7 | 20 | - | the MacBook Pro specs page shows M5, M5 Pro and M5 Max chips and 36GB–128GB memory, so the reference's M3 valu… |

## 2026-10-24, server browser, Haiku

Report: [webvoyager-haiku-summary.md](../results/2026-10-24/webvoyager-haiku-summary.md)

| Task | Result | Steps | Time (s) | Left out of headline? | Why (judge's reason) |
| :-- | :-- | --: | --: | :-- | :-- |
| Google Flights--39 | Failed | 26 | 100 | - | no final answer after 26 turns |
| Cambridge Dictionary--16 | Passed | 5 | 14 | - | The definition, UK and US pronunciations, and both example sentences all appear in the page text the agent rea… |
| ArXiv--27 | Passed | 5 | 11 | - | The agent's answer lists Econometrics (econ.EM), General Economics (econ.GN), and Theoretical Economics (econ. |
| Coursera--31 | Passed | 13 | 46 | - | The opened course page (Exploring Quantum Physics, University of Maryland, College Park) shows 5 stars at 61.3… |
| ArXiv--16 | Passed | 6 | 15 | - | The answer names arXiv:2610.30187, a gr-qc new submission on the listing page the agent read, and its summary… |
| Huggingface--31 | Passed | 9 | 19 | - | the "Recently updated" search page lists analuciahm/tucuy-fake-news-spanish-onnx first, and its commit history… |
| ESPN--1 | Failed | 18 | 103 | - | The answer's date claims ("from today," "from July") appear nowhere in the page text the agent read, and the t… |
| Amazon--15 | Failed | 14 | 58 | - | The task required adding a qualifying shoe to the cart, but the agent reported it was not added, and it did no… |
| GitHub--18 | Passed | 11 | 20 | - | the reference 'OpenCV' is in the answer |
| Wolfram Alpha--41 | Passed | 8 | 19 | - | the reference '110 bpm' is in the answer |
| Huggingface--2 | Failed | 12 | 28 | - | Only the 2B model's "Sept 2026" date is claimed, and the visible page text is truncated before any date, so it… |
| Wolfram Alpha--33 | Passed | 12 | 35 | - | The screenshot shows "89.5 TWh (terawatt hours)" for Itaipu Dam annual power generation, matching the referenc… |
| Huggingface--42 | Passed | 4 | 13 | - | The page text shows the first message (complex_qa_0, role user) with content "Please provide a reasonable subg… |
| ArXiv--4 | Passed | 5 | 9 | - | the live astro-ph.GA/new page shows "New submissions (showing 22 of 22 entries)", which supports the agent's 2… |
| Google Search--37 | Blocked by a bot wall | 10 | 28 | left out: bot wall | bot wall (recaptcha) and no passing answer; a person solves it, the bench does not; judge: The answer is the a… |
| Google Map--19 | Failed | 30 | 64 | - | The hotel name is correct, but the 35-minute figure is not shown as a walking time. The walking-mode screen wa… |
| ESPN--12 | Passed | 5 | 21 | - | The page's Top Headlines list the Brewers World Series opener (MLB), the NFL House in Paris headline (NFL), an… |
| GitHub--29 | Passed | 7 | 14 | - | the reference 'Unlimited' is in the answer |
| Allrecipes--32 | Blocked by a bot wall | 3 | 8 | left out: bot wall | bot wall (cloudflare_turnstile) and no passing answer; a person solves it, the bench does not; judge: The agen… |
| Google Map--35 | Passed | 11 | 35 | - | Every fact in the answer (4.8 stars, 6,336 reviews, 24 hours, +1 432-477-2251, nps.gov, 6PXX+WW plus code, Tex… |
| BBC News--19 | Passed | 18 | 36 | - | The live calendar screenshot shows the New York City Marathon on Sunday 01 Nov 2026, which matches the agent's… |
| Apple--36 | Failed | 30 | 45 | - | The answer's "Miley" is supported by the screenshots, but the task asks for the singers' names (plural), and t… |
| Cambridge Dictionary--32 | Passed | 5 | 12 | - | every rule and example in the answer appears in the fetched "Less or fewer?" page text, including "I do less w… |
| BBC News--41 | Passed | 16 | 42 | - | The page shows Japan, USA and South Korea each with 4 players in the top 20 (ties included), and Hannah Green… |
| Booking--19 | Passed | 7 | 21 | - | The sorted Paris search for 2027-03-18 to 2027-03-20 shows all three answered hotels scored 9.6 with matching… |
| Google Search--36 | Passed | 9 | 21 | - | The Nobel Physics page the agent read names Francis Halzen as the 2026 laureate for IceCube and the discovery… |
| Booking--31 | Passed | 16 | 34 | - | the live page text lists Windsor with 15 properties as the most and Days Inn by Wyndham with 1 as the last bra… |
| BBC News--32 | Passed | 11 | 31 | - | The live AI topic page's top headline is "The rise of AI election ads in US midterms campaign", which the answ… |
| Google Flights--14 | Passed | 19 | 87 | - | The pages show the Cheapest tab at TRY 29,475 round trip, matching the Tap Air Portugal Newark–Gatwick itinera… |
| Google Map--14 | Passed | 9 | 22 | - | The search results page lists Rising Wolf Garage at 338 E 9th St as "Motosiklet Park Yeri" (motorcycle parking… |
| Wolfram Alpha--42 | Failed | 11 | 26 | - | The pages the agent read show only the query echoed in the input box, with no computed memory figure, so the 1… |
| Coursera--6 | Passed | 42 | 147 | - | The module pages show nine modules at 1 hour each except Module 9 at 15 minutes, which sums to 8h15m as the an… |
| ESPN--7 | Passed | 12 | 61 | - | The live ESPN pages show Lakers 125, Clippers 117 (FINAL, Lakers home), with Reaves 28 pts/9 ast and Kessler 2… |
| Amazon--26 | Failed | 12 | 69 | - | The answer names no product confirmed under $50; it says prices "could not be verified," and the pages read sh… |
| Allrecipes--5 | Blocked by a bot wall | 4 | 12 | left out: bot wall | bot wall (cloudflare_turnstile) and no passing answer; a person solves it, the bench does not; judge: The agen… |
| GitHub--24 | Passed | 11 | 31 | - | The closed-issues pages show #71567 and #71562 as the most recent closures, and #71551 appears as a closed iss… |
| Google Flights--19 | Passed | 24 | 55 | - | The page shows easyJet nonstop, LGW 7:00 AM to CDG 9:20 AM, 1 hr 20 min, for TRY 2,127 on Monday, January 25,… |
| Google Search--3 | Blocked by a bot wall | 12 | 39 | left out: bot wall | bot wall (recaptcha) and no passing answer; a person solves it, the bench does not; judge: the reference is ma… |
| Amazon--29 | Failed | 9 | 38 | - | The agent gave no product; it reported "Not determined" after Amazon's checkpoint blocked access, and the page… |
| Apple--10 | Failed | 10 | 24 | - | The agent's specs (A18 Pro, 8GB, 256GB) appear in none of the page text it read. The specs page returned "No d… |
