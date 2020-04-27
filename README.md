Aika 3
======

In the past I've written some Discord bots, which have iteratively improved my code for every rewrite I undergo; and with all the free time from quarantine, I thought I'd give Aika another go, this time with a bit more planning..

Requirements
------------
- Python >= 3.8
- MySQL

Design choices
--------------
**More broad focus from prior iterations** - In my past iterations of Aika, the main focus has always been [Akatsuki](https://github.com/osuAkatsuki), since it was my main project at the time, and most of the reason I was coding to begin with.
Since then, I have left Akatsuki, and have been focusing much more on improving my programming abilities. With all the knowledge I have gained since the previous iteration, I thought I would try to tackle making an actual multi-functional bot this time around; maybe something others could actually use.

**Modularity** - This is a big one for this project. I like the idea of being able to just code a module and slide it into an already well-rounded bot to add additional functionality - this also allows for others to code their own modules and perhaps even contribute to the overall project.

**Over-engineering** - While this isn't really a design choice, this project *is* just my quarantined-up excuse to practice more python, and my main goal is just to learn - I know I'll look back at this bot a few years down the road and think it was garbage, but that just shows improvement.

Things that are already bothering me
------------------------------------
1. The async background loop feels sloppy but I'm very (days) new to asynchronous programming. maybe it's fine?
2. While I first started inlining the color codes as a method of memorizing them (which was successful btw, already), I actually haven't managed to find a better method.. Every time I write something to replace it, I just end up scrapping it after realizing it makes it worse or equal.
3. Config embed_color can't be hex unless we used [json5](https://github.com/dpranke/pyjson5) but its hyper-slow (~200x slower than pyjson) and it just looks retarded as a decimal.
4. There are a few little rough spots in the code that just feel wrong - I just feel like there are better ways to solve the puzzle, I just can't see it I guess.