---
title: "Åk 2 – Aktivitet 02 – Något i vägen – Robot med villkor"
slug: "ak-2-aktivitet-02-robot-med-villkor"
kind: activity
grade: 2
activity: 2
date: 2018-08-19
authors: ["Micke Kring", "Jonas Johansson"]
concepts: ["problemlosning", "repetition", "stegvisa-instruktioner", "symbolers-anvandning", "villkor"]
subjects: ["ma", "tk"]
methods: ["programmering-utan-dator"]
image: "/media/img/ronot.webp"
syfte: |
  **Syftet med aktiviteten är att introducera eleverna i begreppet villkor (om - annars | if - else). De ska programmera sin robotkompis att gå rakt fram från ena sidan av klassrummet till den andra. Men vad händer om det helt plötsligt står ett hinder i vägen?**
laroplan: |
  **Matematik - Centralt Innehåll Åk 1-3 | Algebra**
  * Hur entydiga stegvisa instruktioner kan konstrueras, beskrivas och följas som grund för programmering.
  * Symbolers användning vid stegvisa instruktioner.

  **Teknik – Centralt Innehåll Åk 1-3 | Tekniska lösningar**
  * Att styra föremål med programmering.
---

## Material

Penna, papper och dina bästa läroplansglasögon.

## Varför använder vi villkor? {.steg}

**Vi börjar övningen med att förklara för eleverna vad villkor är och därefter låta eleverna prata om hur villkor styr deras vardag. Be eleverna lista några egna villkor enligt exemplen nedan - med OM och ANNARS (If och Else).**

**Om** det regnar ute: ta med ett paraply - **Annars:** Lämna paraply hemma
**Om** det finns flingor: ät flingor - **Annars:** ät en macka
**Om** min röda tröja är tvättad: ta på mig den - **Annars:** ta på mig den blå tröjan
**Om** min kompis fyller år: sjung för hen - **Annars:** sjung inte

## Kodspråk {.steg}

**I den kommande uppgiften kommer vi att prova ett nytt kodspråk, ett textbaserat språk istället för symboler. Vi skriver och läser instruktionerna uppifrån och ned.**

**Rörelse
fram()** = gå framåt tills något händer
**fram(1)** = steg framåt (antal steg om flera)
**bak(1)** = steg bakåt (antal steg om flera)
**höger(1)** = rotera höger 90° (antal gånger om flera)
**vänster(1)** = rotera vänster 90° (antal gånger om flera)
**stopp** = stanna och avsluta programmet

**Villkor**
**om** (någon händer)
gör vi detta
**annars**
gör vi något annat

## Något i vägen - RoBot med villkor {.steg}

#### Uppgift [A]

Eleverna jobbar i par eller flera i denna uppgift och turas om att vara programmerare och att vara robot.
**Din robot ska ta sig från längst bak i klassrummet fram till tavlan på andra sidan klassrummet så snabbt och rakt det bara går. Det finns ingenting i vägen. Hur kan vi programmera roboten? Finns det olika sätt?**

1. Låt eleverna fundera och diskutera fram en lösning. Skriv ned koden. Visa de olika gruppernas lösningar och diskutera tillsammans.

*Visa på skillnaden och diskutera problemen med att använda exempelvis **fram(16)** - om det skulle vara 16 steg fram till tavlan mot att använda **fram()** där roboten för evigt fortsätter att gå fram? Vad är bra respektive mindre bra med bägge exemplen? I det första exemplet, fungerar det med 16 steg för alla "robotar", både små som stora med olika längd på benen? Om man använder det andra exemplet, hur stoppas roboten när den kommer fram till tavlan? Den kommer garanterat att nå fram till väggen, men den kommer att fortsätta för evigt att gå in i väggen tills batterierna tar slut.*

2. Lägg till ett villkor.
Låt eleverna diskutera och komma fram till ett villkor när de kommer fram till väggen. När roboten nuddar väggen så ska den stanna. Skriv ned koden. Visa de olika gruppernas lösningar och diskutera för- och nackdelar tillsammans.

**Exempel:**

```
fram()
om nuddar vägg
stopp
```

:::video /media/video/2-2-1.mp4

**eller:**

```
fram(26)
om går in i vägg
stopp
```

*Här är det viktigt att ni läser koden exakt som den är skriven och utför den i exakt den ordning som den står. Vad händer om man skriver om det första exemplets kod och utför detta:*

```
om nuddar vägg
stopp
fram()
```

:::fakta
begrepp: Stegvisa Instruktioner, Symbolers användning, Repetition (Loop), Villkor
fokus: Villkor | Hur kan villkor användas?
ålder: Åk 2, Åk 3
:::

#### Uppgift [B]

Eleverna jobbar i par eller flera i denna uppgift och turas om att vara programmerare och att vara robot.
**Din robot ska ta sig från längst bak i klassrummet fram till tavlan på andra sidan klassrummet så snabbt och rakt det bara går. Det kan ibland stå en stol i vägen, men inte alltid. Hur kan vi programmera roboten så att den tar sig hela vägen oavsett om det finns ett hinder eller ej? Finns det olika sätt?**

1. Ställ en stol i färdvägen. Låt eleverna diskutera hur de skulle kunna använda ett villkor för att ta sig runt stolen, om den finns där. Om det inte finns en stol, hur löser eleverna det? Låt eleverna diskutera och sedan skriva ned sin kod. Tänk på vikten av i vilken ordning instruktionerna skrivs och läses.

*Här kan vi använda OM och ANNARS i villkoret. Ett exempel på lösning skulle kunna vara:*

```
fram()
om stol i vägen
    vänster(1)
    fram(1)
    höger(1)
    fram(1)
    höger(1)
    fram(1)
    vänster(1)
    fram()
annars
    fram()
om nuddar väggen
    stopp
```

:::video /media/video/2-2-2.mp4

För att göra koden lite mer läsbar flyttar vi in den kod som tillhör villkoret lite till höger, det som kallas för indrag. På så sätt blir det lättare att veta vad som ska hoppas över, om inte villkoret möts, som i vårt exempel skulle kunna vara att ingen stol står i vägen.

:::fakta
begrepp: Stegvisa Instruktioner, Symbolers användning, Repetition (Loop), Villkor, Problemlösning
fokus: Villkor | Hur kan villkor användas?
ålder: Åk 2, Åk 3
:::
