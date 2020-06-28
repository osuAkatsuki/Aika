Aika
====

As of the 27th of June, Aika is now a public bot!
This means you can [invite them to your server](https://discord.com/api/oauth2/authorize?client_id=702310727515504710&permissions=0&scope=bot), if you'd like. :)

In the past I've written some Discord bots, which have iteratively improved my code for every rewrite I undergo; and with all the free time from quarantine, I thought I'd give Aika another go, this time with a bit more planning..

So far, the bot has come a long way; it's [far](https://github.com/cmyui/Aika_old) better than my previous attempts, and it feels like my improvement rate is increasing exponentially (quarantine gives me pretty much infinite time to work on programming).. Maybe this won't end up half bad?

Commands
========
```md
Mandatory = <>
Optional = ()

Using commands like !u, !rc, !top, etc. with
no parameters will simply retrieve your own.
(assuming your akatsuki account is linked)

# General commands
!<u/user/profile> (@mention) # display your (or target's) user profile.
!<levelreq/lvreq> <level> # show the xp required for a specific level
!<dlb/deleterboard> # show the global ranking of deleted message counts (lol)
!<lb/xplb/leaderboard> # show the current guild's xp leaderboards.
!<lv/level> # may be removed since !u exists
!<uptime> # shows Aika's time online
!<prune> <count [max 1000]> # prune messages from a channel (up to 1k)

# Akatsuki commands
!<top> (-rx) (-gm 0/1) (@mention/akatsuki username) # shows your (or target's) best 3 plays on akatsuki
!<rc/recent> (@mention/akatsuki username) # shows your (or target's) most recent score on akatsuki

# Akatsuki-only commands (only available in akatsuki's discord)
!<link/linkosu> # allows you to link your akatsuki account to discord
!<faq> (name/id) # get FAQ topics
```

Requirements
------------
- Python >= 3.8
- MySQL

Design choices
--------------
**More broad focus from prior iterations** - In my past iterations of Aika, the main focus has always been [Akatsuki](https://akatsuki.pw/), since it is my main project, but this time around, I thought i'd make a more general-purpose Discord bot with features you'd expect from a normal discord bot, and probably the best akatsuki-discord link you can get.

**Over-engineering** - While this isn't really a design choice, this project *is* just my quarantined-up excuse to practice more python, and my main goal is just to learn - I know I'll look back at this bot a few years down the road and think it was garbage, but that just shows improvement.

Things that are already bothering me
------------------------------------
1. Some spots in the code are quite poorly written and make the codebase rather unreadable - going to have to do some refactoring.
