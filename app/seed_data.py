"""Przykładowe pytania (zdjęcia z Wikimedia Commons, wolne licencje)."""
from urllib.parse import quote


def commons(filename, width=1200):
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{quote(filename)}?width={width}"


QUESTIONS = [
    dict(
        title="Pierogi", category="kuchnia", location_name="Polska",
        lat=52.2297, lng=21.0122,
        description="Pierogi z farszem z ziemniaków i twarogu nazywa się w Polsce „ruskimi”.",
        image_url=commons("Pierogi in Warsaw, 2019.jpg"),
        image_credit="Chris Olszewski, CC BY-SA 4.0, Wikimedia Commons",
    ),
    dict(
        title="Paella valenciana", category="kuchnia", location_name="Walencja, Hiszpania",
        lat=39.4699, lng=-0.3763,
        description="Oryginalna paella z Walencji to królik i kurczak, nie owoce morza.",
        image_url=commons("01 Paella Valenciana original.jpg"),
        image_credit="Jan Harenburg, CC BY-SA 4.0, Wikimedia Commons",
    ),
    dict(
        title="Bunad z Telemarku", category="stroj", location_name="Telemark, Norwegia",
        lat=59.4917, lng=8.6333,
        description="Norwegowie zakładają bunad m.in. 17 maja, w Dzień Konstytucji.",
        image_url=commons("Bunad Telemark.jpeg"),
        image_credit="Axel Lindahl, domena publiczna, Wikimedia Commons",
    ),
    dict(
        title="Strój z Miesbach (Tracht)", category="stroj", location_name="Miesbach, Bawaria, Niemcy",
        lat=47.7890, lng=11.8340,
        description="Miesbacher Tracht uchodzi za wzór bawarskiego stroju ludowego.",
        image_url=commons("MB-Tracht paar.jpg"),
        image_credit="Aquajazz, CC BY-SA 2.0 DE, Wikimedia Commons",
    ),
    dict(
        title="Traje de flamenca na Feria de Abril", category="stroj", location_name="Sewilla, Hiszpania",
        lat=37.3891, lng=-5.9845,
        description="Feria de Abril w Sewilli to tydzień tańca sevillanas w kolorowych sukniach.",
        image_url=commons("Feria abril 2011 0001.jpg"),
        image_credit="Sevilla Congress & Convention Bureau, CC BY-SA 4.0, Wikimedia Commons",
    ),
    dict(
        title="Dwujęzyczny znak walijsko-angielski", category="jezyk", location_name="Walia, Wielka Brytania",
        lat=52.4153, lng=-4.0829,
        description="Walijski ma podwójne litery „ll” i „dd” — po walijsku zakaz parkowania to „dim parcio”.",
        image_url=commons("Bilingual English-Welsh no parking sign.jpg"),
        image_credit="Dominic Nelson, CC BY-SA 4.0, Wikimedia Commons",
    ),
    dict(
        title="Znaki drogowe po baskijsku", category="jezyk", location_name="Bilbao, Kraj Basków",
        lat=43.2630, lng=-2.9350,
        description="Baskijski (euskara) nie jest spokrewniony z żadnym innym żywym językiem Europy.",
        image_url=commons("Basque road signs in Bilbao.jpg"),
        image_credit="Chris Mitchell, CC BY-SA 4.0, Wikimedia Commons",
    ),
    dict(
        title="Gákti — strój Saamów", category="stroj", location_name="Kautokeino, Sápmi (Norwegia)",
        lat=69.0125, lng=23.0412,
        description="Wzór i kolory gákti zdradzają, z jakiego regionu Sápmi pochodzi właściciel.",
        image_url=commons("Berit Alette Mienna's gákti at 2025 Riddu Riđđu.jpg"),
        image_credit="John Sears, CC BY-SA 4.0, Wikimedia Commons",
    ),
    dict(
        title="Strój łowicki", category="stroj", location_name="Łowicz, Polska",
        lat=52.1077, lng=19.9452,
        description="Charakterystyczne pasiaste spódnice łowickie tkano z wełny na krosnach.",
        image_url=commons("Łowicz traditional costume, Poland 01.jpg"),
        image_credit="Emilia Wiśniewska, CC BY-SA 4.0, Wikimedia Commons",
    ),
    dict(
        title="Pastel de nata", category="kuchnia", location_name="Belém, Lizbona, Portugalia",
        lat=38.6975, lng=-9.2063,
        description="Przepis wymyślili mnisi z klasztoru Hieronimitów w Belém.",
        image_url=commons("Pastel de nata septembre 2015.jpg"),
        image_credit="Claude Truong-Ngoc, CC BY-SA 3.0, Wikimedia Commons",
    ),
    dict(
        title="Gulasz (gulyásleves)", category="kuchnia", location_name="Budapeszt, Węgry",
        lat=47.4979, lng=19.0402,
        description="Na Węgrzech gulasz to zupa — gęste danie nazywa się pörkölt.",
        image_url=commons("Goulash soup 2014.jpg"),
        image_credit="ainudil, CC BY-SA 2.0, Wikimedia Commons",
    ),
    dict(
        title="Pizza Margherita", category="kuchnia", location_name="Neapol, Włochy",
        lat=40.8518, lng=14.2681,
        description="Kolory Margherity — bazylia, mozzarella, pomidor — to barwy flagi Włoch.",
        image_url=commons("Margherita Originale.JPG"),
        image_credit="Mario56, CC BY-SA 3.0, Wikimedia Commons",
    ),
    dict(
        title="Fondue serowe", category="kuchnia", location_name="Fryburg, Szwajcaria",
        lat=46.8065, lng=7.1619,
        description="Klasyczne „moitié-moitié” to pół na pół gruyère i vacherin fribourgeois.",
        image_url=commons("Fondue au fromage.jpg"),
        image_credit="BiiJii, CC0, Wikimedia Commons",
    ),
    dict(
        title="Haggis, neeps and tatties", category="kuchnia", location_name="Edynburg, Szkocja",
        lat=55.9533, lng=-3.1883,
        description="Haggis je się tradycyjnie 25 stycznia, w noc poety Roberta Burnsa.",
        image_url=commons("Haggis neeps and tatties.jpg"),
        image_credit="Biology Big Brother, CC BY 2.0, Wikimedia Commons",
    ),
    dict(
        title="Haft matyó", category="zwyczaje", location_name="Mezőkövesd, Węgry",
        lat=47.8167, lng=20.5833,
        description="Haft matyó jest wpisany na listę niematerialnego dziedzictwa UNESCO.",
        image_url=commons("Matyó embroidery from Hungury, EU.jpg"),
        image_credit="Naturpuur, CC BY-SA 4.0, Wikimedia Commons",
    ),
    dict(
        title="Kilt", category="stroj", location_name="Highlands, Szkocja",
        lat=57.4778, lng=-4.2247,
        description="Wzór kratki (tartan) tradycyjnie wskazuje klan lub region.",
        image_url=commons("Highlander-kilt.jpg"),
        image_credit="David Ball, CC BY 2.5, Wikimedia Commons",
    ),
]
